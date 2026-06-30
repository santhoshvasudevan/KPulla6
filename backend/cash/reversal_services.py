"""Broker cash ledger reversal services (CASH-CORR-1A)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction as db_transaction

from cash.models import CashEntryType, CashLedgerEntry
from cash.services import (
    CashValidationError,
    InsufficientCashError,
    _ledger_entry_for_user,
    _reload_ledger_entry,
    cash_balances_for_scope,
    cash_balance_on_date,
    is_manual_editable_entry,
    ledger_entry_has_been_reversed,
    list_ledger_points_for_portfolio,
    parse_ledger_date,
    validate_non_negative_cash_after_change,
)
from finance.cash import CashLedgerPoint
from portfolios.scope import resolve_portfolio_scope


class CashReversalValidationError(CashValidationError):
    pass


REVERSIBLE_MANUAL_ENTRY_TYPES = frozenset(
    {
        CashEntryType.CASH_DEPOSIT,
        CashEntryType.CASH_WITHDRAWAL,
    }
)


@dataclass(frozen=True)
class CashLedgerReversalResult:
    original: CashLedgerEntry
    reversal: CashLedgerEntry
    message: str


def is_reversible_manual_entry(entry: CashLedgerEntry) -> bool:
    return (
        is_manual_editable_entry(entry)
        and entry.entry_type in REVERSIBLE_MANUAL_ENTRY_TYPES
    )


def _validate_reversible_manual_entry(entry: CashLedgerEntry) -> None:
    if entry.is_reversal:
        raise CashReversalValidationError("Cannot reverse a reversal entry.")
    if ledger_entry_has_been_reversed(entry):
        raise CashReversalValidationError("This entry has already been reversed.")
    if not is_manual_editable_entry(entry):
        raise CashReversalValidationError(
            "Linked or system-generated cash entries cannot be reversed."
        )
    if entry.entry_type not in REVERSIBLE_MANUAL_ENTRY_TYPES:
        raise CashReversalValidationError(
            "Only manual cash deposits and withdrawals can be reversed."
        )


def _opposite_manual_entry_type(entry_type: str) -> str:
    if entry_type == CashEntryType.CASH_DEPOSIT:
        return CashEntryType.CASH_WITHDRAWAL
    if entry_type == CashEntryType.CASH_WITHDRAWAL:
        return CashEntryType.CASH_DEPOSIT
    raise CashReversalValidationError(f"Unsupported entry type for reversal: {entry_type}")


def _opposite_signed_amount(entry: CashLedgerEntry) -> Decimal:
    return -entry.amount


def broker_cash_balance_preview(
    user: AbstractBaseUser,
    portfolio_id: int,
    currency: str,
) -> dict[str, float]:
    """Read-only broker cash balance for portfolio currency after a write."""
    scope = resolve_portfolio_scope(user, portfolio_id=portfolio_id)
    raw = cash_balances_for_scope(scope)
    current = Decimal("0")
    if hasattr(raw, "balances"):
        for ccy, bal in raw.balances:
            if ccy == currency:
                current = bal
                break
    return {
        "currency": currency,
        "current_balance": float(current),
    }


@db_transaction.atomic
def reverse_broker_cash_ledger_entry(
    user: AbstractBaseUser,
    entry_id: int,
    *,
    reversal_date: date | str | None = None,
    reason: str = "",
) -> CashLedgerReversalResult:
    if not (reason or "").strip():
        raise CashReversalValidationError("reason is required for audit.")

    entry = _ledger_entry_for_user(user, entry_id)
    _validate_reversible_manual_entry(entry)

    effective_date = (
        parse_ledger_date(reversal_date) if reversal_date is not None else date.today()
    )
    trimmed_reason = reason.strip()
    opposite_type = _opposite_manual_entry_type(entry.entry_type)
    opposite_amount = _opposite_signed_amount(entry)

    if opposite_type == CashEntryType.CASH_WITHDRAWAL:
        required = abs(opposite_amount)
        points = list_ledger_points_for_portfolio(
            entry.portfolio, currency=entry.currency, as_of_date=effective_date
        )
        available = cash_balance_on_date(points, effective_date).get(
            entry.currency, Decimal("0")
        )
        if available < required:
            raise InsufficientCashError(
                "Insufficient cash balance for reversal withdrawal.",
                required=required,
                available=available,
                shortfall=required - available,
                currency=entry.currency,
            )

    proposed = CashLedgerPoint(
        date=effective_date,
        currency=entry.currency,
        amount=opposite_amount,
    )
    validate_non_negative_cash_after_change(
        entry.portfolio,
        entry.currency,
        exclude_entry_id=None,
        proposed_point=proposed,
        from_date=effective_date,
    )

    reversal = CashLedgerEntry(
        portfolio=entry.portfolio,
        date=effective_date,
        currency=entry.currency,
        entry_type=opposite_type,
        amount=opposite_amount,
        source_of_funds="",
        note=f"Reversal of entry #{entry.id}: {trimmed_reason}",
        is_reversal=True,
        reverses=entry,
        reversal_reason=trimmed_reason,
    )
    reversal.full_clean()
    reversal.save()

    return CashLedgerReversalResult(
        original=_reload_ledger_entry(entry.id),
        reversal=_reload_ledger_entry(reversal.id),
        message="Broker cash entry reversed.",
    )
