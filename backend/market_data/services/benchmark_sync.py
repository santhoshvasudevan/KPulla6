from __future__ import annotations

import logging
from datetime import date, timedelta

from django.db.models import Max, Min

from market_data.models import AssetType, BenchmarkIndexConfig, HistoricalPrice
from market_data.providers.base import PriceProvider
from market_data.providers.yfinance_provider import (
    default_price_provider,
    normalize_provider_symbol,
)
from market_data.seed import ensure_benchmark_indices
from market_data.services.price_sync import resolve_stock_sync_start_date
from market_data.services.symbols import earliest_transaction_date

logger = logging.getLogger(__name__)


def _norm_ccy(value: str | None) -> str:
    return (value or "USD").strip().upper() or "USD"


def _earliest_index_price_date(symbol: str) -> date | None:
    agg = (
        HistoricalPrice.objects.filter(
            asset_symbol=symbol,
            asset_type=AssetType.INDEX,
        ).aggregate(min_date=Min("date"))
    )
    return agg.get("min_date")


def _latest_index_price_date(symbol: str) -> date | None:
    agg = (
        HistoricalPrice.objects.filter(
            asset_symbol=symbol,
            asset_type=AssetType.INDEX,
        ).aggregate(max_date=Max("date"))
    )
    return agg.get("max_date")


def upsert_index_price(
    *,
    symbol: str,
    row_date: date,
    close_price,
    currency: str,
    source: str = "yfinance",
) -> HistoricalPrice:
    obj, _ = HistoricalPrice.objects.update_or_create(
        asset_symbol=symbol,
        date=row_date,
        defaults={
            "close_price": close_price,
            "currency": _norm_ccy(currency),
            "source": source,
            "asset_type": AssetType.INDEX,
        },
    )
    return obj


def sync_benchmark_prices(
    *,
    provider: PriceProvider | None = None,
    end: date | None = None,
) -> bool:
    """
    Incrementally sync enabled benchmark indices (asset_type=INDEX).

    Anchor date: earliest transaction date across all portfolios (stocks and MF).
    Start date follows the same rules as stock price sync:
    - No cache: from anchor
    - Anchor before earliest cached row: backfill from anchor
    - Otherwise: latest cached index date + 1 day
    """
    ensure_benchmark_indices()
    anchor_date = earliest_transaction_date()
    if not anchor_date:
        return True

    provider = provider or default_price_provider()
    end = end or date.today()
    success = True

    configs = BenchmarkIndexConfig.objects.filter(enabled=True).order_by("display_name")
    for cfg in configs:
        sym = normalize_provider_symbol(cfg.symbol, is_benchmark=True)
        if not sym:
            continue

        min_hist = _earliest_index_price_date(sym)
        max_hist = _latest_index_price_date(sym)
        start_date = resolve_stock_sync_start_date(
            min_txn_date=anchor_date,
            min_hist_date=min_hist,
            max_hist_date=max_hist,
        )
        if start_date > end:
            continue

        if min_hist and anchor_date < min_hist:
            logger.info(
                "Backfilling benchmark prices for %s from %s (anchor before "
                "earliest cached price %s)",
                sym,
                start_date,
                min_hist,
            )

        try:
            rows, quote_ccy = provider.fetch_history(sym, start_date, end)
        except Exception as exc:
            logger.error("Failed to sync benchmark %s: %s", sym, exc)
            success = False
            continue

        if not rows:
            logger.warning("Empty benchmark history for %s", sym)
            continue

        ccy = _norm_ccy(cfg.currency) if cfg.currency else _norm_ccy(quote_ccy)
        src = cfg.source or "yfinance"
        for row in rows:
            upsert_index_price(
                symbol=sym,
                row_date=row.date,
                close_price=row.close,
                currency=row.currency or ccy,
                source=src,
            )

    return success


def list_enabled_benchmark_indices() -> list[dict[str, str]]:
    rows = (
        BenchmarkIndexConfig.objects.filter(enabled=True)
        .order_by("display_name")
        .values("symbol", "display_name")
    )
    return [{"symbol": r["symbol"], "name": r["display_name"]} for r in rows]
