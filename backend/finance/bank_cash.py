"""Pure bank cash movement balance helpers (no Django imports)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable

from finance.cash import CashLedgerPoint, cash_balance_timeseries

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


def bank_cash_to_ledger_points(
    movements: Iterable[BankCashMovementPoint],
) -> list[CashLedgerPoint]:
    """Convert bank movement points to signed cash ledger points."""
    return [
        CashLedgerPoint(
            date=movement.movement_date,
            currency=movement.currency,
            amount=signed_movement_amount(movement.amount, movement.direction),
        )
        for movement in movements
    ]


def bank_cash_balance_timeseries(
    movements: Iterable[BankCashMovementPoint],
    start_date: date,
    end_date: date,
) -> list[tuple[date, Decimal]]:
    """End-of-day bank balances for each calendar day in [start_date, end_date].

    Bank accounts are single-currency; returns the series for the currency present
    in ``movements`` (empty list when there are no points).
    """
    points = bank_cash_to_ledger_points(movements)
    if not points:
        return []
    currency = points[0].currency
    series = cash_balance_timeseries(points, start_date, end_date)
    return series.get(currency, [])


def bank_cash_balances_on_event_dates(
    movements: Iterable[BankCashMovementPoint],
    *,
    from_date: date,
) -> list[tuple[date, Decimal]]:
    """End-of-day balances on ``from_date`` and each movement date on/after it.

    Same-day movements are applied together before the day's balance is recorded,
    matching dense daily timeseries semantics without scanning every calendar day.
    Safe for endpoint boundary dates (e.g. year 0001 / 9999).
    """
    points = list(movements)
    if not points:
        return []

    by_date: dict[date, Decimal] = {}
    opening = _ZERO
    for movement in points:
        delta = signed_movement_amount(movement.amount, movement.direction)
        if movement.movement_date < from_date:
            opening += delta
            continue
        by_date[movement.movement_date] = by_date.get(movement.movement_date, _ZERO) + delta

    check_dates = sorted({from_date, *by_date.keys()})
    running = opening
    series: list[tuple[date, Decimal]] = []
    for day in check_dates:
        running += by_date.get(day, _ZERO)
        series.append((day, running))
    return series


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
