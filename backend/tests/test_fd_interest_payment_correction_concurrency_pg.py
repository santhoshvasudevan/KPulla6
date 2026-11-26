"""PostgreSQL lock contention proofs for FD interest Bank Cash writers (#64).

Skipped under SQLite. Run against a disposable Postgres database, for example:

  docker start kpulla6_postgres
  docker exec kpulla6_postgres psql -U santhosh_admin -d postgres \\
    -c \"DROP DATABASE IF EXISTS kpulla6_test_64;\" \\
    -c \"CREATE DATABASE kpulla6_test_64;\"
  cd backend && \\
    DJANGO_TEST_USE_SQLITE=0 \\
    DATABASE_URL=postgres://santhosh_admin:kpulla6@localhost:5432/kpulla6_test_64 \\
    .venv/bin/python -m pytest tests/test_fd_interest_payment_correction_concurrency_pg.py -q
  docker exec kpulla6_postgres psql -U santhosh_admin -d postgres \\
    -c \"DROP DATABASE IF EXISTS test_kpulla6_test_64;\" \\
    -c \"DROP DATABASE IF EXISTS kpulla6_test_64;\"
"""

from __future__ import annotations

import threading
import time
from datetime import date
from decimal import Decimal

import pytest
from django.db import connection, transaction as db_transaction

from debt.bank_ledger_services import (
    create_manual_cash_movement,
    lock_bank_account_for_update,
)
from debt.interest_payment_services import (
    InterestPaymentValidationError,
    create_fixed_deposit_interest_payment,
    get_fixed_deposit_interest_payment,
    update_fixed_deposit_interest_payment,
)
from debt.models import CashMovementType, FixedDepositInterestPayment
from debt.reversal_services import reverse_fixed_deposit_interest_payment
from debt.services import create_fixed_deposit
from portfolios.seed import ensure_default_portfolio
from tests.debt_test_helpers import create_test_bank_account, fund_bank_account


pytestmark = pytest.mark.django_db(transaction=True)


def _requires_postgres():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL row locks required for interest Bank Cash contention")


def _wait_until_lock_wait(timeout: float = 5.0) -> None:
    """Block until PostgreSQL reports at least one ungranted lock wait."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*) FROM pg_locks
                WHERE NOT granted AND locktype = 'relation'
                """
            )
            # Also check tuple/transactionid waits which select_for_update uses.
            cursor.execute(
                """
                SELECT COUNT(*) FROM pg_locks
                WHERE NOT granted
                """
            )
            waiting = cursor.fetchone()[0]
        if waiting:
            return
        time.sleep(0.05)
    raise AssertionError("Timed out waiting for PostgreSQL to report a lock wait")


def _create_editable_payment(user, *, account_number: str = "LOCK-64"):
    portfolio = ensure_default_portfolio(user)
    bank = create_test_bank_account(user, portfolio=portfolio, account_number=account_number)
    fund_bank_account(user, bank, "100000", movement_date=date(2023, 12, 31))
    fd = create_fixed_deposit(
        user,
        portfolio_id=portfolio.id,
        bank_account_id=bank.id,
        institution_name="HDFC",
        deposit_account_number=f"FD-{account_number}",
        principal_amount=Decimal("100000"),
        currency="INR",
        interest_rate_percent=Decimal("7.0"),
        interest_payout_frequency="QUARTERLY",
        investment_date=date(2024, 1, 1),
        maturity_date=date(2026, 1, 1),
    )
    payment = create_fixed_deposit_interest_payment(
        user,
        fd.id,
        payment_date=date(2024, 4, 1),
        gross_interest=Decimal("1000"),
        tax_withheld=Decimal("0"),
        comment="Lock target",
    ).payment
    bank.refresh_from_db()
    return bank, payment


def _run_holder_then_waiter(
    *,
    holder,
    waiter,
    holder_ready: threading.Event,
    release_holder: threading.Event,
):
    """Start holder, wait until waiter is blocked in PostgreSQL, then release."""
    holder_thread = threading.Thread(target=holder)
    waiter_thread = threading.Thread(target=waiter)
    holder_thread.start()
    assert holder_ready.wait(timeout=5)
    waiter_thread.start()
    _wait_until_lock_wait(timeout=5)
    release_holder.set()
    holder_thread.join(timeout=10)
    waiter_thread.join(timeout=10)
    assert not holder_thread.is_alive()
    assert not waiter_thread.is_alive()


def test_edit_then_reverse_uses_post_edit_amount_after_lock_wait(seeded, test_user):
    _requires_postgres()
    bank, payment = _create_editable_payment(test_user, account_number="EDIT-REV")
    payment_id = payment.id
    bank_id = bank.id

    edit_ready = threading.Event()
    release_edit = threading.Event()
    results: dict[str, object] = {}

    def edit_holder():
        connection.close()
        try:
            with db_transaction.atomic():
                lock_bank_account_for_update(test_user, bank_id)
                locked = get_fixed_deposit_interest_payment(
                    test_user, payment_id, for_update=True
                )
                assert locked.net_interest == Decimal("1000")
                edit_ready.set()
                assert release_edit.wait(timeout=5)
                update_fixed_deposit_interest_payment(
                    test_user,
                    payment_id,
                    gross_interest=Decimal("1500"),
                    tax_withheld=Decimal("0"),
                )
            results["edit"] = "ok"
        except Exception as exc:  # noqa: BLE001
            results["edit"] = exc
        finally:
            connection.close()

    def reverse_waiter():
        connection.close()
        try:
            result = reverse_fixed_deposit_interest_payment(
                test_user,
                payment_id,
                reason="Reverse after edit",
            )
            results["reverse"] = result
        except Exception as exc:  # noqa: BLE001
            results["reverse"] = exc
        finally:
            connection.close()

    _run_holder_then_waiter(
        holder=edit_holder,
        waiter=reverse_waiter,
        holder_ready=edit_ready,
        release_holder=release_edit,
    )

    assert results.get("edit") == "ok"
    reverse_result = results.get("reverse")
    assert not isinstance(reverse_result, Exception), reverse_result
    assert reverse_result.reversal_cash_movement.amount == Decimal("1500")
    refreshed = FixedDepositInterestPayment.objects.get(pk=payment_id)
    assert refreshed.is_reversed is True
    assert refreshed.net_interest == Decimal("1500")
    bank.refresh_from_db()
    assert bank.current_balance == Decimal("0")


def test_reverse_then_edit_rejects_reversed_payment_after_lock_wait(seeded, test_user):
    _requires_postgres()
    bank, payment = _create_editable_payment(test_user, account_number="REV-WAIT")
    payment_id = payment.id
    bank_id = bank.id

    reverse_ready = threading.Event()
    release_reverse = threading.Event()
    results: dict[str, object] = {}

    def reverse_holder():
        connection.close()
        try:
            with db_transaction.atomic():
                lock_bank_account_for_update(test_user, bank_id)
                locked = get_fixed_deposit_interest_payment(
                    test_user, payment_id, for_update=True
                )
                assert locked.is_reversed is False
                reverse_ready.set()
                assert release_reverse.wait(timeout=5)
                reverse_fixed_deposit_interest_payment(
                    test_user,
                    payment_id,
                    reason="Reverse holds bank lock",
                )
            results["reverse"] = "ok"
        except Exception as exc:  # noqa: BLE001
            results["reverse"] = exc
        finally:
            connection.close()

    def edit_waiter():
        connection.close()
        try:
            update_fixed_deposit_interest_payment(
                test_user,
                payment_id,
                gross_interest=Decimal("1100"),
            )
            results["edit"] = "ok"
        except Exception as exc:  # noqa: BLE001
            results["edit"] = exc
        finally:
            connection.close()

    _run_holder_then_waiter(
        holder=reverse_holder,
        waiter=edit_waiter,
        holder_ready=reverse_ready,
        release_holder=release_reverse,
    )

    assert results.get("reverse") == "ok"
    assert isinstance(results.get("edit"), InterestPaymentValidationError)
    assert "reversed" in str(results["edit"]).lower()
    refreshed = FixedDepositInterestPayment.objects.get(pk=payment_id)
    assert refreshed.is_reversed is True
    assert refreshed.gross_interest == Decimal("1000")
    bank.refresh_from_db()
    assert bank.current_balance == Decimal("0")


def test_correction_versus_withdrawal_serialized_on_bank_account_lock(seeded, test_user):
    _requires_postgres()
    bank, payment = _create_editable_payment(test_user, account_number="CORR-WD")
    payment_id = payment.id
    bank_id = bank.id
    # After FD open + interest: balance is 1000 (funded solely by interest credit).

    correction_ready = threading.Event()
    release_correction = threading.Event()
    results: dict[str, object] = {}

    def correction_holder():
        connection.close()
        try:
            with db_transaction.atomic():
                lock_bank_account_for_update(test_user, bank_id)
                get_fixed_deposit_interest_payment(test_user, payment_id, for_update=True)
                correction_ready.set()
                assert release_correction.wait(timeout=5)
                update_fixed_deposit_interest_payment(
                    test_user,
                    payment_id,
                    gross_interest=Decimal("100"),
                    tax_withheld=Decimal("0"),
                )
            results["correction"] = "ok"
        except Exception as exc:  # noqa: BLE001
            results["correction"] = exc
        finally:
            connection.close()

    def withdrawal_waiter():
        connection.close()
        try:
            create_manual_cash_movement(
                test_user,
                bank_account_id=bank_id,
                movement_type=CashMovementType.MANUAL_WITHDRAWAL,
                amount=Decimal("1000"),
                movement_date=date(2024, 4, 15),
                description="Competing withdrawal",
            )
            results["withdrawal"] = "ok"
        except Exception as exc:  # noqa: BLE001
            results["withdrawal"] = exc
        finally:
            connection.close()

    _run_holder_then_waiter(
        holder=correction_holder,
        waiter=withdrawal_waiter,
        holder_ready=correction_ready,
        release_holder=release_correction,
    )

    # Correction reduces credit to 100; withdrawal of 1000 must then fail overdraft
    # (or future-impact) and leave the reduced credit intact.
    assert results.get("correction") == "ok"
    assert isinstance(results.get("withdrawal"), Exception), results.get("withdrawal")
    payment.refresh_from_db()
    assert payment.net_interest == Decimal("100")
    bank.refresh_from_db()
    assert bank.current_balance == Decimal("100")
