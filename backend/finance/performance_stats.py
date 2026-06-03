"""
Core performance metrics from daily fractional returns (Metric Sheet).

Conventions
-----------
* Input daily returns: ``Decimal`` fractions (``0.10`` = +10%). ``DailyReturnPoint`` or
  bare ``Optional[Decimal]`` iterables are accepted; ``None`` entries are ignored.
* Output metrics are **fractions** unless noted (counts are ``int``).
* ``cagr`` uses calendar-day elapsed time between ``start_date`` and ``end_date`` (inclusive
  span: ``(end - start).days``; must be ``> 0``).
* Exponentiation in ``cagr`` uses float math internally, then converts back to ``Decimal``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable, Mapping, Optional

from finance._return_inputs import ReturnInput, valid_fractions
from finance.returns import compound_return

_ZERO = Decimal("0")
_ONE = Decimal("1")
_DAYS_PER_YEAR = Decimal("365")


@dataclass(frozen=True)
class PeriodSummary:
    """Summary statistics over valid daily return observations."""

    count: int
    wins: int
    losses: int
    flats: int
    win_rate: Optional[Decimal]
    best: Optional[Decimal]
    worst: Optional[Decimal]
    average: Optional[Decimal]


def cumulative_return(daily_returns: Iterable[ReturnInput]) -> Optional[Decimal]:
    """Compound valid daily returns: (Π(1+r)) - 1. ``None`` if no valid returns."""
    return compound_return(valid_fractions(daily_returns))


def contributions_and_withdrawals_through(
    flows_by_date: Mapping[date, Decimal], as_of: date
) -> tuple[Decimal, Decimal]:
    """Sum external contributions (buys) and withdrawals (sells) through ``as_of`` inclusive."""
    contrib = _ZERO
    withdraw = _ZERO
    for flow_date, amount in flows_by_date.items():
        if flow_date > as_of:
            continue
        if amount >= _ZERO:
            contrib += amount
        else:
            withdraw += -amount
    return contrib, withdraw


def economic_cumulative_return_fraction(
    *,
    terminal_value: Decimal,
    contributions: Decimal,
    withdrawals: Decimal,
) -> Optional[Decimal]:
    """
    Money-weighted cumulative return for a window end date.

    ``(terminal_value + withdrawals - contributions) / contributions`` as a fraction.
    Matches ``GET /portfolio/performance?metric=cumulative_return`` terminal points.
    """
    if contributions <= _ZERO:
        return None
    return (terminal_value + withdrawals - contributions) / contributions


def cagr_from_total_return(
    total_return: Decimal,
    start_date: date,
    end_date: date,
) -> Optional[Decimal]:
    """
    Compound annual growth rate from a total return fraction and calendar span.

    ``(1 + total_return) ** (365 / days) - 1`` with ``days = (end_date - start_date).days``.
    """
    if end_date < start_date:
        return None
    days = (end_date - start_date).days
    if days <= 0:
        return None
    base = float(_ONE + total_return)
    exponent = float(_DAYS_PER_YEAR) / float(days)
    return Decimal(str(base**exponent - 1.0))


def cagr(
    daily_returns: Iterable[ReturnInput],
    start_date: date,
    end_date: date,
) -> Optional[Decimal]:
    """
    Compound annual growth rate from compounded daily returns and calendar span.

    Uses ``cumulative_return(daily_returns)`` as the total return input. For Metric Sheet
    headline CAGR, prefer ``cagr_from_total_return`` with economic cumulative return.
    """
    cum = cumulative_return(daily_returns)
    if cum is None:
        return None
    return cagr_from_total_return(cum, start_date, end_date)


def best_return(daily_returns: Iterable[ReturnInput]) -> Optional[Decimal]:
    """Maximum single-period return; ``None`` if no valid returns."""
    vals = valid_fractions(daily_returns)
    if not vals:
        return None
    return max(vals)


def worst_return(daily_returns: Iterable[ReturnInput]) -> Optional[Decimal]:
    """Minimum single-period return; ``None`` if no valid returns."""
    vals = valid_fractions(daily_returns)
    if not vals:
        return None
    return min(vals)


def win_rate(daily_returns: Iterable[ReturnInput]) -> Optional[Decimal]:
    """
    Fraction of valid periods with return > 0 (flat ``0`` is not a win).

    Returns ``None`` if no valid returns.
    """
    vals = valid_fractions(daily_returns)
    if not vals:
        return None
    wins = sum(1 for r in vals if r > _ZERO)
    return Decimal(wins) / Decimal(len(vals))


def average_return(daily_returns: Iterable[ReturnInput]) -> Optional[Decimal]:
    """Arithmetic mean of valid daily returns; ``None`` if none."""
    vals = valid_fractions(daily_returns)
    if not vals:
        return None
    return sum(vals, _ZERO) / Decimal(len(vals))


def period_summary(daily_returns: Iterable[ReturnInput]) -> PeriodSummary:
    """Convenience bundle: counts, win rate, best/worst/average."""
    vals = valid_fractions(daily_returns)
    if not vals:
        return PeriodSummary(
            count=0,
            wins=0,
            losses=0,
            flats=0,
            win_rate=None,
            best=None,
            worst=None,
            average=None,
        )
    wins = sum(1 for r in vals if r > _ZERO)
    losses = sum(1 for r in vals if r < _ZERO)
    flats = sum(1 for r in vals if r == _ZERO)
    return PeriodSummary(
        count=len(vals),
        wins=wins,
        losses=losses,
        flats=flats,
        win_rate=Decimal(wins) / Decimal(len(vals)),
        best=max(vals),
        worst=min(vals),
        average=sum(vals, _ZERO) / Decimal(len(vals)),
    )
