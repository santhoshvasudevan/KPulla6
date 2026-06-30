"""Pure bank cash movement balance helpers (no Django imports)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable

_ZERO = Decimal("0")


@dataclass(frozen=True)
class BankCashMovementPoint:
    """Framework-independent bank cash movement for balance math."""

    movement_date: date
    currency: str
    amount: Decimal  # always positive magnitude
    direction: str  # CREDIT | DEBIT


@dataclass(frozen=True)
class BankFundingMovementPoint(BankCashMovementPoint):
    """Movement point for FD funding checks (excludes reversed ledger rows)."""

    is_reversal: bool = False
    is_reversed: bool = False


def signed_movement_amount(amount: Decimal, direction: str) -> Decimal:
    """Return signed ledger delta: CREDIT positive, DEBIT negative."""
    if direction == "CREDIT":
        return amount
    if direction == "DEBIT":
        return -amount
    raise ValueError(f"Unsupported direction: {direction}")


def bank_cash_balance(
    movements: Iterable[BankCashMovementPoint],
    *,
    as_of_date: date | None = None,
) -> Decimal:
    """Sum signed movement amounts; optional as-of filter by movement_date."""
    total = _ZERO
    for movement in movements:
        if as_of_date is not None and movement.movement_date > as_of_date:
            continue
        total += signed_movement_amount(movement.amount, movement.direction)
    return total


def bank_funding_balance(
    movements: Iterable[BankFundingMovementPoint],
    *,
    as_of_date: date | None = None,
) -> Decimal:
    """Balance available for FD funding as of a date.

    Excludes movements that were later reversed and reversal rows themselves so
    cancelled FD openings do not block recreation on the same investment date.
    """
    total = _ZERO
    for movement in movements:
        if as_of_date is not None and movement.movement_date > as_of_date:
            continue
        if movement.is_reversal or movement.is_reversed:
            continue
        total += signed_movement_amount(movement.amount, movement.direction)
    return total
