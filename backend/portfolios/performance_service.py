from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal, Optional

import pandas as pd

from finance.benchmarks import PerformancePoint, merge_performance_and_benchmarks
from finance.performance_range import resolve_performance_range_start
from finance.performance_stats import contributions_and_withdrawals_through
from finance.twror import compute_twror_series
from finance.types import TransactionType
from fx.lookup import (
    convert_amount_with_fill,
    convert_amount_with_fill_from_maps,
    fx_lookup_from_maps,
    load_fx_rate_maps,
)
from market_data.models import BenchmarkIndexConfig
from market_data.price_repository import list_index_prices_in_range
from portfolios import dates as portfolio_dates
from portfolios.scope import ResolvedPortfolioScope
from portfolios.summary_service import (
    MF_BASE_CURRENCY,
    build_all_scope_portfolio_value_timeseries,
    build_portfolio_value_timeseries,
    fifo_eligible_queryset,
    norm_display_currency,
    portfolio_base_currency,
    transactions_by_mf_holding,
    transactions_by_symbol,
)
from transactions.models import Transaction as TransactionModel

MetricCode = Literal["value", "cumulative_return", "twror"]


class BenchmarkConfigError(Exception):
    pass


@dataclass(frozen=True)
class PerformanceListResult:
    points: list[dict]


@dataclass(frozen=True)
class PerformanceComparisonResult:
    metric: str
    series: list[dict]
    warnings: list[str]


def _is_mutual_fund_transaction(txn: TransactionModel) -> bool:
    from django.core.exceptions import ObjectDoesNotExist

    try:
        txn.mutual_fund_detail
    except ObjectDoesNotExist:
        return False
    return True


def _build_external_flows(
    all_txns: list[TransactionModel],
    base_currency: str,
) -> tuple[dict[date, Decimal], Optional[date]]:
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


def _flows_known(flows_unknown_from: Optional[date], d: date) -> bool:
    return flows_unknown_from is None or d < flows_unknown_from


def portfolio_external_flows(
    all_txns: list[TransactionModel],
    base_currency: str,
) -> tuple[dict[date, Decimal], Optional[date]]:
    """Net external flows by date in portfolio base currency (for analytics / TWROR)."""
    return _build_external_flows(all_txns, base_currency)


def _merge_flow_maps(
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


def build_all_scope_external_flows(
    scope: ResolvedPortfolioScope,
    display_currency: str,
) -> tuple[dict[date, Decimal], Optional[date]]:
    """Per-portfolio external flows converted to display currency, aggregated by date."""
    disp_ccy = norm_display_currency(display_currency)
    parts: list[tuple[dict[date, Decimal], Optional[date]]] = []
    for portfolio_id in scope.portfolio_ids:
        child_scope = ResolvedPortfolioScope(kind="single", portfolio_ids=[portfolio_id])
        queryset = fifo_eligible_queryset(child_scope.portfolio_ids)
        txns = list(queryset)
        if not txns:
            continue
        portfolio_base = portfolio_base_currency(txns)
        raw_flows, raw_unknown = _build_external_flows(txns, portfolio_base)
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
    return _merge_flow_maps(parts)


def portfolio_flows_known_on_date(flows_unknown_from: Optional[date], d: date) -> bool:
    return _flows_known(flows_unknown_from, d)


def _to_response_point(pt: PerformancePoint, *, label: str | None = None) -> dict:
    row: dict = {
        "date": pt.date,
        "value": pt.value,
        "metric": pt.metric,
        "label": label,
    }
    if pt.currency is not None:
        row["currency"] = pt.currency
    return row


def _get_benchmark_config(symbol: str) -> BenchmarkIndexConfig | None:
    sym = (symbol or "").strip().upper()
    if not sym:
        return None
    return (
        BenchmarkIndexConfig.objects.filter(symbol__iexact=sym, enabled=True).first()
    )


def _load_benchmark_series(symbol: str, start: date, end: date) -> pd.Series | None:
    rows = list_index_prices_in_range(symbol, start, end)
    if not rows:
        return None
    idx = pd.to_datetime([r.date for r in rows])
    return pd.Series([float(r.close_price) for r in rows], index=idx)


def build_portfolio_performance(
    *,
    scope: ResolvedPortfolioScope,
    metric: MetricCode,
    range_code: str,
    display_currency: str,
    today: date | None = None,
) -> list[PerformancePoint]:
    today = today or portfolio_dates.current_date()
    queryset = fifo_eligible_queryset(scope.portfolio_ids)
    all_txns = list(queryset)
    if not all_txns:
        return []

    by_symbol = transactions_by_symbol(queryset)
    by_mf = transactions_by_mf_holding(queryset)
    base_currency = portfolio_base_currency(all_txns)
    disp_ccy = norm_display_currency(display_currency)
    use_all_scope_display = scope.kind == "all_active"

    inception = min(t.date for t in all_txns)
    range_start = resolve_performance_range_start(range_code, today, inception)
    range_start_iso = range_start.isoformat()
    emit_start = None if range_code == "ALL" else range_start

    if use_all_scope_display:
        timeseries_full = build_all_scope_portfolio_value_timeseries(
            scope, disp_ccy, emit_start_date=emit_start
        )
    else:
        timeseries_full = build_portfolio_value_timeseries(
            all_txns, by_symbol, by_mf, emit_start_date=emit_start
        )
    if not timeseries_full:
        return []

    if metric == "value":
        needs_display_conv = (
            not use_all_scope_display
            and norm_display_currency(base_currency) != disp_ccy
        )

        def _convert_value(pv: float, pt_date: date) -> float | None:
            if not needs_display_conv:
                return float(pv)
            cv, _ = convert_amount_with_fill(pv, base_currency, disp_ccy, pt_date)
            return float(cv) if cv is not None else None

        out: list[PerformancePoint] = []
        for p in timeseries_full:
            if p["date"] < range_start_iso:
                continue
            pv = p.get("portfolio_value")
            if pv is None:
                out.append(
                    PerformancePoint(
                        date=p["date"], value=None, metric="value", currency=disp_ccy
                    )
                )
                continue
            pt_date = date.fromisoformat(p["date"])
            cv = float(pv) if use_all_scope_display else _convert_value(float(pv), pt_date)
            out.append(
                PerformancePoint(
                    date=p["date"], value=cv, metric="value", currency=disp_ccy
                )
            )
        return out

    if use_all_scope_display:
        flows_by_date, flows_unknown_from = build_all_scope_external_flows(scope, disp_ccy)
        metric_currency = disp_ccy
    else:
        flows_by_date, flows_unknown_from = _build_external_flows(all_txns, base_currency)
        metric_currency = base_currency

    if metric == "cumulative_return":
        out: list[PerformancePoint] = []
        for p in timeseries_full:
            d = date.fromisoformat(p["date"])
            if p["date"] < range_start_iso:
                continue
            pv = p.get("portfolio_value")
            if pv is None or not _flows_known(flows_unknown_from, d):
                out.append(
                    PerformancePoint(
                        date=p["date"],
                        value=None,
                        metric="cumulative_return",
                        currency=metric_currency,
                    )
                )
                continue
            contrib, withdraw = contributions_and_withdrawals_through(
                flows_by_date, d
            )
            if contrib <= 0:
                out.append(
                    PerformancePoint(
                        date=p["date"],
                        value=None,
                        metric="cumulative_return",
                        currency=metric_currency,
                    )
                )
                continue
            val = (
                (Decimal(str(pv)) + withdraw - contrib) / contrib
            ) * Decimal("100")
            out.append(
                PerformancePoint(
                    date=p["date"],
                    value=float(val),
                    metric="cumulative_return",
                    currency=metric_currency,
                )
            )
        return out

    ts_use = timeseries_full if range_code == "ALL" else [
        p for p in timeseries_full if p["date"] >= range_start_iso
    ]

    twror_pts = compute_twror_series(
        ts_use, flows_by_date, flows_unknown_from=flows_unknown_from
    )
    return [
        PerformancePoint(
            date=p.date.isoformat(),
            value=float(p.value) if p.value is not None else None,
            metric="twror",
            currency=metric_currency,
        )
        for p in twror_pts
    ]


def build_portfolio_performance_with_benchmarks(
    *,
    scope: ResolvedPortfolioScope,
    metric: Literal["cumulative_return", "twror"],
    benchmark_symbol: str,
    range_code: str,
    display_currency: str,
    today: date | None = None,
) -> PerformanceComparisonResult:
    cfg = _get_benchmark_config(benchmark_symbol)
    if not cfg:
        raise BenchmarkConfigError(
            f"Unknown or disabled benchmark symbol: {benchmark_symbol!r}"
        )

    pts = build_portfolio_performance(
        scope=scope,
        metric=metric,
        range_code=range_code,
        display_currency=display_currency,
        today=today,
    )

    if not pts:
        raw = merge_performance_and_benchmarks(
            pts,
            metric,
            benchmark_symbol,
            benchmark_display_name=cfg.display_name,
            benchmark_price_series=None,
        )
        return PerformanceComparisonResult(
            metric=raw["metric"],
            series=raw["series"],
            warnings=raw["warnings"],
        )

    dates = [date.fromisoformat(p.date) for p in pts]
    bench_series = _load_benchmark_series(cfg.symbol, min(dates), max(dates))
    raw = merge_performance_and_benchmarks(
        pts,
        metric,
        cfg.symbol,
        benchmark_display_name=cfg.display_name,
        benchmark_price_series=bench_series,
    )
    return PerformanceComparisonResult(
        metric=raw["metric"],
        series=raw["series"],
        warnings=raw["warnings"],
    )


def performance_list_payload(points: list[PerformancePoint]) -> list[dict]:
    return [_to_response_point(p) for p in points]
