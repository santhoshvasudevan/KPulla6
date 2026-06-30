"""Tests for fixed deposit pure finance helpers."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from finance.fixed_deposits import (
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


def test_expected_maturity_compounded_exceeds_principal():
    value = expected_maturity_value(_fd(interest_payout_frequency="COMPOUNDED"))
    assert value > Decimal("100000")


def test_expected_maturity_simple_interest():
    value = expected_maturity_value(_fd(interest_payout_frequency="ANNUALLY"))
    assert value > Decimal("100000")


def test_expected_maturity_zero_rate_returns_principal():
    value = expected_maturity_value(_fd(interest_rate_percent=Decimal("0")))
    assert value == Decimal("100000")


def test_estimate_maturity_non_whole_term():
    from finance.fixed_deposits import estimate_maturity_value

    result = estimate_maturity_value(
        _fd(
            interest_payout_frequency="COMPOUNDED",
            investment_date=date(2024, 1, 1),
            maturity_date=date(2026, 10, 1),
        )
    )
    assert result.value is not None
    assert result.value > Decimal("100000")
    assert result.method == "ANNUAL_COMPOUND_ACTUAL_365"
