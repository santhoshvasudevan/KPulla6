"""Tests for fixed deposit pure finance helpers."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from finance.fixed_deposits import (
    ANNUAL_COMPOUND_ACTUAL_365,
    COMPOUNDED_MATURITY,
    PAYOUT_INTEREST,
    SIMPLE_PAYOUT_ACTUAL_365,
    estimate_fd_interest,
    estimate_maturity_value,
    expected_maturity_value,
    fixed_deposit_principal_value,
)


def _fd(**overrides):
    base = dict(
        principal_amount=Decimal("100000"),
        status="ACTIVE",
        is_active=True,
        interest_rate_percent=Decimal("7.5"),
        interest_payout_frequency="COMPOUNDED",
        investment_date=date(2024, 1, 1),
        maturity_date=date(2026, 1, 1),
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_principal_value_active_returns_principal():
    assert fixed_deposit_principal_value(_fd(), date.today()) == Decimal("100000")


def test_principal_value_matured_active_returns_principal():
    assert fixed_deposit_principal_value(_fd(status="MATURED"), date.today()) == Decimal(
        "100000"
    )


def test_principal_value_closed_returns_zero():
    assert fixed_deposit_principal_value(_fd(status="CLOSED"), date.today()) == Decimal("0")


def test_principal_value_inactive_returns_zero():
    assert fixed_deposit_principal_value(_fd(is_active=False), date.today()) == Decimal("0")


def test_compounded_maturity_exceeds_principal():
    result = estimate_fd_interest(_fd(interest_payout_frequency="COMPOUNDED"))
    assert result.estimate_type == COMPOUNDED_MATURITY
    assert result.maturity_value > Decimal("100000")
    assert result.total_interest == result.maturity_value - Decimal("100000")
    assert result.periodic_interest is None
    assert result.method == ANNUAL_COMPOUND_ACTUAL_365


@pytest.mark.parametrize(
    "frequency,periods",
    [
        ("MONTHLY", 12),
        ("QUARTERLY", 4),
        ("HALF_YEARLY", 2),
        ("ANNUALLY", 1),
    ],
)
def test_payout_fd_maturity_equals_principal(frequency, periods):
    result = estimate_fd_interest(_fd(interest_payout_frequency=frequency))
    assert result.estimate_type == PAYOUT_INTEREST
    assert result.maturity_value == Decimal("100000")
    assert result.total_interest > Decimal("0")
    assert result.periodic_interest == pytest.approx(
        Decimal("100000") * Decimal("0.075") / Decimal(periods), abs=Decimal("0.0001")
    )
    assert result.method == SIMPLE_PAYOUT_ACTUAL_365


def test_payout_total_interest_actual_365_non_whole_term():
    result = estimate_fd_interest(
        _fd(
            interest_payout_frequency="QUARTERLY",
            investment_date=date(2024, 1, 1),
            maturity_date=date(2026, 10, 1),
        )
    )
    days = Decimal((date(2026, 10, 1) - date(2024, 1, 1)).days)
    expected_total = (Decimal("100000") * Decimal("0.075") * days / Decimal("365")).quantize(
        Decimal("0.0001")
    )
    assert result.maturity_value == Decimal("100000")
    assert result.total_interest == expected_total


def test_compounded_non_whole_term_maturity_estimate():
    result = estimate_fd_interest(
        _fd(
            interest_payout_frequency="COMPOUNDED",
            investment_date=date(2024, 1, 1),
            maturity_date=date(2026, 10, 1),
        )
    )
    assert result.maturity_value is not None
    assert result.maturity_value > Decimal("100000")
    assert result.method == ANNUAL_COMPOUND_ACTUAL_365


def test_expected_maturity_compounded_exceeds_principal():
    value = expected_maturity_value(_fd(interest_payout_frequency="COMPOUNDED"))
    assert value > Decimal("100000")


def test_expected_maturity_payout_returns_principal():
    value = expected_maturity_value(_fd(interest_payout_frequency="ANNUALLY"))
    assert value == Decimal("100000")


def test_expected_maturity_zero_rate_returns_principal():
    value = expected_maturity_value(_fd(interest_rate_percent=Decimal("0")))
    assert value == Decimal("100000")


def test_estimate_maturity_value_backward_compatible_wrapper():
    result = estimate_maturity_value(_fd(interest_payout_frequency="QUARTERLY"))
    assert result.value == Decimal("100000")
    assert result.interest > Decimal("0")
