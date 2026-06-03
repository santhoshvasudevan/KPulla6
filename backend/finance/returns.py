"""
Daily and periodic return helpers for Quantitative Statistics / Metric Sheet.

Conventions
-----------
* **Fractional returns** (e.g. ``Decimal("0.10")`` = +10%) are used throughout this module
  for period, daily, monthly, and yearly outputs, and for ``compound_return`` /
  ``chain_returns`` results.
* **TWROR cumulative inputs** to ``daily_returns_from_twror_series`` use **percentage
  points** (e.g. ``10`` = 10%), matching ``compute_twror_series`` in ``finance.twror``.
* **External flows** are net cash flow per calendar date (positive = contribution).
  Callers must net multiple flows on the same day before passing ``flows_by_date``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable, Mapping, Optional

from finance.twror import TwrorPoint

_ZERO = Decimal("0")
_ONE = Decimal("1")
_HUNDRED = Decimal("100")


@dataclass(frozen=True)
class ValuePoint:
    """End-of-day valuation on a calendar date."""

    date: date
    value: Optional[Decimal]


@dataclass(frozen=True)
class DailyReturnPoint:
    """Cash-flow-adjusted daily period return (fraction, not percent)."""

    date: date
    return_fraction: Optional[Decimal]


@dataclass(frozen=True)
class PeriodReturnPoint:
    """Compounded fractional return over a calendar month or year."""

    period: str
    return_fraction: Decimal


def period_return(
    previous_value: Decimal,
    current_value: Decimal,
    external_flow: Decimal = _ZERO,
) -> Optional[Decimal]:
    """
    Single-period TWROR return: (current - flow - previous) / previous.

    Returns a fractional return, or ``None`` when ``previous_value <= 0``.
    """
    if previous_value <= _ZERO:
        return None
    return (current_value - external_flow - previous_value) / previous_value


def compound_return(period_returns: Iterable[Optional[Decimal]]) -> Optional[Decimal]:
    """
    Compound fractional period returns: (Π(1 + r_i)) - 1.

    ``None`` entries are skipped (not treated as zero). Returns ``None`` when no
    valid returns are present.
    """
    factor = _ONE
    seen = False
    for r in period_returns:
        if r is None:
            continue
        seen = True
        factor *= _ONE + r
    if not seen:
        return None
    return factor - _ONE


def chain_returns(period_returns: Iterable[Optional[Decimal]]) -> Optional[Decimal]:
    """
    Cumulative fractional return by chain-linking period returns.

    Same compounding as ``compound_return``: multiplies ``(1 + r)`` for each
    non-``None`` period return in order. Skipped ``None`` values do **not** break
    the product (unlike ``compute_twror_series``, which still advances the
    valuation baseline on ``None`` days). Use ``daily_returns_from_values`` when
    you need TWROR-aligned day-by-day logic including baseline advancement.
    """
    return compound_return(period_returns)


def daily_returns_from_values(
    value_points: Iterable[ValuePoint],
    flows_by_date: Mapping[date, Decimal] | None = None,
) -> list[DailyReturnPoint]:
    """
    Daily cash-flow-adjusted returns from an ordered value series.

    First point is always ``None`` (no prior value). For each subsequent day::

        r_d = (PV_d - Flow_d - PV_{d-1}) / PV_{d-1}

    ``flows_by_date`` maps each date to one **netted** external flow. Missing dates
    imply zero flow. If either endpoint value is ``None``, or ``PV_{d-1} <= 0``,
    the daily return is ``None`` but the baseline still advances to ``PV_d`` when
    present (matching ``compute_twror_series``).
    """
    flows = flows_by_date or {}
    points = list(value_points)
    if not points:
        return []

    out: list[DailyReturnPoint] = []
    prev_value: Optional[Decimal] = None

    for i, pt in enumerate(points):
        if i == 0:
            out.append(DailyReturnPoint(date=pt.date, return_fraction=None))
            prev_value = pt.value
            continue

        r: Optional[Decimal] = None
        if pt.value is not None and prev_value is not None and prev_value > _ZERO:
            flow = flows.get(pt.date, _ZERO)
            r = period_return(prev_value, pt.value, flow)

        out.append(DailyReturnPoint(date=pt.date, return_fraction=r))
        prev_value = pt.value

    return out


def daily_returns_from_twror_series(twror_points: Iterable[TwrorPoint]) -> list[DailyReturnPoint]:
    """
    Infer daily fractional returns from cumulative TWROR percentage points.

    Each ``TwrorPoint.value`` is cumulative return since series start in **percent**
    (``10`` = 10% cumulative). The first point, or any point with ``value is None``,
    yields a daily return of ``None``. For the first point with a numeric cumulative
    percent, the implied period return is ``value / 100``. Thereafter::

        r_d = (1 + C_d/100) / (1 + C_{d-1}/100) - 1

    where ``C`` is the last numeric cumulative percent used.
    """
    points = list(twror_points)
    out: list[DailyReturnPoint] = []
    prev_factor: Optional[Decimal] = None

    for pt in points:
        if pt.value is None:
            out.append(DailyReturnPoint(date=pt.date, return_fraction=None))
            continue

        factor = _ONE + pt.value / _HUNDRED
        if prev_factor is None:
            r = factor - _ONE
        else:
            r = factor / prev_factor - _ONE
        prev_factor = factor
        out.append(DailyReturnPoint(date=pt.date, return_fraction=r))

    return out


def _compound_daily_by_key(
    daily_points: Iterable[DailyReturnPoint],
    key_fn,
) -> list[PeriodReturnPoint]:
    buckets: dict[str, list[Decimal]] = {}
    for pt in daily_points:
        if pt.return_fraction is None:
            continue
        key = key_fn(pt.date)
        buckets.setdefault(key, []).append(pt.return_fraction)

    result: list[PeriodReturnPoint] = []
    for key in sorted(buckets):
        compounded = compound_return(buckets[key])
        if compounded is not None:
            result.append(PeriodReturnPoint(period=key, return_fraction=compounded))
    return result


def resample_monthly_returns(
    daily_return_points: Iterable[DailyReturnPoint],
) -> list[PeriodReturnPoint]:
    """
    Compound daily fractional returns by calendar month (``YYYY-MM``).

    Months with no valid (non-``None``) daily returns are omitted.
    """
    return _compound_daily_by_key(
        daily_return_points,
        lambda d: f"{d.year:04d}-{d.month:02d}",
    )


def resample_yearly_returns(
    daily_return_points: Iterable[DailyReturnPoint],
) -> list[PeriodReturnPoint]:
    """
    Compound daily fractional returns by calendar year (``YYYY``).

    Each row is **Calendar-Year Return**: cash-flow-adjusted daily returns
    (TWROR-style) compounded within the calendar year — not simple start-vs-end
    portfolio value change. Years with no valid daily returns are omitted.
    """
    return _compound_daily_by_key(
        daily_return_points,
        lambda d: f"{d.year:04d}",
    )
