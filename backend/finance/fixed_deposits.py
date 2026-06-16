"""Pure fixed-deposit valuation helpers (no Django imports)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Protocol


class FixedDepositLike(Protocol):
    principal_amount: Decimal
    status: str
    is_active: bool
    interest_rate_percent: Decimal
    interest_payout_frequency: str
    investment_date: date
    maturity_date: date


VALUE_CONTRIBUTING_STATUSES = frozenset({"ACTIVE", "MATURED"})


def contributes_to_portfolio_value(fd: FixedDepositLike) -> bool:
    """Return True when principal should count toward portfolio value."""
    if not fd.is_active:
        return False
    if fd.status in {"CLOSED", "MATURED_SETTLED"}:
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
        return Decimal("0")
    return Decimal(fd.principal_amount)


def _years_between(start: date, end: date) -> Decimal:
    days = (end - start).days
    if days <= 0:
        return Decimal("0")
    return Decimal(days) / Decimal("365")


def expected_maturity_value(fd: FixedDepositLike) -> Decimal:
    """
    Estimate maturity value (not used in portfolio current value in MVP).

    COMPOUNDED: annual compounding on principal.
    Other payout modes: simple interest over full term.
    """
    principal = Decimal(fd.principal_amount)
    rate = Decimal(fd.interest_rate_percent) / Decimal("100")
    years = _years_between(fd.investment_date, fd.maturity_date)
    if years <= 0 or rate <= 0:
        return principal

    if fd.interest_payout_frequency == "COMPOUNDED":
        # (1 + r)^t - 1 on principal, return principal + interest
        one_plus_r = Decimal("1") + rate
        # Use float pow for fractional years then convert back — acceptable for estimate
        factor = Decimal(str(float(one_plus_r) ** float(years)))
        return principal * factor

    # Simple interest: P * (1 + r * t)
    return principal * (Decimal("1") + rate * years)
