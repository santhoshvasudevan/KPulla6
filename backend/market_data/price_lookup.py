from __future__ import annotations

from django.db.models import Q

from market_data.models import AssetType, HistoricalPrice


def normalize_asset_symbol(symbol: str) -> str:
    return (symbol or "").strip().upper()


def latest_historical_price(asset_symbol: str) -> HistoricalPrice | None:
    """Latest STOCK (or legacy null asset_type) close for symbol, case-insensitive."""
    sym = normalize_asset_symbol(asset_symbol)
    if not sym:
        return None
    return (
        HistoricalPrice.objects.filter(
            Q(asset_symbol__iexact=sym),
            Q(asset_type=AssetType.STOCK) | Q(asset_type__isnull=True),
        )
        .order_by("-date", "-id")
        .first()
    )
