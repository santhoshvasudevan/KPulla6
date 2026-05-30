"""
Benchmark-relative metrics from aligned daily return fractions (Metric Sheet).

Conventions
-----------
* Input daily returns: ``Decimal`` fractions (``0.01`` = +1%). Use ``DailyReturnPoint`` when
  dates are required for alignment.
* Alignment: **exact calendar date** intersection only; ``None`` returns skipped; no
  forward-fill; missing dates omitted (not treated as zero).
* Annualized means: arithmetic ``mean(daily) × periods_per_year`` (default **252**),
  consistent with Phase 3 Sharpe/Sortino.
* ``risk_free_rate``: annual fraction (default ``0``); daily ``rf / periods_per_year``.
* Correlation is unitless; return metrics are fractional unless noted.
* Pearson correlation and sample cov/variance use float math internally where needed,
  then convert results to ``Decimal``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable, Optional

from finance._return_inputs import ReturnInput, iter_return_points
from finance.returns import DailyReturnPoint, compound_return

_ZERO = Decimal("0")
_ONE = Decimal("1")
_DEFAULT_PERIODS = 252


@dataclass(frozen=True)
class AlignedReturnPoint:
    """Paired subject and benchmark fractional returns on one calendar date."""

    date: date
    subject_return: Decimal
    benchmark_return: Decimal


@dataclass(frozen=True)
class BenchmarkSummary:
    """Bundle of benchmark-relative Metric Sheet statistics."""

    paired_count: int
    correlation: Optional[Decimal]
    beta: Optional[Decimal]
    alpha: Optional[Decimal]
    active_return: Optional[Decimal]
    tracking_error: Optional[Decimal]
    information_ratio: Optional[Decimal]
    treynor_ratio: Optional[Decimal]


def align_return_series(
    subject_returns: Iterable[ReturnInput],
    benchmark_returns: Iterable[ReturnInput],
) -> list[AlignedReturnPoint]:
    """
    Pair subject and benchmark returns on common dates.

    Only dates present in **both** series with non-``None`` fractions are included,
    sorted ascending. Points without a ``date`` (bare ``Decimal`` rows) cannot align
    and are ignored.
    """
    subject_by_date: dict[date, Decimal] = {}
    for d, r in iter_return_points(subject_returns):
        if d is not None and r is not None:
            subject_by_date[d] = r

    benchmark_by_date: dict[date, Decimal] = {}
    for d, r in iter_return_points(benchmark_returns):
        if d is not None and r is not None:
            benchmark_by_date[d] = r

    common_dates = sorted(set(subject_by_date) & set(benchmark_by_date))
    return [
        AlignedReturnPoint(
            date=d,
            subject_return=subject_by_date[d],
            benchmark_return=benchmark_by_date[d],
        )
        for d in common_dates
    ]


def _paired_lists(
    aligned: list[AlignedReturnPoint],
) -> tuple[list[Decimal], list[Decimal]]:
    return (
        [p.subject_return for p in aligned],
        [p.benchmark_return for p in aligned],
    )


def _sample_mean(values: list[Decimal]) -> Decimal:
    return sum(values, _ZERO) / Decimal(len(values))


def _sample_covariance(x: list[Decimal], y: list[Decimal]) -> Optional[Decimal]:
    n = len(x)
    if n < 2 or n != len(y):
        return None
    mx = _sample_mean(x)
    my = _sample_mean(y)
    return sum((xi - mx) * (yi - my) for xi, yi in zip(x, y)) / Decimal(n - 1)


def _sample_variance(values: list[Decimal]) -> Optional[Decimal]:
    n = len(values)
    if n < 2:
        return None
    mean = _sample_mean(values)
    var = sum((v - mean) ** 2 for v in values) / Decimal(n - 1)
    return var


def _sample_stdev(values: list[Decimal]) -> Optional[Decimal]:
    var = _sample_variance(values)
    if var is None:
        return None
    if var <= _ZERO:
        return _ZERO
    return Decimal(str(math.sqrt(float(var))))


def correlation(
    subject_returns: Iterable[ReturnInput],
    benchmark_returns: Iterable[ReturnInput],
) -> Optional[Decimal]:
    """Pearson correlation of aligned daily return fractions (unitless)."""
    aligned = align_return_series(subject_returns, benchmark_returns)
    if len(aligned) < 2:
        return None
    xs, ys = _paired_lists(aligned)
    cov = _sample_covariance(xs, ys)
    if cov is None:
        return None
    sx = _sample_stdev(xs)
    sy = _sample_stdev(ys)
    if sx is None or sy is None or sx == _ZERO or sy == _ZERO:
        return None
    return cov / (sx * sy)


def beta(
    subject_returns: Iterable[ReturnInput],
    benchmark_returns: Iterable[ReturnInput],
) -> Optional[Decimal]:
    """Sample covariance(subject, benchmark) / sample variance(benchmark)."""
    aligned = align_return_series(subject_returns, benchmark_returns)
    if len(aligned) < 2:
        return None
    xs, ys = _paired_lists(aligned)
    cov = _sample_covariance(xs, ys)
    var_b = _sample_variance(ys)
    if cov is None or var_b is None or var_b == _ZERO:
        return None
    return cov / var_b


def _annualized_mean(returns: list[Decimal], periods_per_year: int) -> Optional[Decimal]:
    if not returns:
        return None
    return _sample_mean(returns) * Decimal(periods_per_year)


def alpha(
    subject_returns: Iterable[ReturnInput],
    benchmark_returns: Iterable[ReturnInput],
    risk_free_rate: Decimal = _ZERO,
    periods_per_year: int = _DEFAULT_PERIODS,
) -> Optional[Decimal]:
    """
    Annualized CAPM alpha (fraction).

    ``subject_ann - (rf + beta × (benchmark_ann - rf))`` with annualized means
    ``mean(daily) × periods_per_year``.
    """
    aligned = align_return_series(subject_returns, benchmark_returns)
    if not aligned:
        return None
    xs, ys = _paired_lists(aligned)
    b = beta(subject_returns, benchmark_returns)
    if b is None:
        return None
    sub_ann = _annualized_mean(xs, periods_per_year)
    bench_ann = _annualized_mean(ys, periods_per_year)
    if sub_ann is None or bench_ann is None:
        return None
    expected = risk_free_rate + b * (bench_ann - risk_free_rate)
    return sub_ann - expected


def tracking_error(
    subject_returns: Iterable[ReturnInput],
    benchmark_returns: Iterable[ReturnInput],
    periods_per_year: int = _DEFAULT_PERIODS,
) -> Optional[Decimal]:
    """Annualized sample std dev of active daily returns (subject - benchmark)."""
    aligned = align_return_series(subject_returns, benchmark_returns)
    if len(aligned) < 2:
        return None
    xs, ys = _paired_lists(aligned)
    active = [x - y for x, y in zip(xs, ys)]
    daily_std = _sample_stdev(active)
    if daily_std is None:
        return None
    return daily_std * Decimal(str(math.sqrt(float(periods_per_year))))


def active_return(
    subject_returns: Iterable[ReturnInput],
    benchmark_returns: Iterable[ReturnInput],
    periods_per_year: int = _DEFAULT_PERIODS,
) -> Optional[Decimal]:
    """Annualized mean of (subject - benchmark) daily returns."""
    aligned = align_return_series(subject_returns, benchmark_returns)
    if not aligned:
        return None
    xs, ys = _paired_lists(aligned)
    active = [x - y for x, y in zip(xs, ys)]
    return _annualized_mean(active, periods_per_year)


def information_ratio(
    subject_returns: Iterable[ReturnInput],
    benchmark_returns: Iterable[ReturnInput],
    periods_per_year: int = _DEFAULT_PERIODS,
) -> Optional[Decimal]:
    """Active return / tracking error."""
    act = active_return(subject_returns, benchmark_returns, periods_per_year)
    te = tracking_error(subject_returns, benchmark_returns, periods_per_year)
    if act is None or te is None or te == _ZERO:
        return None
    return act / te


def treynor_ratio(
    subject_returns: Iterable[ReturnInput],
    benchmark_returns: Iterable[ReturnInput],
    risk_free_rate: Decimal = _ZERO,
    periods_per_year: int = _DEFAULT_PERIODS,
) -> Optional[Decimal]:
    """Annualized mean excess subject return / beta."""
    aligned = align_return_series(subject_returns, benchmark_returns)
    if not aligned:
        return None
    b = beta(subject_returns, benchmark_returns)
    if b is None or b == _ZERO:
        return None
    xs, _ = _paired_lists(aligned)
    rf_daily = risk_free_rate / Decimal(periods_per_year)
    mean_excess = _sample_mean([r - rf_daily for r in xs])
    ann_excess = mean_excess * Decimal(periods_per_year)
    return ann_excess / b


def benchmark_summary(
    subject_returns: Iterable[ReturnInput],
    benchmark_returns: Iterable[ReturnInput],
    risk_free_rate: Decimal = _ZERO,
    periods_per_year: int = _DEFAULT_PERIODS,
) -> BenchmarkSummary:
    """Convenience bundle of all benchmark-relative metrics."""
    aligned = align_return_series(subject_returns, benchmark_returns)
    return BenchmarkSummary(
        paired_count=len(aligned),
        correlation=correlation(subject_returns, benchmark_returns),
        beta=beta(subject_returns, benchmark_returns),
        alpha=alpha(subject_returns, benchmark_returns, risk_free_rate, periods_per_year),
        active_return=active_return(
            subject_returns, benchmark_returns, periods_per_year
        ),
        tracking_error=tracking_error(
            subject_returns, benchmark_returns, periods_per_year
        ),
        information_ratio=information_ratio(
            subject_returns, benchmark_returns, periods_per_year
        ),
        treynor_ratio=treynor_ratio(
            subject_returns, benchmark_returns, risk_free_rate, periods_per_year
        ),
    )


def align_multi_subject_returns(
    series_by_id: dict[str, list[DailyReturnPoint]],
) -> tuple[list[date], dict[str, list[Decimal]]]:
    """
    Intersect daily return dates across multiple subjects.

    Only dates present in **every** series with non-``None`` fractions are kept,
    sorted ascending. No forward-fill.
    """
    if not series_by_id:
        return [], {}

    by_date: dict[str, dict[date, Decimal]] = {}
    for subject_id, points in series_by_id.items():
        subject_map: dict[date, Decimal] = {}
        for pt in points:
            if pt.return_fraction is not None:
                subject_map[pt.date] = pt.return_fraction
        by_date[subject_id] = subject_map

    subject_ids = list(series_by_id.keys())
    candidate_dates: set[date] = set()
    for subject_id in subject_ids:
        candidate_dates.update(by_date[subject_id].keys())

    common_dates = sorted(
        d for d in candidate_dates if all(d in by_date[sid] for sid in subject_ids)
    )
    aligned = {
        sid: [by_date[sid][d] for d in common_dates] for sid in subject_ids
    }
    return common_dates, aligned


def normalized_cumulative_return_series(
    common_dates: list[date],
    aligned_returns: dict[str, list[Decimal]],
) -> list[dict[str, object]]:
    """
    Rebased cumulative fractional returns for side-by-side comparison.

    The first common date is ``0`` for every subject. Each later date compounds
    daily returns from the second common date through that date (returns on the
    first common date are not applied to cumulative values).
    """
    if not common_dates:
        return []

    subject_ids = list(aligned_returns.keys())
    out: list[dict[str, object]] = [
        {
            "date": common_dates[0].isoformat(),
            "values": {sid: 0.0 for sid in subject_ids},
        }
    ]
    if len(common_dates) == 1:
        return out

    running: dict[str, Decimal] = {sid: _ZERO for sid in subject_ids}
    for i in range(1, len(common_dates)):
        values: dict[str, float] = {}
        for sid in subject_ids:
            running[sid] = compound_return([running[sid], aligned_returns[sid][i]]) or _ZERO
            values[sid] = float(running[sid])
        out.append({"date": common_dates[i].isoformat(), "values": values})
    return out
