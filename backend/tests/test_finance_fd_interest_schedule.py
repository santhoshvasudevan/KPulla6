from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from finance.fd_interest_schedule import (
    generate_compounded_maturity_row,
    generate_expected_interest_schedule,
    generate_payout_schedule,
    parse_indian_financial_year,
)


def _fd(**kwargs):
    defaults = dict(
        principal_amount=Decimal("100000"),
        interest_rate_percent=Decimal("7"),
        interest_payout_frequency="QUARTERLY",
        investment_date=date(2024, 1, 1),
        maturity_date=date(2026, 1, 1),
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_quarterly_schedule_has_eight_periods():
    rows = generate_payout_schedule(_fd())
    assert len(rows) == 8
    assert rows[0].expected_payout_date == date(2024, 4, 1)
    assert rows[-1].expected_payout_date == date(2026, 1, 1)


def test_monthly_schedule_frequency():
    rows = generate_payout_schedule(
        _fd(
            interest_payout_frequency="MONTHLY",
            maturity_date=date(2024, 4, 1),
        )
    )
    assert len(rows) == 3
    assert rows[0].expected_payout_date == date(2024, 2, 1)


def test_half_yearly_schedule_frequency():
    rows = generate_payout_schedule(
        _fd(
            interest_payout_frequency="HALF_YEARLY",
            maturity_date=date(2025, 1, 1),
        )
    )
    assert len(rows) == 2
    assert rows[1].expected_payout_date == date(2025, 1, 1)


def test_annual_schedule_frequency():
    rows = generate_payout_schedule(
        _fd(
            interest_payout_frequency="ANNUALLY",
            maturity_date=date(2025, 1, 1),
        )
    )
    assert len(rows) == 1
    assert rows[0].expected_gross_interest == Decimal("7000.0000")


def test_non_whole_term_partial_last_period():
    rows = generate_payout_schedule(
        _fd(
            investment_date=date(2024, 1, 15),
            maturity_date=date(2025, 6, 1),
            interest_payout_frequency="QUARTERLY",
        )
    )
    assert rows[-1].is_partial_period is True
    assert rows[-1].days_in_period < 92


def test_compounded_schedule_single_maturity_row():
    rows = generate_expected_interest_schedule(
        _fd(interest_payout_frequency="COMPOUNDED")
    )
    assert len(rows) == 1
    assert rows[0].schedule_row_type == "MATURITY_ACCRUAL"
    assert rows[0].expected_gross_interest > Decimal("0")


def test_parse_indian_financial_year():
    start, end = parse_indian_financial_year("2025-26")
    assert start == date(2025, 4, 1)
    assert end == date(2026, 3, 31)
