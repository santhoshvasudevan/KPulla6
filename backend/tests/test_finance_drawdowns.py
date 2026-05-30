from datetime import date
from decimal import Decimal

from finance.drawdowns import (
    calmar_ratio,
    drawdown_series,
    longest_drawdown_days,
    max_drawdown,
    worst_drawdown_periods,
)
from finance.returns import DailyReturnPoint, ValuePoint, daily_returns_from_values
from finance.performance_stats import cumulative_return

_TOL = Decimal("0.0001")

_DRAWDOWN_EXAMPLE = [
    Decimal("0.10"),
    Decimal("-0.10"),
    Decimal("-0.10"),
    Decimal("0.30"),
]


def _assert_frac(actual: Decimal | None, expected: Decimal) -> None:
    assert actual is not None
    assert abs(actual - expected) < _TOL


# --- G. drawdown_series ---


def test_drawdown_series_example_path():
    series = drawdown_series(_DRAWDOWN_EXAMPLE)
    dds = [p.drawdown_fraction for p in series]
    assert len(dds) == 4
    _assert_frac(dds[0], Decimal("0"))
    # wealth 0.99 / peak 1.1 → ratio 0.9 in Decimal, drawdown -10%
    _assert_frac(dds[1], Decimal("-0.10"))
    _assert_frac(dds[2], Decimal("-0.19"))
    _assert_frac(dds[3], Decimal("0"))


# --- H. max_drawdown ---


def test_max_drawdown_example():
    _assert_frac(max_drawdown(_DRAWDOWN_EXAMPLE), Decimal("-0.19"))


# --- I. longest_drawdown_days ---


def test_longest_drawdown_days_calendar_span_inclusive():
    """Two calendar days below peak before recovery: Jan 2–3 inclusive."""
    daily = [
        DailyReturnPoint(date(2026, 1, 1), Decimal("0.10")),
        DailyReturnPoint(date(2026, 1, 2), Decimal("-0.10")),
        DailyReturnPoint(date(2026, 1, 3), Decimal("-0.10")),
        DailyReturnPoint(date(2026, 1, 4), Decimal("0.30")),
    ]
    assert longest_drawdown_days(daily) == 2


def test_longest_drawdown_days_period_count_without_dates():
    """Undated returns: two consecutive periods below peak."""
    returns = [Decimal("0.10"), Decimal("-0.05"), Decimal("-0.03"), Decimal("0.20")]
    assert longest_drawdown_days(returns) == 2


def test_longest_drawdown_no_drawdown_returns_none():
    assert longest_drawdown_days([Decimal("0.10"), Decimal("0.05")]) is None


# --- J. calmar_ratio ---


def test_calmar_ratio_positive():
    returns = [Decimal("0.10"), Decimal("-0.10"), Decimal("-0.10"), Decimal("0.30")]
    start = date(2025, 1, 1)
    end = date(2026, 1, 1)
    calmar = calmar_ratio(returns, start, end)
    assert calmar is not None
    assert calmar > Decimal("0")


def test_calmar_ratio_zero_drawdown_returns_none():
    assert calmar_ratio(
        [Decimal("0.10")],
        date(2025, 1, 1),
        date(2026, 1, 1),
    ) is None


# --- K. integration with Phase 2 ---


# --- L. worst_drawdown_periods ---


def test_worst_drawdown_periods_detects_recovery():
    daily = [
        DailyReturnPoint(date(2026, 1, 1), Decimal("0.10")),
        DailyReturnPoint(date(2026, 1, 2), Decimal("-0.10")),
        DailyReturnPoint(date(2026, 1, 3), Decimal("-0.10")),
        DailyReturnPoint(date(2026, 1, 4), Decimal("0.30")),
    ]
    episodes = worst_drawdown_periods(daily, limit=10)
    assert len(episodes) == 1
    ep = episodes[0]
    assert ep.start_date == date(2026, 1, 1)
    assert ep.trough_date == date(2026, 1, 3)
    assert ep.recovery_date == date(2026, 1, 4)
    assert ep.recovered is True
    _assert_frac(ep.drawdown_fraction, Decimal("-0.19"))
    assert ep.days_to_trough == (date(2026, 1, 3) - date(2026, 1, 1)).days
    assert ep.days_to_recovery == (date(2026, 1, 4) - date(2026, 1, 1)).days


def test_worst_drawdown_periods_unrecovered_at_end():
    daily = [
        DailyReturnPoint(date(2026, 1, 1), Decimal("0.10")),
        DailyReturnPoint(date(2026, 1, 2), Decimal("-0.05")),
        DailyReturnPoint(date(2026, 1, 3), Decimal("-0.05")),
    ]
    episodes = worst_drawdown_periods(daily, limit=10)
    assert len(episodes) == 1
    ep = episodes[0]
    assert ep.recovered is False
    assert ep.recovery_date is None
    assert ep.days_to_recovery is None


def test_worst_drawdown_periods_requires_dated_returns():
    assert worst_drawdown_periods(_DRAWDOWN_EXAMPLE) == []
    assert worst_drawdown_periods([]) == []


def test_worst_drawdown_periods_sorts_most_severe_first():
    daily = [
        DailyReturnPoint(date(2026, 1, 1), Decimal("0.20")),
        DailyReturnPoint(date(2026, 1, 2), Decimal("-0.05")),
        DailyReturnPoint(date(2026, 1, 3), Decimal("0.15")),
        DailyReturnPoint(date(2026, 1, 4), Decimal("-0.15")),
        DailyReturnPoint(date(2026, 1, 5), Decimal("0.20")),
    ]
    episodes = worst_drawdown_periods(daily, limit=10)
    assert len(episodes) >= 2
    assert episodes[0].drawdown_fraction <= episodes[1].drawdown_fraction


def test_integration_daily_returns_from_values_matches_cumulative():
    daily = daily_returns_from_values(
        [
            ValuePoint(date(2026, 1, 1), Decimal("100")),
            ValuePoint(date(2026, 1, 2), Decimal("110")),
            ValuePoint(date(2026, 1, 3), Decimal("220")),
        ],
        flows_by_date={date(2026, 1, 3): Decimal("100")},
    )
    fractions = [p.return_fraction for p in daily if p.return_fraction is not None]
    _assert_frac(cumulative_return(fractions), Decimal("0.20"))
