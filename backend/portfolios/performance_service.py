from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Literal, Optional

import pandas as pd

from cash.services import (
    cash_ledger_inception_date,
    merge_cash_into_value_timeseries,
    scope_has_cash_ledger_entries,
)
from finance.benchmarks import PerformancePoint, merge_performance_and_benchmarks
from finance.performance_range import resolve_performance_range_start
from finance.performance_stats import contributions_and_withdrawals_through
from finance.twror import compute_twror_series
from fx.lookup import (
    convert_amount_with_fill,
    convert_amount_with_fill_from_maps,
    load_fx_rate_maps,
)
from market_data.models import BenchmarkIndexConfig
from market_data.price_repository import list_index_prices_in_range
from portfolios import dates as portfolio_dates
from portfolios.external_flows_service import (
    build_all_scope_external_flows,
    portfolio_external_flows,
    portfolio_external_flows_for_scope,
    portfolio_flows_known_on_date,
)
from portfolios.models import Portfolio
from portfolios.scope import ResolvedPortfolioScope
from portfolios.summary_service import (
    _aggregate_timeseries_lists,
    _data_load_start,
    build_all_scope_portfolio_value_timeseries,
    build_portfolio_value_timeseries,
    fifo_eligible_queryset,
    norm_display_currency,
    portfolio_base_currency,
    transactions_by_mf_holding,
    transactions_by_symbol,
)
from debt.portfolio_value import (
    merge_fd_bank_into_value_timeseries,
    value_timeseries_inception_date,
)
from transactions.models import Transaction as TransactionModel

RETURN_FLOWS_FX_WARNING = (
    "FX rates are missing for some external cash flows; returns may be incomplete."
)

MetricCode = Literal["value", "cumulative_return", "twror"]


class BenchmarkConfigError(Exception):
    pass


@dataclass(frozen=True)
class PerformanceListResult:
    points: list[dict]


@dataclass(frozen=True)
class PerformanceSeriesResult:
    points: list[PerformancePoint]
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PerformanceComparisonResult:
    metric: str
    series: list[dict]
    warnings: list[str]


def _single_portfolio_cash_aware_returns(scope: ResolvedPortfolioScope) -> bool:
    portfolio = Portfolio.objects.filter(pk=scope.portfolio_ids[0]).only(
        "cash_aware_enabled"
    ).first()
    return portfolio is not None and portfolio.cash_aware_enabled


def _convert_investment_ts_to_display(
    raw_ts: list[dict],
    *,
    portfolio_base: str,
    disp_ccy: str,
    emit_start: date | None,
) -> list[dict]:
    if not raw_ts or portfolio_base == disp_ccy:
        return raw_ts
    series_start = date.fromisoformat(raw_ts[0]["date"])
    end = date.fromisoformat(raw_ts[-1]["date"])
    fx_start = _data_load_start(emit_start, series_start)
    fx_maps = load_fx_rate_maps({(portfolio_base, disp_ccy)}, fx_start, end)
    converted: list[dict] = []
    for p in raw_ts:
        pp = dict(p)
        pt_date = date.fromisoformat(pp["date"])
        if pp.get("portfolio_value") is not None:
            cv, _ = convert_amount_with_fill_from_maps(
                Decimal(str(pp["portfolio_value"])),
                portfolio_base,
                disp_ccy,
                pt_date,
                fx_maps,
            )
            pp["portfolio_value"] = float(cv) if cv is not None else None
        converted.append(pp)
    return converted


def _apply_fd_bank_to_return_timeseries(
    timeseries: list[dict],
    *,
    user,
    scope: ResolvedPortfolioScope,
    disp_ccy: str,
    today: date,
    emit_start: date | None,
    include_fd: bool = True,
    include_bank: bool = True,
) -> tuple[list[dict], list[str]]:
    if user is None or (not include_fd and not include_bank):
        return timeseries, []
    fd_bank_start = value_timeseries_inception_date(user, scope, today=today)
    if not timeseries and not fd_bank_start:
        return timeseries, []
    if timeseries:
        ts_start = date.fromisoformat(timeseries[0]["date"])
        ts_end = date.fromisoformat(timeseries[-1]["date"])
        loop_start = min(ts_start, fd_bank_start) if fd_bank_start else ts_start
    else:
        ts_end = today
        loop_start = emit_start if emit_start is not None else (fd_bank_start or today)
    return merge_fd_bank_into_value_timeseries(
        timeseries,
        user=user,
        scope=scope,
        display_currency=disp_ccy,
        start_date=loop_start,
        end_date=ts_end,
        include_fd=include_fd,
        include_bank=include_bank,
    )


def build_return_value_timeseries(
    *,
    scope: ResolvedPortfolioScope,
    all_txns: list[TransactionModel],
    by_symbol: dict,
    by_mf: dict,
    disp_ccy: str,
    emit_start: date | None,
    today: date,
    user=None,
) -> tuple[list[dict], list[str]]:
    """
    Daily portfolio values for TWROR / cumulative_return.

    Cash-aware portfolios: investment + cash (display currency).
    Legacy portfolios: investment-only (unchanged).
    All Portfolios: per-portfolio rules, then summed in display currency.
    """
    warnings: list[str] = []

    if scope.kind == "all_active":
        portfolios = {
            p.id: p
            for p in Portfolio.objects.filter(pk__in=scope.portfolio_ids).only(
                "id", "cash_aware_enabled"
            )
        }
        child_series: list[list[dict]] = []
        for portfolio_id in scope.portfolio_ids:
            portfolio = portfolios.get(portfolio_id)
            if portfolio is None:
                continue
            child_scope = ResolvedPortfolioScope(
                kind="single", portfolio_ids=[portfolio_id]
            )
            queryset = fifo_eligible_queryset(child_scope.portfolio_ids)
            child_txns = list(queryset)
            if portfolio.cash_aware_enabled:
                if child_txns:
                    raw_ts = build_portfolio_value_timeseries(
                        child_txns,
                        transactions_by_symbol(queryset),
                        transactions_by_mf_holding(queryset),
                        emit_start_date=emit_start,
                    )
                else:
                    raw_ts = []
                cash_start = cash_ledger_inception_date(child_scope) or today
                loop_start = emit_start if emit_start is not None else cash_start
                merged, cash_warnings = merge_cash_into_value_timeseries(
                    raw_ts,
                    scope=child_scope,
                    display_currency=disp_ccy,
                    start_date=loop_start,
                    end_date=today,
                )
                warnings.extend(cash_warnings)
                merged, fb_warnings = _apply_fd_bank_to_return_timeseries(
                    merged,
                    user=user,
                    scope=child_scope,
                    disp_ccy=disp_ccy,
                    today=today,
                    emit_start=emit_start,
                    include_fd=True,
                    include_bank=False,
                )
                warnings.extend(fb_warnings)
                child_series.append(merged)
                continue

            if not child_txns:
                merged, fb_warnings = _apply_fd_bank_to_return_timeseries(
                    [],
                    user=user,
                    scope=child_scope,
                    disp_ccy=disp_ccy,
                    today=today,
                    emit_start=emit_start,
                    include_fd=True,
                    include_bank=False,
                )
                if merged:
                    warnings.extend(fb_warnings)
                    child_series.append(merged)
                continue

            portfolio_base = portfolio_base_currency(child_txns)
            raw_ts = build_portfolio_value_timeseries(
                child_txns,
                transactions_by_symbol(queryset),
                transactions_by_mf_holding(queryset),
                emit_start_date=emit_start,
            )
            if not raw_ts:
                continue
            converted = _convert_investment_ts_to_display(
                raw_ts,
                portfolio_base=portfolio_base,
                disp_ccy=disp_ccy,
                emit_start=emit_start,
            )
            merged, fb_warnings = _apply_fd_bank_to_return_timeseries(
                converted,
                user=user,
                scope=child_scope,
                disp_ccy=disp_ccy,
                today=today,
                emit_start=emit_start,
                include_fd=True,
                include_bank=False,
            )
            warnings.extend(fb_warnings)
            child_series.append(merged)
        aggregated, agg_warnings = _aggregate_timeseries_lists(child_series), warnings
        merged, bank_warnings = _apply_fd_bank_to_return_timeseries(
            aggregated,
            user=user,
            scope=scope,
            disp_ccy=disp_ccy,
            today=today,
            emit_start=emit_start,
            include_fd=False,
            include_bank=True,
        )
        return merged, agg_warnings + bank_warnings

    portfolio = Portfolio.objects.filter(pk=scope.portfolio_ids[0]).first()
    if portfolio is None:
        return [], warnings

    if portfolio.cash_aware_enabled:
        if all_txns:
            raw_ts = build_portfolio_value_timeseries(
                all_txns, by_symbol, by_mf, emit_start_date=emit_start
            )
        else:
            raw_ts = []
        cash_start = cash_ledger_inception_date(scope) or today
        loop_start = emit_start if emit_start is not None else cash_start
        merged, cash_warnings = merge_cash_into_value_timeseries(
            raw_ts,
            scope=scope,
            display_currency=disp_ccy,
            start_date=loop_start,
            end_date=today,
        )
        warnings.extend(cash_warnings)
        merged, fb_warnings = _apply_fd_bank_to_return_timeseries(
            merged,
            user=user,
            scope=scope,
            disp_ccy=disp_ccy,
            today=today,
            emit_start=emit_start,
        )
        warnings.extend(fb_warnings)
        return merged, warnings

    if not all_txns:
        merged, fb_warnings = _apply_fd_bank_to_return_timeseries(
            [],
            user=user,
            scope=scope,
            disp_ccy=disp_ccy,
            today=today,
            emit_start=emit_start,
        )
        return merged, warnings + fb_warnings

    raw_ts = build_portfolio_value_timeseries(
        all_txns, by_symbol, by_mf, emit_start_date=emit_start
    )
    portfolio_base = portfolio_base_currency(all_txns)
    converted = _convert_investment_ts_to_display(
        raw_ts,
        portfolio_base=portfolio_base,
        disp_ccy=disp_ccy,
        emit_start=emit_start,
    )
    merged, fb_warnings = _apply_fd_bank_to_return_timeseries(
        converted,
        user=user,
        scope=scope,
        disp_ccy=disp_ccy,
        today=today,
        emit_start=emit_start,
    )
    return merged, warnings + fb_warnings


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


def _cumulative_return_points(
    timeseries_full: list[dict],
    flows_by_date: dict[date, Decimal],
    flows_unknown_from: Optional[date],
    *,
    range_start_iso: str,
    metric_currency: str,
) -> list[PerformancePoint]:
    out: list[PerformancePoint] = []
    for p in timeseries_full:
        d = date.fromisoformat(p["date"])
        if p["date"] < range_start_iso:
            continue
        pv = p.get("portfolio_value")
        if pv is None or not portfolio_flows_known_on_date(flows_unknown_from, d):
            out.append(
                PerformancePoint(
                    date=p["date"],
                    value=None,
                    metric="cumulative_return",
                    currency=metric_currency,
                )
            )
            continue
        contrib, withdraw = contributions_and_withdrawals_through(flows_by_date, d)
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
        val = ((Decimal(str(pv)) + withdraw - contrib) / contrib) * Decimal("100")
        out.append(
            PerformancePoint(
                date=p["date"],
                value=float(val),
                metric="cumulative_return",
                currency=metric_currency,
            )
        )
    return out


def _merge_fd_bank_for_value_series(
    timeseries_full: list[dict],
    *,
    user,
    scope: ResolvedPortfolioScope,
    disp_ccy: str,
    start_date: date,
    end_date: date,
) -> tuple[list[dict], list[str]]:
    """FD-ACC-8B: add FD principal and included bank cash to value metric only."""
    return merge_fd_bank_into_value_timeseries(
        timeseries_full,
        user=user,
        scope=scope,
        display_currency=disp_ccy,
        start_date=start_date,
        end_date=end_date,
    )


def build_portfolio_performance(
    *,
    scope: ResolvedPortfolioScope,
    metric: MetricCode,
    range_code: str,
    display_currency: str,
    today: date | None = None,
    user=None,
) -> PerformanceSeriesResult:
    today = today or portfolio_dates.current_date()
    queryset = fifo_eligible_queryset(scope.portfolio_ids)
    all_txns = list(queryset)
    disp_ccy = norm_display_currency(display_currency)
    use_all_scope_display = scope.kind == "all_active"

    if not all_txns:
        has_cash = scope_has_cash_ledger_entries(scope)
        cash_aware_only = (
            scope.kind == "all_active" or _single_portfolio_cash_aware_returns(scope)
        )
        if metric == "value":
            fd_bank_start = value_timeseries_inception_date(user, scope, today=today) if user else None
            cash_inception = cash_ledger_inception_date(scope) or today
            inception_candidates = [today]
            if fd_bank_start:
                inception_candidates.append(fd_bank_start)
            if has_cash:
                inception_candidates.append(cash_inception)
            series_inception = min(inception_candidates)
            range_start = resolve_performance_range_start(
                range_code, today, series_inception
            )
            emit_start = None if range_code == "ALL" else range_start
            loop_start = emit_start if emit_start is not None else series_inception
            timeseries_full, value_warnings = merge_cash_into_value_timeseries(
                [],
                scope=scope,
                display_currency=disp_ccy,
                start_date=loop_start,
                end_date=today,
            )
            timeseries_full, fb_warnings = _merge_fd_bank_for_value_series(
                timeseries_full,
                user=user,
                scope=scope,
                disp_ccy=disp_ccy,
                start_date=loop_start,
                end_date=today,
            )
            value_warnings = list(value_warnings) + list(fb_warnings)
            if not timeseries_full:
                return PerformanceSeriesResult(points=[])
            range_start_iso = range_start.isoformat()
            out: list[PerformancePoint] = []
            for p in timeseries_full:
                if p["date"] < range_start_iso:
                    continue
                pv = p.get("portfolio_value")
                out.append(
                    PerformancePoint(
                        date=p["date"],
                        value=float(pv) if pv is not None else None,
                        metric="value",
                        currency=disp_ccy,
                    )
                )
            return PerformanceSeriesResult(points=out, warnings=value_warnings)
        if metric in {"twror", "cumulative_return"}:
            fd_bank_start = (
                value_timeseries_inception_date(user, scope, today=today) if user else None
            )
            cash_inception = cash_ledger_inception_date(scope) or today
            inception_candidates = [today]
            if fd_bank_start:
                inception_candidates.append(fd_bank_start)
            if has_cash:
                inception_candidates.append(cash_inception)
            series_inception = min(inception_candidates)
            if not (has_cash and cash_aware_only) and not fd_bank_start:
                return PerformanceSeriesResult(points=[])
            range_start = resolve_performance_range_start(
                range_code, today, series_inception
            )
            emit_start = None if range_code == "ALL" else range_start
            timeseries_full, return_warnings = build_return_value_timeseries(
                scope=scope,
                all_txns=all_txns,
                by_symbol={},
                by_mf={},
                disp_ccy=disp_ccy,
                emit_start=emit_start,
                today=today,
                user=user,
            )
            if not timeseries_full:
                return PerformanceSeriesResult(points=[], warnings=return_warnings)
            range_start_iso = range_start.isoformat()
            if use_all_scope_display:
                flows_by_date, flows_unknown_from = build_all_scope_external_flows(
                    scope, disp_ccy, user=user
                )
            else:
                flows_by_date, flows_unknown_from = portfolio_external_flows_for_scope(
                    scope,
                    all_txns=all_txns,
                    calculation_currency=disp_ccy,
                    user=user,
                )
            metric_warnings = list(return_warnings)
            if flows_unknown_from is not None:
                metric_warnings.append(RETURN_FLOWS_FX_WARNING)
            if metric == "cumulative_return":
                out = _cumulative_return_points(
                    timeseries_full,
                    flows_by_date,
                    flows_unknown_from,
                    range_start_iso=range_start_iso,
                    metric_currency=disp_ccy,
                )
                return PerformanceSeriesResult(points=out, warnings=metric_warnings)
            ts_use = (
                timeseries_full
                if range_code == "ALL"
                else [p for p in timeseries_full if p["date"] >= range_start_iso]
            )
            twror_pts = compute_twror_series(
                ts_use, flows_by_date, flows_unknown_from=flows_unknown_from
            )
            return PerformanceSeriesResult(
                points=[
                    PerformancePoint(
                        date=p.date.isoformat(),
                        value=float(p.value) if p.value is not None else None,
                        metric="twror",
                        currency=disp_ccy,
                    )
                    for p in twror_pts
                ],
                warnings=metric_warnings,
            )
        return PerformanceSeriesResult(points=[])

    by_symbol = transactions_by_symbol(queryset)
    by_mf = transactions_by_mf_holding(queryset)
    base_currency = portfolio_base_currency(all_txns)

    inception = min(t.date for t in all_txns)
    fd_bank_start = (
        value_timeseries_inception_date(user, scope, today=today) if user else None
    )
    series_inception = min(inception, fd_bank_start) if fd_bank_start else inception
    range_start = resolve_performance_range_start(range_code, today, series_inception)
    range_start_iso = range_start.isoformat()
    emit_start = None if range_code == "ALL" else range_start
    value_warnings: list[str] = []

    if use_all_scope_display:
        inv_ts = build_all_scope_portfolio_value_timeseries(
            scope, disp_ccy, emit_start_date=emit_start
        )
    else:
        inv_ts = build_portfolio_value_timeseries(
            all_txns, by_symbol, by_mf, emit_start_date=emit_start
        )

    if metric == "value":
        if inv_ts:
            ts_start = date.fromisoformat(inv_ts[0]["date"])
            ts_end = date.fromisoformat(inv_ts[-1]["date"])
            loop_start = min(ts_start, fd_bank_start) if fd_bank_start else ts_start
            timeseries_full, value_warnings = merge_cash_into_value_timeseries(
                inv_ts,
                scope=scope,
                display_currency=disp_ccy,
                start_date=loop_start,
                end_date=ts_end,
            )
        else:
            cash_start = cash_ledger_inception_date(scope) or today
            loop_start_candidates = [cash_start]
            if fd_bank_start:
                loop_start_candidates.append(fd_bank_start)
            loop_start = min(loop_start_candidates)
            if emit_start is not None:
                loop_start = min(loop_start, emit_start)
            timeseries_full, value_warnings = merge_cash_into_value_timeseries(
                [],
                scope=scope,
                display_currency=disp_ccy,
                start_date=loop_start,
                end_date=today,
            )
        ts_end = (
            date.fromisoformat(timeseries_full[-1]["date"])
            if timeseries_full
            else today
        )
        ts_start = (
            date.fromisoformat(timeseries_full[0]["date"]) if timeseries_full else loop_start
        )
        timeseries_full, fb_warnings = _merge_fd_bank_for_value_series(
            timeseries_full,
            user=user,
            scope=scope,
            disp_ccy=disp_ccy,
            start_date=ts_start,
            end_date=ts_end,
        )
        value_warnings = list(value_warnings) + list(fb_warnings)
        if not timeseries_full:
            return PerformanceSeriesResult(points=[])

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
        return PerformanceSeriesResult(points=out, warnings=value_warnings)

    timeseries_full, return_warnings = build_return_value_timeseries(
        scope=scope,
        all_txns=all_txns,
        by_symbol=by_symbol,
        by_mf=by_mf,
        disp_ccy=disp_ccy,
        emit_start=emit_start,
        today=today,
        user=user,
    )
    if not timeseries_full:
        return PerformanceSeriesResult(points=[], warnings=return_warnings)

    cash_aware_returns = (
        scope.kind == "all_active"
        or _single_portfolio_cash_aware_returns(scope)
    )
    has_fd_bank_wealth = (
        user is not None
        and value_timeseries_inception_date(user, scope, today=today) is not None
    )
    if use_all_scope_display or cash_aware_returns or has_fd_bank_wealth:
        flows_by_date, flows_unknown_from = build_all_scope_external_flows(
            scope, disp_ccy, user=user
        ) if use_all_scope_display else portfolio_external_flows_for_scope(
            scope, all_txns=all_txns, calculation_currency=disp_ccy, user=user
        )
        metric_currency = disp_ccy
    else:
        flows_by_date, flows_unknown_from = portfolio_external_flows_for_scope(
            scope, all_txns=all_txns, calculation_currency=base_currency, user=user
        )
        metric_currency = base_currency

    metric_warnings = list(return_warnings)
    if flows_unknown_from is not None:
        metric_warnings.append(RETURN_FLOWS_FX_WARNING)

    if metric == "cumulative_return":
        return PerformanceSeriesResult(
            points=_cumulative_return_points(
                timeseries_full,
                flows_by_date,
                flows_unknown_from,
                range_start_iso=range_start_iso,
                metric_currency=metric_currency,
            ),
            warnings=metric_warnings,
        )

    ts_use = timeseries_full if range_code == "ALL" else [
        p for p in timeseries_full if p["date"] >= range_start_iso
    ]

    twror_pts = compute_twror_series(
        ts_use, flows_by_date, flows_unknown_from=flows_unknown_from
    )
    return PerformanceSeriesResult(
        points=[
            PerformancePoint(
                date=p.date.isoformat(),
                value=float(p.value) if p.value is not None else None,
                metric="twror",
                currency=metric_currency,
            )
            for p in twror_pts
        ],
        warnings=metric_warnings,
    )


def build_portfolio_performance_with_benchmarks(
    *,
    scope: ResolvedPortfolioScope,
    metric: Literal["cumulative_return", "twror"],
    benchmark_symbol: str,
    range_code: str,
    display_currency: str,
    today: date | None = None,
    user=None,
) -> PerformanceComparisonResult:
    cfg = _get_benchmark_config(benchmark_symbol)
    if not cfg:
        raise BenchmarkConfigError(
            f"Unknown or disabled benchmark symbol: {benchmark_symbol!r}"
        )

    result = build_portfolio_performance(
        scope=scope,
        metric=metric,
        range_code=range_code,
        display_currency=display_currency,
        today=today,
        user=user,
    )
    pts = result.points

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
