"""Regression: protect Bank Cash when correcting FD interest payments (#64)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from debt.bank_ledger_services import create_manual_cash_movement
from debt.interest_payment_services import create_fixed_deposit_interest_payment
from debt.models import (
    CashMovement,
    CashMovementType,
    FixedDepositInterestPayment,
)
from debt.services import create_fixed_deposit
from portfolios.seed import ensure_default_portfolio
from tests.debt_test_helpers import create_test_bank_account, fund_bank_account


def _fd_payload(portfolio_id, bank_account_id, **overrides):
    payload = dict(
        portfolio_id=portfolio_id,
        bank_account_id=bank_account_id,
        institution_name="HDFC",
        deposit_account_number="FD-CORR-001",
        principal_amount=Decimal("100000"),
        currency="INR",
        interest_rate_percent=Decimal("7.0"),
        interest_payout_frequency="QUARTERLY",
        investment_date=date(2024, 1, 1),
        maturity_date=date(2026, 1, 1),
    )
    payload.update(overrides)
    return payload


def _setup_interest_funded_withdrawal(user):
    """Bank ends at zero: FD opens to zero, interest funds a later withdrawal."""
    portfolio = ensure_default_portfolio(user)
    bank = create_test_bank_account(user, portfolio=portfolio, account_number="CORR-64")
    fund_bank_account(user, bank, "100000", movement_date=date(2023, 12, 31))
    fd = create_fixed_deposit(user, **_fd_payload(portfolio.id, bank.id))
    bank.refresh_from_db()
    assert bank.current_balance == Decimal("0")

    payment = create_fixed_deposit_interest_payment(
        user,
        fd.id,
        payment_date=date(2024, 4, 1),
        gross_interest=Decimal("1000"),
        tax_withheld=Decimal("0"),
        comment="Interest that funds withdrawal",
    ).payment
    bank.refresh_from_db()
    assert bank.current_balance == Decimal("1000")

    withdrawal = create_manual_cash_movement(
        user,
        bank_account_id=bank.id,
        movement_type=CashMovementType.MANUAL_WITHDRAWAL,
        amount=Decimal("1000"),
        movement_date=date(2024, 4, 15),
        description="Withdrawal funded by interest",
    )
    bank.refresh_from_db()
    assert bank.current_balance == Decimal("0")
    return portfolio, bank, fd, payment, withdrawal


@pytest.mark.django_db
def test_reduce_interest_credit_below_funded_withdrawal_returns_409(
    api_client, seeded, test_user
):
    _portfolio, bank, _fd, payment, withdrawal = _setup_interest_funded_withdrawal(
        test_user
    )
    original_net = payment.net_interest
    original_date = payment.payment_date
    original_movement_amount = payment.cash_movement.amount
    original_balance = bank.current_balance

    response = api_client.patch(
        f"/api/v1/fixed-deposit-interest-payments/{payment.id}",
        {"gross_interest": "100", "tax_withheld": "0"},
        format="json",
    )

    assert response.status_code == 409
    body = response.json()
    assert "earliest_negative_date" in body
    assert body["earliest_negative_date"] == "2024-04-15"
    assert body["currency"] == "INR"
    assert isinstance(body["affected_entries"], list)
    assert len(body["affected_entries"]) >= 1
    affected_ids = {row["id"] for row in body["affected_entries"]}
    assert withdrawal.id in affected_ids
    assert any(row["entry_type"] == CashMovementType.MANUAL_WITHDRAWAL for row in body["affected_entries"])

    payment.refresh_from_db()
    payment.cash_movement.refresh_from_db()
    bank.refresh_from_db()
    assert payment.net_interest == original_net
    assert payment.gross_interest == Decimal("1000")
    assert payment.payment_date == original_date
    assert payment.cash_movement.amount == original_movement_amount
    assert bank.current_balance == original_balance


@pytest.mark.django_db
def test_move_interest_credit_past_funded_withdrawal_returns_409(
    api_client, seeded, test_user
):
    _portfolio, bank, _fd, payment, withdrawal = _setup_interest_funded_withdrawal(
        test_user
    )
    original_date = payment.payment_date
    original_movement_date = payment.cash_movement.movement_date
    original_balance = bank.current_balance

    response = api_client.patch(
        f"/api/v1/fixed-deposit-interest-payments/{payment.id}",
        {"payment_date": "2024-04-20"},
        format="json",
    )

    assert response.status_code == 409
    body = response.json()
    assert body["earliest_negative_date"] == "2024-04-15"
    assert isinstance(body["affected_entries"], list)
    assert any(row["id"] == withdrawal.id for row in body["affected_entries"])

    payment.refresh_from_db()
    payment.cash_movement.refresh_from_db()
    bank.refresh_from_db()
    assert payment.payment_date == original_date
    assert payment.cash_movement.movement_date == original_movement_date
    assert bank.current_balance == original_balance


@pytest.mark.django_db
def test_valid_interest_correction_updates_payment_credit_and_balance(
    api_client, seeded, test_user
):
    portfolio = ensure_default_portfolio(test_user)
    bank = create_test_bank_account(user=test_user, portfolio=portfolio, account_number="CORR-OK")
    fund_bank_account(test_user, bank, "200000", movement_date=date(2023, 12, 31))
    fd = create_fixed_deposit(test_user, **_fd_payload(portfolio.id, bank.id))

    other = create_fixed_deposit_interest_payment(
        test_user,
        fd.id,
        payment_date=date(2024, 3, 1),
        gross_interest=Decimal("500"),
        tax_withheld=Decimal("0"),
        comment="Unrelated payment",
    ).payment
    payment = create_fixed_deposit_interest_payment(
        test_user,
        fd.id,
        payment_date=date(2024, 4, 1),
        gross_interest=Decimal("1000"),
        tax_withheld=Decimal("100"),
        comment="Editable payment",
    ).payment
    bank.refresh_from_db()
    balance_before = bank.current_balance

    response = api_client.patch(
        f"/api/v1/fixed-deposit-interest-payments/{payment.id}",
        {
            "payment_date": "2024-04-02",
            "gross_interest": "1200",
            "tax_withheld": "120",
            "comment": "Corrected credit",
        },
        format="json",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["payment_date"] == "2024-04-02"
    assert body["gross_interest"] == 1200.0
    assert body["tax_withheld"] == 120.0
    assert body["net_interest"] == 1080.0
    assert body["comment"] == "Corrected credit"

    payment.refresh_from_db()
    payment.cash_movement.refresh_from_db()
    other.refresh_from_db()
    bank.refresh_from_db()

    assert payment.payment_date == date(2024, 4, 2)
    assert payment.net_interest == Decimal("1080")
    assert payment.cash_movement.amount == Decimal("1080")
    assert payment.cash_movement.movement_date == date(2024, 4, 2)
    assert payment.cash_movement.movement_type == CashMovementType.FD_INTEREST
    # Net rose by 180 (900 → 1080)
    assert bank.current_balance == balance_before + Decimal("180")

    assert other.gross_interest == Decimal("500")
    assert other.net_interest == Decimal("500")
    assert other.payment_date == date(2024, 3, 1)
    assert other.comment == "Unrelated payment"
    assert CashMovement.objects.filter(id=other.cash_movement_id, amount=Decimal("500")).exists()
