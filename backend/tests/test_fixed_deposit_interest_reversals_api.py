"""FD-ACC-10B: fixed deposit interest payment reversal API tests."""

from datetime import date
from decimal import Decimal

import pytest

from debt.cash_ledger_flows import BankCashFlowKind, classify_bank_cash_movement
from debt.interest_payment_services import create_fixed_deposit_interest_payment
from debt.models import (
    CashMovement,
    CashMovementDirection,
    CashMovementType,
    FixedDepositStatus,
)
from debt.services import create_bank_account, create_fixed_deposit, update_bank_account
from debt.settlement_services import (
    create_fixed_deposit_settlement,
    mark_fixed_deposit_matured,
)
from portfolios.scope import ResolvedPortfolioScope
from portfolios.seed import ensure_default_portfolio
from portfolios.xirr_service import compute_scope_xirr_detail
from tests.debt_test_helpers import create_test_bank_account, fund_bank_account


def _bank(user, portfolio=None, **overrides):
    return create_test_bank_account(user, portfolio=portfolio, **overrides)



def _fd(user, portfolio_id, bank):
    fund_bank_account(user, bank, "200000")
    return create_fixed_deposit(
        user,
        portfolio_id=portfolio_id,
        bank_account_id=bank.id,
        institution_name="HDFC",
        deposit_account_number="FD-INT-REV",
        principal_amount=Decimal("100000"),
        currency="INR",
        interest_rate_percent=Decimal("7"),
        interest_payout_frequency="QUARTERLY",
        investment_date=date(2024, 1, 1),
        maturity_date=date(2026, 1, 1),
    )


def _reverse_interest(api_client, payment_id, **extra):
    payload = {"reason": "Wrong amount recorded", **extra}
    return api_client.post(
        f"/api/v1/fixed-deposit-interest-payments/{payment_id}/reverse",
        payload,
        format="json",
    )


@pytest.mark.django_db
def test_reverse_interest_payment_creates_debit_reversal(seeded, test_user, api_client):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _fd(test_user, portfolio.id, bank)
    bank.refresh_from_db()
    before = bank.current_balance

    created = api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/interest-payments",
        {
            "payment_date": "2024-04-01",
            "gross_interest": "1000",
            "tax_withheld": "100",
        },
        format="json",
    )
    payment_id = created.json()["id"]
    bank.refresh_from_db()
    assert bank.current_balance == before + Decimal("900")

    response = _reverse_interest(api_client, payment_id, reversal_date="2024-04-15")
    assert response.status_code == 201
    body = response.json()
    assert body["original"]["is_reversed"] is True
    assert body["original"]["reversed_at"] is not None
    assert body["reversal_cash_movement_id"] == body["reversed_by"]

    reversal = CashMovement.objects.get(id=body["reversal_cash_movement_id"])
    assert reversal.movement_type == CashMovementType.FD_INTEREST_REVERSAL
    assert reversal.direction == CashMovementDirection.DEBIT
    assert reversal.amount == Decimal("900")
    assert reversal.is_reversal is True
    assert reversal.reversal_reason == "Wrong amount recorded"

    bank.refresh_from_db()
    assert bank.current_balance == before


@pytest.mark.django_db
def test_cannot_reverse_interest_twice(seeded, test_user, api_client):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _fd(test_user, portfolio.id, bank)
    payment_result = create_fixed_deposit_interest_payment(
        test_user,
        fd.id,
        payment_date=date(2024, 4, 1),
        gross_interest=Decimal("1000"),
        tax_withheld=Decimal("0"),
    )
    assert _reverse_interest(api_client, payment_result.payment.id).status_code == 201
    again = _reverse_interest(api_client, payment_result.payment.id)
    assert again.status_code == 400
    assert "already been reversed" in again.json()["detail"]


@pytest.mark.django_db
def test_cannot_reverse_another_users_interest_payment(
    seeded, test_user, other_user, api_client
):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _fd(test_user, portfolio.id, bank)
    payment_result = create_fixed_deposit_interest_payment(
        test_user,
        fd.id,
        payment_date=date(2024, 4, 1),
        gross_interest=Decimal("500"),
    )
    api_client.force_authenticate(user=other_user)
    response = _reverse_interest(api_client, payment_result.payment.id)
    assert response.status_code == 404


@pytest.mark.django_db
def test_settlement_blocks_interest_reversal(seeded, test_user, api_client):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _fd(test_user, portfolio.id, bank)
    payment_result = create_fixed_deposit_interest_payment(
        test_user,
        fd.id,
        payment_date=date(2024, 4, 1),
        gross_interest=Decimal("1000"),
    )
    mark_fixed_deposit_matured(test_user, fd.id)
    create_fixed_deposit_settlement(
        test_user,
        fd.id,
        settlement_type="MATURITY",
        settlement_date=date(2026, 1, 1),
        principal_returned=Decimal("100000"),
        gross_interest=Decimal("0"),
    )
    response = _reverse_interest(api_client, payment_result.payment.id)
    assert response.status_code == 409
    assert "deferred" in response.json()["detail"].lower()


@pytest.mark.django_db
def test_interest_reversal_classification_offsets_income_not_external(
    seeded, test_user, api_client
):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    update_bank_account(test_user, bank.id, include_in_portfolio_value=True)
    fd = _fd(test_user, portfolio.id, bank)
    payment_result = create_fixed_deposit_interest_payment(
        test_user,
        fd.id,
        payment_date=date(2024, 4, 1),
        gross_interest=Decimal("1000"),
    )
    response = _reverse_interest(api_client, payment_result.payment.id)
    assert response.status_code == 201
    reversal = CashMovement.objects.get(
        movement_type=CashMovementType.FD_INTEREST_REVERSAL,
    )
    assert (
        classify_bank_cash_movement(reversal, bank_included=True)
        == BankCashFlowKind.INCOME_RETURN
    )
    from debt.cash_ledger_flows import twror_flow_amount_from_bank_movement

    assert twror_flow_amount_from_bank_movement(reversal) == Decimal("0")


@pytest.mark.django_db
def test_portfolio_summary_reflects_interest_reversal_when_bank_included(
    api_client, seeded, test_user
):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    update_bank_account(test_user, bank.id, include_in_portfolio_value=True)
    fd = _fd(test_user, portfolio.id, bank)
    payment_result = create_fixed_deposit_interest_payment(
        test_user,
        fd.id,
        payment_date=date(2024, 4, 1),
        gross_interest=Decimal("1000"),
        tax_withheld=Decimal("100"),
    )
    summary_with_interest = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false&display_currency=INR"
    ).json()
    assert summary_with_interest["current_value"] == pytest.approx(200900.0, rel=1e-6)

    _reverse_interest(api_client, payment_result.payment.id)
    summary_after = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false&display_currency=INR"
    ).json()
    assert summary_after["current_value"] == pytest.approx(200000.0, rel=1e-6)

    scope = ResolvedPortfolioScope(kind="all_active", portfolio_ids=[portfolio.id])
    xirr = compute_scope_xirr_detail(scope, display_currency="INR", user=test_user)
    assert xirr.value is not None
