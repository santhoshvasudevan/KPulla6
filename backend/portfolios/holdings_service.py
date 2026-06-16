from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import QuerySet

from cash.services import build_cash_display_summary, cash_allocation_rows
from debt.portfolio_value import build_bank_cash_holding_rows, build_fd_holding_rows
from finance.fifo import calculate_fifo_cost_basis_metrics
from finance.oversell import detect_oversell
from finance.types import TransactionType
from finance.xirr import calculate_xirr
from fx.lookup import convert_amount_with_fill
from market_data.mutual_fund_classification_bridge import classification_fields_for_asset
from market_data.nav_lookup import latest_nav_for_asset, normalize_scheme_code
from market_data.price_lookup import latest_historical_price, normalize_asset_symbol
from portfolios.scope import ResolvedPortfolioScope
from settings_app.models import DisplayCurrency
from transactions.finance_adapter import transaction_to_finance_dto
from transactions.models import Transaction as TransactionModel

MF_BASE_CURRENCY = "INR"


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
        .select_related(
            "portfolio",
            "mutual_fund_detail",
            "mutual_fund_detail__folio",
            "mutual_fund_detail__folio__asset",
            "mutual_fund_detail__folio__asset__mutual_fund_profile",
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


def _transactions_by_mf_holding(
    queryset: QuerySet[TransactionModel],
) -> dict[str, list[TransactionModel]]:
    by_key: dict[str, list[TransactionModel]] = {}
    for txn in queryset:
        if not _is_mutual_fund_transaction(txn):
            continue
        detail = txn.mutual_fund_detail
        scheme = normalize_scheme_code(txn.asset_symbol)
        folio = detail.folio.folio_number
        key = _mf_holding_key(scheme, folio)
        by_key.setdefault(key, []).append(txn)
    return by_key


def _mf_asset_and_profile(db_txns: list[TransactionModel]):
    detail = db_txns[0].mutual_fund_detail
    asset = detail.folio.asset
    profile = getattr(asset, "mutual_fund_profile", None)
    return asset, profile


def _mf_classification_fields(db_txns: list[TransactionModel]) -> dict[str, str]:
    asset, profile = _mf_asset_and_profile(db_txns)
    return classification_fields_for_asset(asset, profile)


def _scheme_name_for_mf_txns(db_txns: list[TransactionModel]) -> str:
    for txn in db_txns:
        profile = getattr(
            txn.mutual_fund_detail.folio.asset,
            "mutual_fund_profile",
            None,
        )
        if profile is not None:
            return profile.scheme_name
    return ""


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


def _resolve_nav(
    *,
    scheme_code: str,
    display_currency: str,
) -> tuple[Optional[Decimal], str, str, bool]:
    """
    Returns (latest NAV, nav_status, price_status, display_fx_unavailable).

    NAV is always INR; price_status mirrors nav_status for UI compatibility.
    """
    display_fx_unavailable = display_currency != MF_BASE_CURRENCY
    nav_result = latest_nav_for_asset(scheme_code)
    if nav_result is None or nav_result.status != "ok" or nav_result.nav is None:
        return None, "nav_missing", "price_missing", display_fx_unavailable
    return nav_result.nav, "ok", "ok", display_fx_unavailable


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


def _build_mf_holding_item(
    *,
    scheme_code: str,
    folio_number: str,
    db_txns: list[TransactionModel],
    display_currency: str,
) -> dict:
    scheme_code = normalize_scheme_code(scheme_code)
    finance_txns = _to_finance_dtos(db_txns)
    oversold = detect_oversell(finance_txns)

    current_nav, nav_status, price_status, fx_missing = _resolve_nav(
        scheme_code=scheme_code,
        display_currency=display_currency,
    )

    fifo_metrics = calculate_fifo_cost_basis_metrics(
        finance_txns,
        current_price=current_nav,
    )
    qty = fifo_metrics.cumulative_qty
    invested = fifo_metrics.cumulative_invested_amount
    avg_cost = fifo_metrics.avg_cost_per_share if qty > 0 else Decimal("0")

    if current_nav is not None and qty > 0:
        current_value = current_nav * qty
    else:
        current_value = Decimal("0")

    warnings: list[str] = []
    status = _holding_status(qty=qty, oversold=oversold)
    if oversold:
        warnings.append("SELL quantity exceeded available FIFO lots for this asset")
    if nav_status == "nav_missing" and qty > 0:
        warnings.append("Latest cached NAV is missing")

    xirr = None
    if current_nav is not None:
        xirr = calculate_xirr(
            finance_txns,
            current_price=current_nav,
            current_date=date.today(),
            include_fees_in_cashflows=True,
        )

    item = {
        "asset_type": "MUTUAL_FUND",
        "asset_symbol": scheme_code,
        "scheme_code": scheme_code,
        "scheme_name": _scheme_name_for_mf_txns(db_txns),
        "folio_number": folio_number,
        "holding_key": _mf_holding_key(scheme_code, folio_number),
        "quantity": float(qty),
        "units": float(qty),
        "avg_cost_per_share": float(avg_cost),
        "latest_price": _float_or_none(current_nav),
        "latest_nav": _float_or_none(current_nav),
        "current_price": _float_or_none(current_nav),
        "current_value": float(current_value),
        "invested_amount": float(invested),
        "invested": float(invested),
        "realized_gain_loss": float(fifo_metrics.realized_pl),
        "realized_pl": float(fifo_metrics.realized_pl),
        "unrealized_gain_loss": float(fifo_metrics.unrealized_pl),
        "unrealized_pl": float(fifo_metrics.unrealized_pl),
        "currency": MF_BASE_CURRENCY,
        "price_status": price_status,
        "nav_status": nav_status,
        "holding_status": status,
        "warnings": warnings,
        "xirr": xirr,
        "fx_status": "fx_unavailable" if fx_missing else "ok",
        "_fx_missing": fx_missing,
    }
    item.update(_mf_classification_fields(db_txns))
    return item


@dataclass
class HoldingsResult:
    fx_status: str
    holdings: list[dict] = field(default_factory=list)
    allocation: list[dict] = field(default_factory=list)
    display_currency: str = "EUR"
    warnings: list[str] = field(default_factory=list)


def build_holdings(
    *,
    scope: ResolvedPortfolioScope,
    display_currency: str = "EUR",
    user=None,
) -> HoldingsResult:
    display_currency = _norm_ccy(display_currency)
    queryset = _fifo_eligible_queryset(scope.portfolio_ids)
    by_symbol = _transactions_by_symbol(queryset)
    by_mf = _transactions_by_mf_holding(queryset)

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

    for key in sorted(by_mf.keys()):
        db_txns = by_mf[key]
        scheme_code = normalize_scheme_code(db_txns[0].asset_symbol)
        folio_number = db_txns[0].mutual_fund_detail.folio.folio_number
        item = _build_mf_holding_item(
            scheme_code=scheme_code,
            folio_number=folio_number,
            db_txns=db_txns,
            display_currency=display_currency,
        )
        if item.pop("_fx_missing", False):
            any_fx_missing = True
        if display_currency != item["currency"]:
            any_fx_missing = True
        holdings.append(item)

    fd_rows = build_fd_holding_rows(scope, display_currency=display_currency)
    for item in fd_rows:
        if item.pop("_fx_missing", False):
            any_fx_missing = True
        if display_currency != item["currency"]:
            any_fx_missing = True
        holdings.append(item)

    if user is not None:
        bank_rows = build_bank_cash_holding_rows(
            user, scope, display_currency=display_currency
        )
        for item in bank_rows:
            if item.pop("_fx_missing", False):
                any_fx_missing = True
            if display_currency != item["currency"]:
                any_fx_missing = True
            holdings.append(item)

    fx_status = "fx_unavailable" if any_fx_missing else "ok"

    cash_display = build_cash_display_summary(scope, display_currency)
    cash_rows = cash_allocation_rows(cash_display)
    if cash_display.fx_status == "fx_unavailable":
        fx_status = "fx_unavailable"
    elif cash_display.fx_status == "filled" and fx_status == "ok":
        fx_status = "filled"

    allocation: list[dict] = []
    for item in holdings:
        qty = Decimal(str(item.get("quantity") or 0))
        cv = Decimal(str(item.get("current_value") or 0))
        if item.get("asset_type") == "FIXED_DEPOSIT":
            if item.get("holding_status") == "closed" or cv <= 0:
                continue
            allocation.append({k: v for k, v in item.items() if not k.startswith("_")})
            continue
        if item.get("asset_type") == "BANK_CASH":
            if item.get("holding_status") == "closed" or cv <= 0:
                continue
            allocation.append({k: v for k, v in item.items() if not k.startswith("_")})
            continue
        if item.get("holding_status") == "closed" or qty <= 0 or cv <= 0:
            continue
        allocation.append({k: v for k, v in item.items() if not k.startswith("_")})
    allocation.extend(cash_rows)

    return HoldingsResult(
        fx_status=fx_status,
        holdings=holdings,
        allocation=allocation,
        display_currency=display_currency,
        warnings=list(cash_display.warnings),
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
    asset_type: Optional[str] = None
    scheme_code: Optional[str] = None
    scheme_name: Optional[str] = None
    folio_number: Optional[str] = None
    latest_nav: Optional[float] = None
    nav_status: Optional[str] = None
    units: Optional[float] = None
    primary_asset_class: Optional[str] = None
    classification_source: Optional[str] = None
    classification_notes: Optional[str] = None


class AssetNotFoundError(Exception):
    pass


class AssetDetailValidationError(Exception):
    pass


def _stock_transaction_rows(db_txns: list[TransactionModel]) -> list[dict]:
    return [
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


def _mf_transaction_rows(db_txns: list[TransactionModel]) -> list[dict]:
    rows: list[dict] = []
    for t in sorted(db_txns, key=lambda x: (x.date, x.id)):
        detail = t.mutual_fund_detail
        rows.append(
            {
                "id": t.id,
                "date": t.date.isoformat(),
                "type": t.type,
                "quantity": float(t.quantity),
                "price_per_share": float(t.price_per_share or 0),
                "fees": float(t.fees),
                "asset_type": "MUTUAL_FUND",
                "investment_date": detail.investment_date.isoformat(),
                "nav_date": detail.nav_date.isoformat(),
                "nav": float(detail.nav),
                "units_allotted": float(detail.units_allotted),
                "paid_value": float(detail.paid_value),
                "market_value": float(detail.market_value),
                "folio_number": detail.folio.folio_number,
            }
        )
    return rows


def _build_stock_asset_detail(
    *,
    sym: str,
    db_txns: list[TransactionModel],
    display_currency: str,
) -> AssetDetailResult:
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
        transactions=_stock_transaction_rows(db_txns),
    )


def _build_mf_asset_detail(
    *,
    scheme_code: str,
    folio_number: str,
    db_txns: list[TransactionModel],
    display_currency: str,
) -> AssetDetailResult:
    scheme_code = normalize_scheme_code(scheme_code)
    finance_txns = _to_finance_dtos(db_txns)
    oversold = detect_oversell(finance_txns)

    current_nav, nav_status, price_status, fx_missing = _resolve_nav(
        scheme_code=scheme_code,
        display_currency=display_currency,
    )
    if display_currency != MF_BASE_CURRENCY:
        fx_missing = True

    fifo_metrics = calculate_fifo_cost_basis_metrics(
        finance_txns,
        current_price=current_nav,
    )
    qty = fifo_metrics.cumulative_qty
    if current_nav is not None and qty > 0:
        current_value = current_nav * qty
    else:
        current_value = Decimal("0")

    warnings: list[str] = []
    status = _holding_status(qty=qty, oversold=oversold)
    if oversold:
        warnings.append("SELL quantity exceeded available FIFO lots for this asset")
    if nav_status == "nav_missing" and qty > 0:
        warnings.append("Latest cached NAV is missing")

    xirr = None
    if current_nav is not None:
        xirr = calculate_xirr(
            finance_txns,
            current_price=current_nav,
            current_date=date.today(),
            include_fees_in_cashflows=True,
        )

    asset, profile = _mf_asset_and_profile(db_txns)
    cls_fields = classification_fields_for_asset(asset, profile)

    return AssetDetailResult(
        asset_symbol=scheme_code,
        currency=MF_BASE_CURRENCY,
        current_price=_float_or_none(current_nav),
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
        transactions=_mf_transaction_rows(db_txns),
        asset_type="MUTUAL_FUND",
        scheme_code=scheme_code,
        scheme_name=_scheme_name_for_mf_txns(db_txns),
        folio_number=folio_number,
        latest_nav=_float_or_none(current_nav),
        nav_status=nav_status,
        units=float(qty),
        primary_asset_class=cls_fields.get("primary_asset_class"),
        classification_source=cls_fields.get("classification_source"),
        classification_notes=cls_fields.get("classification_notes"),
    )


def build_asset_detail(
    *,
    asset_symbol: str,
    scope: ResolvedPortfolioScope,
    display_currency: str = "EUR",
    folio_number: str | None = None,
) -> AssetDetailResult:
    display_currency = _norm_ccy(display_currency)
    if not (asset_symbol or "").strip():
        raise AssetNotFoundError("Asset symbol is required")

    base_qs = _fifo_eligible_queryset(scope.portfolio_ids)
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
        folios = {
            t.mutual_fund_detail.folio.folio_number for t in mf_txns
        }
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
            return _build_mf_asset_detail(
                scheme_code=scheme,
                folio_number=folio_filter,
                db_txns=db_txns,
                display_currency=display_currency,
            )
        if len(folios) > 1:
            raise AssetDetailValidationError(
                "folio_number is required when multiple folios exist for this scheme"
            )
        folio = next(iter(folios))
        return _build_mf_asset_detail(
            scheme_code=scheme,
            folio_number=folio,
            db_txns=mf_txns,
            display_currency=display_currency,
        )

    if stock_txns:
        return _build_stock_asset_detail(
            sym=stock_sym,
            db_txns=stock_txns,
            display_currency=display_currency,
        )

    raise AssetNotFoundError(f"No transactions found for {asset_symbol}")


def validate_display_currency(value: str) -> str:
    normalized = _norm_ccy(value)
    allowed = {c.value for c in DisplayCurrency}
    if normalized not in allowed:
        raise HoldingsValidationError(f"Unsupported display_currency: {value}")
    return normalized
