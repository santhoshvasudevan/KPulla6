"""Mutual fund cash-flow helpers for portfolio XIRR (no Django imports)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable, Optional

import pyxirr

from finance.splits import apply_stock_split_adjustments
from finance.types import TransactionType


@dataclass(frozen=True)
class MutualFundCashflowEvent:
    """Signed cash flow on investment_date; amount in fund currency (INR)."""

    flow_date: date
    amount: Decimal  # negative = outflow (BUY), positive = inflow (SELL)


def merge_portfolio_xirr(
    stock_transactions: Iterable,
    mutual_fund_events: Iterable[MutualFundCashflowEvent],
    *,
    terminal_value: Decimal,
    current_date: Optional[date] = None,
    include_fees_in_cashflows: bool = True,
) -> Optional[float]:
    """
    Portfolio XIRR from stock BUY/SELL (transaction date, qty×price±fees) plus MF
    cash flows (investment_date, paid_value) and a terminal valuation.
    """
    if current_date is None:
        current_date = date.today()

    dates: list[date] = []
    amounts: list[float] = []

    for t in sorted(stock_transactions, key=lambda x: x.date):
        if t.type == TransactionType.BUY:
            cost = t.quantity * t.price
            if include_fees_in_cashflows:
                cost += t.fees
            dates.append(t.date)
            amounts.append(float(-cost))
        elif t.type == TransactionType.SELL:
            proceeds = t.quantity * t.price
            if include_fees_in_cashflows:
                proceeds -= t.fees
            dates.append(t.date)
            amounts.append(float(proceeds))

    for ev in sorted(mutual_fund_events, key=lambda e: e.flow_date):
        dates.append(ev.flow_date)
        amounts.append(float(ev.amount))

    if terminal_value > 0 or amounts:
        dates.append(current_date)
        amounts.append(float(terminal_value))

    if not dates:
        return None
    try:
        return pyxirr.xirr(dates, amounts)
    except Exception:
        return None
