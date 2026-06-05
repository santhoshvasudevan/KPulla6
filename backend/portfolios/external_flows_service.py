"""Portfolio external cash flows for TWROR, cumulative return, and Metric Sheet."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from portfolios.cash_ledger_flows import build_cash_aware_twror_external_flows
from portfolios.models import Portfolio
from portfolios.scope import ResolvedPortfolioScope
from portfolios.summary_service import (
    MF_BASE_CURRENCY,
    fifo_eligible_queryset,
    norm_display_currency,
    portfolio_base_currency,
)
from finance.types import TransactionType
from fx.lookup import (
    convert_amount_with_fill_from_maps,
    fx_lookup_from_maps,
    load_fx_rate_maps,
)
from transactions.models import Transaction as TransactionModel


def _is_mutual_fund_transaction(txn: TransactionModel) -> bool:
    from django.core.exceptions import ObjectDoesNotExist

    try:
        txn.mutual_fund_detail
    except ObjectDoesNotExist:
        return False
    return True


def build_legacy_transaction_external_flows(
    all_txns: list[TransactionModel],
    base_currency: str,
) -> tuple[dict[date, Decimal], Optional[date]]:
    """Legacy BUY/SELL (+ MF paid_value) external flows in ``base_currency``."""
    flows_by_date: dict[date, Decimal] = {}
    flows_unknown_from: Optional[date] = None

    fx_pairs: set[tuple[str, str]] = set()
    flow_dates: list[date] = []
    for t in all_txns:
        if t.type not in {TransactionType.BUY.value, TransactionType.SELL.value}:
            continue
        if _is_mutual_fund_transaction(t):
            flow_dates.append(t.mutual_fund_detail.investment_date)
            if MF_BASE_CURRENCY != base_currency:
                fx_pairs.add((MF_BASE_CURRENCY, base_currency))
            continue
        if t.price_per_share is None or t.quantity is None:
            continue
        fc = norm_display_currency(t.currency)
        if fc != base_currency:
            fx_pairs.add((fc, base_currency))
        flow_dates.append(t.date)

    if not flow_dates:
        return flows_by_date, flows_unknown_from

    fx_maps = load_fx_rate_maps(fx_pairs, min(flow_dates), max(flow_dates))

    for t in all_txns:
        if t.type not in {TransactionType.BUY.value, TransactionType.SELL.value}:
            continue

        if _is_mutual_fund_transaction(t):
            detail = t.mutual_fund_detail
            cash = Decimal(detail.paid_value)
            flow_date = detail.investment_date
            if MF_BASE_CURRENCY != base_currency:
                fx_rate, _ = fx_lookup_from_maps(
                    fx_maps, MF_BASE_CURRENCY, base_currency, flow_date
                )
                if fx_rate is None:
                    flows_unknown_from = (
                        min(flows_unknown_from, flow_date)
                        if flows_unknown_from
                        else flow_date
                    )
                    continue
                cash = cash * fx_rate
            if t.type == TransactionType.BUY.value:
                flows_by_date[flow_date] = (
                    flows_by_date.get(flow_date, Decimal("0")) + cash
                )
            else:
                flows_by_date[flow_date] = (
                    flows_by_date.get(flow_date, Decimal("0")) - cash
                )
            continue

        if t.price_per_share is None or t.quantity is None:
            continue
        amt = Decimal(t.quantity) * Decimal(t.price_per_share)
        fees = Decimal(t.fees or 0)
        if t.type == TransactionType.BUY.value:
            cash = amt + fees
        else:
            cash = amt - fees

        fc = norm_display_currency(t.currency)
        if fc != base_currency:
            fx_rate, _ = fx_lookup_from_maps(fx_maps, fc, base_currency, t.date)
            if fx_rate is None:
                flows_unknown_from = (
                    min(flows_unknown_from, t.date) if flows_unknown_from else t.date
                )
                continue
            cash = cash * fx_rate

        if t.type == TransactionType.BUY.value:
            flows_by_date[t.date] = flows_by_date.get(t.date, Decimal("0")) + cash
        else:
            flows_by_date[t.date] = flows_by_date.get(t.date, Decimal("0")) - cash

    return flows_by_date, flows_unknown_from


def merge_external_flow_maps(
    parts: list[tuple[dict[date, Decimal], Optional[date]]],
) -> tuple[dict[date, Decimal], Optional[date]]:
    merged: dict[date, Decimal] = {}
    unknown_from: Optional[date] = None
    for flows, ufrom in parts:
        for d, amt in flows.items():
            merged[d] = merged.get(d, Decimal("0")) + amt
        if ufrom is not None:
            unknown_from = min(unknown_from, ufrom) if unknown_from else ufrom
    return merged, unknown_from


def portfolio_external_flows(
    all_txns: list[TransactionModel],
    base_currency: str,
    *,
    portfolio: Portfolio | None = None,
) -> tuple[dict[date, Decimal], Optional[date]]:
    """
    Net external flows by date for TWROR / cumulative return.

    Legacy portfolios: BUY/SELL (+ MF paid_value) in ``base_currency``.
    Cash-aware portfolios: cash ledger deposits/withdrawals (+ unlinked ADJUSTMENT).
    """
    if portfolio is not None and portfolio.cash_aware_enabled:
        return build_cash_aware_twror_external_flows(
            portfolio.id, calculation_currency=base_currency
        )
    return build_legacy_transaction_external_flows(all_txns, base_currency)


def portfolio_external_flows_for_scope(
    scope: ResolvedPortfolioScope,
    *,
    all_txns: list[TransactionModel],
    calculation_currency: str,
) -> tuple[dict[date, Decimal], Optional[date]]:
    """External flows for a single-portfolio scope."""
    calc_ccy = norm_display_currency(calculation_currency)
    portfolio = Portfolio.objects.filter(pk=scope.portfolio_ids[0]).first()
    if portfolio is None:
        return {}, None
    if not all_txns and not portfolio.cash_aware_enabled:
        return {}, None
    flow_ccy = calc_ccy if portfolio.cash_aware_enabled else portfolio_base_currency(all_txns)
    return portfolio_external_flows(all_txns, flow_ccy, portfolio=portfolio)


def build_all_scope_external_flows(
    scope: ResolvedPortfolioScope,
    display_currency: str,
) -> tuple[dict[date, Decimal], Optional[date]]:
    """
    Per-portfolio external flows (cash-aware or legacy), converted to display currency.

    Mixed mode: cash-aware portfolios use ledger flows; legacy use transaction BUY/SELL.
    """
    disp_ccy = norm_display_currency(display_currency)
    portfolios = {
        p.id: p
        for p in Portfolio.objects.filter(pk__in=scope.portfolio_ids).only(
            "id", "cash_aware_enabled"
        )
    }
    parts: list[tuple[dict[date, Decimal], Optional[date]]] = []
    for portfolio_id in scope.portfolio_ids:
        portfolio = portfolios.get(portfolio_id)
        if portfolio is None:
            continue
        child_scope = ResolvedPortfolioScope(kind="single", portfolio_ids=[portfolio_id])
        queryset = fifo_eligible_queryset(child_scope.portfolio_ids)
        txns = list(queryset)

        if portfolio.cash_aware_enabled:
            raw_flows, raw_unknown = build_cash_aware_twror_external_flows(
                portfolio_id, calculation_currency=disp_ccy
            )
            if raw_flows or raw_unknown is not None:
                parts.append((raw_flows, raw_unknown))
            continue

        if not txns:
            continue
        portfolio_base = portfolio_base_currency(txns)
        raw_flows, raw_unknown = build_legacy_transaction_external_flows(
            txns, portfolio_base
        )
        converted: dict[date, Decimal] = {}
        unknown_from = raw_unknown
        if portfolio_base == disp_ccy:
            converted = dict(raw_flows)
        elif raw_flows:
            flow_start = min(raw_flows.keys())
            flow_end = max(raw_flows.keys())
            fx_maps = load_fx_rate_maps({(portfolio_base, disp_ccy)}, flow_start, flow_end)
            for flow_date, amount in raw_flows.items():
                cv, _ = convert_amount_with_fill_from_maps(
                    amount, portfolio_base, disp_ccy, flow_date, fx_maps
                )
                if cv is None:
                    unknown_from = (
                        min(unknown_from, flow_date) if unknown_from else flow_date
                    )
                    continue
                converted[flow_date] = converted.get(flow_date, Decimal("0")) + cv
        parts.append((converted, unknown_from))
    return merge_external_flow_maps(parts)


def portfolio_flows_known_on_date(flows_unknown_from: Optional[date], d: date) -> bool:
    return flows_unknown_from is None or d < flows_unknown_from
