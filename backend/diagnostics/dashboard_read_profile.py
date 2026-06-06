"""Read-only Dashboard read-path profiling helpers (STAB-5A)."""

from __future__ import annotations

import re
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any, Callable

from django.db import connection, reset_queries
from django.test.utils import CaptureQueriesContext

from analytics.services import build_portfolio_performance_metrics
from portfolios.holdings_service import build_holdings
from portfolios.performance_service import build_portfolio_performance
from portfolios.scope import ResolvedPortfolioScope
from portfolios.summary_service import build_portfolio_summary


@dataclass(frozen=True)
class EndpointNotes:
    cash_inclusive_value_series: bool = False
    uses_external_flows: bool = False
    uses_benchmark: bool = False
    all_scope: bool = False
    range_slicing: str = "n/a"  # early | late | n/a


@dataclass
class EndpointProfile:
    id: str
    http_method: str
    path: str
    elapsed_ms: float
    sql_query_count: int
    top_query_patterns: list[dict[str, Any]]
    result_point_count: int | None = None
    warnings_count: int = 0
    notes: EndpointNotes = field(default_factory=EndpointNotes)
    detail: str = ""


_SQL_TABLE_RE = re.compile(
    r'\b(?:FROM|JOIN|INTO|UPDATE)\s+"?([a-z_]+)"?',
    re.IGNORECASE,
)


def _normalize_sql(sql: str) -> str:
    line = sql.split("\n")[0].strip()
    if len(line) > 140:
        line = line[:137] + "..."
    return line


def _query_patterns(queries: list[dict]) -> list[dict[str, Any]]:
    by_sql: Counter[str] = Counter()
    by_table: Counter[str] = Counter()
    for q in queries:
        sql = q.get("sql", "")
        norm = _normalize_sql(sql)
        by_sql[norm] += 1
        for match in _SQL_TABLE_RE.finditer(sql):
            by_table[match.group(1).lower()] += 1
    patterns = [
        {"sql_prefix": sql, "count": count}
        for sql, count in by_sql.most_common(8)
    ]
    tables = [
        {"table": table, "count": count}
        for table, count in by_table.most_common(8)
    ]
    return [{"repeated_sql": patterns, "tables": tables}]


def _count_warnings(obj: Any) -> int:
    warnings = getattr(obj, "warnings", None)
    if isinstance(warnings, list):
        return len(warnings)
    if isinstance(obj, dict):
        w = obj.get("warnings")
        return len(w) if isinstance(w, list) else 0
    return 0


def _result_point_count(obj: Any) -> int | None:
    points = getattr(obj, "points", None)
    if isinstance(points, list):
        return len(points)
    holdings = getattr(obj, "holdings", None)
    if isinstance(holdings, list):
        return len(holdings)
    timeseries = getattr(obj, "timeseries", None)
    if isinstance(timeseries, list):
        return len(timeseries)
    payload = getattr(obj, "payload", None)
    if isinstance(payload, dict):
        for key in ("periodic_returns", "drawdown_periods"):
            val = payload.get(key)
            if isinstance(val, list) and val:
                return len(val)
    return None


def profile_call(
    *,
    endpoint_id: str,
    http_method: str,
    path: str,
    fn: Callable[[], Any],
    notes: EndpointNotes,
) -> EndpointProfile:
    reset_queries()
    connection.force_debug_cursor = True
    t0 = time.perf_counter()
    try:
        with CaptureQueriesContext(connection) as ctx:
            result = fn()
    finally:
        connection.force_debug_cursor = False
    elapsed_ms = (time.perf_counter() - t0) * 1000
    queries = ctx.captured_queries
    return EndpointProfile(
        id=endpoint_id,
        http_method=http_method,
        path=path,
        elapsed_ms=round(elapsed_ms, 2),
        sql_query_count=len(queries),
        top_query_patterns=_query_patterns(queries),
        result_point_count=_result_point_count(result),
        warnings_count=_count_warnings(result),
        notes=notes,
    )


def build_dashboard_endpoint_cases(
    *,
    scope: ResolvedPortfolioScope,
    display_currency: str,
    user,
    today: date | None = None,
) -> list[tuple[str, str, str, Callable[[], Any], EndpointNotes]]:
    """Return (id, method, path, callable, notes) for each Dashboard read path."""
    disp = display_currency.upper()
    scope_q = "portfolio_scope=all"
    disp_q = f"display_currency={disp}"
    all_scope = scope.kind == "all_active"

    def _perf_path(metric: str, range_code: str) -> str:
        return (
            f"/api/v1/portfolio/performance?{scope_q}&{disp_q}"
            f"&metric={metric}&range={range_code}"
        )

    def _metric_sheet_path(range_code: str) -> str:
        return (
            f"/api/v1/analytics/performance-metrics?{scope_q}&{disp_q}"
            f"&range={range_code}"
        )

    cases: list[tuple[str, str, str, Callable[[], Any], EndpointNotes]] = []

    cases.append(
        (
            "summary",
            "GET",
            f"/api/v1/portfolio/summary?{scope_q}&{disp_q}&include_timeseries=false",
            lambda: build_portfolio_summary(
                scope=scope,
                include_timeseries=False,
                display_currency=disp,
                user=user,
            ),
            EndpointNotes(
                cash_inclusive_value_series=False,
                uses_external_flows=False,
                uses_benchmark=False,
                all_scope=all_scope,
                range_slicing="n/a",
            ),
        )
    )

    for range_code in ("1Y", "ALL"):
        cases.append(
            (
                f"performance_value_{range_code.lower()}",
                "GET",
                _perf_path("value", range_code),
                lambda rc=range_code: build_portfolio_performance(
                    scope=scope,
                    metric="value",
                    range_code=rc,
                    display_currency=disp,
                    today=today,
                ),
                EndpointNotes(
                    cash_inclusive_value_series=True,
                    uses_external_flows=False,
                    uses_benchmark=False,
                    all_scope=all_scope,
                    range_slicing="early" if range_code != "ALL" else "late",
                ),
            )
        )

    cases.append(
        (
            "performance_cumulative_return_1y",
            "GET",
            _perf_path("cumulative_return", "1Y"),
            lambda: build_portfolio_performance(
                scope=scope,
                metric="cumulative_return",
                range_code="1Y",
                display_currency=disp,
                today=today,
            ),
            EndpointNotes(
                cash_inclusive_value_series=True,
                uses_external_flows=True,
                uses_benchmark=False,
                all_scope=all_scope,
                range_slicing="late",
            ),
        )
    )

    cases.append(
        (
            "performance_twror_1y",
            "GET",
            _perf_path("twror", "1Y"),
            lambda: build_portfolio_performance(
                scope=scope,
                metric="twror",
                range_code="1Y",
                display_currency=disp,
                today=today,
            ),
            EndpointNotes(
                cash_inclusive_value_series=True,
                uses_external_flows=True,
                uses_benchmark=False,
                all_scope=all_scope,
                range_slicing="early",
            ),
        )
    )

    for range_code in ("1Y", "ALL"):
        cases.append(
            (
                f"metric_sheet_{range_code.lower()}",
                "GET",
                _metric_sheet_path(range_code),
                lambda rc=range_code: build_portfolio_performance_metrics(
                    scope=scope,
                    range_code=rc,
                    display_currency=disp,
                    benchmark_symbol=None,
                    today=today,
                ),
                EndpointNotes(
                    cash_inclusive_value_series=True,
                    uses_external_flows=True,
                    uses_benchmark=False,
                    all_scope=all_scope,
                    range_slicing="early",
                ),
            )
        )

    cases.append(
        (
            "holdings",
            "GET",
            f"/api/v1/portfolio/holdings?{scope_q}&{disp_q}",
            lambda: build_holdings(scope=scope, display_currency=disp),
            EndpointNotes(
                cash_inclusive_value_series=False,
                uses_external_flows=False,
                uses_benchmark=False,
                all_scope=all_scope,
                range_slicing="n/a",
            ),
        )
    )

    return cases


def profile_dashboard_read_paths(
    *,
    scope: ResolvedPortfolioScope,
    display_currency: str,
    user,
    today: date | None = None,
) -> list[EndpointProfile]:
    profiles: list[EndpointProfile] = []
    for endpoint_id, method, path, fn, notes in build_dashboard_endpoint_cases(
        scope=scope,
        display_currency=display_currency,
        user=user,
        today=today,
    ):
        profiles.append(
            profile_call(
                endpoint_id=endpoint_id,
                http_method=method,
                path=path,
                fn=fn,
                notes=notes,
            )
        )
    return profiles


def profiles_to_baseline_payload(
    profiles: list[EndpointProfile],
    *,
    username: str,
    scope: ResolvedPortfolioScope,
    display_currency: str,
    captured_at: str,
) -> dict[str, Any]:
    return {
        "captured_at": captured_at,
        "username": username,
        "scope_kind": scope.kind,
        "portfolio_ids": scope.portfolio_ids,
        "display_currency": display_currency.upper(),
        "endpoints": [
            {
                **{k: v for k, v in asdict(p).items() if k != "notes"},
                "notes": asdict(p.notes),
            }
            for p in profiles
        ],
        "totals": {
            "endpoint_count": len(profiles),
            "total_elapsed_ms": round(sum(p.elapsed_ms for p in profiles), 2),
            "total_sql_queries": sum(p.sql_query_count for p in profiles),
        },
    }


def format_profile_table(profiles: list[EndpointProfile]) -> str:
    lines = [
        "Dashboard read-path baseline (service-layer, read-only)",
        f"{'id':<34} {'ms':>8} {'queries':>8} {'pts':>6} {'warn':>5}",
        "-" * 70,
    ]
    for p in profiles:
        pts = p.result_point_count if p.result_point_count is not None else "-"
        lines.append(
            f"{p.id:<34} {p.elapsed_ms:>8.1f} {p.sql_query_count:>8} {str(pts):>6} {p.warnings_count:>5}"
        )
    lines.append("-" * 70)
    lines.append(
        f"{'TOTAL':<34} {sum(p.elapsed_ms for p in profiles):>8.1f} "
        f"{sum(p.sql_query_count for p in profiles):>8}"
    )
    return "\n".join(lines)
