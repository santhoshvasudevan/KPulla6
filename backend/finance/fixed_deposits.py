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
SIMPLE_INTEREST_ACTUAL_365 = "SIMPLE_INTEREST_ACTUAL_365"  # legacy alias
SIMPLE_PAYOUT_ACTUAL_365 = "SIMPLE_PAYOUT_ACTUAL_365"
UNSUPPORTED = "UNSUPPORTED"

COMPOUNDED_MATURITY = "COMPOUNDED_MATURITY"
PAYOUT_INTEREST = "PAYOUT_INTEREST"
UNSUPPORTED_ESTIMATE = "UNSUPPORTED"

PAYOUT_FREQUENCIES = frozenset({"MONTHLY", "QUARTERLY", "HALF_YEARLY", "ANNUALLY"})

PAYOUT_PERIODS_PER_YEAR = {
    "MONTHLY": 12,
    "QUARTERLY": 4,
    "HALF_YEARLY": 2,
    "ANNUALLY": 1,
}

MATURITY_ESTIMATE_METHOD_LABELS = {
    ANNUAL_COMPOUND_ACTUAL_365: "Compounded interest, Actual/365",
    SIMPLE_INTEREST_ACTUAL_365: "Simple interest payout, Actual/365",
    SIMPLE_PAYOUT_ACTUAL_365: "Simple interest payout, Actual/365",
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
    """Backward-compatible maturity estimate result."""

    value: Decimal | None
    method: str
    interest: Decimal | None


@dataclass(frozen=True)
class FdInterestEstimateResult:
    estimate_type: str
    maturity_value: Decimal | None
    total_interest: Decimal | None
    periodic_interest: Decimal | None
    method: str
    message: str | None = None

    @property
    def value(self) -> Decimal | None:
        return self.maturity_value

    @property
    def interest(self) -> Decimal | None:
        return self.total_interest


def is_compounded_fd(fd: FixedDepositLike) -> bool:
    return fd.interest_payout_frequency == "COMPOUNDED"


def is_payout_fd(fd: FixedDepositLike) -> bool:
    return fd.interest_payout_frequency in PAYOUT_FREQUENCIES


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


def _unsupported_estimate() -> FdInterestEstimateResult:
    return FdInterestEstimateResult(
        estimate_type=UNSUPPORTED_ESTIMATE,
        maturity_value=None,
        total_interest=None,
        periodic_interest=None,
        method=UNSUPPORTED,
        message=None,
    )


def estimate_fd_interest(fd: FixedDepositLike) -> FdInterestEstimateResult:
    """
    FD interest/maturity estimate by payout mode.

    COMPOUNDED: maturity value = principal + compounded interest.
    Payout modes: maturity value = principal; interest paid out separately.
    """
    principal = Decimal(fd.principal_amount)
    if principal <= 0:
        return _unsupported_estimate()

    inv = fd.investment_date
    mat = fd.maturity_date
    if not inv or not mat or mat <= inv:
        return _unsupported_estimate()

    rate = Decimal(fd.interest_rate_percent) / Decimal("100")
    years = _fractional_years_actual_365(inv, mat)
    if years <= 0:
        return FdInterestEstimateResult(
            estimate_type=(
                COMPOUNDED_MATURITY
                if is_compounded_fd(fd)
                else PAYOUT_INTEREST if is_payout_fd(fd) else UNSUPPORTED_ESTIMATE
            ),
            maturity_value=_quantize_currency(principal),
            total_interest=_ZERO,
            periodic_interest=_ZERO,
            method=UNSUPPORTED,
            message=None,
        )

    if is_compounded_fd(fd):
        if rate <= 0:
            return FdInterestEstimateResult(
                estimate_type=COMPOUNDED_MATURITY,
                maturity_value=_quantize_currency(principal),
                total_interest=_ZERO,
                periodic_interest=None,
                method=ANNUAL_COMPOUND_ACTUAL_365,
                message=None,
            )
        factor = _decimal_pow(Decimal("1") + rate, years)
        maturity_value = _quantize_currency(principal * factor)
        total_interest = _quantize_currency(maturity_value - principal)
        return FdInterestEstimateResult(
            estimate_type=COMPOUNDED_MATURITY,
            maturity_value=maturity_value,
            total_interest=total_interest,
            periodic_interest=None,
            method=ANNUAL_COMPOUND_ACTUAL_365,
            message=None,
        )

    if is_payout_fd(fd):
        periods_per_year = PAYOUT_PERIODS_PER_YEAR[fd.interest_payout_frequency]
        if rate <= 0:
            return FdInterestEstimateResult(
                estimate_type=PAYOUT_INTEREST,
                maturity_value=_quantize_currency(principal),
                total_interest=_ZERO,
                periodic_interest=_ZERO,
                method=SIMPLE_PAYOUT_ACTUAL_365,
                message=(
                    "Maturity value is principal returned at maturity. "
                    "Interest is paid out separately on the selected schedule."
                ),
            )
        total_interest = _quantize_currency(principal * rate * years)
        annual_interest = principal * rate
        periodic_interest = _quantize_currency(annual_interest / Decimal(periods_per_year))
        return FdInterestEstimateResult(
            estimate_type=PAYOUT_INTEREST,
            maturity_value=_quantize_currency(principal),
            total_interest=total_interest,
            periodic_interest=periodic_interest,
            method=SIMPLE_PAYOUT_ACTUAL_365,
            message=(
                "Maturity value is principal returned at maturity. "
                "Periodic interest is indicative; actual payout dates, rounding, "
                "and the final period may differ."
            ),
        )

    return _unsupported_estimate()


def estimate_maturity_value(fd: FixedDepositLike) -> MaturityEstimateResult:
    """Backward-compatible wrapper around estimate_fd_interest."""
    result = estimate_fd_interest(fd)
    return MaturityEstimateResult(
        value=result.maturity_value,
        method=result.method,
        interest=result.total_interest,
    )


def expected_maturity_value(fd: FixedDepositLike) -> Decimal:
    """Backward-compatible estimate helper returning principal when unavailable."""
    result = estimate_fd_interest(fd)
    if result.maturity_value is None:
        return Decimal(fd.principal_amount)
    return result.maturity_value


def maturity_interest_from_value(
    principal: Decimal, maturity_value: Decimal | None
) -> Decimal | None:
    if maturity_value is None:
        return None
    return _quantize_currency(Decimal(maturity_value) - Decimal(principal))
