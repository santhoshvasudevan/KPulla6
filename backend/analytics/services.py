"""
Portfolio and asset Metric Sheet orchestration (Django allowed).

Data flow (read path, cached DB only)
-------------------------------------
Asset/portfolio value timeseries + external flows
→ ``ValuePoint`` series + net flows per date
→ ``daily_returns_from_values`` (fractional daily returns, not TWROR percent)
→ ``performance_stats`` / ``risk_metrics`` / ``drawdowns`` / optional ``comparison``

Non-``ALL`` ranges slice the value/flow series from ``range_start`` onward (re-chain
window, matching ``build_portfolio_performance`` TWROR behavior). **XIRR** is an
exception: it is always full-scope (inception through today), not range-sliced; the
response includes ``xirr_scope: "full_scope"``.

Return and risk ratios are dimensionless fractions from same-currency value and flow
inputs. **Cumulative return** and **CAGR** in ``metrics.return`` use the money-weighted
formula aligned with ``GET /portfolio/performance?metric=cumulative_return`` (not
compounded TWROR daily returns). **TWROR** matches the performance chart TWROR series.
Risk metrics still use TWROR-style daily returns from values and flows. The
``currency`` field is valuation/display context only.

Benchmark metrics use simple daily price returns from cached INDEX rows (no chart
rebase from ``finance.benchmarks``).

Stock valuation invariant (Metric Sheet + summary/performance)
---------------------------------------------------------------
``build_split_adjusted_lot_snapshots`` scales pre-split transaction quantities.
Cached stock ``HistoricalPrice`` rows must therefore be **split-adjusted** closes
(yfinance ``Adj Close`` via ``make sync-prices``). Raw nominal pre-split prices
combined with split-adjusted quantity produce false value spikes and Metric Sheet
returns; see ``_split_adjusted_price_inconsistency_warnings``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Optional

from django.core.exceptions import ObjectDoesNotExist

from finance.comparison import (
    align_multi_subject_returns,
    benchmark_summary,
    normalized_cumulative_return_series,
)
from finance.drawdowns import (
    calmar_ratio,
    drawdown_series,
    longest_drawdown_days,
    max_drawdown,
    worst_drawdown_periods,
)
from finance.mutual_fund_cashflows import MutualFundCashflowEvent, merge_portfolio_xirr
from finance.performance_stats import (
    cagr_from_total_return,
    contributions_and_withdrawals_through,
    economic_cumulative_return_fraction,
    period_summary,
)
from finance.performance_range import resolve_performance_range_start
from finance.returns import (
    DailyReturnPoint,
    PeriodReturnPoint,
    ValuePoint,
    daily_returns_from_values,
    resample_monthly_returns,
    resample_yearly_returns,
)
from finance.risk_metrics import (
    annualized_volatility,
    downside_deviation,
    sharpe_ratio,
    sortino_ratio,
)
from finance.fifo import build_split_adjusted_lot_snapshots
from finance.splits import apply_stock_split_adjustments
from finance.twror import compute_twror_series
from finance.types import TransactionType
from finance.xirr import calculate_xirr
from market_data.nav_lookup import latest_nav_for_asset, normalize_scheme_code
from market_data.price_lookup import normalize_asset_symbol
from market_data.price_repository import list_index_prices_in_range, list_stock_prices_in_range
from portfolios import dates as portfolio_dates
from portfolios.holdings_service import AssetDetailValidationError, AssetNotFoundError
from portfolios.models import Portfolio
from portfolios.performance_service import (
    BenchmarkConfigError,
    build_all_scope_external_flows,
    portfolio_external_flows,
    portfolio_flows_known_on_date,
)
from portfolios.scope import ResolvedPortfolioScope
from portfolios.summary_service import (
    MF_BASE_CURRENCY,
    build_all_scope_portfolio_value_timeseries,
    build_portfolio_value_timeseries,
    compute_scope_xirr,
    fifo_eligible_queryset,
    norm_display_currency,
    portfolio_base_currency,
    transactions_by_mf_holding,
    transactions_by_symbol,
)
from transactions.finance_adapter import transaction_to_finance_dto
from transactions.models import Transaction as TransactionModel

_ZERO = Decimal("0")
_SPLIT_RAW_PRICE_RATIO_TOLERANCE = Decimal("0.15")
_SPLIT_RAW_PRICE_MIN_FACTOR = Decimal("1.5")
_WARN_MISSING_STOCK_PRICES = (
    "Cached prices are missing for one or more dates; "
    "Metric Sheet values may be unavailable."
)
MF_NAV_STALE_AFTER_DAYS = 5
_WARN_MISSING_MF_NAVS = (
    "No cached NAV is available for one or more mutual funds; "
    "run NAV sync to load valuations."
)
_WARN_STALE_MF_NAVS = (
    "Latest cached NAV is older than 5 days for one or more mutual funds; "
    "run NAV sync to refresh valuations."
)
_MF_NAV_QUALITY_WARNINGS = frozenset({_WARN_MISSING_MF_NAVS, _WARN_STALE_MF_NAVS})


@dataclass(frozen=True)
class PerformanceMetricsResult:
    payload: dict[str, Any]


@dataclass(frozen=True)
class CompareResult:
    payload: dict[str, Any]


@dataclass(frozen=True)
class AssetDailyMetricsInputs:
    ctx: ResolvedAssetMetricsContext
    daily_pts: list[DailyReturnPoint]
    daily_fracs: list
    ts_use: list[dict]
    flows_by_date: dict[date, Decimal]
    flows_unknown_from: Optional[date]
    window_start: date
    window_end: date
    xirr_val: Optional[float]
    warnings: list[str]


class CompareSubjectsError(ValueError):
    """Invalid compare `subjects` query parameter."""


@dataclass(frozen=True)
class ParsedCompareSubject:
    subject_id: str
    asset_symbol: str


@dataclass(frozen=True)
class ResolvedAssetMetricsContext:
    asset_symbol: str
    display_name: str
    folio_number: str | None
    is_mutual_fund: bool
    asset_txns: list[TransactionModel]
    base_currency: str


def parse_compare_subjects(raw: str | None) -> list[ParsedCompareSubject]:
    """Parse `subjects=asset:AAPL,asset:MSFT` (MVP: exactly two asset subjects)."""
    if raw is None or not str(raw).strip():
        raise CompareSubjectsError("subjects is required")

    parts = [p.strip() for p in str(raw).split(",") if p.strip()]
    if len(parts) != 2:
        raise CompareSubjectsError("Exactly two subjects are required for compare (MVP)")

    parsed: list[ParsedCompareSubject] = []
    for part in parts:
        if ":" not in part:
            raise CompareSubjectsError(
                f"Invalid subject format: {part!r} (expected asset:<symbol>)"
            )
        subject_type, symbol = part.split(":", 1)
        subject_type = subject_type.strip().lower()
        symbol = symbol.strip()
        if subject_type != "asset":
            raise CompareSubjectsError(
                f"Unsupported subject type: {subject_type!r} (MVP supports asset only)"
            )
        if not symbol:
            raise CompareSubjectsError(f"Invalid subject format: {part!r}")
        parsed.append(ParsedCompareSubject(subject_id=part, asset_symbol=symbol))
    return parsed


def _float_or_none(value: Decimal | float | None) -> float | None:
    if value is None:
        return None
    return float(value)


def _is_mutual_fund_transaction(txn: TransactionModel) -> bool:
    try:
        txn.mutual_fund_detail
    except ObjectDoesNotExist:
        return False
    return True


def _mf_holding_key(scheme_code: str, folio_number: str) -> str:
    return f"{normalize_scheme_code(scheme_code)}:{folio_number.strip()}"


def _scheme_name_for_mf_txns(db_txns: list[TransactionModel]) -> str:
    for txn in db_txns:
        profile = getattr(
            txn.mutual_fund_detail.folio.asset,
            "mutual_fund_profile",
            None,
        )
        if profile is not None:
            return profile.scheme_name
    return normalize_scheme_code(db_txns[0].asset_symbol)


def _mf_cashflow_events(db_txns: list[TransactionModel]) -> list[MutualFundCashflowEvent]:
    events: list[MutualFundCashflowEvent] = []
    for txn in db_txns:
        if not _is_mutual_fund_transaction(txn):
            continue
        detail = txn.mutual_fund_detail
        if txn.type == TransactionType.BUY.value:
            events.append(
                MutualFundCashflowEvent(
                    flow_date=detail.investment_date,
                    amount=-Decimal(detail.paid_value),
                )
            )
        elif txn.type == TransactionType.SELL.value:
            events.append(
                MutualFundCashflowEvent(
                    flow_date=detail.investment_date,
                    amount=Decimal(detail.paid_value),
                )
            )
    return events


def _to_fifo_dtos(db_txns: list[TransactionModel]):
    return [
        transaction_to_finance_dto(t)
        for t in db_txns
        if t.type
        in {
            TransactionType.BUY.value,
            TransactionType.SELL.value,
            TransactionType.STOCK_SPLIT.value,
        }
    ]


def _subject_block(
    scope: ResolvedPortfolioScope,
    *,
    display_currency: str,
) -> dict[str, Any]:
    if scope.kind == "single":
        portfolio = Portfolio.objects.filter(pk=scope.portfolio_ids[0]).first()
        name = portfolio.name if portfolio else f"Portfolio {scope.portfolio_ids[0]}"
        return {
            "type": "portfolio",
            "portfolio_scope": None,
            "portfolio_id": scope.portfolio_ids[0],
            "name": name,
        }
    return {
        "type": "portfolio",
        "portfolio_scope": "all",
        "portfolio_id": None,
        "name": "All Portfolios",
    }


def _asset_subject_block(
    scope: ResolvedPortfolioScope,
    *,
    asset_symbol: str,
    name: str,
    folio_number: str | None,
) -> dict[str, Any]:
    base: dict[str, Any] = {
        "type": "asset",
        "asset_symbol": asset_symbol,
        "name": name,
        "folio_number": folio_number,
    }
    if scope.kind == "single":
        return {
            **base,
            "portfolio_scope": None,
            "portfolio_id": scope.portfolio_ids[0],
        }
    return {
        **base,
        "portfolio_scope": "all",
        "portfolio_id": None,
    }


def _timeseries_to_value_points(
    rows: list[dict],
    *,
    flows_unknown_from: Optional[date],
) -> list[ValuePoint]:
    points: list[ValuePoint] = []
    for row in rows:
        d = date.fromisoformat(row["date"])
        if not portfolio_flows_known_on_date(flows_unknown_from, d):
            points.append(ValuePoint(date=d, value=None))
            continue
        pv_raw = row.get("portfolio_value")
        if pv_raw is None:
            points.append(ValuePoint(date=d, value=None))
        else:
            points.append(ValuePoint(date=d, value=Decimal(str(pv_raw))))
    return points


def _benchmark_daily_returns(
    symbol: str,
    window_start: date,
    window_end: date,
) -> list[DailyReturnPoint]:
    """Daily fractional returns from cached INDEX close prices (no external calls)."""
    rows = list_index_prices_in_range(symbol, window_start, window_end)
    if not rows:
        return []

    out: list[DailyReturnPoint] = []
    prev_price: Optional[Decimal] = None
    for row in rows:
        price = Decimal(str(row.close_price))
        if prev_price is None or prev_price <= _ZERO:
            out.append(DailyReturnPoint(date=row.date, return_fraction=None))
        else:
            r = (price - prev_price) / prev_price
            out.append(DailyReturnPoint(date=row.date, return_fraction=r))
        prev_price = price
    return out


def _get_benchmark_config(symbol: str):
    from market_data.models import BenchmarkIndexConfig

    sym = (symbol or "").strip()
    if not sym:
        return None
    return (
        BenchmarkIndexConfig.objects.filter(symbol__iexact=sym, enabled=True).first()
    )


def _twror_cumulative_fraction(
    ts_rows: list[dict],
    flows_by_date: dict[date, Decimal],
    flows_unknown_from: Optional[date],
) -> Optional[Decimal]:
    """Last cumulative TWROR in the sliced window as a fraction (from percent points)."""
    twror_pts = compute_twror_series(
        ts_rows, flows_by_date, flows_unknown_from=flows_unknown_from
    )
    for pt in reversed(twror_pts):
        if pt.value is not None:
            return pt.value / Decimal("100")
    return None


def _economic_cumulative_return_fraction(
    ts_rows: list[dict],
    flows_by_date: dict[date, Decimal],
    flows_unknown_from: Optional[date],
    window_end: date,
) -> Optional[Decimal]:
    """Terminal money-weighted cumulative return for the sliced window (performance chart)."""
    terminal_value: Decimal | None = None
    terminal_date: date | None = None
    for row in reversed(ts_rows):
        d = date.fromisoformat(row["date"])
        if d > window_end:
            continue
        if not portfolio_flows_known_on_date(flows_unknown_from, d):
            return None
        pv = row.get("portfolio_value")
        if pv is not None:
            terminal_value = Decimal(str(pv))
            terminal_date = d
            break
    if terminal_value is None or terminal_date is None:
        return None
    contrib, withdraw = contributions_and_withdrawals_through(
        flows_by_date, terminal_date
    )
    return economic_cumulative_return_fraction(
        terminal_value=terminal_value,
        contributions=contrib,
        withdrawals=withdraw,
    )


def _terminal_value_from_timeseries(timeseries_full: list[dict]) -> Decimal:
    for row in reversed(timeseries_full):
        pv = row.get("portfolio_value")
        if pv is not None:
            return Decimal(str(pv))
    return Decimal("0")


def _forward_fill_qty_by_day(
    timeline: dict[date, Decimal],
    window_start: date,
    window_end: date,
) -> dict[date, Decimal]:
    """Expand event-based quantity changes to each calendar day in the window."""
    out: dict[date, Decimal] = {}
    current = Decimal("0")
    event_dates = sorted(timeline.keys())
    idx = 0
    d = window_start
    while d <= window_end:
        while idx < len(event_dates) and event_dates[idx] <= d:
            current = timeline[event_dates[idx]]
            idx += 1
        out[d] = current
        d += timedelta(days=1)
    return out


def _mf_qty_timeline(txns: list[TransactionModel]) -> dict[date, Decimal]:
    adjusted = _to_fifo_dtos(txns)
    txns_sorted = sorted(adjusted, key=lambda x: x.date)
    timeline: dict[date, Decimal] = {}
    lots: list[dict[str, Decimal]] = []

    for t in txns_sorted:
        if t.type == TransactionType.BUY:
            if t.quantity > 0:
                lots.append({"qty": t.quantity, "unit_cost": t.price})
        elif t.type == TransactionType.SELL:
            remaining = t.quantity
            while remaining > 0 and lots:
                lot = lots[0]
                take = min(lot["qty"], remaining)
                lot["qty"] -= take
                remaining -= take
                if lot["qty"] <= 0:
                    lots.pop(0)
        timeline[t.date] = sum(l["qty"] for l in lots)
    return timeline


def _stock_missing_cached_prices_in_window(
    sym: str,
    txns: list[TransactionModel],
    window_start: date,
    window_end: date,
) -> bool:
    timeline, _ = build_split_adjusted_lot_snapshots(_to_fifo_dtos(txns))
    if not timeline:
        return False

    sym_key = normalize_asset_symbol(sym)
    prices = list_stock_prices_in_range([sym_key], window_start, window_end)
    price_by_date = {p.date: p for p in prices}
    qty_by_day = _forward_fill_qty_by_day(timeline, window_start, window_end)

    last_price = None
    d = window_start
    while d <= window_end:
        if d in price_by_date:
            last_price = price_by_date[d]
        if qty_by_day.get(d, _ZERO) > _ZERO and last_price is None:
            return True
        d += timedelta(days=1)
    return False


def _has_mf_nav_quality_warning(warnings: list[str]) -> bool:
    return any(w in _MF_NAV_QUALITY_WARNINGS for w in warnings)


def _mf_has_holdings_in_window(
    txns: list[TransactionModel],
    window_start: date,
    window_end: date,
) -> bool:
    timeline = _mf_qty_timeline(txns)
    if not timeline:
        return False

    qty_by_day = _forward_fill_qty_by_day(timeline, window_start, window_end)
    d = window_start
    while d <= window_end:
        if qty_by_day.get(d, _ZERO) > _ZERO:
            return True
        d += timedelta(days=1)
    return False


def _mf_nav_freshness_issue(
    scheme: str,
    txns: list[TransactionModel],
    window_start: date,
    window_end: date,
) -> str | None:
    """
    Return ``missing`` or ``stale`` when an MF NAV warning is warranted, else None.

    Uses latest cached NAV age vs ``window_end``. Weekend/holiday gaps are acceptable
    when the latest cached NAV is recent enough for forward-fill.
    """
    if not _mf_has_holdings_in_window(txns, window_start, window_end):
        return None

    scheme_key = normalize_scheme_code(scheme)
    nav_result = latest_nav_for_asset(scheme_key)
    if (
        nav_result is None
        or nav_result.status != "ok"
        or nav_result.nav is None
        or nav_result.date is None
    ):
        return "missing"

    if (window_end - nav_result.date).days > MF_NAV_STALE_AFTER_DAYS:
        return "stale"

    return None


def _valuation_coverage_warnings(
    *,
    window_start: date,
    window_end: date,
    by_symbol: dict[str, list[TransactionModel]] | None = None,
    by_mf: dict[str, list[TransactionModel]] | None = None,
    asset_ctx: ResolvedAssetMetricsContext | None = None,
) -> list[str]:
    """Calm data-quality warnings when cached prices or NAVs are missing in-range."""
    warnings: list[str] = []

    if asset_ctx is not None:
        if asset_ctx.is_mutual_fund:
            issue = _mf_nav_freshness_issue(
                asset_ctx.asset_symbol,
                asset_ctx.asset_txns,
                window_start,
                window_end,
            )
            if issue == "missing":
                warnings.append(_WARN_MISSING_MF_NAVS)
            elif issue == "stale":
                warnings.append(_WARN_STALE_MF_NAVS)
        elif _stock_missing_cached_prices_in_window(
            asset_ctx.asset_symbol,
            asset_ctx.asset_txns,
            window_start,
            window_end,
        ):
            warnings.append(_WARN_MISSING_STOCK_PRICES)
        return warnings

    stock_missing = False
    for sym, txns in (by_symbol or {}).items():
        if _stock_missing_cached_prices_in_window(sym, txns, window_start, window_end):
            stock_missing = True
            break
    if stock_missing:
        warnings.append(_WARN_MISSING_STOCK_PRICES)

    mf_missing = False
    mf_stale = False
    for txns in (by_mf or {}).values():
        scheme = normalize_scheme_code(txns[0].asset_symbol)
        issue = _mf_nav_freshness_issue(scheme, txns, window_start, window_end)
        if issue == "missing":
            mf_missing = True
        elif issue == "stale":
            mf_stale = True
    if mf_missing:
        warnings.append(_WARN_MISSING_MF_NAVS)
    if mf_stale:
        warnings.append(_WARN_STALE_MF_NAVS)

    return warnings


def _split_symbol_timeseries_cache(
    by_symbol: dict[str, list[TransactionModel]],
) -> dict[str, list[dict]]:
    """Pre-build per-symbol value series only for symbols with stock splits."""
    cache: dict[str, list[dict]] = {}
    for sym, txns in by_symbol.items():
        has_split = any(
            t.type == TransactionType.STOCK_SPLIT.value
            and t.split_from
            and t.split_to
            and Decimal(t.split_from) > 0
            and Decimal(t.split_to) > 0
            for t in txns
        )
        if has_split:
            cache[sym] = build_portfolio_value_timeseries(txns, {sym: txns}, {})
    return cache


def _split_adjusted_price_inconsistency_warnings(
    *,
    by_symbol: dict[str, list[TransactionModel]],
    timeseries_by_symbol: dict[str, list[dict]] | None = None,
) -> list[str]:
    """
    Detect likely raw (non-split-adjusted) cached prices when STOCK_SPLIT rows exist.

    Compares holding value immediately before vs after each split date on a per-symbol
    mini timeseries. When the drop ratio matches the split factor (e.g. 10 for 1:10),
    cached prices are probably nominal, not Adj Close — Metric Sheet returns would be
    unreliable around the split.
    """
    warnings: list[str] = []
    for sym, txns in by_symbol.items():
        splits = [
            t
            for t in txns
            if t.type == TransactionType.STOCK_SPLIT.value
            and t.split_from
            and t.split_to
            and Decimal(t.split_from) > 0
            and Decimal(t.split_to) > 0
        ]
        if not splits:
            continue

        sym_ts = (timeseries_by_symbol or {}).get(sym)
        if sym_ts is None:
            sym_ts = build_portfolio_value_timeseries(txns, {sym: txns}, {})
        if not sym_ts:
            continue
        by_date = {row["date"]: row for row in sym_ts}
        sorted_dates = sorted(by_date.keys())

        for split in splits:
            factor = Decimal(split.split_to) / Decimal(split.split_from)
            if factor < _SPLIT_RAW_PRICE_MIN_FACTOR:
                continue
            split_iso = split.date.isoformat()

            v_before: Decimal | None = None
            for d in reversed(sorted_dates):
                if d >= split_iso:
                    continue
                pv = by_date[d].get("portfolio_value")
                if pv is not None and float(pv) > 0:
                    v_before = Decimal(str(pv))
                    break

            v_after: Decimal | None = None
            for d in sorted_dates:
                if d < split_iso:
                    continue
                pv = by_date[d].get("portfolio_value")
                if pv is not None and float(pv) > 0:
                    v_after = Decimal(str(pv))
                    break

            if v_before is None or v_after is None or v_after <= _ZERO:
                continue

            ratio = v_before / v_after
            if ratio < _SPLIT_RAW_PRICE_MIN_FACTOR:
                continue
            rel_err = abs(ratio - factor) / factor
            if rel_err <= _SPLIT_RAW_PRICE_RATIO_TOLERANCE:
                warnings.append(
                    f"Cached historical prices for {normalize_asset_symbol(sym)} may not be "
                    "split-adjusted; Metric Sheet returns around stock splits may be unreliable. "
                    "Stock price sync uses yfinance Adj Close (split-adjusted)."
                )
                break

    return warnings


def _compute_asset_xirr(
    *,
    ctx: ResolvedAssetMetricsContext,
    terminal_value: Decimal,
    today: date,
) -> Optional[float]:
    if not ctx.asset_txns:
        return None
    if ctx.is_mutual_fund:
        return merge_portfolio_xirr(
            [],
            _mf_cashflow_events(ctx.asset_txns),
            terminal_value=terminal_value,
            current_date=today,
            include_fees_in_cashflows=True,
        )
    stock_dtos = apply_stock_split_adjustments(_to_fifo_dtos(ctx.asset_txns))
    qty = Decimal("0")
    for t in stock_dtos:
        if t.type == TransactionType.BUY:
            qty += t.quantity
        elif t.type == TransactionType.SELL:
            qty -= t.quantity
    current_price = terminal_value / qty if qty > _ZERO else Decimal("0")
    return calculate_xirr(
        stock_dtos,
        current_price=current_price,
        current_date=today,
        include_fees_in_cashflows=True,
    )


def _empty_periodic_returns_block() -> dict[str, Any]:
    return {"monthly": [], "yearly": []}


def _empty_drawdown_periods_block() -> dict[str, Any]:
    return {"worst": []}


def _empty_drawdown_series_block() -> list[dict[str, Any]]:
    return []


def _period_return_rows(points: list[PeriodReturnPoint]) -> list[dict[str, Any]]:
    return [
        {"period": p.period, "return": _float_or_none(p.return_fraction)}
        for p in points
    ]


def build_periodic_returns_block(
    daily_pts: list[DailyReturnPoint],
) -> dict[str, Any]:
    """
    Compounded monthly/yearly fractional returns for Metric Sheet APIs.

    ``yearly`` rows are **Calendar-Year Return**: cash-flow-adjusted daily returns
    (TWROR-style ``period_return`` from values and external flows) compounded
    within each calendar year — not simple start-vs-end value change.
    """
    return {
        "monthly": _period_return_rows(resample_monthly_returns(daily_pts)),
        "yearly": _period_return_rows(resample_yearly_returns(daily_pts)),
    }


def build_drawdown_series_block(
    daily_pts: list[DailyReturnPoint],
) -> list[dict[str, Any]]:
    """Running drawdown fractions (0 or negative) for Metric Sheet chart APIs."""
    return [
        {
            "date": pt.date.isoformat(),
            "drawdown": _float_or_none(pt.drawdown_fraction),
        }
        for pt in drawdown_series(daily_pts)
        if pt.date is not None and pt.drawdown_fraction is not None
    ]


def build_drawdown_periods_block(
    daily_pts: list[DailyReturnPoint],
    *,
    limit: int = 10,
) -> dict[str, Any]:
    """Worst drawdown episodes ranked by severity (fractions, not percent)."""
    worst = worst_drawdown_periods(daily_pts, limit=limit)
    return {
        "worst": [
            {
                "rank": rank,
                "start_date": ep.start_date.isoformat(),
                "trough_date": ep.trough_date.isoformat(),
                "recovery_date": (
                    ep.recovery_date.isoformat() if ep.recovery_date else None
                ),
                "drawdown": _float_or_none(ep.drawdown_fraction),
                "days_to_trough": ep.days_to_trough,
                "days_to_recovery": ep.days_to_recovery,
                "recovered": ep.recovered,
            }
            for rank, ep in enumerate(worst, start=1)
        ]
    }


def build_metric_sheet_extension_blocks(
    daily_pts: list[DailyReturnPoint],
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """Periodic returns, drawdown periods, and drawdown series from daily returns."""
    return (
        build_periodic_returns_block(daily_pts),
        build_drawdown_periods_block(daily_pts),
        build_drawdown_series_block(daily_pts),
    )


def _null_metrics_block() -> dict[str, Any]:
    return {
        "return": {
            "cumulative_return": None,
            "cagr": None,
            "xirr": None,
            "xirr_scope": "full_scope",
            "twror": None,
        },
        "risk": {
            "volatility_annualized": None,
            "downside_deviation": None,
            "sharpe_ratio": None,
            "sortino_ratio": None,
        },
        "drawdown": {
            "max_drawdown": None,
            "longest_drawdown_days": None,
            "calmar_ratio": None,
        },
        "periods": {
            "best_day": None,
            "worst_day": None,
            "win_rate": None,
            "average_daily_return": None,
        },
    }


def build_metric_sheet_from_daily_returns(
    *,
    daily_pts: list[DailyReturnPoint],
    daily_fracs: list,
    ts_use: list[dict],
    flows_by_date: dict[date, Decimal],
    flows_unknown_from: Optional[date],
    window_start: date,
    window_end: date,
    xirr_val: Optional[float],
    benchmark_symbol: str | None,
    warnings: list[str],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Assemble return/risk/drawdown/period metrics and optional benchmark block."""
    summary = period_summary(daily_fracs)
    twror_frac = _twror_cumulative_fraction(ts_use, flows_by_date, flows_unknown_from)
    cum_ret = _economic_cumulative_return_fraction(
        ts_use, flows_by_date, flows_unknown_from, window_end
    )

    metrics_block: dict[str, Any] = {
        "return": {
            "cumulative_return": _float_or_none(cum_ret),
            "cagr": _float_or_none(
                cagr_from_total_return(cum_ret, window_start, window_end)
                if cum_ret is not None
                else None
            ),
            "xirr": _float_or_none(
                Decimal(str(xirr_val)) if xirr_val is not None else None
            ),
            "xirr_scope": "full_scope",
            "twror": _float_or_none(twror_frac),
        },
        "risk": {
            "volatility_annualized": _float_or_none(
                annualized_volatility(daily_fracs)
            ),
            "downside_deviation": _float_or_none(downside_deviation(daily_fracs)),
            "sharpe_ratio": _float_or_none(sharpe_ratio(daily_fracs)),
            "sortino_ratio": _float_or_none(sortino_ratio(daily_fracs)),
        },
        "drawdown": {
            "max_drawdown": _float_or_none(max_drawdown(daily_fracs)),
            "longest_drawdown_days": longest_drawdown_days(daily_pts),
            "calmar_ratio": _float_or_none(
                calmar_ratio(daily_fracs, window_start, window_end)
            ),
        },
        "periods": {
            "best_day": _float_or_none(summary.best),
            "worst_day": _float_or_none(summary.worst),
            "win_rate": _float_or_none(summary.win_rate),
            "average_daily_return": _float_or_none(summary.average),
        },
    }

    benchmark_block: dict[str, Any] | None = None
    if benchmark_symbol:
        cfg = _get_benchmark_config(benchmark_symbol)
        if not cfg:
            raise BenchmarkConfigError(
                f"Unknown or disabled benchmark symbol: {benchmark_symbol!r}"
            )
        bench_daily = _benchmark_daily_returns(cfg.symbol, window_start, window_end)
        if not bench_daily:
            warnings.append(
                "Benchmark prices are not in the local database for the selected range."
            )
            bench_metrics = None
            paired = 0
        else:
            b_summary = benchmark_summary(daily_pts, bench_daily)
            paired = b_summary.paired_count
            if paired < 2:
                warnings.append(
                    "Insufficient overlapping benchmark daily returns for comparison metrics."
                )
                bench_metrics = None
            else:
                bench_metrics = {
                    "correlation": _float_or_none(b_summary.correlation),
                    "beta": _float_or_none(b_summary.beta),
                    "alpha": _float_or_none(b_summary.alpha),
                    "active_return": _float_or_none(b_summary.active_return),
                    "tracking_error": _float_or_none(b_summary.tracking_error),
                    "information_ratio": _float_or_none(b_summary.information_ratio),
                    "treynor_ratio": _float_or_none(b_summary.treynor_ratio),
                }
        benchmark_block = {
            "symbol": cfg.symbol,
            "paired_count": paired,
            "metrics": bench_metrics,
        }

    return metrics_block, benchmark_block


def _resolve_asset_metrics_context(
    *,
    asset_symbol: str,
    scope: ResolvedPortfolioScope,
    folio_number: str | None,
) -> ResolvedAssetMetricsContext:
    if not (asset_symbol or "").strip():
        raise AssetNotFoundError("Asset symbol is required")

    base_qs = fifo_eligible_queryset(scope.portfolio_ids)
    stock_sym = normalize_asset_symbol(asset_symbol)
    scheme = normalize_scheme_code(asset_symbol)

    stock_txns = list(
        base_qs.filter(asset_symbol__iexact=stock_sym).exclude(
            mutual_fund_detail__isnull=False
        )
    )
    mf_qs = base_qs.filter(mutual_fund_detail__isnull=False)
    if scheme:
        mf_qs = mf_qs.filter(asset_symbol__iexact=scheme)
    mf_txns = list(mf_qs)

    if mf_txns:
        folios = {t.mutual_fund_detail.folio.folio_number for t in mf_txns}
        folio_filter = (folio_number or "").strip()
        if folio_filter:
            db_txns = [
                t
                for t in mf_txns
                if t.mutual_fund_detail.folio.folio_number == folio_filter
            ]
            if not db_txns:
                raise AssetNotFoundError(
                    f"No transactions found for {asset_symbol} folio {folio_filter}"
                )
            resolved_folio = folio_filter
        elif len(folios) > 1:
            raise AssetDetailValidationError(
                "folio_number is required when multiple folios exist for this scheme"
            )
        else:
            resolved_folio = next(iter(folios))
            db_txns = mf_txns

        display_name = _scheme_name_for_mf_txns(db_txns) or scheme
        return ResolvedAssetMetricsContext(
            asset_symbol=scheme,
            display_name=display_name,
            folio_number=resolved_folio,
            is_mutual_fund=True,
            asset_txns=db_txns,
            base_currency=MF_BASE_CURRENCY,
        )

    if stock_txns:
        return ResolvedAssetMetricsContext(
            asset_symbol=stock_sym,
            display_name=stock_sym,
            folio_number=None,
            is_mutual_fund=False,
            asset_txns=stock_txns,
            base_currency=portfolio_base_currency(stock_txns),
        )

    raise AssetNotFoundError(f"No transactions found for {asset_symbol}")


def _build_asset_value_timeseries(
    ctx: ResolvedAssetMetricsContext,
) -> list[dict]:
    if ctx.is_mutual_fund:
        by_mf = transactions_by_mf_holding(
            TransactionModel.objects.filter(
                pk__in=[t.pk for t in ctx.asset_txns]
            ).select_related(
                "mutual_fund_detail",
                "mutual_fund_detail__folio",
            )
        )
        return build_portfolio_value_timeseries(ctx.asset_txns, {}, by_mf)

    sym = ctx.asset_symbol
    return build_portfolio_value_timeseries(
        ctx.asset_txns,
        {sym: ctx.asset_txns},
        {},
    )


def _slice_timeseries_for_range(
    timeseries_full: list[dict],
    *,
    range_code: str,
    today: date,
    inception: date | None = None,
) -> tuple[list[dict], date, date, date]:
    true_inception = inception or date.fromisoformat(timeseries_full[0]["date"])
    series_end = date.fromisoformat(timeseries_full[-1]["date"])
    range_start = resolve_performance_range_start(range_code, today, true_inception)
    range_start_iso = range_start.isoformat()
    if range_code == "ALL":
        ts_use = timeseries_full
    else:
        ts_use = [p for p in timeseries_full if p["date"] >= range_start_iso]
    window_start = date.fromisoformat(ts_use[0]["date"]) if ts_use else range_start
    window_end = date.fromisoformat(ts_use[-1]["date"]) if ts_use else series_end
    return ts_use, window_start, window_end, range_start


def _slice_timeseries_to_window(
    ts_rows: list[dict],
    window_start: date,
    window_end: date,
) -> list[dict]:
    """Restrict value/timeseries rows to an inclusive date window."""
    start_iso = window_start.isoformat()
    end_iso = window_end.isoformat()
    return [row for row in ts_rows if start_iso <= row["date"] <= end_iso]


def _prepare_asset_daily_metrics_inputs(
    *,
    asset_symbol: str,
    scope: ResolvedPortfolioScope,
    range_code: str,
    folio_number: str | None = None,
    today: date | None = None,
) -> AssetDailyMetricsInputs:
    """Load asset value series and daily returns for Metric Sheet or compare."""
    today = today or portfolio_dates.current_date()
    ctx = _resolve_asset_metrics_context(
        asset_symbol=asset_symbol,
        scope=scope,
        folio_number=folio_number,
    )
    warnings: list[str] = []

    timeseries_full = _build_asset_value_timeseries(ctx)
    if not timeseries_full:
        warnings.append("No asset value history available.")
        return AssetDailyMetricsInputs(
            ctx=ctx,
            daily_pts=[],
            daily_fracs=[],
            ts_use=[],
            flows_by_date={},
            flows_unknown_from=None,
            window_start=today,
            window_end=today,
            xirr_val=None,
            warnings=warnings,
        )

    ts_use, window_start, window_end, _range_start = _slice_timeseries_for_range(
        timeseries_full, range_code=range_code, today=today
    )

    if not ctx.is_mutual_fund:
        warnings.extend(
            _split_adjusted_price_inconsistency_warnings(
                by_symbol={ctx.asset_symbol: ctx.asset_txns},
                timeseries_by_symbol={ctx.asset_symbol: timeseries_full},
            )
        )

    if any(p.get("fx_status") == "fx_unavailable" for p in ts_use):
        warnings.append(
            "FX rates are missing for some asset valuations; returns may be incomplete."
        )

    warnings.extend(
        _valuation_coverage_warnings(
            window_start=window_start,
            window_end=window_end,
            asset_ctx=ctx,
        )
    )
    if not any(p.get("portfolio_value") is not None for p in ts_use) and not any(
        _WARN_MISSING_STOCK_PRICES in w or _has_mf_nav_quality_warning([w]) for w in warnings
    ):
        warnings.append("Asset values are unavailable for the selected range.")

    flows_by_date, flows_unknown_from = portfolio_external_flows(
        ctx.asset_txns, ctx.base_currency
    )
    if flows_unknown_from is not None:
        warnings.append(
            "FX rates are missing for some external cash flows; returns may be incomplete."
        )

    value_points = _timeseries_to_value_points(
        ts_use, flows_unknown_from=flows_unknown_from
    )
    daily_pts = daily_returns_from_values(value_points, flows_by_date)
    daily_fracs = [p.return_fraction for p in daily_pts]

    valid_count = sum(1 for r in daily_fracs if r is not None)
    if valid_count < 2:
        warnings.append("Insufficient daily returns to compute risk metrics.")

    terminal_value = _terminal_value_from_timeseries(timeseries_full)
    xirr_val = _compute_asset_xirr(ctx=ctx, terminal_value=terminal_value, today=today)

    return AssetDailyMetricsInputs(
        ctx=ctx,
        daily_pts=daily_pts,
        daily_fracs=daily_fracs,
        ts_use=ts_use,
        flows_by_date=flows_by_date,
        flows_unknown_from=flows_unknown_from,
        window_start=window_start,
        window_end=window_end,
        xirr_val=xirr_val,
        warnings=warnings,
    )


def build_asset_performance_metrics(
    *,
    asset_symbol: str,
    scope: ResolvedPortfolioScope,
    range_code: str,
    display_currency: str,
    benchmark_symbol: str | None = None,
    folio_number: str | None = None,
    today: date | None = None,
) -> PerformanceMetricsResult:
    today = today or portfolio_dates.current_date()
    inputs = _prepare_asset_daily_metrics_inputs(
        asset_symbol=asset_symbol,
        scope=scope,
        range_code=range_code,
        folio_number=folio_number,
        today=today,
    )
    ctx = inputs.ctx
    warnings = list(inputs.warnings)

    if not inputs.ts_use:
        return PerformanceMetricsResult(
            payload=_empty_asset_payload(
                scope,
                ctx=ctx,
                display_currency=display_currency,
                range_code=range_code,
                today=today,
                warnings=warnings,
                benchmark_symbol=benchmark_symbol,
            )
        )

    metrics_block, benchmark_block = build_metric_sheet_from_daily_returns(
        daily_pts=inputs.daily_pts,
        daily_fracs=inputs.daily_fracs,
        ts_use=inputs.ts_use,
        flows_by_date=inputs.flows_by_date,
        flows_unknown_from=inputs.flows_unknown_from,
        window_start=inputs.window_start,
        window_end=inputs.window_end,
        xirr_val=inputs.xirr_val,
        benchmark_symbol=benchmark_symbol,
        warnings=warnings,
    )
    periodic_returns, drawdown_periods, drawdown_series_block = (
        build_metric_sheet_extension_blocks(inputs.daily_pts)
    )

    payload: dict[str, Any] = {
        "subject": _asset_subject_block(
            scope,
            asset_symbol=ctx.asset_symbol,
            name=ctx.display_name,
            folio_number=ctx.folio_number,
        ),
        "range": {
            "code": range_code,
            "start": inputs.window_start.isoformat(),
            "end": inputs.window_end.isoformat(),
        },
        "currency": display_currency,
        "metrics": metrics_block,
        "periodic_returns": periodic_returns,
        "drawdown_periods": drawdown_periods,
        "drawdown_series": drawdown_series_block,
        "warnings": warnings,
    }
    if benchmark_block is not None:
        payload["benchmark"] = benchmark_block

    return PerformanceMetricsResult(payload=payload)


def _compare_subject_block(
    *,
    subject_id: str,
    ctx: ResolvedAssetMetricsContext,
) -> dict[str, Any]:
    return {
        "id": subject_id,
        "type": "asset",
        "asset_symbol": ctx.asset_symbol,
        "name": ctx.display_name,
        "folio_number": ctx.folio_number,
    }


def _benchmark_block_for_subject(
    *,
    subject_daily_pts: list[DailyReturnPoint],
    benchmark_symbol: str,
    window_start: date,
    window_end: date,
    subject_warnings: list[str],
) -> dict[str, Any] | None:
    cfg = _get_benchmark_config(benchmark_symbol)
    if not cfg:
        raise BenchmarkConfigError(
            f"Unknown or disabled benchmark symbol: {benchmark_symbol!r}"
        )
    bench_daily = _benchmark_daily_returns(cfg.symbol, window_start, window_end)
    if not bench_daily:
        subject_warnings.append(
            "Benchmark prices are not in the local database for the selected range."
        )
        return {
            "symbol": cfg.symbol,
            "paired_count": 0,
            "metrics": None,
        }

    b_summary = benchmark_summary(subject_daily_pts, bench_daily)
    paired = b_summary.paired_count
    if paired < 2:
        subject_warnings.append(
            "Insufficient overlapping benchmark daily returns for comparison metrics."
        )
        bench_metrics = None
    else:
        bench_metrics = {
            "correlation": _float_or_none(b_summary.correlation),
            "beta": _float_or_none(b_summary.beta),
            "alpha": _float_or_none(b_summary.alpha),
            "active_return": _float_or_none(b_summary.active_return),
            "tracking_error": _float_or_none(b_summary.tracking_error),
            "information_ratio": _float_or_none(b_summary.information_ratio),
            "treynor_ratio": _float_or_none(b_summary.treynor_ratio),
        }
    return {
        "symbol": cfg.symbol,
        "paired_count": paired,
        "metrics": bench_metrics,
    }


def build_analytics_compare(
    *,
    subjects: list[ParsedCompareSubject],
    scope: ResolvedPortfolioScope,
    range_code: str,
    display_currency: str,
    benchmark_symbol: str | None = None,
    today: date | None = None,
) -> CompareResult:
    """
    Compare two asset subjects side by side.

    Compare API metrics are computed over common overlapping dates only.
    """
    today = today or portfolio_dates.current_date()
    global_warnings: list[str] = [
        "Compare API metrics are computed over common overlapping dates only."
    ]

    prepared: list[tuple[str, AssetDailyMetricsInputs]] = []
    for subj in subjects:
        inputs = _prepare_asset_daily_metrics_inputs(
            asset_symbol=subj.asset_symbol,
            scope=scope,
            range_code=range_code,
            today=today,
        )
        subject_id = f"asset:{inputs.ctx.asset_symbol}"
        prepared.append((subject_id, inputs))

    series_by_id = {sid: inputs.daily_pts for sid, inputs in prepared}
    common_dates, aligned_returns = align_multi_subject_returns(series_by_id)

    if len(common_dates) < 2:
        global_warnings.append(
            "Insufficient common overlapping daily returns for comparison."
        )

    aligned_start = common_dates[0] if common_dates else today
    aligned_end = common_dates[-1] if common_dates else today
    normalized_series = normalized_cumulative_return_series(common_dates, aligned_returns)

    subject_payloads: list[dict[str, Any]] = []
    for subject_id, inputs in prepared:
        subject_warnings = list(inputs.warnings)
        ctx = inputs.ctx

        if len(common_dates) >= 2:
            aligned_fracs = aligned_returns[subject_id]
            aligned_pts = [
                DailyReturnPoint(date=d, return_fraction=r)
                for d, r in zip(common_dates, aligned_fracs)
            ]
            aligned_ts_use = _slice_timeseries_to_window(
                inputs.ts_use, aligned_start, aligned_end
            )
            metrics_block, _ = build_metric_sheet_from_daily_returns(
                daily_pts=aligned_pts,
                daily_fracs=aligned_fracs,
                ts_use=aligned_ts_use,
                flows_by_date=inputs.flows_by_date,
                flows_unknown_from=inputs.flows_unknown_from,
                window_start=aligned_start,
                window_end=aligned_end,
                xirr_val=inputs.xirr_val,
                benchmark_symbol=None,
                warnings=subject_warnings,
            )
            periodic_returns, drawdown_periods, drawdown_series_block = (
                build_metric_sheet_extension_blocks(aligned_pts)
            )
            benchmark_block: dict[str, Any] | None = None
            if benchmark_symbol:
                aligned_pts_for_bench = aligned_pts
                benchmark_block = _benchmark_block_for_subject(
                    subject_daily_pts=aligned_pts_for_bench,
                    benchmark_symbol=benchmark_symbol,
                    window_start=aligned_start,
                    window_end=aligned_end,
                    subject_warnings=subject_warnings,
                )
        else:
            metrics_block = _null_metrics_block()
            periodic_returns = _empty_periodic_returns_block()
            drawdown_periods = _empty_drawdown_periods_block()
            drawdown_series_block = _empty_drawdown_series_block()
            benchmark_block = None
            if benchmark_symbol:
                cfg = _get_benchmark_config(benchmark_symbol)
                sym = cfg.symbol if cfg else benchmark_symbol.strip()
                benchmark_block = {
                    "symbol": sym,
                    "paired_count": 0,
                    "metrics": None,
                }
                if not cfg:
                    raise BenchmarkConfigError(
                        f"Unknown or disabled benchmark symbol: {benchmark_symbol!r}"
                    )
                subject_warnings.append(
                    "Insufficient overlapping benchmark daily returns for comparison metrics."
                )

        subject_payloads.append(
            {
                **_compare_subject_block(subject_id=subject_id, ctx=ctx),
                "metrics": metrics_block,
                "periodic_returns": periodic_returns,
                "drawdown_periods": drawdown_periods,
                "drawdown_series": drawdown_series_block,
                "benchmark": benchmark_block,
                "warnings": subject_warnings,
            }
        )

    payload: dict[str, Any] = {
        "range": {
            "code": range_code,
            "start": aligned_start.isoformat(),
            "end": aligned_end.isoformat(),
        },
        "currency": display_currency,
        "subjects": subject_payloads,
        "normalized_series": normalized_series,
        "common_start_date": aligned_start.isoformat() if common_dates else None,
        "common_end_date": aligned_end.isoformat() if common_dates else None,
        "common_point_count": len(common_dates),
        "warnings": global_warnings,
    }
    return CompareResult(payload=payload)


def build_portfolio_performance_metrics(
    *,
    scope: ResolvedPortfolioScope,
    range_code: str,
    display_currency: str,
    benchmark_symbol: str | None = None,
    today: date | None = None,
) -> PerformanceMetricsResult:
    today = today or portfolio_dates.current_date()
    warnings: list[str] = []

    queryset = fifo_eligible_queryset(scope.portfolio_ids)
    all_txns = list(queryset)
    if not all_txns:
        warnings.append("No transactions in portfolio scope.")
        return PerformanceMetricsResult(
            payload=_empty_payload(
                scope,
                display_currency=display_currency,
                range_code=range_code,
                today=today,
                warnings=warnings,
                benchmark_symbol=benchmark_symbol,
            )
        )

    by_symbol = transactions_by_symbol(queryset)
    by_mf = transactions_by_mf_holding(queryset)
    disp_ccy = norm_display_currency(display_currency)
    inception = min(t.date for t in all_txns)
    emit_start = (
        None
        if range_code == "ALL"
        else resolve_performance_range_start(range_code, today, inception)
    )
    if scope.kind == "all_active":
        base_currency = disp_ccy
        timeseries_full = build_all_scope_portfolio_value_timeseries(
            scope, disp_ccy, emit_start_date=emit_start
        )
    else:
        base_currency = portfolio_base_currency(all_txns)
        timeseries_full = build_portfolio_value_timeseries(
            all_txns, by_symbol, by_mf, emit_start_date=emit_start
        )
    if not timeseries_full:
        warnings.append("No portfolio value history available.")
        return PerformanceMetricsResult(
            payload=_empty_payload(
                scope,
                display_currency=display_currency,
                range_code=range_code,
                today=today,
                warnings=warnings,
                benchmark_symbol=benchmark_symbol,
                currency=base_currency,
            )
        )

    ts_use, window_start, window_end, _range_start = _slice_timeseries_for_range(
        timeseries_full, range_code=range_code, today=today, inception=inception
    )

    warnings.extend(
        _split_adjusted_price_inconsistency_warnings(
            by_symbol=by_symbol,
            timeseries_by_symbol=_split_symbol_timeseries_cache(by_symbol),
        )
    )

    warnings.extend(
        _valuation_coverage_warnings(
            window_start=window_start,
            window_end=window_end,
            by_symbol=by_symbol,
            by_mf=by_mf,
        )
    )
    if not any(p.get("portfolio_value") is not None for p in ts_use) and not any(
        _WARN_MISSING_STOCK_PRICES in w or _has_mf_nav_quality_warning([w]) for w in warnings
    ):
        warnings.append("Portfolio values are unavailable for the selected range.")

    flows_by_date, flows_unknown_from = (
        build_all_scope_external_flows(scope, disp_ccy)
        if scope.kind == "all_active"
        else portfolio_external_flows(all_txns, base_currency)
    )
    if flows_unknown_from is not None:
        warnings.append(
            "FX rates are missing for some external cash flows; returns may be incomplete."
        )

    value_points = _timeseries_to_value_points(
        ts_use, flows_unknown_from=flows_unknown_from
    )
    daily_pts = daily_returns_from_values(value_points, flows_by_date)
    daily_fracs = [p.return_fraction for p in daily_pts]

    valid_count = sum(1 for r in daily_fracs if r is not None)
    if valid_count < 2:
        warnings.append("Insufficient daily returns to compute risk metrics.")

    xirr_val = compute_scope_xirr(scope)

    metrics_block, benchmark_block = build_metric_sheet_from_daily_returns(
        daily_pts=daily_pts,
        daily_fracs=daily_fracs,
        ts_use=ts_use,
        flows_by_date=flows_by_date,
        flows_unknown_from=flows_unknown_from,
        window_start=window_start,
        window_end=window_end,
        xirr_val=xirr_val,
        benchmark_symbol=benchmark_symbol,
        warnings=warnings,
    )
    periodic_returns, drawdown_periods, drawdown_series_block = (
        build_metric_sheet_extension_blocks(daily_pts)
    )

    payload: dict[str, Any] = {
        "subject": _subject_block(scope, display_currency=display_currency),
        "range": {
            "code": range_code,
            "start": window_start.isoformat(),
            "end": window_end.isoformat(),
        },
        "currency": display_currency,
        "metrics": metrics_block,
        "periodic_returns": periodic_returns,
        "drawdown_periods": drawdown_periods,
        "drawdown_series": drawdown_series_block,
        "warnings": warnings,
    }
    if benchmark_block is not None:
        payload["benchmark"] = benchmark_block

    return PerformanceMetricsResult(payload=payload)


def _empty_asset_payload(
    scope: ResolvedPortfolioScope,
    *,
    ctx: ResolvedAssetMetricsContext,
    display_currency: str,
    range_code: str,
    today: date,
    warnings: list[str],
    benchmark_symbol: str | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "subject": _asset_subject_block(
            scope,
            asset_symbol=ctx.asset_symbol,
            name=ctx.display_name,
            folio_number=ctx.folio_number,
        ),
        "range": {
            "code": range_code,
            "start": today.isoformat(),
            "end": today.isoformat(),
        },
        "currency": display_currency,
        "metrics": _null_metrics_block(),
        "periodic_returns": _empty_periodic_returns_block(),
        "drawdown_periods": _empty_drawdown_periods_block(),
        "drawdown_series": _empty_drawdown_series_block(),
        "warnings": warnings,
    }
    if benchmark_symbol:
        payload["benchmark"] = {
            "symbol": benchmark_symbol.strip(),
            "paired_count": 0,
            "metrics": None,
        }
    return payload


def _empty_payload(
    scope: ResolvedPortfolioScope,
    *,
    display_currency: str,
    range_code: str,
    today: date,
    warnings: list[str],
    benchmark_symbol: str | None,
    currency: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "subject": _subject_block(scope, display_currency=display_currency),
        "range": {
            "code": range_code,
            "start": today.isoformat(),
            "end": today.isoformat(),
        },
        "currency": currency or display_currency,
        "metrics": _null_metrics_block(),
        "periodic_returns": _empty_periodic_returns_block(),
        "drawdown_periods": _empty_drawdown_periods_block(),
        "drawdown_series": _empty_drawdown_series_block(),
        "warnings": warnings,
    }
    if benchmark_symbol:
        payload["benchmark"] = {
            "symbol": benchmark_symbol.strip(),
            "paired_count": 0,
            "metrics": None,
        }
    return payload
