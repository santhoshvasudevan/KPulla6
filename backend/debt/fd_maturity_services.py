"""Fixed deposit expected maturity value application (ORM services)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from debt.models import FixedDeposit, MaturityValueSource
from finance.fixed_deposits import (
    estimate_maturity_value,
    maturity_estimate_method_label,
    maturity_interest_from_value,
)


def _apply_estimate_fields(fd: FixedDeposit) -> None:
    result = estimate_maturity_value(fd)
    fd.estimated_maturity_value = result.value
    fd.maturity_estimate_method = result.method if result.value is not None else ""


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
        fd.maturity_value_source = MaturityValueSource.AUTO_ESTIMATE
        fd.expected_maturity_value = fd.estimated_maturity_value
    elif expected_maturity_value is not None:
        fd.expected_maturity_value = expected_maturity_value
        fd.maturity_value_source = MaturityValueSource.USER_CONFIRMED
    elif fd.maturity_value_source == MaturityValueSource.AUTO_ESTIMATE:
        fd.expected_maturity_value = fd.estimated_maturity_value


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
    result = estimate_maturity_value(fd)
    warning = None
    if maturity_date <= investment_date:
        warning = "Maturity date must be after investment date."
    return {
        "estimated_maturity_value": (
            float(result.value) if result.value is not None else None
        ),
        "estimated_interest": (
            float(result.interest) if result.interest is not None else None
        ),
        "maturity_estimate_method": result.method,
        "maturity_estimate_method_label": maturity_estimate_method_label(result.method),
        "warning": warning,
    }
