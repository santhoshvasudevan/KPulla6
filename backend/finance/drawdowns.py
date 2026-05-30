"""
Drawdown metrics from daily fractional returns (Metric Sheet).

Conventions
-----------
* Input daily returns: ``Decimal`` fractions; ``None`` skipped for wealth compounding.
* Drawdown values are **fractions** (``-0.20`` = -20% from running peak).
* Wealth index starts at ``1``; each valid return multiplies wealth by ``(1 + r)``.
* ``longest_drawdown_days``: when input includes dates, measures the longest calendar-day
  span from the first day wealth drops below the running peak through the last day still
  below that peak before a new high (inclusive day count). When dates are absent, counts
  consecutive return **periods** in drawdown instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable, Optional

from finance._return_inputs import ReturnInput, iter_return_points
from finance.performance_stats import cagr

_ZERO = Decimal("0")
_ONE = Decimal("1")


@dataclass(frozen=True)
class DrawdownPoint:
    """Drawdown fraction on a date (or ordered index when date unknown)."""

    date: Optional[date]
    drawdown_fraction: Optional[Decimal]


@dataclass(frozen=True)
class WorstDrawdownPeriod:
    """Single drawdown episode from peak through trough and optional recovery."""

    start_date: date
    trough_date: date
    recovery_date: Optional[date]
    drawdown_fraction: Decimal
    days_to_trough: int
    days_to_recovery: Optional[int]
    recovered: bool


def _wealth_path(
    daily_returns: Iterable[ReturnInput],
) -> list[tuple[Optional[date], Decimal]]:
    """Cumulative wealth after each valid return (starting wealth 1)."""
    path: list[tuple[Optional[date], Decimal]] = []
    wealth = _ONE
    for d, r in iter_return_points(daily_returns):
        if r is None:
            continue
        wealth *= _ONE + r
        path.append((d, wealth))
    return path


def drawdown_series(daily_returns: Iterable[ReturnInput]) -> list[DrawdownPoint]:
    """
    Running drawdown from peak wealth after each valid return.

    Emits one point per input row (including ``None`` return days with ``drawdown_fraction``
    ``None``). Wealth compounding applies only on valid returns.
    """
    peak = _ONE
    wealth = _ONE
    out: list[DrawdownPoint] = []

    for d, r in iter_return_points(daily_returns):
        if r is None:
            out.append(DrawdownPoint(date=d, drawdown_fraction=None))
            continue
        wealth = (wealth * (_ONE + r)).normalize()
        if wealth > peak:
            peak = wealth
        dd = (wealth / peak - _ONE) if peak > _ZERO else _ZERO
        out.append(DrawdownPoint(date=d, drawdown_fraction=dd))

    return out


def max_drawdown(daily_returns: Iterable[ReturnInput]) -> Optional[Decimal]:
    """Minimum drawdown fraction (most negative); ``None`` if no valid returns."""
    series = drawdown_series(daily_returns)
    vals = [p.drawdown_fraction for p in series if p.drawdown_fraction is not None]
    if not vals:
        return None
    return min(vals)


def longest_drawdown_days(daily_returns: Iterable[ReturnInput]) -> Optional[int]:
    """
    Longest drawdown episode length.

    With dates on every drawdown point: inclusive calendar days from the first day below
    the running peak through the last day still below that peak before recovery.
    Without dates: longest consecutive count of periods with drawdown < 0.
    Returns ``None`` if no valid returns or no drawdown episode occurred.
    """
    points = drawdown_series(daily_returns)
    entries = [(p.date, p.drawdown_fraction) for p in points if p.drawdown_fraction is not None]
    if not entries:
        return None

    use_calendar = all(d is not None for d, _ in entries)
    longest = 0
    episode_start: Optional[date] = None
    episode_end: Optional[date] = None
    period_run = 0

    for d, dd in entries:
        if dd < _ZERO:
            if use_calendar:
                if episode_start is None:
                    episode_start = d
                episode_end = d
            else:
                period_run += 1
                longest = max(longest, period_run)
        else:
            if use_calendar and episode_start is not None and episode_end is not None:
                length = (episode_end - episode_start).days + 1
                longest = max(longest, length)
            episode_start = None
            episode_end = None
            period_run = 0

    if use_calendar and episode_start is not None and episode_end is not None:
        length = (episode_end - episode_start).days + 1
        longest = max(longest, length)

    return longest if longest > 0 else None


def _append_drawdown_episode(
    episodes: list[WorstDrawdownPeriod],
    *,
    peak_date: date,
    peak_wealth: Decimal,
    trough_date: date,
    trough_wealth: Decimal,
    recovery_date: Optional[date],
) -> None:
    if peak_wealth <= _ZERO or trough_wealth >= peak_wealth:
        return
    dd = (trough_wealth / peak_wealth - _ONE).normalize()
    days_to_trough = (trough_date - peak_date).days
    recovered = recovery_date is not None
    days_to_recovery = (
        (recovery_date - peak_date).days if recovery_date is not None else None
    )
    episodes.append(
        WorstDrawdownPeriod(
            start_date=peak_date,
            trough_date=trough_date,
            recovery_date=recovery_date,
            drawdown_fraction=dd,
            days_to_trough=days_to_trough,
            days_to_recovery=days_to_recovery,
            recovered=recovered,
        )
    )


def worst_drawdown_periods(
    daily_returns: Iterable[ReturnInput],
    limit: int = 10,
) -> list[WorstDrawdownPeriod]:
    """
    Rank drawdown episodes by severity (most negative first).

    Uses dated daily fractional returns only. Builds wealth from valid returns,
    tracks each peak-to-trough episode, and records recovery when wealth reaches
    or exceeds the episode peak. Unrecovered episodes at series end have
    ``recovery_date=None`` and ``recovered=False``.
    """
    if limit < 1:
        return []

    path = _wealth_path(daily_returns)
    if len(path) < 2 or any(d is None for d, _ in path):
        return []

    episodes: list[WorstDrawdownPeriod] = []
    peak_wealth = path[0][1]
    peak_date = path[0][0]
    assert peak_date is not None

    trough_wealth = peak_wealth
    trough_date = peak_date
    in_drawdown = False

    for d, wealth in path[1:]:
        assert d is not None
        if wealth >= peak_wealth:
            if in_drawdown:
                _append_drawdown_episode(
                    episodes,
                    peak_date=peak_date,
                    peak_wealth=peak_wealth,
                    trough_date=trough_date,
                    trough_wealth=trough_wealth,
                    recovery_date=d,
                )
            peak_wealth = wealth
            peak_date = d
            trough_wealth = wealth
            trough_date = d
            in_drawdown = False
        else:
            if not in_drawdown:
                in_drawdown = True
                trough_wealth = wealth
                trough_date = d
            elif wealth < trough_wealth:
                trough_wealth = wealth
                trough_date = d

    if in_drawdown:
        _append_drawdown_episode(
            episodes,
            peak_date=peak_date,
            peak_wealth=peak_wealth,
            trough_date=trough_date,
            trough_wealth=trough_wealth,
            recovery_date=None,
        )

    episodes.sort(key=lambda ep: ep.drawdown_fraction)
    return episodes[:limit]


def calmar_ratio(
    daily_returns: Iterable[ReturnInput],
    start_date: date,
    end_date: date,
) -> Optional[Decimal]:
    """
    CAGR / absolute max drawdown.

    Returns ``None`` when CAGR or max drawdown is unavailable, or max drawdown is zero.
    """
    growth = cagr(daily_returns, start_date, end_date)
    mdd = max_drawdown(daily_returns)
    if growth is None or mdd is None or mdd == _ZERO:
        return None
    return growth / abs(mdd)
