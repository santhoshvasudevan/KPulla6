from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Iterable

from django.db.models import Max, Min, Q

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


def _earliest_fx_date(frm: str, to: str) -> date | None:
    agg = FXRate.objects.filter(
        from_currency=frm, to_currency=to
    ).aggregate(min_date=Min("date"))
    return agg.get("min_date")


def _latest_fx_date(frm: str, to: str) -> date | None:
    agg = FXRate.objects.filter(
        from_currency=frm, to_currency=to
    ).aggregate(max_date=Max("date"))
    return agg.get("max_date")


def resolve_fx_sync_start_date(
    *,
    min_required_date: date,
    min_fx_date: date | None,
    max_fx_date: date | None,
) -> date:
    """
    Choose provider fetch start for incremental FX sync.

    - No cached rows: from earliest required valuation date.
    - Required date before earliest cached FX: backfill from required date.
    - Otherwise: incremental from latest cached date + 1 day.
    """
    if max_fx_date is None or min_fx_date is None:
        return min_required_date
    if min_required_date < min_fx_date:
        return min_required_date
    return max_fx_date + timedelta(days=1)


def _symbol_base_currency(sym: str) -> str:
    raw = (
        Transaction.objects.filter(asset_symbol__iexact=sym)
        .aggregate(min_ccy=Min("currency"))
        .get("min_ccy")
    )
    return _norm_ccy(raw) or "EUR"


def earliest_required_fx_date(frm: str, to: str) -> date | None:
    """Earliest date an FX pair is needed for portfolio valuation."""
    frm = _norm_ccy(frm)
    to = _norm_ccy(to)
    if not frm or not to or frm == to:
        return None

    candidates: list[date] = []
    settings = AppSettings.objects.first()
    display = _norm_ccy(settings.display_currency if settings else "EUR")

    if to == display:
        agg = Transaction.objects.filter(currency__iexact=frm).aggregate(
            min_date=Min("date")
        )
        if agg.get("min_date"):
            candidates.append(agg["min_date"])

    symbols = {
        normalize_asset_symbol(s)
        for s in Transaction.objects.values_list("asset_symbol", flat=True).distinct()
        if s
    }

    stock_filter = Q(asset_type=AssetType.STOCK) | Q(asset_type__isnull=True)

    for sym in symbols:
        min_txn = (
            Transaction.objects.filter(asset_symbol__iexact=sym)
            .aggregate(min_date=Min("date"))
            .get("min_date")
        )
        if not min_txn:
            continue
        base = _symbol_base_currency(sym)

        price_qs = HistoricalPrice.objects.filter(
            Q(asset_symbol__iexact=sym),
            stock_filter,
        )
        min_price = price_qs.aggregate(min_date=Min("date")).get("min_date")
        first_price = price_qs.order_by("date").first()
        price_ccy = _norm_ccy(first_price.currency) if first_price else None

        relevant_dates = [d for d in (min_txn, min_price) if d is not None]

        if price_ccy == frm and base == to:
            candidates.extend(relevant_dates)
        if price_ccy == frm and display == to:
            candidates.extend(relevant_dates)
        if base == frm and display == to:
            candidates.append(min_txn)

    return min(candidates) if candidates else None


def sync_fx_pair(
    frm: str,
    to: str,
    min_required: date,
    end: date,
    provider: FxProvider,
) -> bool:
    if frm == to or min_required > end:
        return True

    min_fx = _earliest_fx_date(frm, to)
    max_fx = _latest_fx_date(frm, to)
    start_eff = resolve_fx_sync_start_date(
        min_required_date=min_required,
        min_fx_date=min_fx,
        max_fx_date=max_fx,
    )
    if start_eff > end:
        return True

    if min_fx and min_required < min_fx:
        logger.info(
            "Backfilling FX %s->%s from %s (required from %s before earliest cached %s)",
            frm,
            to,
            start_eff,
            min_required,
            min_fx,
        )

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
    if not pair_set:
        return FxSyncResult(success=True, partial=False, pairs_attempted=0)

    end = date.today()
    success = True
    partial = False

    for frm, to in sorted(pair_set):
        min_required = earliest_required_fx_date(frm, to)
        if min_required is None:
            continue
        ok = sync_fx_pair(frm, to, min_required, end, provider)
        if not ok:
            success = False
        elif not _pair_has_rates_in_range(frm, to, min_required, end):
            partial = True

    return FxSyncResult(
        success=success,
        partial=partial,
        pairs_attempted=len(pair_set),
    )
