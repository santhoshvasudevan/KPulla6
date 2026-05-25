from __future__ import annotations

from datetime import date

from django.db.models import Min

from market_data.price_lookup import normalize_asset_symbol
from transactions.models import Transaction


def transaction_symbols() -> set[str]:
    symbols: set[str] = set()
    for raw in Transaction.objects.values_list("asset_symbol", flat=True).distinct():
        sym = normalize_asset_symbol(raw)
        if sym:
            symbols.add(sym)
    return symbols


def earliest_transaction_date() -> date | None:
    agg = Transaction.objects.aggregate(min_date=Min("date"))
    value = agg.get("min_date")
    return value if isinstance(value, date) else None


def earliest_transaction_date_for_symbol(symbol: str) -> date | None:
    sym = normalize_asset_symbol(symbol)
    if not sym:
        return None
    agg = (
        Transaction.objects.filter(asset_symbol__iexact=sym)
        .aggregate(min_date=Min("date"))
    )
    value = agg.get("min_date")
    return value if isinstance(value, date) else None
