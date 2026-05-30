from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from django.db.models import Max, Min, Q
from django.utils import timezone

from market_data.models import AssetType, HistoricalPrice
from market_data.price_lookup import normalize_asset_symbol
from market_data.providers.base import PriceProvider
from market_data.providers.yfinance_provider import default_price_provider
from market_data.services.symbols import (
    earliest_transaction_date_for_symbol,
    stock_transaction_symbols,
)
from settings_app.models import AppSettings
from transactions.models import Transaction

logger = logging.getLogger(__name__)


def _stock_price_filter() -> Q:
    return Q(asset_type=AssetType.STOCK) | Q(asset_type__isnull=True)


def _earliest_stock_price_date(symbol: str) -> date | None:
    sym = normalize_asset_symbol(symbol)
    agg = (
        HistoricalPrice.objects.filter(
            Q(asset_symbol__iexact=sym),
            _stock_price_filter(),
        ).aggregate(min_date=Min("date"))
    )
    return agg.get("min_date")


def _latest_stock_price_date(symbol: str) -> date | None:
    sym = normalize_asset_symbol(symbol)
    agg = (
        HistoricalPrice.objects.filter(
            Q(asset_symbol__iexact=sym),
            _stock_price_filter(),
        ).aggregate(max_date=Max("date"))
    )
    return agg.get("max_date")


def resolve_stock_sync_start_date(
    *,
    min_txn_date: date,
    min_hist_date: date | None,
    max_hist_date: date | None,
) -> date:
    """
    Choose provider fetch start for incremental stock price sync.

    - No cached rows: from earliest transaction date.
    - Earliest transaction before earliest cached price: backfill from transaction date.
    - Otherwise: incremental from latest cached date + 1 day.
    """
    if max_hist_date is None or min_hist_date is None:
        return min_txn_date
    if min_txn_date < min_hist_date:
        return min_txn_date
    return max_hist_date + timedelta(days=1)


def _symbol_base_currency(symbol: str) -> str:
    sym = normalize_asset_symbol(symbol)
    raw = (
        Transaction.objects.filter(
            asset_symbol__iexact=sym,
            mutual_fund_detail__isnull=True,
        )
        .aggregate(min_ccy=Min("currency"))
        .get("min_ccy")
    )
    return (raw or "EUR").strip().upper() or "EUR"


def upsert_stock_price(
    *,
    symbol: str,
    row_date: date,
    close_price,
    currency: str,
    source: str = "yfinance",
) -> HistoricalPrice:
    sym = normalize_asset_symbol(symbol)
    obj, _ = HistoricalPrice.objects.update_or_create(
        asset_symbol=sym,
        date=row_date,
        defaults={
            "close_price": close_price,
            "currency": (currency or "USD").strip().upper() or "USD",
            "source": source,
            "asset_type": AssetType.STOCK,
        },
    )
    return obj


def sync_one_stock_symbol(
    symbol: str,
    provider: PriceProvider,
    *,
    end: date | None = None,
) -> bool:
    """Incremental sync for one stock symbol. Returns False on provider failure."""
    sym = normalize_asset_symbol(symbol)
    if not sym:
        return True

    min_txn_date = earliest_transaction_date_for_symbol(sym)
    if not min_txn_date:
        return True

    end = end or date.today()
    min_hist_date = _earliest_stock_price_date(sym)
    max_hist_date = _latest_stock_price_date(sym)
    start_date = resolve_stock_sync_start_date(
        min_txn_date=min_txn_date,
        min_hist_date=min_hist_date,
        max_hist_date=max_hist_date,
    )

    if start_date > end:
        return True

    if min_hist_date and min_txn_date < min_hist_date:
        logger.info(
            "Backfilling stock prices for %s from %s (earliest transaction before "
            "earliest cached price %s)",
            sym,
            start_date,
            min_hist_date,
        )

    try:
        rows, quote_ccy = provider.fetch_history(sym, start_date, end)
    except Exception as exc:
        logger.error("Failed to fetch history for %s: %s", sym, exc)
        return False

    if not rows:
        logger.warning(
            "Empty price history for %s from %s to %s",
            sym,
            start_date,
            end,
        )
        return True

    default_ccy = quote_ccy or _symbol_base_currency(sym)
    for row in rows:
        upsert_stock_price(
            symbol=sym,
            row_date=row.date,
            close_price=row.close,
            currency=row.currency or default_ccy,
        )
    return True


@dataclass
class StockSyncResult:
    success: bool
    symbols_synced: int


def sync_stock_prices(
    *,
    only_symbols: Optional[set[str]] = None,
    provider: PriceProvider | None = None,
    update_last_sync: bool = True,
) -> StockSyncResult:
    """
    Incrementally sync STOCK historical prices for transaction symbols.
    When only_symbols is set, sync intersection with transaction symbols only.
    """
    provider = provider or default_price_provider()
    txn_symbols = stock_transaction_symbols()
    if only_symbols is not None:
        requested = {normalize_asset_symbol(s) for s in only_symbols if s}
        symbols = sorted(txn_symbols & requested)
    else:
        symbols = sorted(txn_symbols)

    success = True
    for sym in symbols:
        ok = sync_one_stock_symbol(sym, provider)
        if not ok:
            success = False

    if success and update_last_sync:
        settings = AppSettings.objects.first()
        if settings:
            settings.last_sync_timestamp = timezone.now()
            settings.save(update_fields=["last_sync_timestamp", "updated_at"])

    return StockSyncResult(success=success, symbols_synced=len(symbols))
