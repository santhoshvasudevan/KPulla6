from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Iterable, Optional

import pyxirr

from finance.splits import apply_stock_split_adjustments
from finance.types import Transaction, TransactionType


def build_xirr_cashflows(
    transactions: Iterable[Transaction],
    *,
    current_price: Decimal,
    current_date: Optional[date] = None,
    include_fees_in_cashflows: bool = True,
) -> tuple[list[date], list[float]]:
    """
    Build XIRR date/amount series from transactions.

    - BUY: negative cash flow (cost + fees when include_fees_in_cashflows).
    - SELL: positive cash flow (proceeds - fees when include_fees_in_cashflows).
    - STOCK_SPLIT / DIVIDEND: excluded.
    - Terminal positive flow: current holding value at current_date.
    """
    if current_date is None:
        current_date = date.today()

    txns = apply_stock_split_adjustments(
        [t for t in transactions if t.type in (TransactionType.BUY, TransactionType.SELL)]
    )
    dates: list[date] = []
    amounts: list[float] = []
    qty = Decimal("0")

    for t in sorted(txns, key=lambda x: x.date):
        if t.type == TransactionType.BUY:
            cost = t.quantity * t.price
            if include_fees_in_cashflows:
                cost += t.fees
            dates.append(t.date)
            amounts.append(float(-cost))
            qty += t.quantity
        elif t.type == TransactionType.SELL:
            proceeds = t.quantity * t.price
            if include_fees_in_cashflows:
                proceeds -= t.fees
            dates.append(t.date)
            amounts.append(float(proceeds))
            qty -= t.quantity

    current_value = qty * current_price
    if current_value > 0 or amounts:
        dates.append(current_date)
        amounts.append(float(current_value))

    return dates, amounts


def calculate_portfolio_xirr(
    transactions: Iterable[Transaction],
    *,
    terminal_value: Decimal,
    current_date: Optional[date] = None,
    include_fees_in_cashflows: bool = True,
) -> Optional[float]:
    """
    Portfolio-level XIRR from BUY/SELL cash flows plus a terminal valuation.
    Splits/dividends are excluded; apply split adjustments before calling if needed.
    """
    if current_date is None:
        current_date = date.today()

    dates: list[date] = []
    amounts: list[float] = []
    for t in sorted(transactions, key=lambda x: x.date):
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

    if terminal_value > 0 or amounts:
        dates.append(current_date)
        amounts.append(float(terminal_value))

    if not dates:
        return None
    try:
        return pyxirr.xirr(dates, amounts)
    except Exception:
        return None


def calculate_xirr(
    transactions: Iterable[Transaction],
    *,
    current_price: Decimal,
    current_date: Optional[date] = None,
    include_fees_in_cashflows: bool = True,
) -> Optional[float]:
    """Return annualized XIRR or None when pyxirr cannot solve."""
    dates, amounts = build_xirr_cashflows(
        transactions,
        current_price=current_price,
        current_date=current_date,
        include_fees_in_cashflows=include_fees_in_cashflows,
    )
    if not dates:
        return None
    try:
        return pyxirr.xirr(dates, amounts)
    except Exception:
        return None
