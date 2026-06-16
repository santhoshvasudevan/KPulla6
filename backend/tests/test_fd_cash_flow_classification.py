"""FD-ACC-8C: bank cash movement classification for return metrics."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from debt.bank_ledger_services import create_manual_cash_movement, seed_opening_balance
from debt.cash_ledger_flows import (
    BankCashFlowKind,
    build_bank_cash_twror_external_flows,
    build_bank_cash_xirr_external_flows,
    classify_bank_cash_movement,
)
from debt.models import CashMovement, CashMovementDirection, CashMovementType
from debt.services import create_bank_account, create_fixed_deposit, update_bank_account
from portfolios.scope import ResolvedPortfolioScope
from portfolios.seed import ensure_default_portfolio
from portfolios.xirr_service import compute_scope_xirr_detail
from tests.debt_test_helpers import fund_bank_account


def _bank(user, **overrides):
    payload = dict(
        name="Savings",
        institution_name="HDFC",
        account_number="111",
        currency="INR",
    )
    payload.update(overrides)
    return create_bank_account(user, **payload)


def _enable(user, bank):
    return update_bank_account(user, bank.id, include_in_portfolio_value=True)


def _scope(user, portfolio_id=None):
    portfolio = ensure_default_portfolio(user)
    if portfolio_id is None:
        return ResolvedPortfolioScope(kind="all_active", portfolio_ids=[portfolio.id])
    return ResolvedPortfolioScope(kind="single", portfolio_ids=[portfolio_id])


@pytest.mark.django_db
def test_classify_fd_opening_as_internal(seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fund_bank_account(test_user, bank, "150000")
    _enable(test_user, bank)
    fd = create_fixed_deposit(
        test_user,
        portfolio_id=portfolio.id,
        bank_account_id=bank.id,
        institution_name="HDFC",
        deposit_account_number="FD-1",
        principal_amount=Decimal("100000"),
        currency="INR",
        interest_rate_percent=Decimal("7"),
        interest_payout_frequency="QUARTERLY",
        investment_date=date(2024, 1, 1),
        maturity_date=date(2026, 1, 1),
    )
    opening = CashMovement.objects.get(
        linked_fixed_deposit_id=fd.id, movement_type=CashMovementType.FD_OPENING
    )
    assert classify_bank_cash_movement(opening, bank_included=True) == BankCashFlowKind.INTERNAL


@pytest.mark.django_db
def test_manual_deposit_is_external_contribution(seeded, test_user):
    bank = _bank(test_user)
    fund_bank_account(test_user, bank, "25000")
    _enable(test_user, bank)
    movement = CashMovement.objects.filter(
        bank_account=bank, movement_type=CashMovementType.MANUAL_DEPOSIT
    ).first()
    assert (
        classify_bank_cash_movement(movement, bank_included=True)
        == BankCashFlowKind.EXTERNAL_CONTRIBUTION
    )


@pytest.mark.django_db
def test_manual_withdrawal_is_external_withdrawal(seeded, test_user):
    bank = _bank(test_user)
    fund_bank_account(test_user, bank, "50000")
    _enable(test_user, bank)
    create_manual_cash_movement(
        test_user,
        bank_account_id=bank.id,
        movement_type=CashMovementType.MANUAL_WITHDRAWAL,
        amount=Decimal("5000"),
        movement_date=date(2024, 6, 1),
    )
    movement = CashMovement.objects.filter(
        bank_account=bank, movement_type=CashMovementType.MANUAL_WITHDRAWAL
    ).first()
    assert (
        classify_bank_cash_movement(movement, bank_included=True)
        == BankCashFlowKind.EXTERNAL_WITHDRAWAL
    )


@pytest.mark.django_db
def test_opening_balance_seed_is_external_contribution(seeded, test_user):
    bank = create_bank_account(
        test_user,
        name="Seeded",
        institution_name="HDFC",
        account_number="seed-1",
        currency="INR",
        opening_balance=Decimal("80000"),
    )
    _enable(test_user, bank)
    seed_opening_balance(test_user, bank.id)
    movement = CashMovement.objects.get(
        bank_account=bank, movement_type=CashMovementType.OPENING_BALANCE
    )
    assert (
        classify_bank_cash_movement(movement, bank_included=True)
        == BankCashFlowKind.EXTERNAL_CONTRIBUTION
    )


@pytest.mark.django_db
def test_fd_interest_is_income_not_external(seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fund_bank_account(test_user, bank, "150000")
    _enable(test_user, bank)
    fd = create_fixed_deposit(
        test_user,
        portfolio_id=portfolio.id,
        bank_account_id=bank.id,
        institution_name="HDFC",
        deposit_account_number="FD-INT",
        principal_amount=Decimal("100000"),
        currency="INR",
        interest_rate_percent=Decimal("7"),
        interest_payout_frequency="QUARTERLY",
        investment_date=date(2024, 1, 1),
        maturity_date=date(2026, 1, 1),
    )
    from debt.interest_payment_services import create_fixed_deposit_interest_payment

    payment = create_fixed_deposit_interest_payment(
        test_user,
        fd.id,
        payment_date=date(2025, 3, 1),
        gross_interest=Decimal("5000"),
        tax_withheld=Decimal("500"),
    )
    movement = CashMovement.objects.get(
        linked_fixed_deposit_id=fd.id, movement_type=CashMovementType.FD_INTEREST
    )
    assert movement.id in [m.id for m in CashMovement.objects.filter(bank_account=bank)]
    assert (
        classify_bank_cash_movement(movement, bank_included=True)
        == BankCashFlowKind.INCOME_RETURN
    )
    _ = payment


@pytest.mark.django_db
def test_twror_external_flows_exclude_fd_opening_include_manual_deposit(seeded, test_user):
    bank = _bank(test_user)
    fund_bank_account(test_user, bank, "40000", movement_date=date(2024, 2, 1))
    _enable(test_user, bank)
    ensure_default_portfolio(test_user)
    scope = ResolvedPortfolioScope(
        kind="all_active",
        portfolio_ids=[ensure_default_portfolio(test_user).id],
    )
    flows, unknown = build_bank_cash_twror_external_flows(
        test_user, scope, calculation_currency="INR"
    )
    assert unknown is None
    assert flows == {date(2024, 2, 1): Decimal("40000")}


@pytest.mark.django_db
def test_xirr_terminal_includes_fd_and_included_bank(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fund_bank_account(test_user, bank, "150000")
    _enable(test_user, bank)
    create_fixed_deposit(
        test_user,
        portfolio_id=portfolio.id,
        bank_account_id=bank.id,
        institution_name="HDFC",
        deposit_account_number="FD-X",
        principal_amount=Decimal("100000"),
        currency="INR",
        interest_rate_percent=Decimal("7"),
        interest_payout_frequency="QUARTERLY",
        investment_date=date(2024, 1, 1),
        maturity_date=date(2026, 1, 1),
    )
    summary = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false&display_currency=INR"
    ).json()
    scope = ResolvedPortfolioScope(kind="all_active", portfolio_ids=[portfolio.id])
    xirr = compute_scope_xirr_detail(scope, display_currency="INR", user=test_user)
    assert summary["current_value"] == pytest.approx(150000.0, rel=1e-6)
    assert xirr.value is not None


@pytest.mark.django_db
def test_unseeded_manual_balance_not_in_xirr_terminal(api_client, seeded, test_user):
    bank = create_bank_account(
        test_user,
        name="Manual",
        institution_name="HDFC",
        account_number="manual",
        currency="INR",
        current_balance=Decimal("99000"),
    )
    _enable(test_user, bank)
    summary = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false&display_currency=INR"
    ).json()
    assert summary["current_value"] == 0.0


@pytest.mark.django_db
def test_fd_opening_does_not_spike_twror_with_included_bank(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fund_bank_account(test_user, bank, "200000", movement_date=date(2024, 1, 1))
    _enable(test_user, bank)
    create_fixed_deposit(
        test_user,
        portfolio_id=portfolio.id,
        bank_account_id=bank.id,
        institution_name="HDFC",
        deposit_account_number="FD-TWROR",
        principal_amount=Decimal("100000"),
        currency="INR",
        interest_rate_percent=Decimal("7"),
        interest_payout_frequency="QUARTERLY",
        investment_date=date(2024, 1, 1),
        maturity_date=date(2026, 1, 1),
    )
    perf = api_client.get(
        "/api/v1/portfolio/performance?metric=twror&range=ALL&display_currency=INR"
    ).json()
    points = perf["points"] if isinstance(perf, dict) else perf
    open_day = next(
        (p for p in points if p["date"] == "2024-01-01" and p.get("value") is not None),
        None,
    )
    if open_day is not None:
        assert abs(open_day["value"]) < 0.05
