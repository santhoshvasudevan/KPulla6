"""Pure fixed-deposit valuation helpers (no Django imports)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Protocol

_ZERO = Decimal("0")
_DAYS_PER_YEAR = Decimal("365")
_CURRENCY_QUANT = Decimal("0.0001")

ANNUAL_COMPOUND_ACTUAL_365 = "ANNUAL_COMPOUND_ACTUAL_365"
SIMPLE_INTEREST_ACTUAL_365 = "SIMPLE_INTEREST_ACTUAL_365"
UNSUPPORTED = "UNSUPPORTED"

MATURITY_ESTIMATE_METHOD_LABELS = {
    ANNUAL_COMPOUND_ACTUAL_365: "Annual compounding, Actual/365",
    SIMPLE_INTEREST_ACTUAL_365: "Simple interest, Actual/365",
    UNSUPPORTED: "Unsupported",
}


class FixedDepositLike(Protocol):
    principal_amount: Decimal
    status: str
    is_active: bool
    interest_rate_percent: Decimal
    interest_payout_frequency: str
    investment_date: date
    maturity_date: date


VALUE_CONTRIBUTING_STATUSES = frozenset({"ACTIVE", "MATURED"})


@dataclass(frozen=True)
class MaturityEstimateResult:
    value: Decimal | None
    method: str
    interest: Decimal | None


def contributes_to_portfolio_value(fd: FixedDepositLike) -> bool:
    """Return True when principal should count toward portfolio value."""
    if not fd.is_active:
        return False
    if fd.status in {"CLOSED", "MATURED_SETTLED", "CANCELLED"}:
        return False
    return fd.status in VALUE_CONTRIBUTING_STATUSES


def fixed_deposit_principal_value(
    fd: FixedDepositLike,
    as_of_date: date | None = None,
) -> Decimal:
    """
    Principal-only portfolio value for a fixed deposit.

    MVP: no interest accrual. ACTIVE and MATURED (while is_active) contribute
    principal; CLOSED or inactive contribute zero.
    """
    _ = as_of_date  # reserved for future date-aware rules
    if not contributes_to_portfolio_value(fd):
        return _ZERO
    return Decimal(fd.principal_amount)


def _days_between(start: date, end: date) -> int:
    return (end - start).days


def _fractional_years_actual_365(start: date, end: date) -> Decimal:
    days = _days_between(start, end)
    if days <= 0:
        return _ZERO
    return Decimal(days) / _DAYS_PER_YEAR


def _decimal_pow(base: Decimal, exponent: Decimal) -> Decimal:
    if exponent == 0:
        return Decimal("1")
    if base <= 0:
        return _ZERO
    result = math.exp(float(exponent) * math.log(float(base)))
    return Decimal(str(result))


def _quantize_currency(value: Decimal) -> Decimal:
    return value.quantize(_CURRENCY_QUANT, rounding=ROUND_HALF_UP)


def maturity_estimate_method_label(method: str | None) -> str | None:
    if not method:
        return None
    return MATURITY_ESTIMATE_METHOD_LABELS.get(method)


def estimate_maturity_value(fd: FixedDepositLike) -> MaturityEstimateResult:
    """
    App-calculated maturity estimate (approximation; bank settlement may differ).

    COMPOUNDED: annual compounding with Actual/365 fractional years.
    Other payout modes: simple interest over full term with Actual/365 years.
    """
    principal = Decimal(fd.principal_amount)
    if principal <= 0:
        return MaturityEstimateResult(value=None, method=UNSUPPORTED, interest=None)

    inv = fd.investment_date
    mat = fd.maturity_date
    if not inv or not mat or mat <= inv:
        return MaturityEstimateResult(value=None, method=UNSUPPORTED, interest=None)

    rate = Decimal(fd.interest_rate_percent) / Decimal("100")
    years = _fractional_years_actual_365(inv, mat)
    if years <= 0:
        return MaturityEstimateResult(
            value=_quantize_currency(principal),
            method=UNSUPPORTED,
            interest=_ZERO,
        )

    if rate <= 0:
        return MaturityEstimateResult(
            value=_quantize_currency(principal),
            method=(
                ANNUAL_COMPOUND_ACTUAL_365
                if fd.interest_payout_frequency == "COMPOUNDED"
                else SIMPLE_INTEREST_ACTUAL_365
            ),
            interest=_ZERO,
        )

    if fd.interest_payout_frequency == "COMPOUNDED":
        factor = _decimal_pow(Decimal("1") + rate, years)
        value = _quantize_currency(principal * factor)
        return MaturityEstimateResult(
            value=value,
            method=ANNUAL_COMPOUND_ACTUAL_365,
            interest=_quantize_currency(value - principal),
        )

    value = _quantize_currency(principal * (Decimal("1") + rate * years))
    return MaturityEstimateResult(
        value=value,
        method=SIMPLE_INTEREST_ACTUAL_365,
        interest=_quantize_currency(value - principal),
    )


def expected_maturity_value(fd: FixedDepositLike) -> Decimal:
    """Backward-compatible estimate helper returning principal when unavailable."""
    result = estimate_maturity_value(fd)
    if result.value is None:
        return Decimal(fd.principal_amount)
    return result.value


def maturity_interest_from_value(
    principal: Decimal, maturity_value: Decimal | None
) -> Decimal | None:
    if maturity_value is None:
        return None
    return _quantize_currency(Decimal(maturity_value) - Decimal(principal))
