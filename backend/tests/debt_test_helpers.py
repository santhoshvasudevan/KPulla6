"""Shared helpers for debt / fixed-deposit tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from debt.bank_ledger_services import create_manual_cash_movement
from debt.models import BankAccount
from debt.services import create_bank_account
from portfolios.seed import ensure_default_portfolio


def create_test_bank_account(user, portfolio=None, **overrides):
    """Create a bank account with portfolio assigned (CASH-UNIFY-2 default)."""
    if portfolio is None:
        portfolio = ensure_default_portfolio(user)
    payload = dict(
        name="Savings",
        institution_name="HDFC",
        account_number="111222333",
        currency="INR",
        portfolio_id=portfolio.id,
    )
    payload.update(overrides)
    return create_bank_account(user, **payload)


def create_legacy_fixed_deposit(user, *, portfolio, bank, **overrides):
    """Insert FD row directly for legacy / inference / scope test fixtures."""
    from debt.models import FixedDeposit

    payload = dict(
        user=user,
        portfolio=portfolio,
        bank_account=bank,
        institution_name="HDFC",
        deposit_account_number="FD-1",
        principal_amount=Decimal("100000"),
        currency="INR",
        interest_rate_percent=Decimal("7"),
        interest_payout_frequency="QUARTERLY",
        investment_date=date(2024, 6, 1),
        maturity_date=date(2025, 6, 1),
        status="ACTIVE",
        is_active=True,
    )
    payload.update(overrides)
    fd = FixedDeposit(**payload)
    fd.save()
    return fd


def create_legacy_fixed_deposit_with_opening(user, *, portfolio, bank, **overrides):
    """Legacy FD row plus opening bank debit (multi-portfolio scope fixtures)."""
    from debt.bank_ledger_services import create_fd_opening_cash_movement

    fd = create_legacy_fixed_deposit(user, portfolio=portfolio, bank=bank, **overrides)
    create_fd_opening_cash_movement(user, fd)
    bank.refresh_from_db()
    return fd


def fund_bank_account(
    user,
    bank: BankAccount,
    amount,
    *,
    movement_date=None,
) -> BankAccount:
    """Credit a bank account via MANUAL_DEPOSIT so FD opening debits can succeed."""
    create_manual_cash_movement(
        user,
        bank_account_id=bank.id,
        movement_type="MANUAL_DEPOSIT",
        amount=Decimal(str(amount)),
        movement_date=movement_date or date(2024, 1, 1),
    )
    bank.refresh_from_db()
    return bank
