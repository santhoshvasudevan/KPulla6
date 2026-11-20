"""Pure-finance tests for native-INR personal holding XIRR."""
from datetime import date
from decimal import Decimal

import pytest

from finance.personal_holding_xirr import (
    mf_holding_settlement_amount,
    solve_native_inr_holding_xirr,
)
from finance.types import TransactionType


def test_958_day_oracle_and_npv_near_zero():
    rate = solve_native_inr_holding_xirr(
        [(date(2024, 1, 1), Decimal("-10000"))],
        remaining_qty=Decimal("100"),
        current_nav=Decimal("118.089530"),
        today=date(2026, 8, 16),
    )
    assert rate == pytest.approx(0.0654, abs=5e-4)
    # NPV of the same flows at the solved rate should be near zero.
    t0, t1 = date(2024, 1, 1), date(2026, 8, 16)
    years = (t1 - t0).days / 365.0
    npv = -10000.0 + 11808.953 / ((1.0 + rate) ** years)
    assert abs(npv) < 1.0


def test_sell_fallback_uses_units_times_nav_minus_fees_when_paid_value_zero():
    amount = mf_holding_settlement_amount(
        txn_type=TransactionType.SELL,
        paid_value=Decimal("0"),
        units_allotted=Decimal("10"),
        nav=Decimal("100"),
        fees=Decimal("25"),
        actual_cash_received=None,
    )
    assert amount == Decimal("975")


def test_open_position_without_nav_is_unavailable():
    assert (
        solve_native_inr_holding_xirr(
            [(date(2024, 1, 1), Decimal("-10000"))],
            remaining_qty=Decimal("100"),
            current_nav=None,
            today=date(2025, 1, 1),
        )
        is None
    )
