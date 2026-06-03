from datetime import date
from decimal import Decimal

from finance.performance_stats import (
    average_return,
    best_return,
    cagr,
    cagr_from_total_return,
    contributions_and_withdrawals_through,
    cumulative_return,
    economic_cumulative_return_fraction,
    period_summary,
    win_rate,
    worst_return,
)

_TOL = Decimal("0.0001")


def _assert_frac(actual: Decimal | None, expected: Decimal) -> None:
    assert actual is not None
    assert abs(actual - expected) < _TOL


# --- A. cumulative_return ---


def test_cumulative_return_compounds_two_periods():
    _assert_frac(
        cumulative_return([Decimal("0.10"), Decimal("0.20")]),
        Decimal("0.32"),
    )


def test_cumulative_return_empty_returns_none():
    assert cumulative_return([]) is None
    assert cumulative_return([None, None]) is None


# --- B. CAGR ---


def test_cagr_one_year_hundred_percent_cumulative():
    """100% cumulative return over 365 calendar days ≈ 100% CAGR."""
    start = date(2025, 1, 1)
    end = date(2026, 1, 1)
    _assert_frac(cagr([Decimal("1")], start, end), Decimal("1"))


def test_cagr_zero_days_returns_none():
    d = date(2026, 1, 1)
    assert cagr([Decimal("0.10")], d, d) is None


def test_cagr_invalid_date_order_returns_none():
    assert cagr(
        [Decimal("0.10")],
        date(2026, 1, 2),
        date(2026, 1, 1),
    ) is None


def test_economic_cumulative_return_fraction():
    _assert_frac(
        economic_cumulative_return_fraction(
            terminal_value=Decimal("2400"),
            contributions=Decimal("2200"),
            withdrawals=Decimal("0"),
        ),
        Decimal("200") / Decimal("2200"),
    )


def test_economic_cumulative_return_none_without_contributions():
    assert (
        economic_cumulative_return_fraction(
            terminal_value=Decimal("100"),
            contributions=Decimal("0"),
            withdrawals=Decimal("0"),
        )
        is None
    )


def test_cagr_from_total_return_one_year_doubles():
    start = date(2025, 1, 1)
    end = date(2026, 1, 1)
    _assert_frac(cagr_from_total_return(Decimal("1"), start, end), Decimal("1"))


def test_contributions_and_withdrawals_through():
    flows = {
        date(2026, 1, 1): Decimal("1000"),
        date(2026, 1, 15): Decimal("-200"),
        date(2026, 2, 1): Decimal("500"),
    }
    contrib, withdraw = contributions_and_withdrawals_through(flows, date(2026, 1, 20))
    assert contrib == Decimal("1000")
    assert withdraw == Decimal("200")


# --- C. best / worst / win_rate ---


def test_best_worst_win_rate_mixed_returns():
    returns = [Decimal("0.10"), Decimal("-0.05"), Decimal("0"), Decimal("0.02")]
    _assert_frac(best_return(returns), Decimal("0.10"))
    _assert_frac(worst_return(returns), Decimal("-0.05"))
    _assert_frac(win_rate(returns), Decimal("0.5"))


def test_period_summary_mixed_returns():
    summary = period_summary(
        [Decimal("0.10"), Decimal("-0.05"), Decimal("0"), Decimal("0.02")]
    )
    assert summary.count == 4
    assert summary.wins == 2
    assert summary.losses == 1
    assert summary.flats == 1
    _assert_frac(summary.win_rate, Decimal("0.5"))
    _assert_frac(summary.average, Decimal("0.0175"))


def test_average_return_none_when_empty():
    assert average_return([]) is None
