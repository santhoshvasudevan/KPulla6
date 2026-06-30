"""Fixed deposit expected maturity value application (ORM services)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from debt.models import FixedDeposit, MaturityValueSource
from finance.fixed_deposits import (
    COMPOUNDED_MATURITY,
    PAYOUT_INTEREST,
    estimate_fd_interest,
    is_compounded_fd,
    is_payout_fd,
    maturity_estimate_method_label,
    maturity_interest_from_value,
)


def _apply_estimate_fields(fd: FixedDeposit) -> None:
    result = estimate_fd_interest(fd)
    fd.estimated_maturity_value = result.maturity_value
    fd.maturity_estimate_method = result.method if result.maturity_value is not None else ""


def apply_maturity_values_on_create(
    fd: FixedDeposit,
    *,
    expected_maturity_value: Decimal | None = None,
    maturity_value_note: str = "",
) -> None:
    _apply_estimate_fields(fd)
    note = (maturity_value_note or "").strip()
    if note:
        fd.maturity_value_note = note

    if expected_maturity_value is not None:
        fd.expected_maturity_value = expected_maturity_value
        fd.maturity_value_source = MaturityValueSource.USER_CONFIRMED
    elif is_payout_fd(fd) and fd.estimated_maturity_value is not None:
        fd.expected_maturity_value = fd.estimated_maturity_value
        fd.maturity_value_source = MaturityValueSource.AUTO_PRINCIPAL
    elif fd.estimated_maturity_value is not None:
        fd.expected_maturity_value = fd.estimated_maturity_value
        fd.maturity_value_source = MaturityValueSource.AUTO_ESTIMATE
    else:
        fd.expected_maturity_value = None
        fd.maturity_value_source = MaturityValueSource.AUTO_ESTIMATE


def apply_maturity_values_on_update(
    fd: FixedDeposit,
    *,
    expected_maturity_value: Decimal | None = None,
    use_auto_maturity_estimate: bool = False,
    maturity_value_note: str | None = None,
) -> None:
    _apply_estimate_fields(fd)

    if maturity_value_note is not None:
        fd.maturity_value_note = (maturity_value_note or "").strip()

    if use_auto_maturity_estimate:
        fd.expected_maturity_value = fd.estimated_maturity_value
        if is_payout_fd(fd):
            fd.maturity_value_source = MaturityValueSource.AUTO_PRINCIPAL
        else:
            fd.maturity_value_source = MaturityValueSource.AUTO_ESTIMATE
    elif expected_maturity_value is not None:
        fd.expected_maturity_value = expected_maturity_value
        fd.maturity_value_source = MaturityValueSource.USER_CONFIRMED
    elif fd.maturity_value_source in {
        MaturityValueSource.AUTO_ESTIMATE,
        MaturityValueSource.AUTO_PRINCIPAL,
    }:
        fd.expected_maturity_value = fd.estimated_maturity_value
        if is_payout_fd(fd):
            fd.maturity_value_source = MaturityValueSource.AUTO_PRINCIPAL
        else:
            fd.maturity_value_source = MaturityValueSource.AUTO_ESTIMATE


def resolve_maturity_display(fd: FixedDeposit) -> dict:
    """
    API maturity fields with dynamic estimate fallback for legacy rows.

    Does not mutate the FD or affect settlement accounting.
    """
    result = estimate_fd_interest(fd)
    principal = Decimal(fd.principal_amount)

    stored_estimated = fd.estimated_maturity_value
    stored_expected = fd.expected_maturity_value
    stored_source = fd.maturity_value_source or MaturityValueSource.AUTO_ESTIMATE
    stored_method = (fd.maturity_estimate_method or "").strip()

    computed_maturity = result.maturity_value
    method = (
        stored_method
        if stored_estimated is not None and stored_method and is_compounded_fd(fd)
        else result.method
    )

    if stored_source == MaturityValueSource.USER_CONFIRMED and stored_expected is not None:
        expected = stored_expected
        source = MaturityValueSource.USER_CONFIRMED
        estimated = (
            stored_estimated
            if stored_estimated is not None and is_compounded_fd(fd)
            else computed_maturity
        )
    elif is_payout_fd(fd):
        estimated = computed_maturity if computed_maturity is not None else principal
        if stored_source == MaturityValueSource.USER_CONFIRMED and stored_expected is not None:
            expected = stored_expected
            source = MaturityValueSource.USER_CONFIRMED
        else:
            expected = estimated
            source = MaturityValueSource.AUTO_PRINCIPAL
    elif stored_expected is not None and stored_source != MaturityValueSource.AUTO_PRINCIPAL:
        expected = stored_expected
        source = stored_source
        estimated = (
            stored_estimated if stored_estimated is not None else computed_maturity
        )
    elif computed_maturity is not None:
        estimated = computed_maturity
        expected = computed_maturity
        source = MaturityValueSource.AUTO_ESTIMATE
    else:
        estimated = None
        expected = None
        source = stored_source

    if is_payout_fd(fd) and source != MaturityValueSource.USER_CONFIRMED:
        estimated = principal
        expected = principal

    total_interest = result.total_interest
    periodic_interest = result.periodic_interest
    if is_compounded_fd(fd):
        expected_interest = maturity_interest_from_value(principal, expected)
        if expected_interest is None:
            expected_interest = total_interest
        estimated_interest = total_interest
    else:
        estimated_interest = total_interest
        expected_interest = total_interest

    return {
        "estimate_type": result.estimate_type,
        "estimated_maturity_value": estimated,
        "expected_maturity_value": expected,
        "maturity_value_source": source,
        "maturity_estimate_method": method or "",
        "maturity_estimate_method_label": maturity_estimate_method_label(method),
        "estimated_interest": estimated_interest,
        "expected_interest": expected_interest,
        "estimated_total_interest": total_interest,
        "estimated_periodic_interest": periodic_interest,
        "estimate_message": result.message,
    }


def preview_maturity_estimate(
    *,
    principal_amount: Decimal,
    interest_rate_percent: Decimal,
    interest_payout_frequency: str,
    investment_date: date,
    maturity_date: date,
) -> dict:
    fd = SimpleNamespace(
        principal_amount=principal_amount,
        interest_rate_percent=interest_rate_percent,
        interest_payout_frequency=interest_payout_frequency,
        investment_date=investment_date,
        maturity_date=maturity_date,
        status="ACTIVE",
        is_active=True,
    )
    result = estimate_fd_interest(fd)
    warning = None
    if maturity_date <= investment_date:
        warning = "Maturity date must be after investment date."
    return {
        "estimate_type": result.estimate_type,
        "estimated_maturity_value": (
            float(result.maturity_value) if result.maturity_value is not None else None
        ),
        "estimated_interest": (
            float(result.total_interest) if result.total_interest is not None else None
        ),
        "estimated_total_interest": (
            float(result.total_interest) if result.total_interest is not None else None
        ),
        "estimated_periodic_interest": (
            float(result.periodic_interest)
            if result.periodic_interest is not None
            else None
        ),
        "maturity_estimate_method": result.method,
        "maturity_estimate_method_label": maturity_estimate_method_label(result.method),
        "estimate_message": result.message,
        "warning": warning,
    }
