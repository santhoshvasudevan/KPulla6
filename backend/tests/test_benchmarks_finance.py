from datetime import date

import numpy as np
import pandas as pd
import pytest

from finance.benchmarks import (
    PerformancePoint,
    align_single_benchmark_to_portfolio_calendar,
    build_benchmark_comparison_data,
    rebase_portfolio_for_comparison,
)


def test_align_benchmark_starts_next_trading_day():
    portfolio_dates = [date(2026, 1, 3), date(2026, 1, 4), date(2026, 1, 5)]
    port_vals = [None, None, 1.0]
    s = pd.Series(
        [100.0, 105.0],
        index=pd.DatetimeIndex([pd.Timestamp("2026-01-05"), pd.Timestamp("2026-01-06")]),
    )
    arr, anchor_i, w = align_single_benchmark_to_portfolio_calendar(
        portfolio_dates, port_vals, s, port_start_i=2
    )
    assert not w
    assert anchor_i == 2
    assert np.isnan(arr[0])


def test_build_benchmark_comparison_data():
    arr = np.array([float("nan"), 100.0, 110.0])
    out = build_benchmark_comparison_data(
        arr, 1, ["2026-01-01", "2026-01-02", "2026-01-03"], "^X", "X"
    )
    vals = [p["value"] for p in out["data"]]
    assert vals[0] is None
    assert abs(vals[1] - 0.0) < 1e-9
    assert abs(vals[2] - 10.0) < 1e-9


def test_rebase_cumulative_return():
    pts = [
        PerformancePoint(date="2026-01-01", value=5.0, metric="cumulative_return"),
        PerformancePoint(date="2026-01-02", value=15.0, metric="cumulative_return"),
    ]
    out = rebase_portfolio_for_comparison(pts, "cumulative_return", 0)
    assert out[0] == 0.0
    assert abs(out[1] - 10.0) < 1e-9
