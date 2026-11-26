"""PostgreSQL row-lock serialization for interest edit vs reverse (#64).

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
    -c \"DROP DATABASE IF EXISTS kpulla6_test_64;\"
"""

from __future__ import annotations

import threading
from datetime import date
from decimal import Decimal

import pytest
from django.db import connection, transaction as db_transaction

from debt.interest_payment_services import (
    InterestPaymentValidationError,
    create_fixed_deposit_interest_payment,
    get_fixed_deposit_interest_payment,
    update_fixed_deposit_interest_payment,
)
from debt.models import FixedDepositInterestPayment
from debt.reversal_services import reverse_fixed_deposit_interest_payment
from debt.services import create_fixed_deposit
from portfolios.seed import ensure_default_portfolio
from tests.debt_test_helpers import create_test_bank_account, fund_bank_account


pytestmark = pytest.mark.django_db(transaction=True)


def _requires_postgres():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL row locks required for interest edit/reverse concurrency")


def _create_editable_payment(user):
    portfolio = ensure_default_portfolio(user)
    bank = create_test_bank_account(user, portfolio=portfolio, account_number="LOCK-64")
    fund_bank_account(user, bank, "200000", movement_date=date(2023, 12, 31))
    fd = create_fixed_deposit(
        user,
        portfolio_id=portfolio.id,
        bank_account_id=bank.id,
        institution_name="HDFC",
        deposit_account_number="FD-LOCK-64",
        principal_amount=Decimal("100000"),
        currency="INR",
        interest_rate_percent=Decimal("7.0"),
        interest_payout_frequency="QUARTERLY",
        investment_date=date(2024, 1, 1),
        maturity_date=date(2026, 1, 1),
    )
    return create_fixed_deposit_interest_payment(
        user,
        fd.id,
        payment_date=date(2024, 4, 1),
        gross_interest=Decimal("1000"),
        tax_withheld=Decimal("0"),
        comment="Lock target",
    ).payment


def test_overlapping_reverse_cannot_edit_already_reversed_payment(seeded, test_user):
    _requires_postgres()
    payment = _create_editable_payment(test_user)
    payment_id = payment.id

    barrier = threading.Barrier(2)
    reverse_holds_lock = threading.Event()
    allow_reverse_commit = threading.Event()
    results: dict[str, object] = {}

    def reverse_worker():
        connection.close()
        try:
            with db_transaction.atomic():
                locked = get_fixed_deposit_interest_payment(
                    test_user, payment_id, for_update=True
                )
                assert locked.is_reversed is False
                reverse_holds_lock.set()
                barrier.wait(timeout=5)
                # Hold the payment lock until the edit thread is blocked/waiting.
                assert allow_reverse_commit.wait(timeout=5)
                reverse_fixed_deposit_interest_payment(
                    test_user,
                    payment_id,
                    reason="Concurrent reverse wins",
                )
            results["reverse"] = "ok"
        except Exception as exc:  # noqa: BLE001 — capture for assertion in main thread
            results["reverse"] = exc
        finally:
            connection.close()

    def edit_worker():
        connection.close()
        try:
            barrier.wait(timeout=5)
            assert reverse_holds_lock.wait(timeout=5)
            # Release reverse to commit after edit has entered its transaction and blocked.
            allow_reverse_commit.set()
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

    reverse_thread = threading.Thread(target=reverse_worker)
    edit_thread = threading.Thread(target=edit_worker)
    reverse_thread.start()
    edit_thread.start()
    reverse_thread.join(timeout=10)
    edit_thread.join(timeout=10)

    assert results.get("reverse") == "ok"
    assert isinstance(results.get("edit"), InterestPaymentValidationError)
    assert "reversed" in str(results["edit"]).lower()

    refreshed = FixedDepositInterestPayment.objects.get(pk=payment_id)
    assert refreshed.is_reversed is True
    assert refreshed.gross_interest == Decimal("1000")
    assert refreshed.net_interest == Decimal("1000")


def test_overlapping_edit_cannot_reverse_stale_amount(seeded, test_user):
    _requires_postgres()
    payment = _create_editable_payment(test_user)
    payment_id = payment.id

    barrier = threading.Barrier(2)
    edit_holds_lock = threading.Event()
    allow_edit_commit = threading.Event()
    results: dict[str, object] = {}

    def edit_worker():
        connection.close()
        try:
            with db_transaction.atomic():
                locked = get_fixed_deposit_interest_payment(
                    test_user, payment_id, for_update=True
                )
                assert locked.net_interest == Decimal("1000")
                edit_holds_lock.set()
                barrier.wait(timeout=5)
                assert allow_edit_commit.wait(timeout=5)
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

    def reverse_worker():
        connection.close()
        try:
            barrier.wait(timeout=5)
            assert edit_holds_lock.wait(timeout=5)
            allow_edit_commit.set()
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

    edit_thread = threading.Thread(target=edit_worker)
    reverse_thread = threading.Thread(target=reverse_worker)
    edit_thread.start()
    reverse_thread.start()
    edit_thread.join(timeout=10)
    reverse_thread.join(timeout=10)

    assert results.get("edit") == "ok"
    reverse_result = results.get("reverse")
    assert not isinstance(reverse_result, Exception), reverse_result
    # Reverse must debit the post-edit net, not the stale pre-edit amount.
    assert reverse_result.reversal_cash_movement.amount == Decimal("1500")
    refreshed = FixedDepositInterestPayment.objects.get(pk=payment_id)
    assert refreshed.is_reversed is True
    assert refreshed.net_interest == Decimal("1500")
