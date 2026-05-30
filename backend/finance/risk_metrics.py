"""
Risk metrics from daily fractional returns (Metric Sheet).

Conventions
-----------
* Input daily returns: ``Decimal`` fractions; ``None`` ignored.
* Output ratios and volatilities are **annualized fractions** (``0.14`` = 14% vol).
* ``periods_per_year`` defaults to **252** trading days.
* ``risk_free_rate`` is an **annual fraction** (``0.04`` = 4%/year); converted to a daily
  rate as ``risk_free_rate / periods_per_year`` for excess-return calculations.
* **Sharpe / Sortino (MVP):** annualized arithmetic mean excess return
  ``mean(r - rf_daily) * periods_per_year`` divided by annualized volatility or
  downside deviation (not CAGR-based).
* Sample standard deviation (``n - 1`` denominator) is used when ``n >= 2``; float ``sqrt``
  is used for annualization, then converted to ``Decimal``.
"""

from __future__ import annotations

import math
from decimal import Decimal
from typing import Iterable, Optional

from finance._return_inputs import ReturnInput, valid_fractions

_ZERO = Decimal("0")
_DEFAULT_PERIODS = 252


def _sample_stdev(values: list[Decimal]) -> Optional[Decimal]:
    n = len(values)
    if n < 2:
        return None
    mean = sum(values, _ZERO) / Decimal(n)
    variance = sum((v - mean) ** 2 for v in values) / Decimal(n - 1)
    if variance <= _ZERO:
        return _ZERO
    return Decimal(str(math.sqrt(float(variance))))


def _annualize_daily_stdev(daily_stdev: Decimal, periods_per_year: int) -> Decimal:
    return daily_stdev * Decimal(str(math.sqrt(float(periods_per_year))))


def annualized_volatility(
    daily_returns: Iterable[ReturnInput],
    periods_per_year: int = _DEFAULT_PERIODS,
) -> Optional[Decimal]:
    """
    Sample std dev of daily returns × ``sqrt(periods_per_year)``.

    Returns ``Decimal('0')`` when all valid returns are identical (``n >= 2``).
    Returns ``None`` when fewer than two valid returns.
    """
    vals = valid_fractions(daily_returns)
    daily_std = _sample_stdev(vals)
    if daily_std is None:
        return None
    return _annualize_daily_stdev(daily_std, periods_per_year)


def downside_deviation(
    daily_returns: Iterable[ReturnInput],
    target_return: Decimal = _ZERO,
    periods_per_year: int = _DEFAULT_PERIODS,
) -> Optional[Decimal]:
    """
    Sample std dev of returns strictly below ``target_return``, annualized.

    Returns ``None`` when fewer than two downside observations exist.
    """
    vals = valid_fractions(daily_returns)
    downside = [r for r in vals if r < target_return]
    daily_std = _sample_stdev(downside)
    if daily_std is None:
        return None
    return _annualize_daily_stdev(daily_std, periods_per_year)


def _annualized_mean_excess(
    daily_returns: Iterable[ReturnInput],
    risk_free_rate: Decimal,
    periods_per_year: int,
) -> Optional[Decimal]:
    vals = valid_fractions(daily_returns)
    if not vals:
        return None
    rf_daily = risk_free_rate / Decimal(periods_per_year)
    mean = sum((r - rf_daily for r in vals), _ZERO) / Decimal(len(vals))
    return mean * Decimal(periods_per_year)


def sharpe_ratio(
    daily_returns: Iterable[ReturnInput],
    risk_free_rate: Decimal = _ZERO,
    periods_per_year: int = _DEFAULT_PERIODS,
) -> Optional[Decimal]:
    """
    Annualized mean excess return / annualized volatility.

    Returns ``None`` when volatility is ``None``, zero, or there are no valid returns.
    """
    vol = annualized_volatility(daily_returns, periods_per_year)
    if vol is None or vol == _ZERO:
        return None
    excess = _annualized_mean_excess(daily_returns, risk_free_rate, periods_per_year)
    if excess is None:
        return None
    return excess / vol


def sortino_ratio(
    daily_returns: Iterable[ReturnInput],
    risk_free_rate: Decimal = _ZERO,
    periods_per_year: int = _DEFAULT_PERIODS,
) -> Optional[Decimal]:
    """
    Annualized mean excess return / annualized downside deviation.

    Returns ``None`` when downside deviation is ``None`` or zero.
    """
    ddev = downside_deviation(daily_returns, _ZERO, periods_per_year)
    if ddev is None or ddev == _ZERO:
        return None
    excess = _annualized_mean_excess(daily_returns, risk_free_rate, periods_per_year)
    if excess is None:
        return None
    return excess / ddev
