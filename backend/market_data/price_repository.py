from __future__ import annotations

from datetime import date
from typing import Iterable

from django.db.models import Q

from market_data.models import AssetType, HistoricalPrice
from market_data.price_lookup import normalize_asset_symbol


def _stock_filter() -> Q:
    return Q(asset_type=AssetType.STOCK) | Q(asset_type__isnull=True)


def list_stock_prices_in_range(
    symbols: Iterable[str],
    start: date,
    end: date,
) -> list[HistoricalPrice]:
    normalized = sorted({normalize_asset_symbol(s) for s in symbols if s})
    if not normalized:
        return []
    sym_filter = Q()
    for sym in normalized:
        sym_filter |= Q(asset_symbol__iexact=sym)
    return list(
        HistoricalPrice.objects.filter(
            sym_filter,
            _stock_filter(),
            date__gte=start,
            date__lte=end,
        ).order_by("asset_symbol", "date")
    )


def list_index_prices_in_range(
    symbol: str,
    start: date,
    end: date,
) -> list[HistoricalPrice]:
    """Benchmark index rows (asset_type INDEX), ascending by date."""
    sym = normalize_asset_symbol(symbol)
    if not sym:
        return []
    return list(
        HistoricalPrice.objects.filter(
            Q(asset_symbol__iexact=sym),
            asset_type=AssetType.INDEX,
            date__gte=start,
            date__lte=end,
        ).order_by("date")
    )


def latest_stock_prices_by_symbol(symbols: Iterable[str]) -> dict[str, HistoricalPrice]:
    normalized = sorted({normalize_asset_symbol(s) for s in symbols if s})
    out: dict[str, HistoricalPrice] = {}
    for sym in normalized:
        row = (
            HistoricalPrice.objects.filter(
                Q(asset_symbol__iexact=sym),
                _stock_filter(),
            )
            .order_by("-date", "-id")
            .first()
        )
        if row:
            out[sym] = row
    return out


def last_stock_prices_on_or_before(
    symbols: Iterable[str], as_of: date
) -> list[HistoricalPrice]:
    """Latest cached stock row per symbol with ``date <= as_of`` (for range bootstrap)."""
    normalized = sorted({normalize_asset_symbol(s) for s in symbols if s})
    rows: list[HistoricalPrice] = []
    for sym in normalized:
        row = (
            HistoricalPrice.objects.filter(
                Q(asset_symbol__iexact=sym),
                _stock_filter(),
                date__lte=as_of,
            )
            .order_by("-date", "-id")
            .first()
        )
        if row:
            rows.append(row)
    return rows
