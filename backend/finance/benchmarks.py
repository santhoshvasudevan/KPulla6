"""
Benchmark index helpers for performance comparison (framework-independent).

Benchmark levels are supplied as a pandas Series by the service layer (DB-backed
INDEX rows). No external market-data calls in this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal, Optional

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class PerformancePoint:
    date: str
    value: float | None
    metric: str
    currency: str | None = None


def first_portfolio_metric_index(portfolio_values: list[float | None]) -> int | None:
    for i, v in enumerate(portfolio_values):
        if v is not None:
            return i
    return None


def _normalize_series_index_to_naive_dates(ser: pd.Series) -> pd.Series:
    out = ser.copy()
    idx = pd.to_datetime(out.index, utc=True).tz_localize(None)
    out.index = idx.normalize()
    return out.sort_index().groupby(level=0).last()


def align_single_benchmark_to_portfolio_calendar(
    portfolio_dates: list[date],
    portfolio_values: list[float | None],
    price_series: pd.Series,
    port_start_i: int,
) -> tuple[np.ndarray | None, int | None, list[str]]:
    local_warn: list[str] = []
    n = len(portfolio_dates)
    if n == 0 or port_start_i < 0 or port_start_i >= n:
        return None, None, ["Invalid portfolio date range."]

    ser = _normalize_series_index_to_naive_dates(price_series)
    if ser.empty:
        return None, None, ["Benchmark has no price observations."]

    full_idx = pd.DatetimeIndex([pd.Timestamp(d).normalize() for d in portfolio_dates])
    port_start_date = portfolio_dates[port_start_i]
    ts_port_start = pd.Timestamp(port_start_date).normalize()

    eligible = ser.index[ser.index >= ts_port_start]
    if len(eligible) == 0:
        return None, None, ["No benchmark prices on or after the portfolio start date."]

    bench_anchor_ts = eligible.min()
    ba_date = bench_anchor_ts.date()

    expanded = ser.reindex(full_idx).ffill()
    arr = expanded.to_numpy(dtype=float, copy=True)
    mask_before_anchor = np.asarray(full_idx < bench_anchor_ts, dtype=bool)
    arr[mask_before_anchor] = np.nan

    anchor_i: int | None = None
    for i in range(n):
        if portfolio_dates[i] < ba_date:
            continue
        if portfolio_values[i] is not None:
            anchor_i = i
            break

    if anchor_i is None:
        return None, None, ["No portfolio metric value on or after the benchmark start date."]

    p_anchor = arr[anchor_i]
    if np.isnan(p_anchor) or float(p_anchor) == 0.0:
        return None, None, ["Benchmark price missing or zero at the comparison anchor date."]

    return arr, anchor_i, local_warn


def build_benchmark_comparison_data(
    aligned_prices: np.ndarray,
    anchor_i: int,
    dates_iso: list[str],
    symbol: str,
    display_name: str,
) -> dict:
    p0 = float(aligned_prices[anchor_i])
    data: list[dict] = []
    for i, dstr in enumerate(dates_iso):
        px = aligned_prices[i]
        if np.isnan(px):
            data.append({"date": dstr, "value": None})
        else:
            data.append({"date": dstr, "value": float((float(px) / p0 - 1.0) * 100.0)})
    return {
        "name": display_name,
        "symbol": symbol,
        "type": "benchmark",
        "data": data,
    }


def rebase_portfolio_for_comparison(
    points: list[PerformancePoint],
    metric: Literal["cumulative_return", "twror"],
    anchor_i: int,
) -> list[float | None]:
    if anchor_i < 0 or anchor_i >= len(points):
        return [p.value for p in points]
    anchor_val = points[anchor_i].value
    if anchor_val is None:
        return [p.value for p in points]

    if metric == "cumulative_return":
        a = float(anchor_val)
        return [None if p.value is None else float(p.value) - a for p in points]

    f_anchor = 1.0 + float(anchor_val) / 100.0
    out: list[float | None] = []
    for p in points:
        if p.value is None:
            out.append(None)
        else:
            f_d = 1.0 + float(p.value) / 100.0
            out.append((f_d / f_anchor - 1.0) * 100.0)
    return out


def merge_performance_and_benchmarks(
    portfolio_points: list[PerformancePoint],
    metric: Literal["cumulative_return", "twror"],
    benchmark_symbol: str,
    *,
    benchmark_display_name: str,
    benchmark_price_series: pd.Series | None,
) -> dict:
    warnings: list[str] = []
    sym = (benchmark_symbol or "").strip()
    if not sym:
        series = [
            {
                "name": "Portfolio",
                "type": "portfolio",
                "data": [{"date": p.date, "value": p.value} for p in portfolio_points],
            }
        ]
        return {"metric": metric, "series": series, "warnings": warnings}

    if not portfolio_points:
        return {"metric": metric, "series": [], "warnings": warnings}

    dates_iso = [p.date for p in portfolio_points]
    dates = [date.fromisoformat(x) for x in dates_iso]
    port_vals = [p.value for p in portfolio_points]

    port_start_i = first_portfolio_metric_index(port_vals)
    if port_start_i is None:
        warnings.append("No portfolio performance values available for benchmark comparison.")
        series = [
            {
                "name": "Portfolio",
                "type": "portfolio",
                "data": [{"date": p.date, "value": p.value} for p in portfolio_points],
            }
        ]
        return {"metric": metric, "series": series, "warnings": warnings}

    ser = benchmark_price_series
    if ser is None or ser.empty:
        warnings.append(
            "Benchmark prices are not in the local database yet; wait for the next background sync."
        )
        series = [
            {
                "name": "Portfolio",
                "type": "portfolio",
                "data": [{"date": p.date, "value": p.value} for p in portfolio_points],
            }
        ]
        return {"metric": metric, "series": series, "warnings": warnings}

    aligned_arr, anchor_i, align_warnings = align_single_benchmark_to_portfolio_calendar(
        dates, port_vals, ser, port_start_i
    )
    warnings.extend(align_warnings)

    if aligned_arr is None or anchor_i is None:
        warnings.append(
            "Benchmark data could not be aligned with the portfolio series (missing quotes or anchor)."
        )
        series = [
            {
                "name": "Portfolio",
                "type": "portfolio",
                "data": [{"date": p.date, "value": p.value} for p in portfolio_points],
            }
        ]
        return {"metric": metric, "series": series, "warnings": warnings}

    rebased = rebase_portfolio_for_comparison(portfolio_points, metric, anchor_i)
    portfolio_series = {
        "name": "Portfolio",
        "type": "portfolio",
        "data": [{"date": p.date, "value": v} for p, v in zip(portfolio_points, rebased)],
    }
    bench_series = build_benchmark_comparison_data(
        aligned_arr, anchor_i, dates_iso, sym, benchmark_display_name
    )

    return {
        "metric": metric,
        "series": [portfolio_series, bench_series],
        "warnings": warnings,
    }
