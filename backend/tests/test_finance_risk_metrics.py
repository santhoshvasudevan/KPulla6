from decimal import Decimal

from finance.risk_metrics import (
    annualized_volatility,
    downside_deviation,
    sharpe_ratio,
    sortino_ratio,
)

_TOL = Decimal("0.0001")


def _assert_frac(actual: Decimal | None, expected: Decimal) -> None:
    assert actual is not None
    assert abs(actual - expected) < _TOL


# --- D. annualized_volatility ---


def test_annualized_volatility_constant_returns_zero():
    returns = [Decimal("0.01"), Decimal("0.01"), Decimal("0.01")]
    vol = annualized_volatility(returns)
    assert vol is not None
    assert vol == Decimal("0")


def test_annualized_volatility_insufficient_data_returns_none():
    assert annualized_volatility([Decimal("0.01")]) is None


def test_annualized_volatility_hand_computed():
    returns = [Decimal("0.10"), Decimal("-0.05"), Decimal("0.02")]
    mean = sum(returns, Decimal("0")) / Decimal(3)
    variance = sum((r - mean) ** 2 for r in returns) / Decimal(2)
    daily_std = variance.sqrt()
    expected = daily_std * Decimal(252).sqrt()
    vol = annualized_volatility(returns)
    assert vol is not None
    assert abs(vol - expected) < _TOL


# --- E. Sharpe ---


def test_sharpe_positive_with_volatility():
    returns = [Decimal("0.01"), Decimal("0.02"), Decimal("-0.005"), Decimal("0.015")]
    sharpe = sharpe_ratio(returns)
    assert sharpe is not None
    assert sharpe > Decimal("0")


def test_sharpe_zero_volatility_returns_none():
    returns = [Decimal("0.01"), Decimal("0.01")]
    assert sharpe_ratio(returns) is None


def test_sharpe_all_none_returns_none():
    assert sharpe_ratio([None, None]) is None


# --- F. Sortino ---


def test_sortino_with_downside_observations():
    returns = [Decimal("0.05"), Decimal("-0.02"), Decimal("0.03"), Decimal("-0.01")]
    sortino = sortino_ratio(returns)
    assert sortino is not None
    assert sortino > Decimal("0")


def test_sortino_no_downside_returns_none():
    returns = [Decimal("0.01"), Decimal("0.02"), Decimal("0.03")]
    assert sortino_ratio(returns) is None
