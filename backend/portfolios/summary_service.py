from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from django.db.models import QuerySet

from finance.fifo import calculate_fifo_cost_basis_metrics
from finance.oversell import detect_oversell
from finance.splits import apply_stock_split_adjustments
from finance.types import TransactionType
from finance.xirr import calculate_portfolio_xirr
from fx.lookup import convert_amount_with_fill, fx_lookup_from_maps, load_fx_rate_maps
from market_data.price_lookup import normalize_asset_symbol
from market_data.price_repository import latest_stock_prices_by_symbol, list_stock_prices_in_range
from portfolios import dates as portfolio_dates
from portfolios.scope import ResolvedPortfolioScope
from settings_app.services import get_settings
from transactions.finance_adapter import transaction_to_finance_dto
from transactions.models import Transaction as TransactionModel


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
        .order_by("date", "id")
    )


def _transactions_by_symbol(
    queryset: QuerySet[TransactionModel],
) -> dict[str, list[TransactionModel]]:
    by_symbol: dict[str, list[TransactionModel]] = {}
    for txn in queryset:
        sym = normalize_asset_symbol(txn.asset_symbol)
        by_symbol.setdefault(sym, []).append(txn)
    return by_symbol


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

        fifo_txns = apply_stock_split_adjustments(_to_fifo_dtos(txns))
        if detect_oversell(_to_fifo_dtos(txns)):
            warnings.append(f"Oversell detected for {sym}")

        fifo_metrics = calculate_fifo_cost_basis_metrics(
            fifo_txns, current_price=current_price
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


def _build_portfolio_value_timeseries(
    all_txns: list[TransactionModel],
    by_symbol: dict[str, list[TransactionModel]],
) -> list[dict]:
    if not all_txns:
        return []

    inception_date = min(t.date for t in all_txns)
    today = portfolio_dates.current_date()

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
        adjusted = apply_stock_split_adjustments(_to_fifo_dtos(txns))
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


def build_portfolio_summary(
    *,
    scope: ResolvedPortfolioScope,
    include_timeseries: bool = True,
    display_currency: str | None = None,
) -> PortfolioSummaryResult:
    settings = get_settings()
    disp_ccy = _norm_ccy(display_currency or settings.display_currency or "EUR")

    queryset = _fifo_eligible_queryset(scope.portfolio_ids)
    all_txns = list(queryset)
    by_symbol = _transactions_by_symbol(queryset)

    holdings_res = _calculate_holdings(by_symbol)
    portfolio_base = _portfolio_base_currency(all_txns)

    timeseries: list[dict] = []
    if include_timeseries:
        timeseries = _build_portfolio_value_timeseries(all_txns, by_symbol)

    xirr: Optional[float] = None
    if all_txns:
        cashflow_txns = []
        for txns in by_symbol.values():
            cashflow_txns.extend(
                apply_stock_split_adjustments(_to_fifo_dtos(txns))
            )
        xirr = calculate_portfolio_xirr(
            cashflow_txns,
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


# Public helpers reused by portfolio performance service (Phase 10).
build_portfolio_value_timeseries = _build_portfolio_value_timeseries
fifo_eligible_queryset = _fifo_eligible_queryset
transactions_by_symbol = _transactions_by_symbol
portfolio_base_currency = _portfolio_base_currency
norm_display_currency = _norm_ccy
