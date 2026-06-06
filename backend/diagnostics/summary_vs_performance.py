"""Summary vs performance value consistency (read-only)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

from django.contrib.auth.models import AbstractBaseUser

from portfolios import dates as portfolio_dates
from portfolios.performance_service import build_portfolio_performance
from portfolios.scope import ResolvedPortfolioScope
from portfolios.summary_service import build_portfolio_summary
from settings_app.services import get_settings


@dataclass(frozen=True)
class SummaryPerformanceMismatch:
    scope_kind: str
    portfolio_ids: list[int]
    display_currency: str
    summary_current_value: float
    performance_latest_date: str | None
    performance_latest_value: float | None
    difference: float | None
    tolerance: float
    summary_warnings: list[str]
    performance_warnings: list[str]


def _last_performance_value(points: list[dict]) -> tuple[str | None, float | None]:
    for point in reversed(points):
        if point.value is not None:
            return point.date, float(point.value)
    return None, None


def check_summary_vs_performance(
    *,
    user: AbstractBaseUser,
    scope: ResolvedPortfolioScope,
    display_currency: str | None,
    tolerance: float,
    today: date | None = None,
) -> SummaryPerformanceMismatch:
    disp = (display_currency or get_settings(user).display_currency or "EUR").upper()
    as_of = today or portfolio_dates.current_date()

    summary = build_portfolio_summary(
        scope=scope,
        include_timeseries=False,
        display_currency=disp,
        user=user,
    )
    perf = build_portfolio_performance(
        scope=scope,
        metric="value",
        range_code="ALL",
        display_currency=disp,
        today=as_of,
    )
    perf_date, perf_value = _last_performance_value(perf.points)

    summary_cv = float(summary.current_value)
    diff: float | None = None
    if perf_value is not None:
        diff = abs(summary_cv - perf_value)

    return SummaryPerformanceMismatch(
        scope_kind=scope.kind,
        portfolio_ids=list(scope.portfolio_ids),
        display_currency=disp,
        summary_current_value=summary_cv,
        performance_latest_date=perf_date,
        performance_latest_value=perf_value,
        difference=diff,
        tolerance=tolerance,
        summary_warnings=list(summary.warnings),
        performance_warnings=list(perf.warnings),
    )


def mismatch_detected(result: SummaryPerformanceMismatch) -> bool:
    if result.performance_latest_value is None:
        return True
    if result.difference is None:
        return True
    return result.difference > result.tolerance


def build_summary_performance_report(
    result: SummaryPerformanceMismatch,
) -> dict[str, Any]:
    return {
        **asdict(result),
        "match": not mismatch_detected(result),
    }


def format_summary_performance_report(result: SummaryPerformanceMismatch) -> None:
    print("\n=== Summary ===")
    print(f"  scope={result.scope_kind} portfolio_ids={result.portfolio_ids}")
    print(f"  display_currency={result.display_currency}")
    print(f"  summary.current_value: {result.summary_current_value}")
    print(
        f"  performance value (latest): date={result.performance_latest_date} "
        f"value={result.performance_latest_value}"
    )
    print(f"  difference: {result.difference} tolerance: {result.tolerance}")
    print(f"  match: {not mismatch_detected(result)}")
    if result.summary_warnings:
        print(f"  summary warnings: {result.summary_warnings}")
    if result.performance_warnings:
        print(f"  performance warnings: {result.performance_warnings}")
