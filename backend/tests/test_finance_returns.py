from datetime import date
from decimal import Decimal

from finance.returns import (
    DailyReturnPoint,
    ValuePoint,
    chain_returns,
    compound_return,
    daily_returns_from_twror_series,
    daily_returns_from_values,
    period_return,
    resample_monthly_returns,
    resample_yearly_returns,
)
from finance.twror import TwrorPoint

_TOL = Decimal("0.0001")


def _assert_frac(actual: Decimal | None, expected: Decimal) -> None:
    assert actual is not None
    assert abs(actual - expected) < _TOL


# --- A. period_return ---


def test_period_return_pure_market_gain():
    _assert_frac(period_return(Decimal("100"), Decimal("110")), Decimal("0.10"))


def test_period_return_contribution_no_market_gain():
    _assert_frac(
        period_return(Decimal("100"), Decimal("200"), Decimal("100")),
        Decimal("0"),
    )


def test_period_return_withdrawal_no_market_gain():
    _assert_frac(
        period_return(Decimal("200"), Decimal("100"), Decimal("-100")),
        Decimal("0"),
    )


def test_period_return_zero_previous_returns_none():
    assert period_return(Decimal("0"), Decimal("100")) is None


# --- B. daily_returns_from_values ---


def test_daily_returns_from_values_three_day_mixed_flow():
    points = daily_returns_from_values(
        [
            ValuePoint(date(2026, 1, 1), Decimal("100")),
            ValuePoint(date(2026, 1, 2), Decimal("110")),
            ValuePoint(date(2026, 1, 3), Decimal("220")),
        ],
        flows_by_date={date(2026, 1, 3): Decimal("100")},
    )
    assert points[0].return_fraction is None
    _assert_frac(points[1].return_fraction, Decimal("0.10"))
    _assert_frac(points[2].return_fraction, Decimal("10") / Decimal("110"))


def test_daily_returns_from_values_first_day_none():
    points = daily_returns_from_values(
        [ValuePoint(date(2026, 1, 1), Decimal("100"))],
    )
    assert len(points) == 1
    assert points[0].return_fraction is None


# --- C. daily_returns_from_twror_series ---


def test_daily_returns_from_twror_series_cumulative_percent():
    twror = [
        TwrorPoint(date(2026, 1, 1), None),
        TwrorPoint(date(2026, 1, 2), Decimal("10")),
        TwrorPoint(date(2026, 1, 3), Decimal("20")),
    ]
    daily = daily_returns_from_twror_series(twror)
    assert daily[0].return_fraction is None
    _assert_frac(daily[1].return_fraction, Decimal("0.10"))
    _assert_frac(daily[2].return_fraction, Decimal("10") / Decimal("110"))


# --- D. compound_return ---


def test_compound_return_two_periods_to_twenty_percent():
    r1 = Decimal("0.10")
    r2 = Decimal("10") / Decimal("110")
    _assert_frac(compound_return([r1, r2]), Decimal("0.20"))


def test_chain_returns_matches_compound_return():
    returns = [Decimal("0.10"), Decimal("10") / Decimal("110")]
    assert chain_returns(returns) == compound_return(returns)


# --- E. monthly returns ---


def test_resample_monthly_returns_compounds_within_month():
    daily = [
        DailyReturnPoint(date(2026, 1, 10), Decimal("0.10")),
        DailyReturnPoint(date(2026, 1, 20), Decimal("0.05")),
    ]
    monthly = resample_monthly_returns(daily)
    assert len(monthly) == 1
    assert monthly[0].period == "2026-01"
    expected = (Decimal("1.10") * Decimal("1.05")) - Decimal("1")
    _assert_frac(monthly[0].return_fraction, expected)


def test_resample_monthly_returns_separate_months():
    daily = [
        DailyReturnPoint(date(2026, 1, 15), Decimal("0.10")),
        DailyReturnPoint(date(2026, 2, 15), Decimal("0.05")),
    ]
    monthly = resample_monthly_returns(daily)
    periods = {m.period: m.return_fraction for m in monthly}
    assert set(periods) == {"2026-01", "2026-02"}
    _assert_frac(periods["2026-01"], Decimal("0.10"))
    _assert_frac(periods["2026-02"], Decimal("0.05"))


# --- F. yearly returns ---


def test_resample_yearly_returns_separate_years():
    daily = [
        DailyReturnPoint(date(2025, 12, 31), Decimal("0.10")),
        DailyReturnPoint(date(2026, 1, 1), Decimal("0.05")),
    ]
    yearly = resample_yearly_returns(daily)
    periods = {y.period: y.return_fraction for y in yearly}
    assert set(periods) == {"2025", "2026"}
    _assert_frac(periods["2025"], Decimal("0.10"))
    _assert_frac(periods["2026"], Decimal("0.05"))


def test_resample_yearly_returns_cashflow_adjusted_not_simple_value_change():
    """Calendar-year return compounds TWROR daily returns; ignores raw value delta."""
    daily = daily_returns_from_values(
        [
            ValuePoint(date(2025, 1, 1), Decimal("100")),
            ValuePoint(date(2025, 6, 1), Decimal("110")),
            ValuePoint(date(2025, 6, 2), Decimal("210")),
            ValuePoint(date(2025, 12, 31), Decimal("220")),
        ],
        flows_by_date={date(2025, 6, 2): Decimal("100")},
    )
    yearly = resample_yearly_returns(daily)
    assert len(yearly) == 1
    assert yearly[0].period == "2025"
    simple_value_return = (Decimal("220") - Decimal("100")) / Decimal("100")
    daily_fracs = [p.return_fraction for p in daily if p.return_fraction is not None]
    expected = compound_return(daily_fracs)
    _assert_frac(yearly[0].return_fraction, expected)
    assert yearly[0].return_fraction != simple_value_return


# --- G. None handling ---


def test_compound_return_skips_none():
    _assert_frac(
        compound_return([Decimal("0.10"), None, Decimal("0.05")]),
        (Decimal("1.10") * Decimal("1.05")) - Decimal("1"),
    )


def test_compound_return_all_none_returns_none():
    assert compound_return([None, None]) is None


def test_compound_return_empty_returns_none():
    assert compound_return([]) is None


def test_daily_returns_none_value_clears_baseline():
    """Missing PV sets baseline to None; next day cannot compute (TWROR parity)."""
    points = daily_returns_from_values(
        [
            ValuePoint(date(2026, 1, 1), Decimal("100")),
            ValuePoint(date(2026, 1, 2), None),
            ValuePoint(date(2026, 1, 3), Decimal("110")),
        ],
    )
    assert points[1].return_fraction is None
    assert points[2].return_fraction is None


def test_resample_monthly_ignores_none_daily_returns():
    daily = [
        DailyReturnPoint(date(2026, 1, 5), None),
        DailyReturnPoint(date(2026, 1, 10), Decimal("0.10")),
    ]
    monthly = resample_monthly_returns(daily)
    assert len(monthly) == 1
    _assert_frac(monthly[0].return_fraction, Decimal("0.10"))


def test_resample_monthly_omits_month_with_only_none():
    daily = [DailyReturnPoint(date(2026, 2, 1), None)]
    assert resample_monthly_returns(daily) == []
