from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import QuerySet

from finance.fifo import build_split_adjusted_lot_snapshots, calculate_fifo_cost_basis_metrics
from finance.mutual_fund_cashflows import MutualFundCashflowEvent, merge_portfolio_xirr
from finance.oversell import detect_oversell
from finance.splits import apply_stock_split_adjustments
from finance.types import TransactionType
from fx.lookup import convert_amount_with_fill, fx_lookup_from_maps, load_fx_rate_maps
from market_data.nav_lookup import normalize_scheme_code
from market_data.nav_repository import (
    latest_mutual_fund_navs_by_scheme,
    list_mutual_fund_navs_for_schemes,
)
from market_data.price_lookup import normalize_asset_symbol
from market_data.price_repository import latest_stock_prices_by_symbol, list_stock_prices_in_range
from portfolios import dates as portfolio_dates
from portfolios.models import Portfolio
from portfolios.scope import ResolvedPortfolioScope
from settings_app.services import get_settings
from transactions.finance_adapter import transaction_to_finance_dto
from transactions.models import Transaction as TransactionModel

MF_BASE_CURRENCY = "INR"


def _norm_ccy(value: str | None) -> str:
    return (value or "EUR").strip().upper() or "EUR"


def _symbol_base_currency(txns: list[TransactionModel]) -> str:
    for txn in txns:
        return _norm_ccy(txn.currency)
    return "EUR"


def _portfolio_base_currency(all_txns: list[TransactionModel]) -> str:
    if not all_txns:
        return "EUR"
    first = min(all_txns, key=lambda t: (t.date, t.id))
    return _norm_ccy(first.currency)


def _fifo_eligible_queryset(portfolio_ids: list[int]) -> QuerySet[TransactionModel]:
    return (
        TransactionModel.objects.filter(portfolio_id__in=portfolio_ids)
        .select_related(
            "mutual_fund_detail",
            "mutual_fund_detail__folio",
        )
        .order_by("date", "id")
    )


def _is_mutual_fund_transaction(txn: TransactionModel) -> bool:
    try:
        txn.mutual_fund_detail
    except ObjectDoesNotExist:
        return False
    return True


def _transactions_by_symbol(
    queryset: QuerySet[TransactionModel],
) -> dict[str, list[TransactionModel]]:
    by_symbol: dict[str, list[TransactionModel]] = {}
    for txn in queryset:
        if _is_mutual_fund_transaction(txn):
            continue
        sym = normalize_asset_symbol(txn.asset_symbol)
        by_symbol.setdefault(sym, []).append(txn)
    return by_symbol


def _mf_holding_key(scheme_code: str, folio_number: str) -> str:
    return f"{normalize_scheme_code(scheme_code)}:{folio_number.strip()}"


def transactions_by_mf_holding(
    queryset: QuerySet[TransactionModel],
) -> dict[str, list[TransactionModel]]:
    by_key: dict[str, list[TransactionModel]] = {}
    for txn in queryset:
        if not _is_mutual_fund_transaction(txn):
            continue
        detail = txn.mutual_fund_detail
        key = _mf_holding_key(txn.asset_symbol, detail.folio.folio_number)
        by_key.setdefault(key, []).append(txn)
    return by_key


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


def _convert_mf_amount_to_base(
    amount: Decimal,
    *,
    conv_date: date,
    portfolio_base: str,
    fx_maps: dict,
) -> tuple[Decimal, bool]:
    if portfolio_base == MF_BASE_CURRENCY:
        return amount, False
    converted, fx_st = fx_lookup_from_maps(
        fx_maps, MF_BASE_CURRENCY, portfolio_base, conv_date
    )
    if converted is None:
        return Decimal("0"), True
    return amount * converted, fx_st == "filled"


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


@dataclass(frozen=True)
class HoldingsCalcResult:
    total_invested: Decimal
    current_value: Decimal
    realized_pl: Decimal
    unrealized_pl: Decimal
    total_pl: Decimal
    any_fx_missing: bool
    warnings: list[str]


def _calculate_holdings(
  by_symbol: dict[str, list[TransactionModel]],
) -> HoldingsCalcResult:
    symbols = list(by_symbol.keys())
    latest_rows = latest_stock_prices_by_symbol(symbols)
    total_invested = Decimal("0")
    current_value = Decimal("0")
    realized_pl = Decimal("0")
    any_fx_missing = False
    warnings: list[str] = []

    fx_pairs: set[tuple[str, str]] = set()
    price_dates: list[date] = []
    for sym, txns in by_symbol.items():
        hp = latest_rows.get(sym)
        if hp:
            base = _symbol_base_currency(txns)
            fx_pairs.add((_norm_ccy(hp.currency), base))
            price_dates.append(hp.date)

    today = portfolio_dates.current_date()
    fx_start = min(price_dates) - timedelta(days=7) if price_dates else today - timedelta(days=7)
    fx_maps = load_fx_rate_maps(fx_pairs, fx_start, today)

    for symbol, txns in by_symbol.items():
        sym = normalize_asset_symbol(symbol)
        hp_row = latest_rows.get(sym)
        current_price: Optional[Decimal] = None
        base_currency = _symbol_base_currency(txns)

        if hp_row is not None:
            current_price = Decimal(hp_row.close_price)
            fx_rate, fx_st = fx_lookup_from_maps(
                fx_maps, _norm_ccy(hp_row.currency), base_currency, hp_row.date
            )
            if fx_rate is None:
                any_fx_missing = True
                current_price = None
            else:
                current_price = current_price * fx_rate
                if fx_st == "filled":
                    pass

        fifo_dtos = _to_fifo_dtos(txns)
        if detect_oversell(fifo_dtos):
            warnings.append(f"Oversell detected for {sym}")

        fifo_metrics = calculate_fifo_cost_basis_metrics(
            fifo_dtos, current_price=current_price
        )
        qty = fifo_metrics.cumulative_qty
        invested = fifo_metrics.cumulative_invested_amount
        cv = (current_price or Decimal("0")) * qty

        total_invested += invested
        current_value += cv
        realized_pl += fifo_metrics.realized_pl

    unrealized_pl = current_value - total_invested
    total_pl = realized_pl + unrealized_pl

    return HoldingsCalcResult(
        total_invested=total_invested,
        current_value=current_value,
        realized_pl=realized_pl,
        unrealized_pl=unrealized_pl,
        total_pl=total_pl,
        any_fx_missing=any_fx_missing,
        warnings=warnings,
    )


def _calculate_mf_holdings(
    by_mf: dict[str, list[TransactionModel]],
    *,
    portfolio_base: str,
) -> HoldingsCalcResult:
    if not by_mf:
        return HoldingsCalcResult(
            total_invested=Decimal("0"),
            current_value=Decimal("0"),
            realized_pl=Decimal("0"),
            unrealized_pl=Decimal("0"),
            total_pl=Decimal("0"),
            any_fx_missing=False,
            warnings=[],
        )

    schemes = sorted(
        {normalize_scheme_code(txns[0].asset_symbol) for txns in by_mf.values()}
    )
    latest_navs = latest_mutual_fund_navs_by_scheme(schemes)
    today = portfolio_dates.current_date()
    nav_dates: list[date] = []
    for nav in latest_navs.values():
        if nav.date is not None:
            nav_dates.append(nav.date)
    fx_start = min(nav_dates) - timedelta(days=7) if nav_dates else today - timedelta(days=7)
    fx_pairs = {(MF_BASE_CURRENCY, portfolio_base)}
    fx_maps = load_fx_rate_maps(fx_pairs, fx_start, today)

    total_invested = Decimal("0")
    current_value = Decimal("0")
    realized_pl = Decimal("0")
    any_fx_missing = False
    warnings: list[str] = []

    for _key, txns in by_mf.items():
        scheme = normalize_scheme_code(txns[0].asset_symbol)
        nav_result = latest_navs.get(scheme)
        current_nav: Optional[Decimal] = None
        nav_date = today
        if nav_result is not None and nav_result.status == "ok" and nav_result.nav is not None:
            current_nav = nav_result.nav
            nav_date = nav_result.date or today
        else:
            warnings.append(f"Latest cached NAV missing for mutual fund {scheme}")

        fifo_txns = _to_fifo_dtos(txns)
        if detect_oversell(fifo_txns):
            warnings.append(f"Oversell detected for mutual fund {scheme}")

        fifo_metrics = calculate_fifo_cost_basis_metrics(
            fifo_txns, current_price=current_nav
        )
        qty = fifo_metrics.cumulative_qty
        cv_inr = (current_nav or Decimal("0")) * qty
        inv_inr = fifo_metrics.cumulative_invested_amount
        real_inr = fifo_metrics.realized_pl

        cv_base, fx_fill = _convert_mf_amount_to_base(
            cv_inr, conv_date=nav_date, portfolio_base=portfolio_base, fx_maps=fx_maps
        )
        inv_base, inv_fx = _convert_mf_amount_to_base(
            inv_inr, conv_date=nav_date, portfolio_base=portfolio_base, fx_maps=fx_maps
        )
        real_base, real_fx = _convert_mf_amount_to_base(
            real_inr, conv_date=nav_date, portfolio_base=portfolio_base, fx_maps=fx_maps
        )
        if fx_fill or inv_fx or real_fx:
            any_fx_missing = True
            cv_base = Decimal("0") if fx_fill else cv_base

        total_invested += inv_base
        current_value += cv_base
        realized_pl += real_base

    unrealized_pl = current_value - total_invested
    total_pl = realized_pl + unrealized_pl

    return HoldingsCalcResult(
        total_invested=total_invested,
        current_value=current_value,
        realized_pl=realized_pl,
        unrealized_pl=unrealized_pl,
        total_pl=total_pl,
        any_fx_missing=any_fx_missing,
        warnings=warnings,
    )


def _merge_holdings_results(
    stock: HoldingsCalcResult, mf: HoldingsCalcResult
) -> HoldingsCalcResult:
    unrealized = (stock.current_value + mf.current_value) - (
        stock.total_invested + mf.total_invested
    )
    total_pl = stock.realized_pl + mf.realized_pl + unrealized
    return HoldingsCalcResult(
        total_invested=stock.total_invested + mf.total_invested,
        current_value=stock.current_value + mf.current_value,
        realized_pl=stock.realized_pl + mf.realized_pl,
        unrealized_pl=unrealized,
        total_pl=total_pl,
        any_fx_missing=stock.any_fx_missing or mf.any_fx_missing,
        warnings=stock.warnings + mf.warnings,
    )


def _mf_timeseries_by_date(
    by_mf: dict[str, list[TransactionModel]],
    *,
    inception_date: date,
    today: date,
    portfolio_base: str,
) -> dict[date, dict]:
    """Per-day MF portfolio value and invested amount in portfolio_base."""
    if not by_mf:
        return {}

    schemes = sorted(
        {normalize_scheme_code(txns[0].asset_symbol) for txns in by_mf.values()}
    )
    hist_navs = list_mutual_fund_navs_for_schemes(schemes, inception_date, today)
    nav_dict: dict[str, dict[date, Decimal]] = {}
    for row in hist_navs:
        scheme = normalize_scheme_code(row.asset_symbol)
        nav_dict.setdefault(scheme, {})[row.date] = Decimal(row.close_price)

    fx_pairs = {(MF_BASE_CURRENCY, portfolio_base)}
    fx_maps = load_fx_rate_maps(fx_pairs, inception_date, today)

    qty_dict: dict[str, dict[date, Decimal]] = {}
    inv_dict: dict[str, dict[date, Decimal]] = {}

    for key, txns in by_mf.items():
        scheme = normalize_scheme_code(txns[0].asset_symbol)
        adjusted = _to_fifo_dtos(txns)
        txns_sorted = sorted(adjusted, key=lambda x: x.date)
        timeline: dict[date, Decimal] = {}
        inv_timeline: dict[date, Decimal] = {}
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
            cum_qty = sum(l["qty"] for l in lots)
            cum_inv = sum(l["qty"] * l["unit_cost"] for l in lots)
            timeline[t.date] = cum_qty
            inv_timeline[t.date] = cum_inv

        qty_dict[key] = timeline
        inv_dict[key] = inv_timeline

    current_state: dict[str, dict] = {}
    for key in by_mf:
        scheme = normalize_scheme_code(by_mf[key][0].asset_symbol)
        current_state[key] = {
            "scheme": scheme,
            "qty": Decimal("0"),
            "inv": Decimal("0"),
            "nav": None,
        }

    daily: dict[date, dict] = {}
    d = inception_date
    while d <= today:
        daily_value_inr = Decimal("0")
        daily_inv_inr = Decimal("0")
        daily_fx_missing = False

        for key in by_mf:
            st = current_state[key]
            if d in qty_dict.get(key, {}):
                st["qty"] = qty_dict[key][d]
            if d in inv_dict.get(key, {}):
                st["inv"] = inv_dict[key][d]
            scheme = st["scheme"]
            if d in nav_dict.get(scheme, {}):
                st["nav"] = nav_dict[scheme][d]

            daily_inv_inr += st["inv"]
            if st["qty"] > 0 and st["nav"] is not None:
                daily_value_inr += st["qty"] * st["nav"]

        value_base: Decimal | None = Decimal("0")
        if daily_value_inr > 0:
            converted, fx_miss = _convert_mf_amount_to_base(
                daily_value_inr,
                conv_date=d,
                portfolio_base=portfolio_base,
                fx_maps=fx_maps,
            )
            if fx_miss:
                daily_fx_missing = True
                value_base = None
            else:
                value_base = converted

        inv_conv, inv_miss = _convert_mf_amount_to_base(
            daily_inv_inr, conv_date=d, portfolio_base=portfolio_base, fx_maps=fx_maps
        )
        inv_base = Decimal("0")
        if inv_miss:
            daily_fx_missing = True
        else:
            inv_base = inv_conv

        daily[d] = {
            "value": None if daily_fx_missing else value_base,
            "invested": inv_base,
            "fx_missing": daily_fx_missing,
        }
        d += timedelta(days=1)

    return daily


def _build_portfolio_value_timeseries(
    all_txns: list[TransactionModel],
    by_symbol: dict[str, list[TransactionModel]],
    by_mf: dict[str, list[TransactionModel]] | None = None,
) -> list[dict]:
    if not all_txns:
        return []

    by_mf = by_mf or {}
    inception_date = min(t.date for t in all_txns)
    today = portfolio_dates.current_date()
    portfolio_base = _portfolio_base_currency(all_txns)
    mf_daily = _mf_timeseries_by_date(
        by_mf,
        inception_date=inception_date,
        today=today,
        portfolio_base=portfolio_base,
    )

    base_ccy_by_sym = {
        normalize_asset_symbol(sym): _symbol_base_currency(txns)
        for sym, txns in by_symbol.items()
    }
    syms = sorted(by_symbol.keys())
    hist_prices = list_stock_prices_in_range(syms, inception_date, today)

    price_dict: dict[str, dict[date, Decimal]] = {}
    price_ccy_dict: dict[str, dict[date, str]] = {}
    fx_pairs: set[tuple[str, str]] = set()

    for hp in hist_prices:
        k = normalize_asset_symbol(hp.asset_symbol)
        price_dict.setdefault(k, {})[hp.date] = Decimal(hp.close_price)
        price_ccy_dict.setdefault(k, {})[hp.date] = _norm_ccy(hp.currency)
        base_ccy = base_ccy_by_sym.get(k) or "EUR"
        fx_pairs.add((_norm_ccy(hp.currency), base_ccy))

    fx_maps = load_fx_rate_maps(fx_pairs, inception_date, today)

    qty_dict: dict[str, dict[date, Decimal]] = {}
    inv_dict: dict[str, dict[date, Decimal]] = {}

    for symbol, txns in by_symbol.items():
        timeline, inv_timeline = build_split_adjusted_lot_snapshots(_to_fifo_dtos(txns))
        qty_dict[symbol] = timeline
        inv_dict[symbol] = inv_timeline

    current_state: dict[str, dict] = {}
    for sym in by_symbol:
        current_state[sym] = {
            "qty": Decimal("0"),
            "inv": Decimal("0"),
            "price": None,
            "price_ccy": None,
        }

    timeseries: list[dict] = []
    d = inception_date
    while d <= today:
        daily_value = Decimal("0")
        daily_inv = Decimal("0")
        daily_fx_missing = False
        fx_status = "ok"

        for sym in by_symbol:
            if d in qty_dict.get(sym, {}):
                current_state[sym]["qty"] = qty_dict[sym][d]
            if d in inv_dict.get(sym, {}):
                current_state[sym]["inv"] = inv_dict[sym][d]

            sym_key = normalize_asset_symbol(sym)
            if d in price_dict.get(sym_key, {}):
                current_state[sym]["price"] = price_dict[sym_key][d]
                current_state[sym]["price_ccy"] = price_ccy_dict[sym_key][d]

            daily_inv += current_state[sym]["inv"]

            if current_state[sym]["qty"] == 0:
                continue
            if current_state[sym]["price"] is None:
                continue

            base_ccy = base_ccy_by_sym.get(sym_key) or _symbol_base_currency(by_symbol[sym])
            fx_rate, fx_st = fx_lookup_from_maps(
                fx_maps,
                current_state[sym]["price_ccy"],
                base_ccy,
                d,
            )
            if fx_rate is None:
                daily_fx_missing = True
                fx_status = "fx_unavailable"
                continue
            if fx_st == "filled" and fx_status == "ok":
                fx_status = "filled"

            daily_value += (
                current_state[sym]["qty"] * current_state[sym]["price"] * fx_rate
            )

        mf_pt = mf_daily.get(d)
        if mf_pt is not None:
            daily_inv += mf_pt["invested"]
            if mf_pt.get("fx_missing"):
                if mf_pt["value"] is None:
                    daily_fx_missing = True
                    fx_status = "fx_unavailable"
            elif mf_pt["value"] is not None:
                daily_value += mf_pt["value"]

        timeseries.append(
            {
                "date": d.isoformat(),
                "portfolio_value": None if daily_fx_missing else float(daily_value),
                "invested_amount": float(daily_inv),
                "fx_status": fx_status,
            }
        )
        d += timedelta(days=1)

    return timeseries


@dataclass
class PortfolioSummaryResult:
    total_invested: float
    current_value: float
    realized_pl: float
    unrealized_pl: float
    total_pl: float
    xirr: Optional[float]
    base_currency: str
    display_currency: str
    fx_status: str
    timeseries: list[dict]
    warnings: list[str]


def _float(v: Decimal) -> float:
    return float(v)


def _combine_fx_status(statuses: list[str]) -> str:
    if any(s == "fx_unavailable" for s in statuses):
        return "fx_unavailable"
    if any(s == "filled" for s in statuses):
        return "filled"
    return "ok"


def compute_scope_xirr(scope: ResolvedPortfolioScope) -> Optional[float]:
    """Money-weighted XIRR for the full portfolio scope (inception through today).

    Uses all BUY/SELL cash flows and current holdings value; not sliced by
    performance ``range``. Shared by summary aggregation and analytics Metric Sheet.
    """
    return _compute_scope_xirr(scope)


def _compute_scope_xirr(scope: ResolvedPortfolioScope) -> Optional[float]:
    queryset = _fifo_eligible_queryset(scope.portfolio_ids)
    all_txns = list(queryset)
    if not all_txns:
        return None
    by_symbol = _transactions_by_symbol(queryset)
    by_mf = transactions_by_mf_holding(queryset)
    portfolio_base = _portfolio_base_currency(all_txns)
    stock_holdings = _calculate_holdings(by_symbol)
    mf_holdings = _calculate_mf_holdings(by_mf, portfolio_base=portfolio_base)
    holdings_res = _merge_holdings_results(stock_holdings, mf_holdings)

    stock_cashflow_txns = []
    for txns in by_symbol.values():
        stock_cashflow_txns.extend(
            apply_stock_split_adjustments(_to_fifo_dtos(txns))
        )
    mf_events = _mf_cashflow_events(all_txns)
    return merge_portfolio_xirr(
        stock_cashflow_txns,
        mf_events,
        terminal_value=holdings_res.current_value,
        include_fees_in_cashflows=True,
    )


def _aggregate_timeseries_from_children(
    children: list[PortfolioSummaryResult],
) -> list[dict]:
    by_date: dict[str, dict] = {}
    for child in children:
        for pt in child.timeseries:
            d = pt["date"]
            if d not in by_date:
                by_date[d] = {
                    "date": d,
                    "portfolio_value": 0.0,
                    "invested_amount": 0.0,
                    "fx_status": "ok",
                }
            row = by_date[d]
            child_pv = pt.get("portfolio_value")
            if child_pv is None:
                row["portfolio_value"] = None
            elif row.get("portfolio_value") is not None:
                row["portfolio_value"] = float(row["portfolio_value"]) + float(child_pv)
            row["invested_amount"] = float(row["invested_amount"]) + float(
                pt.get("invested_amount") or 0
            )
            row["fx_status"] = _combine_fx_status(
                [row["fx_status"], pt.get("fx_status") or "ok"]
            )
    return [by_date[d] for d in sorted(by_date.keys())]


def _build_single_portfolio_summary(
    *,
    scope: ResolvedPortfolioScope,
    include_timeseries: bool = True,
    disp_ccy: str,
) -> PortfolioSummaryResult:
    queryset = _fifo_eligible_queryset(scope.portfolio_ids)
    all_txns = list(queryset)
    by_symbol = _transactions_by_symbol(queryset)
    by_mf = transactions_by_mf_holding(queryset)

    stock_holdings = _calculate_holdings(by_symbol)
    portfolio_base = _portfolio_base_currency(all_txns)
    mf_holdings = _calculate_mf_holdings(by_mf, portfolio_base=portfolio_base)
    holdings_res = _merge_holdings_results(stock_holdings, mf_holdings)

    timeseries: list[dict] = []
    if include_timeseries:
        timeseries = _build_portfolio_value_timeseries(all_txns, by_symbol, by_mf)

    xirr: Optional[float] = None
    if all_txns:
        stock_cashflow_txns = []
        for txns in by_symbol.values():
            stock_cashflow_txns.extend(
                apply_stock_split_adjustments(_to_fifo_dtos(txns))
            )
        mf_events = _mf_cashflow_events(all_txns)
        xirr = merge_portfolio_xirr(
            stock_cashflow_txns,
            mf_events,
            terminal_value=holdings_res.current_value,
            include_fees_in_cashflows=True,
        )

    needs_display_conv = portfolio_base != disp_ccy
    fx_status = "fx_unavailable" if holdings_res.any_fx_missing else "ok"

    def _apply_fx_status(st: str) -> None:
        nonlocal fx_status
        if st == "fx_unavailable":
            fx_status = "fx_unavailable"
        elif st == "filled" and fx_status == "ok":
            fx_status = "filled"

    def _conv_monetary(v: Decimal, conv_date: date) -> Decimal:
        nonlocal fx_status
        if not needs_display_conv:
            return v
        cv, st = convert_amount_with_fill(v, portfolio_base, disp_ccy, conv_date)
        _apply_fx_status(st)
        if cv is None:
            return v
        return cv

    today = portfolio_dates.current_date()
    total_invested = _conv_monetary(holdings_res.total_invested, today)
    current_value = _conv_monetary(holdings_res.current_value, today)
    realized_pl = _conv_monetary(holdings_res.realized_pl, today)
    unrealized_pl = _conv_monetary(holdings_res.unrealized_pl, today)
    total_pl = _conv_monetary(holdings_res.total_pl, today)

    converted_timeseries: list[dict] = []
    for p in timeseries:
        pp = dict(p)
        pt_date = date.fromisoformat(pp["date"])
        if pp.get("portfolio_value") is not None:
            pv = Decimal(str(pp["portfolio_value"]))
            pp["portfolio_value"] = float(_conv_monetary(pv, pt_date))
        if pp.get("invested_amount") is not None:
            inv = Decimal(str(pp["invested_amount"]))
            pp["invested_amount"] = float(_conv_monetary(inv, pt_date))
        converted_timeseries.append(pp)

    return PortfolioSummaryResult(
        total_invested=_float(total_invested),
        current_value=_float(current_value),
        realized_pl=_float(realized_pl),
        unrealized_pl=_float(unrealized_pl),
        total_pl=_float(total_pl),
        xirr=xirr,
        base_currency=portfolio_base,
        display_currency=disp_ccy,
        fx_status=fx_status,
        timeseries=converted_timeseries,
        warnings=holdings_res.warnings,
    )


def _build_all_active_portfolio_summary(
    *,
    scope: ResolvedPortfolioScope,
    include_timeseries: bool = True,
    disp_ccy: str,
) -> PortfolioSummaryResult:
    portfolio_names = {
        p.id: p.name
        for p in Portfolio.objects.filter(pk__in=scope.portfolio_ids).only("id", "name")
    }

    child_summaries: list[PortfolioSummaryResult] = []
    for portfolio_id in scope.portfolio_ids:
        child_scope = ResolvedPortfolioScope(kind="single", portfolio_ids=[portfolio_id])
        child_summaries.append(
            _build_single_portfolio_summary(
                scope=child_scope,
                include_timeseries=include_timeseries,
                disp_ccy=disp_ccy,
            )
        )

    if not child_summaries:
        return PortfolioSummaryResult(
            total_invested=0.0,
            current_value=0.0,
            realized_pl=0.0,
            unrealized_pl=0.0,
            total_pl=0.0,
            xirr=None,
            base_currency=disp_ccy,
            display_currency=disp_ccy,
            fx_status="ok",
            timeseries=[],
            warnings=[],
        )

    total_invested = sum(c.total_invested for c in child_summaries)
    current_value = sum(c.current_value for c in child_summaries)
    realized_pl = sum(c.realized_pl for c in child_summaries)
    unrealized_pl = sum(c.unrealized_pl for c in child_summaries)
    total_pl = sum(c.total_pl for c in child_summaries)

    warnings: list[str] = []
    for portfolio_id, child in zip(scope.portfolio_ids, child_summaries):
        name = portfolio_names.get(portfolio_id, f"Portfolio {portfolio_id}")
        for warning in child.warnings:
            warnings.append(f"{name}: {warning}")

    timeseries: list[dict] = []
    if include_timeseries:
        timeseries = _aggregate_timeseries_from_children(child_summaries)

    return PortfolioSummaryResult(
        total_invested=total_invested,
        current_value=current_value,
        realized_pl=realized_pl,
        unrealized_pl=unrealized_pl,
        total_pl=total_pl,
        xirr=compute_scope_xirr(scope),
        base_currency=disp_ccy,
        display_currency=disp_ccy,
        fx_status=_combine_fx_status([c.fx_status for c in child_summaries]),
        timeseries=timeseries,
        warnings=warnings,
    )


def build_portfolio_summary(
    *,
    scope: ResolvedPortfolioScope,
    include_timeseries: bool = True,
    display_currency: str | None = None,
) -> PortfolioSummaryResult:
    settings = get_settings()
    disp_ccy = _norm_ccy(display_currency or settings.display_currency or "EUR")

    if scope.kind == "all_active":
        return _build_all_active_portfolio_summary(
            scope=scope,
            include_timeseries=include_timeseries,
            disp_ccy=disp_ccy,
        )

    return _build_single_portfolio_summary(
        scope=scope,
        include_timeseries=include_timeseries,
        disp_ccy=disp_ccy,
    )


# Public helpers reused by portfolio performance service (Phase 10).
build_portfolio_value_timeseries = _build_portfolio_value_timeseries
fifo_eligible_queryset = _fifo_eligible_queryset
transactions_by_symbol = _transactions_by_symbol
portfolio_base_currency = _portfolio_base_currency
norm_display_currency = _norm_ccy
