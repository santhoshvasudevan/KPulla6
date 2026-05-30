import pytest

from datetime import date
from decimal import Decimal

from finance.comparison import (
    align_multi_subject_returns,
    align_return_series,
    active_return,
    alpha,
    benchmark_summary,
    beta,
    correlation,
    information_ratio,
    normalized_cumulative_return_series,
    tracking_error,
    treynor_ratio,
)
from finance.returns import DailyReturnPoint

_TOL = Decimal("0.0001")


def _assert_frac(actual: Decimal | None, expected: Decimal) -> None:
    assert actual is not None
    assert abs(actual - expected) < _TOL


def _assert_approx(actual: Decimal | None, expected: float) -> None:
    assert actual is not None
    assert abs(float(actual) - expected) < float(_TOL)


# --- A. Alignment ---


def test_align_return_series_intersection_skips_none():
    subject = [
        DailyReturnPoint(date(2026, 1, 1), Decimal("0.01")),
        DailyReturnPoint(date(2026, 1, 2), None),
        DailyReturnPoint(date(2026, 1, 3), Decimal("0.03")),
    ]
    benchmark = [
        DailyReturnPoint(date(2026, 1, 2), Decimal("0.02")),
        DailyReturnPoint(date(2026, 1, 3), Decimal("0.04")),
        DailyReturnPoint(date(2026, 1, 4), Decimal("0.05")),
    ]
    aligned = align_return_series(subject, benchmark)
    assert len(aligned) == 1
    assert aligned[0].date == date(2026, 1, 3)
    assert aligned[0].subject_return == Decimal("0.03")
    assert aligned[0].benchmark_return == Decimal("0.04")


def test_align_return_series_jan_2_and_3_only():
    subject = [
        DailyReturnPoint(date(2026, 1, 1), Decimal("0.01")),
        DailyReturnPoint(date(2026, 1, 2), Decimal("0.02")),
        DailyReturnPoint(date(2026, 1, 3), Decimal("0.03")),
    ]
    benchmark = [
        DailyReturnPoint(date(2026, 1, 2), Decimal("0.04")),
        DailyReturnPoint(date(2026, 1, 3), Decimal("0.05")),
        DailyReturnPoint(date(2026, 1, 4), Decimal("0.06")),
    ]
    aligned = align_return_series(subject, benchmark)
    assert [p.date for p in aligned] == [date(2026, 1, 2), date(2026, 1, 3)]


# --- B. Correlation ---


def test_correlation_perfect_positive():
    subject = [
        DailyReturnPoint(date(2026, 1, 1), Decimal("0.01")),
        DailyReturnPoint(date(2026, 1, 2), Decimal("0.02")),
        DailyReturnPoint(date(2026, 1, 3), Decimal("0.03")),
    ]
    benchmark = [
        DailyReturnPoint(date(2026, 1, 1), Decimal("0.02")),
        DailyReturnPoint(date(2026, 1, 2), Decimal("0.04")),
        DailyReturnPoint(date(2026, 1, 3), Decimal("0.06")),
    ]
    _assert_approx(correlation(subject, benchmark), 1.0)


def test_correlation_perfect_negative():
    subject = [
        DailyReturnPoint(date(2026, 1, 1), Decimal("0.01")),
        DailyReturnPoint(date(2026, 1, 2), Decimal("0.02")),
    ]
    benchmark = [
        DailyReturnPoint(date(2026, 1, 1), Decimal("-0.01")),
        DailyReturnPoint(date(2026, 1, 2), Decimal("-0.02")),
    ]
    _assert_approx(correlation(subject, benchmark), -1.0)


def test_correlation_zero_variance_returns_none():
    subject = [
        DailyReturnPoint(date(2026, 1, 1), Decimal("0.01")),
        DailyReturnPoint(date(2026, 1, 2), Decimal("0.01")),
    ]
    benchmark = [
        DailyReturnPoint(date(2026, 1, 1), Decimal("0.02")),
        DailyReturnPoint(date(2026, 1, 2), Decimal("0.02")),
    ]
    assert correlation(subject, benchmark) is None


# --- C. Beta ---


def test_beta_subject_twice_benchmark():
    benchmark = [
        DailyReturnPoint(date(2026, 1, 1), Decimal("0.01")),
        DailyReturnPoint(date(2026, 1, 2), Decimal("0.02")),
        DailyReturnPoint(date(2026, 1, 3), Decimal("0.03")),
    ]
    subject = [
        DailyReturnPoint(date(2026, 1, 1), Decimal("0.02")),
        DailyReturnPoint(date(2026, 1, 2), Decimal("0.04")),
        DailyReturnPoint(date(2026, 1, 3), Decimal("0.06")),
    ]
    _assert_approx(beta(subject, benchmark), 2.0)


def test_beta_benchmark_zero_variance_returns_none():
    subject = [
        DailyReturnPoint(date(2026, 1, 1), Decimal("0.01")),
        DailyReturnPoint(date(2026, 1, 2), Decimal("0.02")),
    ]
    benchmark = [
        DailyReturnPoint(date(2026, 1, 1), Decimal("0.05")),
        DailyReturnPoint(date(2026, 1, 2), Decimal("0.05")),
    ]
    assert beta(subject, benchmark) is None


# --- D. Alpha ---


def test_alpha_identical_returns_near_zero():
    returns = [
        DailyReturnPoint(date(2026, 1, 1), Decimal("0.01")),
        DailyReturnPoint(date(2026, 1, 2), Decimal("0.02")),
        DailyReturnPoint(date(2026, 1, 3), Decimal("0.03")),
    ]
    a = alpha(returns, returns, risk_free_rate=Decimal("0"))
    assert a is not None
    assert abs(a) < _TOL


def test_alpha_positive_when_subject_outperforms():
    benchmark = [
        DailyReturnPoint(date(2026, 1, 1), Decimal("0.001")),
        DailyReturnPoint(date(2026, 1, 2), Decimal("0.002")),
        DailyReturnPoint(date(2026, 1, 3), Decimal("0.003")),
    ]
    subject = [
        DailyReturnPoint(date(2026, 1, 1), Decimal("0.005")),
        DailyReturnPoint(date(2026, 1, 2), Decimal("0.006")),
        DailyReturnPoint(date(2026, 1, 3), Decimal("0.007")),
    ]
    a = alpha(subject, benchmark)
    assert a is not None
    assert a > Decimal("0")


# --- E. Tracking error ---


def test_tracking_error_identical_returns_zero():
    returns = [
        DailyReturnPoint(date(2026, 1, 1), Decimal("0.01")),
        DailyReturnPoint(date(2026, 1, 2), Decimal("0.02")),
    ]
    te = tracking_error(returns, returns)
    assert te is not None
    assert te == Decimal("0")


def test_tracking_error_hand_computed():
    subject = [
        DailyReturnPoint(date(2026, 1, 1), Decimal("0.02")),
        DailyReturnPoint(date(2026, 1, 2), Decimal("0.04")),
    ]
    benchmark = [
        DailyReturnPoint(date(2026, 1, 1), Decimal("0.01")),
        DailyReturnPoint(date(2026, 1, 2), Decimal("0.02")),
    ]
    active = [Decimal("0.01"), Decimal("0.02")]
    mean = sum(active) / Decimal(2)
    var = sum((a - mean) ** 2 for a in active) / Decimal(1)
    daily_std = var.sqrt()
    expected = daily_std * Decimal(252).sqrt()
    te = tracking_error(subject, benchmark)
    assert te is not None
    assert abs(te - expected) < _TOL


# --- F. Active return ---


def test_active_return_constant_spread():
    spread = Decimal("0.001")
    benchmark = [
        DailyReturnPoint(date(2026, 1, 1), Decimal("0")),
        DailyReturnPoint(date(2026, 1, 2), Decimal("0")),
        DailyReturnPoint(date(2026, 1, 3), Decimal("0")),
    ]
    subject = [
        DailyReturnPoint(date(2026, 1, 1), spread),
        DailyReturnPoint(date(2026, 1, 2), spread),
        DailyReturnPoint(date(2026, 1, 3), spread),
    ]
    _assert_frac(active_return(subject, benchmark), spread * Decimal("252"))


# --- G. Information ratio ---


def test_information_ratio_zero_tracking_error_returns_none():
    returns = [
        DailyReturnPoint(date(2026, 1, 1), Decimal("0.01")),
        DailyReturnPoint(date(2026, 1, 2), Decimal("0.02")),
    ]
    assert information_ratio(returns, returns) is None


def test_information_ratio_positive_when_active_and_te_positive():
    benchmark = [
        DailyReturnPoint(date(2026, 1, 1), Decimal("0.001")),
        DailyReturnPoint(date(2026, 1, 2), Decimal("0.002")),
        DailyReturnPoint(date(2026, 1, 3), Decimal("0.003")),
    ]
    subject = [
        DailyReturnPoint(date(2026, 1, 1), Decimal("0.01")),
        DailyReturnPoint(date(2026, 1, 2), Decimal("0.02")),
        DailyReturnPoint(date(2026, 1, 3), Decimal("0.03")),
    ]
    ir = information_ratio(subject, benchmark)
    assert ir is not None
    assert ir > Decimal("0")


# --- H. Treynor ratio ---


def test_treynor_ratio_positive_excess_and_beta():
    benchmark = [
        DailyReturnPoint(date(2026, 1, 1), Decimal("0.01")),
        DailyReturnPoint(date(2026, 1, 2), Decimal("0.02")),
    ]
    subject = [
        DailyReturnPoint(date(2026, 1, 1), Decimal("0.02")),
        DailyReturnPoint(date(2026, 1, 2), Decimal("0.04")),
    ]
    tr = treynor_ratio(subject, benchmark)
    assert tr is not None
    assert tr > Decimal("0")


def test_treynor_ratio_beta_none_returns_none():
    subject = [
        DailyReturnPoint(date(2026, 1, 1), Decimal("0.01")),
        DailyReturnPoint(date(2026, 1, 2), Decimal("0.02")),
    ]
    benchmark = [
        DailyReturnPoint(date(2026, 1, 1), Decimal("0.05")),
        DailyReturnPoint(date(2026, 1, 2), Decimal("0.05")),
    ]
    assert treynor_ratio(subject, benchmark) is None


def test_benchmark_summary_returns_all_fields():
    benchmark = [
        DailyReturnPoint(date(2026, 1, 1), Decimal("0.01")),
        DailyReturnPoint(date(2026, 1, 2), Decimal("0.02")),
    ]
    subject = [
        DailyReturnPoint(date(2026, 1, 1), Decimal("0.02")),
        DailyReturnPoint(date(2026, 1, 2), Decimal("0.04")),
    ]
    summary = benchmark_summary(subject, benchmark)
    assert summary.paired_count == 2
    assert summary.correlation is not None
    assert summary.beta is not None
    assert summary.alpha is not None
    assert summary.active_return is not None
    assert summary.tracking_error is not None
    assert summary.information_ratio is not None
    assert summary.treynor_ratio is not None


def test_align_multi_subject_returns_exact_intersection():
    series = {
        "asset:A": [
            DailyReturnPoint(date(2026, 1, 1), Decimal("0.01")),
            DailyReturnPoint(date(2026, 1, 2), Decimal("0.02")),
            DailyReturnPoint(date(2026, 1, 3), Decimal("0.03")),
        ],
        "asset:B": [
            DailyReturnPoint(date(2026, 1, 2), Decimal("0.04")),
            DailyReturnPoint(date(2026, 1, 3), Decimal("0.05")),
        ],
    }
    dates, aligned = align_multi_subject_returns(series)
    assert dates == [date(2026, 1, 2), date(2026, 1, 3)]
    assert aligned["asset:A"] == [Decimal("0.02"), Decimal("0.03")]
    assert aligned["asset:B"] == [Decimal("0.04"), Decimal("0.05")]


def test_normalized_cumulative_return_series_first_point_zero():
    dates = [date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3)]
    aligned = {
        "asset:A": [Decimal("0.01"), Decimal("0.02"), Decimal("0.03")],
        "asset:B": [Decimal("0.04"), Decimal("-0.01"), Decimal("0.02")],
    }
    series = normalized_cumulative_return_series(dates, aligned)
    assert series[0]["values"]["asset:A"] == 0.0
    assert series[0]["values"]["asset:B"] == 0.0
    assert series[1]["values"]["asset:A"] == pytest.approx(0.02)
    assert series[1]["values"]["asset:B"] == pytest.approx(-0.01)
    assert series[2]["values"]["asset:A"] == pytest.approx((1 + 0.02) * (1 + 0.03) - 1)
