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
from typing import Iterable, Optional

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


def cagr(
    daily_returns: Iterable[ReturnInput],
    start_date: date,
    end_date: date,
) -> Optional[Decimal]:
    """
    Compound annual growth rate from cumulative return and calendar span.

    ``(1 + cumulative_return) ** (365 / days) - 1`` with ``days = (end_date - start_date).days``.
    Returns ``None`` when cumulative return is unavailable, dates invalid, or ``days <= 0``.
    """
    if end_date < start_date:
        return None
    days = (end_date - start_date).days
    if days <= 0:
        return None
    cum = cumulative_return(daily_returns)
    if cum is None:
        return None
    base = float(_ONE + cum)
    exponent = float(_DAYS_PER_YEAR) / float(days)
    return Decimal(str(base**exponent - 1.0))


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
