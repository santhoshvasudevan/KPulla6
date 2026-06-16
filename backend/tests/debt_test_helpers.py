"""Shared helpers for debt / fixed-deposit tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from debt.bank_ledger_services import create_manual_cash_movement
from debt.models import BankAccount


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
