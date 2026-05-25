from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Iterable

from django.db.models import Max, Min

from fx.models import FXRate
from fx.providers.base import FxProvider
from fx.providers.yfinance_fx import default_fx_provider
from market_data.models import AssetType, HistoricalPrice
from market_data.price_lookup import normalize_asset_symbol
from settings_app.models import AppSettings
from transactions.models import Transaction

logger = logging.getLogger(__name__)


def _norm_ccy(value: str | None) -> str:
    return (value or "").strip().upper()


def upsert_fx_rate(
    *,
    from_currency: str,
    to_currency: str,
    row_date: date,
    rate: Decimal,
    source: str = "yfinance",
) -> FXRate:
    frm = _norm_ccy(from_currency)
    to = _norm_ccy(to_currency)
    obj, _ = FXRate.objects.update_or_create(
        from_currency=frm,
        to_currency=to,
        date=row_date,
        defaults={"rate": rate, "source": source},
    )
    return obj


def _pair_has_rates_in_range(
    frm: str, to: str, start: date, end: date
) -> bool:
    if FXRate.objects.filter(
        from_currency=frm,
        to_currency=to,
        date__gte=start,
        date__lte=end,
    ).exists():
        return True
    return FXRate.objects.filter(
        from_currency=to,
        to_currency=frm,
        date__gte=start,
        date__lte=end,
    ).exists()


def _latest_fx_date(frm: str, to: str) -> date | None:
    agg = FXRate.objects.filter(
        from_currency=frm, to_currency=to
    ).aggregate(max_date=Max("date"))
    return agg.get("max_date")


def sync_fx_pair(
    frm: str,
    to: str,
    start: date,
    end: date,
    provider: FxProvider,
) -> bool:
    if frm == to or start > end:
        return True

    latest = _latest_fx_date(frm, to)
    start_eff = latest + timedelta(days=1) if latest else start
    if start_eff > end:
        return True

    try:
        rows = provider.fetch_rates(frm, to, start_eff, end)
    except Exception as exc:
        logger.error("Failed FX fetch %s->%s: %s", frm, to, exc)
        return False

    if not rows:
        logger.warning("Empty FX history for %s -> %s", frm, to)
        return True

    for row in rows:
        upsert_fx_rate(
            from_currency=frm,
            to_currency=to,
            row_date=row.date,
            rate=row.rate,
        )
    return True


def collect_fx_pairs() -> set[tuple[str, str]]:
    """Currency pairs implied by transactions, price rows, and display currency."""
    pairs: set[tuple[str, str]] = set()
    settings = AppSettings.objects.first()
    display = _norm_ccy(settings.display_currency if settings else "EUR")

    txn_ccys = {
        _norm_ccy(c)
        for c in Transaction.objects.values_list("currency", flat=True).distinct()
        if c
    }
    for ccy in txn_ccys:
        if ccy and ccy != display:
            pairs.add((ccy, display))

    for hp in HistoricalPrice.objects.filter(asset_type=AssetType.STOCK).only(
        "asset_symbol", "currency"
    ):
        price_ccy = _norm_ccy(hp.currency)
        sym = normalize_asset_symbol(hp.asset_symbol)
        txn_ccy = (
            Transaction.objects.filter(asset_symbol__iexact=sym)
            .aggregate(min_ccy=Min("currency"))
            .get("min_ccy")
        )
        base = _norm_ccy(txn_ccy)
        if price_ccy and base and price_ccy != base:
            pairs.add((price_ccy, base))
        if price_ccy and display and price_ccy != display:
            pairs.add((price_ccy, display))
        if base and display and base != display:
            pairs.add((base, display))

    return {(f, t) for f, t in pairs if f and t and f != t}


@dataclass
class FxSyncResult:
    success: bool
    partial: bool
    pairs_attempted: int


def sync_fx_rates(
    *,
    pairs: Iterable[tuple[str, str]] | None = None,
    provider: FxProvider | None = None,
) -> FxSyncResult:
    """
    Incrementally sync FX rates for discovered currency pairs.
    When provider returns no data, logs a warning and continues (partial=True).
    """
    provider = provider or default_fx_provider()
    pair_set = set(pairs) if pairs is not None else collect_fx_pairs()

    min_txn = Transaction.objects.aggregate(min_date=Min("date")).get("min_date")
    if not min_txn:
        return FxSyncResult(success=True, partial=False, pairs_attempted=0)

    end = date.today()
    success = True
    partial = False

    for frm, to in sorted(pair_set):
        ok = sync_fx_pair(frm, to, min_txn, end, provider)
        if not ok:
            success = False
        elif not _pair_has_rates_in_range(frm, to, min_txn, end):
            partial = True

    return FxSyncResult(
        success=success,
        partial=partial,
        pairs_attempted=len(pair_set),
    )
