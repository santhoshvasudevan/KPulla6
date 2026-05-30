from __future__ import annotations

from datetime import date

from django.db.models import Min, Q

from market_data.models import Asset, AssetType
from market_data.price_lookup import normalize_asset_symbol
from transactions.models import Transaction


def _mutual_fund_asset_symbols() -> set[str]:
    symbols: set[str] = set()
    for raw in Asset.objects.filter(asset_type=AssetType.MUTUAL_FUND).values_list(
        "symbol", flat=True
    ):
        sym = normalize_asset_symbol(raw)
        if sym:
            symbols.add(sym)
    return symbols


def _stock_transaction_filter() -> Q:
    """Transactions eligible for yfinance stock/ETF price sync."""
    return Q(mutual_fund_detail__isnull=True)


def stock_transaction_symbols() -> set[str]:
    """
    Distinct asset symbols from stock/ETF transactions only.

    Excludes mutual fund rows (MutualFundTransactionDetail) and symbols
    registered as MUTUAL_FUND assets (AMFI scheme codes).
    """
    mf_symbols = _mutual_fund_asset_symbols()
    symbols: set[str] = set()
    for raw in (
        Transaction.objects.filter(_stock_transaction_filter())
        .values_list("asset_symbol", flat=True)
        .distinct()
    ):
        sym = normalize_asset_symbol(raw)
        if sym and sym not in mf_symbols:
            symbols.add(sym)
    return symbols


def transaction_symbols() -> set[str]:
    """Alias for stock/ETF transaction symbols used by price sync."""
    return stock_transaction_symbols()


def earliest_stock_transaction_date() -> date | None:
    """
    Earliest transaction date for stock/ETF rows only.

    Used as the per-symbol anchor for yfinance stock price sync (excludes MF buys).
    """
    agg = (
        Transaction.objects.filter(_stock_transaction_filter())
        .aggregate(min_date=Min("date"))
    )
    value = agg.get("min_date")
    return value if isinstance(value, date) else None


def earliest_transaction_date() -> date | None:
    agg = Transaction.objects.aggregate(min_date=Min("date"))
    value = agg.get("min_date")
    return value if isinstance(value, date) else None


def earliest_transaction_date_for_symbol(symbol: str) -> date | None:
    sym = normalize_asset_symbol(symbol)
    if not sym:
        return None
    if sym in _mutual_fund_asset_symbols():
        return None
    agg = (
        Transaction.objects.filter(
            asset_symbol__iexact=sym,
        )
        .filter(_stock_transaction_filter())
        .aggregate(min_date=Min("date"))
    )
    value = agg.get("min_date")
    return value if isinstance(value, date) else None
