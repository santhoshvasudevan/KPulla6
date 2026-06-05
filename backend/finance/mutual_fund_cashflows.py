"""Mutual fund cash-flow helpers for portfolio XIRR (no Django imports)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Iterable, Optional

from finance.types import TransactionType
from finance.xirr import solve_xirr
from fx.lookup import convert_amount_with_fill_from_maps, load_fx_rate_maps

MF_BASE_CURRENCY = "INR"
FX_LOOKBACK_DAYS = 7


@dataclass(frozen=True)
class MutualFundCashflowEvent:
    """Signed cash flow on investment_date; amount in fund currency (INR)."""

    flow_date: date
    amount: Decimal  # negative = outflow (BUY), positive = inflow (SELL)


def build_legacy_portfolio_xirr_flows(
    stock_transactions: Iterable,
    mutual_fund_events: Iterable[MutualFundCashflowEvent],
    *,
    portfolio_base: str,
    calculation_currency: str,
    include_fees_in_cashflows: bool = True,
) -> tuple[dict[date, Decimal], bool]:
    """
    Legacy portfolio external XIRR flows (BUY/SELL + MF paid_value) by date.

    Stock amounts use transaction currency; MF amounts use INR then FX to
    ``calculation_currency``. Returns (flows_by_date, fx_missing).
    """
    calc_ccy = (calculation_currency or portfolio_base).strip().upper() or "EUR"
    flows_by_date: dict[date, Decimal] = {}
    fx_missing = False

    stock_dates: list[date] = []
    for t in stock_transactions:
        if t.type in (TransactionType.BUY, TransactionType.SELL):
            stock_dates.append(t.date)

    mf_dates = [ev.flow_date for ev in mutual_fund_events]
    all_dates = stock_dates + mf_dates
    if not all_dates:
        return flows_by_date, False

    fx_pairs: set[tuple[str, str]] = set()
    base = (portfolio_base or calc_ccy).strip().upper() or "EUR"
    if base != calc_ccy:
        fx_pairs.add((base, calc_ccy))
    if MF_BASE_CURRENCY != calc_ccy and mutual_fund_events:
        fx_pairs.add((MF_BASE_CURRENCY, calc_ccy))

    fx_start = min(all_dates) - timedelta(days=FX_LOOKBACK_DAYS)
    fx_end = max(all_dates)
    fx_maps = load_fx_rate_maps(fx_pairs, fx_start, fx_end) if fx_pairs else {}

    for t in sorted(stock_transactions, key=lambda x: x.date):
        if t.type == TransactionType.BUY:
            cost = t.quantity * t.price
            if include_fees_in_cashflows:
                cost += t.fees
            amt = -cost
        elif t.type == TransactionType.SELL:
            proceeds = t.quantity * t.price
            if include_fees_in_cashflows:
                proceeds -= t.fees
            amt = proceeds
        else:
            continue
        if base != calc_ccy:
            converted, _ = convert_amount_with_fill_from_maps(
                amt, base, calc_ccy, t.date, fx_maps
            )
            if converted is None:
                fx_missing = True
                continue
            amt = converted
        flows_by_date[t.date] = flows_by_date.get(t.date, Decimal("0")) + amt

    for ev in sorted(mutual_fund_events, key=lambda e: e.flow_date):
        amt = ev.amount
        if MF_BASE_CURRENCY != calc_ccy:
            converted, _ = convert_amount_with_fill_from_maps(
                amt, MF_BASE_CURRENCY, calc_ccy, ev.flow_date, fx_maps
            )
            if converted is None:
                fx_missing = True
                continue
            amt = converted
        flows_by_date[ev.flow_date] = flows_by_date.get(ev.flow_date, Decimal("0")) + amt

    return flows_by_date, fx_missing


def merge_portfolio_xirr(
    stock_transactions: Iterable,
    mutual_fund_events: Iterable[MutualFundCashflowEvent],
    *,
    terminal_value: Decimal,
    current_date: Optional[date] = None,
    include_fees_in_cashflows: bool = True,
    portfolio_base: str = "EUR",
    calculation_currency: str | None = None,
) -> Optional[float]:
    """
    Portfolio XIRR from stock BUY/SELL (transaction date, qty×price±fees) plus MF
    cash flows (investment_date, paid_value) and a terminal valuation.
    """
    if current_date is None:
        current_date = date.today()

    calc_ccy = (calculation_currency or portfolio_base).strip().upper() or "EUR"
    flows, fx_missing = build_legacy_portfolio_xirr_flows(
        stock_transactions,
        mutual_fund_events,
        portfolio_base=portfolio_base,
        calculation_currency=calc_ccy,
        include_fees_in_cashflows=include_fees_in_cashflows,
    )
    if fx_missing:
        return None

    dates = sorted(flows.keys())
    amounts = [float(flows[d]) for d in dates]
    if terminal_value > 0 or amounts:
        dates.append(current_date)
        amounts.append(float(terminal_value))

    return solve_xirr(dates, amounts)
