from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional

from django.db.models import QuerySet

from finance.fifo import calculate_fifo_cost_basis_metrics
from finance.oversell import detect_oversell
from finance.types import TransactionType
from finance.xirr import calculate_xirr
from fx.lookup import convert_amount_with_fill
from market_data.price_lookup import latest_historical_price, normalize_asset_symbol
from portfolios.scope import ResolvedPortfolioScope
from settings_app.models import DisplayCurrency
from transactions.finance_adapter import transaction_to_finance_dto
from transactions.models import Transaction as TransactionModel


class HoldingsValidationError(Exception):
    pass


def _norm_ccy(value: str | None) -> str:
    return (value or "EUR").strip().upper() or "EUR"


def _symbol_base_currency(txns: list[TransactionModel]) -> str:
    for txn in txns:
        return _norm_ccy(txn.currency)
    return "EUR"


def _fifo_eligible_queryset(portfolio_ids: list[int]) -> QuerySet[TransactionModel]:
    return (
        TransactionModel.objects.filter(portfolio_id__in=portfolio_ids)
        .select_related("portfolio")
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


def _to_finance_dtos(db_txns: list[TransactionModel]):
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


def _holding_status(*, qty: Decimal, oversold: bool) -> str:
    if oversold:
        return "oversold"
    if qty <= 0:
        return "closed"
    return "ok"


def _resolve_price(
    *,
    symbol: str,
    base_currency: str,
    display_currency: str,
) -> tuple[Optional[Decimal], str, bool]:
    """
    Returns (current_price in holding currency, price_status, display_fx_unavailable).

    Historical closes may be stored in a different currency than the holding;
    convert using cached FX (same pattern as summary_service). Portfolio-level
    display_fx_unavailable is True only when display_currency differs from the
    holding currency (holdings amounts are not converted to display currency).
    """
    display_fx_unavailable = display_currency != base_currency
    hp = latest_historical_price(symbol)
    if hp is None:
        return None, "price_missing", display_fx_unavailable

    price_ccy = _norm_ccy(hp.currency)
    close = Decimal(hp.close_price)
    if price_ccy == base_currency:
        return close, "ok", display_fx_unavailable

    converted, _ = convert_amount_with_fill(close, price_ccy, base_currency, hp.date)
    if converted is None:
        return None, "price_missing", display_fx_unavailable
    return converted, "ok", display_fx_unavailable


def _float_or_none(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value)


def _build_holding_item(
    *,
    symbol: str,
    db_txns: list[TransactionModel],
    display_currency: str,
) -> dict:
    finance_txns = _to_finance_dtos(db_txns)
    base_currency = _symbol_base_currency(db_txns)
    oversold = detect_oversell(finance_txns)

    current_price, price_status, fx_missing = _resolve_price(
        symbol=symbol,
        base_currency=base_currency,
        display_currency=display_currency,
    )

    fifo_metrics = calculate_fifo_cost_basis_metrics(
        finance_txns,
        current_price=current_price,
    )
    qty = fifo_metrics.cumulative_qty
    invested = fifo_metrics.cumulative_invested_amount
    avg_cost = fifo_metrics.avg_cost_per_share if qty > 0 else Decimal("0")

    if current_price is not None and qty > 0:
        current_value = current_price * qty
    else:
        current_value = Decimal("0")

    warnings: list[str] = []
    status = _holding_status(qty=qty, oversold=oversold)
    if oversold:
        warnings.append("SELL quantity exceeded available FIFO lots for this asset")
    if price_status == "price_missing" and qty > 0:
        warnings.append("Latest historical price is missing")

    xirr = None
    if current_price is not None:
        xirr = calculate_xirr(
            finance_txns,
            current_price=current_price,
            current_date=date.today(),
            include_fees_in_cashflows=True,
        )

    return {
        "asset_symbol": symbol,
        "quantity": float(qty),
        "avg_cost_per_share": float(avg_cost),
        "latest_price": _float_or_none(current_price),
        "current_price": _float_or_none(current_price),
        "current_value": float(current_value),
        "invested_amount": float(invested),
        "invested": float(invested),
        "realized_gain_loss": float(fifo_metrics.realized_pl),
        "realized_pl": float(fifo_metrics.realized_pl),
        "unrealized_gain_loss": float(fifo_metrics.unrealized_pl),
        "unrealized_pl": float(fifo_metrics.unrealized_pl),
        "currency": base_currency,
        "price_status": price_status,
        "holding_status": status,
        "warnings": warnings,
        "xirr": xirr,
        "fx_status": "fx_unavailable" if fx_missing else "ok",
        "_fx_missing": fx_missing,
    }


@dataclass
class HoldingsResult:
    fx_status: str
    holdings: list[dict] = field(default_factory=list)
    display_currency: str = "EUR"


def build_holdings(
    *,
    scope: ResolvedPortfolioScope,
    display_currency: str = "EUR",
) -> HoldingsResult:
    display_currency = _norm_ccy(display_currency)
    queryset = _fifo_eligible_queryset(scope.portfolio_ids)
    by_symbol = _transactions_by_symbol(queryset)

    holdings: list[dict] = []
    any_fx_missing = False

    for symbol in sorted(by_symbol.keys()):
        db_txns = by_symbol[symbol]
        item = _build_holding_item(
            symbol=symbol,
            db_txns=db_txns,
            display_currency=display_currency,
        )
        if item.pop("_fx_missing", False):
            any_fx_missing = True
        if display_currency != item["currency"]:
            any_fx_missing = True
        holdings.append(item)

    fx_status = "fx_unavailable" if any_fx_missing else "ok"
    return HoldingsResult(
        fx_status=fx_status,
        holdings=holdings,
        display_currency=display_currency,
    )


@dataclass
class AssetDetailResult:
    asset_symbol: str
    currency: str
    current_price: Optional[float]
    price_status: str
    current_value: float
    cumulative_qty: float
    cumulative_invested_amount: float
    avg_cost_per_share: float
    realized_pl: float
    unrealized_pl: float
    xirr: Optional[float]
    holding_status: str
    fx_status: str
    warnings: list[str]
    transactions: list[dict]


class AssetNotFoundError(Exception):
    pass


def build_asset_detail(
    *,
    asset_symbol: str,
    scope: ResolvedPortfolioScope,
    display_currency: str = "EUR",
) -> AssetDetailResult:
    display_currency = _norm_ccy(display_currency)
    sym = normalize_asset_symbol(asset_symbol)
    if not sym:
        raise AssetNotFoundError("Asset symbol is required")

    db_txns = list(
        _fifo_eligible_queryset(scope.portfolio_ids).filter(asset_symbol__iexact=sym)
    )
    if not db_txns:
        raise AssetNotFoundError(f"No transactions found for {asset_symbol}")

    finance_txns = _to_finance_dtos(db_txns)
    base_currency = _symbol_base_currency(db_txns)
    oversold = detect_oversell(finance_txns)

    current_price, price_status, fx_missing = _resolve_price(
        symbol=sym,
        base_currency=base_currency,
        display_currency=display_currency,
    )
    if display_currency != base_currency:
        fx_missing = True

    fifo_metrics = calculate_fifo_cost_basis_metrics(
        finance_txns,
        current_price=current_price,
    )
    qty = fifo_metrics.cumulative_qty
    if current_price is not None and qty > 0:
        current_value = current_price * qty
    else:
        current_value = Decimal("0")

    warnings: list[str] = []
    status = _holding_status(qty=qty, oversold=oversold)
    if oversold:
        warnings.append("SELL quantity exceeded available FIFO lots for this asset")

    xirr = None
    if current_price is not None:
        xirr = calculate_xirr(
            finance_txns,
            current_price=current_price,
            current_date=date.today(),
            include_fees_in_cashflows=True,
        )

    txn_rows = [
        {
            "id": t.id,
            "date": t.date.isoformat(),
            "type": t.type,
            "quantity": float(t.quantity),
            "price_per_share": float(t.price_per_share or 0),
            "fees": float(t.fees),
        }
        for t in sorted(db_txns, key=lambda x: (x.date, x.id))
    ]

    return AssetDetailResult(
        asset_symbol=sym,
        currency=base_currency,
        current_price=_float_or_none(current_price),
        price_status=price_status,
        current_value=float(current_value),
        cumulative_qty=float(qty),
        cumulative_invested_amount=float(fifo_metrics.cumulative_invested_amount),
        avg_cost_per_share=float(
            fifo_metrics.avg_cost_per_share if qty > 0 else Decimal("0")
        ),
        realized_pl=float(fifo_metrics.realized_pl),
        unrealized_pl=float(fifo_metrics.unrealized_pl),
        xirr=xirr,
        holding_status=status,
        fx_status="fx_unavailable" if fx_missing else "ok",
        warnings=warnings,
        transactions=txn_rows,
    )


def validate_display_currency(value: str) -> str:
    normalized = _norm_ccy(value)
    allowed = {c.value for c in DisplayCurrency}
    if normalized not in allowed:
        raise HoldingsValidationError(f"Unsupported display_currency: {value}")
    return normalized
