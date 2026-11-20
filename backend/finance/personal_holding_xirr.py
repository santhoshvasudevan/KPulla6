"""Native-INR personal money-weighted return for a mutual-fund holding (no Django)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Iterable, Optional

from finance.cash import mf_sell_cash_proceeds
from finance.types import TransactionType
from finance.xirr import solve_xirr


def mf_holding_settlement_amount(
    *,
    txn_type: TransactionType | str,
    paid_value: Decimal,
    units_allotted: Decimal,
    nav: Decimal,
    fees: Decimal,
    actual_cash_received: Decimal | None,
) -> Decimal | None:
    """Signed investor cash for one MF BUY/SELL; None for other types."""
    kind = txn_type.value if isinstance(txn_type, TransactionType) else str(txn_type)
    if kind == TransactionType.BUY.value or kind == TransactionType.BUY:
        return -paid_value
    if kind == TransactionType.SELL.value or kind == TransactionType.SELL:
        if actual_cash_received is not None:
            return actual_cash_received
        return mf_sell_cash_proceeds(
            paid_value=paid_value,
            units_allotted=units_allotted,
            nav=nav,
            fees=fees,
        )
    return None


def solve_native_inr_holding_xirr(
    settlement_flows: Iterable[tuple[date, Decimal]],
    *,
    remaining_qty: Decimal,
    current_nav: Decimal | None,
    today: date,
) -> Optional[float]:
    """
    Annualized personal return from dated INR settlement flows plus remaining units.

    Open positions require a positive eligible ``current_nav``. Fully redeemed
    positions may solve from realized flows alone.
    """
    flows: dict[date, Decimal] = {}
    for flow_date, amount in settlement_flows:
        flows[flow_date] = flows.get(flow_date, Decimal("0")) + amount
    if remaining_qty > 0:
        if current_nav is None or current_nav <= 0:
            return None
        flows[today] = flows.get(today, Decimal("0")) + remaining_qty * current_nav
    if not flows:
        return None
    dates = sorted(flows)
    return solve_xirr(dates, [float(flows[day]) for day in dates])
