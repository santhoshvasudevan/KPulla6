#!/usr/bin/env python3
"""Read-only Dashboard backend profiling (local diagnostic; not part of test suite)."""
from __future__ import annotations

import json
import os
import sys
import time
from collections import Counter
from contextlib import contextmanager
from datetime import date
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.db import connection, reset_queries
from django.test.utils import CaptureQueriesContext

from analytics.services import (
    _slice_timeseries_for_range,
    _split_adjusted_price_inconsistency_warnings,
    _split_symbol_timeseries_cache,
    _timeseries_to_value_points,
    _valuation_coverage_warnings,
    build_metric_sheet_extension_blocks,
    build_metric_sheet_from_daily_returns,
    build_portfolio_performance_metrics,
    compute_scope_xirr,
)
from finance.performance_range import resolve_performance_range_start
from finance.returns import daily_returns_from_values
from portfolios import dates as portfolio_dates
from portfolios.performance_service import (
    build_all_scope_external_flows,
    build_portfolio_performance,
    performance_list_payload,
)
from portfolios.scope import resolve_portfolio_scope
from portfolios.summary_service import (
    build_all_scope_portfolio_value_timeseries,
    build_portfolio_summary,
    fifo_eligible_queryset,
    transactions_by_mf_holding,
    transactions_by_symbol,
)

SCOPE = resolve_portfolio_scope(portfolio_scope="all")
DISP = "EUR"
TIMINGS: list[tuple[str, str, float, str]] = []


@contextmanager
def timed(block: str, endpoint: str = "internal", note: str = ""):
    t0 = time.perf_counter()
    yield
    ms = (time.perf_counter() - t0) * 1000
    TIMINGS.append((block, endpoint, ms, note))


def _print_query_report(label: str, queries: list) -> None:
    print(f"\n=== DB queries: {label} ({len(queries)} total) ===")
    by_sql = Counter()
    for q in queries:
        sql = q["sql"].split("\n")[0][:120]
        by_sql[sql] += 1
    for sql, cnt in by_sql.most_common(12):
        print(f"  x{cnt:3d}  {sql}")


def _profile_performance_breakdown(
    *,
    metric: str,
    range_code: str,
    endpoint: str,
) -> None:
    today = portfolio_dates.current_date()
    queryset = fifo_eligible_queryset(SCOPE.portfolio_ids)
    all_txns = list(queryset)
    by_symbol = transactions_by_symbol(queryset)
    by_mf = transactions_by_mf_holding(queryset)

    with timed("date_range_parse", endpoint, range_code):
        ts_full_probe = build_all_scope_portfolio_value_timeseries(SCOPE, DISP)
        if not ts_full_probe:
            return
        inception = date.fromisoformat(ts_full_probe[0]["date"])
        range_start = resolve_performance_range_start(range_code, today, inception)

    with timed("build_all_scope_portfolio_value_timeseries", endpoint, range_code):
        timeseries_full = build_all_scope_portfolio_value_timeseries(SCOPE, DISP)

    full_len = len(timeseries_full)
    range_start_iso = range_start.isoformat()

    with timed("slice_timeseries", endpoint, f"{range_code} full={full_len}"):
        if metric == "value":
            sliced = [p for p in timeseries_full if p["date"] >= range_start_iso]
        elif metric == "cumulative_return":
            sliced = list(timeseries_full)
        else:
            if range_code == "ALL":
                sliced = timeseries_full
            else:
                sliced = [p for p in timeseries_full if p["date"] >= range_start_iso]

    with timed("metric_conversion", endpoint, f"{metric} out={len(sliced)}"):
        pts = build_portfolio_performance(
            scope=SCOPE,
            metric=metric,  # type: ignore[arg-type]
            range_code=range_code,
            display_currency=DISP,
            today=today,
        )

    with timed("response_serialization", endpoint, f"pts={len(pts)}"):
        performance_list_payload(pts)


def _profile_metric_sheet_breakdown(*, range_code: str, benchmark: str | None) -> None:
    endpoint = f"analytics/{range_code}" + ("+bench" if benchmark else "")
    today = portfolio_dates.current_date()
    queryset = fifo_eligible_queryset(SCOPE.portfolio_ids)
    all_txns = list(queryset)
    by_symbol = transactions_by_symbol(queryset)
    by_mf = transactions_by_mf_holding(queryset)

    with timed("base_value_series_build", endpoint):
        timeseries_full = build_all_scope_portfolio_value_timeseries(SCOPE, DISP)

    with timed("slice_for_range", endpoint, f"full={len(timeseries_full)}"):
        ts_use, window_start, window_end, _ = _slice_timeseries_for_range(
            timeseries_full, range_code=range_code, today=today
        )

    with timed("split_warning_checks", endpoint):
        _split_adjusted_price_inconsistency_warnings(
            by_symbol=by_symbol,
            timeseries_by_symbol=_split_symbol_timeseries_cache(by_symbol),
        )

    with timed("nav_price_coverage_warnings", endpoint):
        _valuation_coverage_warnings(
            window_start=window_start,
            window_end=window_end,
            by_symbol=by_symbol,
            by_mf=by_mf,
        )

    with timed("external_flows_build", endpoint):
        flows_by_date, flows_unknown_from = build_all_scope_external_flows(SCOPE, DISP)

    with timed("daily_returns", endpoint, f"window={len(ts_use)}"):
        value_points = _timeseries_to_value_points(
            ts_use, flows_unknown_from=flows_unknown_from
        )
        daily_pts = daily_returns_from_values(value_points, flows_by_date)
        daily_fracs = [p.return_fraction for p in daily_pts]

    with timed("xirr_full_scope", endpoint):
        xirr_val = compute_scope_xirr(SCOPE)

    with timed("performance_stats+risk+drawdowns+benchmark", endpoint):
        build_metric_sheet_from_daily_returns(
            daily_pts=daily_pts,
            daily_fracs=daily_fracs,
            ts_use=ts_use,
            flows_by_date=flows_by_date,
            flows_unknown_from=flows_unknown_from,
            window_start=window_start,
            window_end=window_end,
            xirr_val=xirr_val,
            benchmark_symbol=benchmark,
            warnings=[],
        )

    with timed("periodic_returns+drawdown_periods", endpoint):
        build_metric_sheet_extension_blocks(daily_pts)

    with timed("full_build_portfolio_performance_metrics", endpoint):
        build_portfolio_performance_metrics(
            scope=SCOPE,
            range_code=range_code,
            display_currency=DISP,
            benchmark_symbol=benchmark,
            today=today,
        )


def profile_endpoint_totals() -> None:
    cases = [
        ("performance value ALL", "performance/value", "value", "ALL"),
        ("performance value 1Y", "performance/value", "value", "1Y"),
        ("performance twror ALL", "performance/twror", "twror", "ALL"),
        ("performance twror 1Y", "performance/twror", "twror", "1Y"),
        ("Metric Sheet ALL", "analytics/metric-sheet", None, "ALL"),
        ("Metric Sheet ALL+bench", "analytics/metric-sheet", None, "ALL+bench"),
        ("Metric Sheet 1Y", "analytics/metric-sheet", None, "1Y"),
        ("Metric Sheet 1Y+bench", "analytics/metric-sheet", None, "1Y+bench"),
    ]
    for label, endpoint, metric, range_code in cases:
        bench = "^GSPC" if "+bench" in range_code else None
        rc = range_code.replace("+bench", "")
        with timed(label, endpoint, rc):
            if metric:
                build_portfolio_performance(
                    scope=SCOPE,
                    metric=metric,  # type: ignore[arg-type]
                    range_code=rc,
                    display_currency=DISP,
                )
            else:
                build_portfolio_performance_metrics(
                    scope=SCOPE,
                    range_code=rc,
                    display_currency=DISP,
                    benchmark_symbol=bench,
                )


def profile_internal_blocks() -> None:
    with timed("build_portfolio_summary", "summary"):
        build_portfolio_summary(
            scope=SCOPE, include_timeseries=False, display_currency=DISP
        )

    with timed("build_all_scope_portfolio_value_timeseries(ALL)", "shared"):
        ts = build_all_scope_portfolio_value_timeseries(SCOPE, DISP)
        if ts:
            TIMINGS[-1] = (
                TIMINGS[-1][0],
                TIMINGS[-1][1],
                TIMINGS[-1][2],
                f"days={len(ts)} {ts[0]['date']}..{ts[-1]['date']}",
            )

    today = portfolio_dates.current_date()
    txns = list(fifo_eligible_queryset(SCOPE.portfolio_ids))
    if txns:
        inception = min(t.date for t in txns)
        emit_1y = resolve_performance_range_start("1Y", today, inception)
        with timed("build_all_scope_portfolio_value_timeseries(1Y emit)", "shared"):
            ts_1y = build_all_scope_portfolio_value_timeseries(
                SCOPE, DISP, emit_start_date=emit_1y
            )
            if ts_1y:
                TIMINGS[-1] = (
                    TIMINGS[-1][0],
                    TIMINGS[-1][1],
                    TIMINGS[-1][2],
                    f"days={len(ts_1y)} {ts_1y[0]['date']}..{ts_1y[-1]['date']}",
                )

    with timed("build_all_scope_external_flows", "shared"):
        build_all_scope_external_flows(SCOPE, DISP)


def profile_query_counts() -> None:
    cases = [
        (
            "performance value ALL",
            lambda: build_portfolio_performance(
                scope=SCOPE,
                metric="value",
                range_code="ALL",
                display_currency=DISP,
            ),
        ),
        (
            "performance value 1Y",
            lambda: build_portfolio_performance(
                scope=SCOPE,
                metric="value",
                range_code="1Y",
                display_currency=DISP,
            ),
        ),
        (
            "analytics Metric Sheet ALL",
            lambda: build_portfolio_performance_metrics(
                scope=SCOPE,
                range_code="ALL",
                display_currency=DISP,
            ),
        ),
        (
            "analytics Metric Sheet 1Y",
            lambda: build_portfolio_performance_metrics(
                scope=SCOPE,
                range_code="1Y",
                display_currency=DISP,
            ),
        ),
    ]
    for label, fn in cases:
        reset_queries()
        with CaptureQueriesContext(connection) as ctx:
            fn()
        _print_query_report(label, ctx.captured_queries)


def main() -> None:
    print("Dashboard read-path profiling — Phase B2A (read-only, live DB)")
    print(f"scope=all display_currency={DISP}")
    profile_internal_blocks()
    profile_endpoint_totals()

    for metric in ("value", "twror"):
        for rc in ("ALL", "1Y"):
            _profile_performance_breakdown(metric=metric, range_code=rc, endpoint=f"perf/{metric}/{rc}")

    for rc in ("ALL", "1Y"):
        _profile_metric_sheet_breakdown(range_code=rc, benchmark=None)
        _profile_metric_sheet_breakdown(range_code=rc, benchmark="^GSPC")

    profile_query_counts()

    print("\n=== Endpoint totals (ms) ===")
    print(f"{'label':<40} {'endpoint':<24} {'time_ms':>10}  note")
    endpoint_rows = [
        t for t in TIMINGS if t[0].startswith("performance ") or t[0].startswith("Metric Sheet")
    ]
    for block, endpoint, ms, note in sorted(endpoint_rows, key=lambda x: x[0]):
        print(f"{block:<40} {endpoint:<24} {ms:10.1f}  {note}")

    print("\n=== Performance breakdown (ms) ===")
    print(f"{'block':<44} {'endpoint':<20} {'time_ms':>10}  note")
    breakdown_prefixes = (
        "date_range_parse",
        "build_all_scope_portfolio_value_timeseries",
        "slice_timeseries",
        "metric_conversion",
        "response_serialization",
    )
    breakdown_rows = [t for t in TIMINGS if t[0] in breakdown_prefixes]
    for block, endpoint, ms, note in breakdown_rows:
        print(f"{block:<44} {endpoint:<20} {ms:10.1f}  {note}")

    print("\n=== Metric Sheet breakdown (ms) ===")
    print(f"{'block':<44} {'endpoint':<20} {'time_ms':>10}  note")
    ms_blocks = (
        "base_value_series_build",
        "slice_for_range",
        "split_warning_checks",
        "nav_price_coverage_warnings",
        "external_flows_build",
        "daily_returns",
        "xirr_full_scope",
        "performance_stats+risk+drawdowns+benchmark",
        "periodic_returns+drawdown_periods",
        "full_build_portfolio_performance_metrics",
    )
    ms_rows = [t for t in TIMINGS if t[0] in ms_blocks]
    for block, endpoint, ms, note in ms_rows:
        print(f"{block:<44} {endpoint:<20} {ms:10.1f}  {note}")

    print("\n=== All internal timing (ms, sorted) ===")
    print(f"{'function/block':<52} {'endpoint':<24} {'time_ms':>10}  note")
    for block, endpoint, ms, note in sorted(TIMINGS, key=lambda x: -x[2]):
        extra = f"  {note}" if note else ""
        print(f"{block:<52} {endpoint:<24} {ms:10.1f}{extra}")


if __name__ == "__main__":
    main()
