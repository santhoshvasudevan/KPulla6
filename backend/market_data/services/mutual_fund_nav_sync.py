from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from django.db.models import Max, Min

from market_data.models import Asset, AssetType, HistoricalPrice, MutualFundProfile
from market_data.nav_lookup import normalize_scheme_code
from market_data.providers.mutual_fund_nav_provider import (
    AmfiNavProvider,
    MutualFundNavProvider,
    default_mutual_fund_nav_provider,
)
from transactions.models import MutualFundTransactionDetail, Transaction

logger = logging.getLogger(__name__)

MF_NAV_SOURCE = AmfiNavProvider.source_label
MF_NAV_CURRENCY = "INR"


def _latest_mutual_fund_nav_date(scheme_code: str) -> date | None:
    code = normalize_scheme_code(scheme_code)
    if not code:
        return None
    agg = HistoricalPrice.objects.filter(
        asset_symbol=code,
        asset_type=AssetType.MUTUAL_FUND,
    ).aggregate(max_date=Max("date"))
    return agg.get("max_date")


def _earliest_relevant_nav_date(scheme_code: str) -> date | None:
    """
    Earliest nav_date from MF transaction details, else earliest transaction date
    for the scheme_code, if any.
    """
    code = normalize_scheme_code(scheme_code)
    if not code:
        return None

    detail_agg = MutualFundTransactionDetail.objects.filter(
        transaction__asset_symbol=code,
    ).aggregate(min_date=Min("nav_date"))
    detail_min = detail_agg.get("min_date")

    txn_agg = Transaction.objects.filter(asset_symbol=code).aggregate(
        min_date=Min("date")
    )
    txn_min = txn_agg.get("min_date")

    candidates = [d for d in (detail_min, txn_min) if d is not None]
    if not candidates:
        return None
    return min(candidates)


def upsert_mutual_fund_nav(
    *,
    scheme_code: str,
    row_date: date,
    nav,
    currency: str = MF_NAV_CURRENCY,
    source: str = MF_NAV_SOURCE,
    asset: Asset | None = None,
) -> HistoricalPrice:
    code = normalize_scheme_code(scheme_code)
    obj, _ = HistoricalPrice.objects.update_or_create(
        asset_symbol=code,
        date=row_date,
        defaults={
            "close_price": nav,
            "currency": (currency or MF_NAV_CURRENCY).strip().upper() or MF_NAV_CURRENCY,
            "source": source,
            "asset_type": AssetType.MUTUAL_FUND,
            "asset": asset,
        },
    )
    return obj


def sync_one_mutual_fund(
    profile: MutualFundProfile,
    provider: MutualFundNavProvider,
    *,
    end: date | None = None,
) -> bool:
    """
    Incrementally sync NAV history for one mutual fund profile.

    Returns False on provider failure; True when skipped (up-to-date / empty) or synced.
    """
    asset = profile.asset
    if asset.asset_type != AssetType.MUTUAL_FUND or not asset.is_active:
        return True

    scheme_code = normalize_scheme_code(profile.scheme_code or asset.symbol)
    if not scheme_code:
        return True

    end = end or date.today()
    max_hist_date = _latest_mutual_fund_nav_date(scheme_code)
    if max_hist_date is not None:
        start_date = max_hist_date + timedelta(days=1)
    else:
        start_date = _earliest_relevant_nav_date(scheme_code)
        if start_date is None:
            logger.info(
                "Skipping MF NAV sync for %s: no cached NAV and no transaction/detail date",
                scheme_code,
            )
            return True

    if start_date > end:
        return True

    try:
        rows = provider.get_nav_history(scheme_code, start_date, end)
    except Exception as exc:
        logger.error("Failed to fetch NAV history for %s: %s", scheme_code, exc)
        return False

    if not rows:
        logger.warning(
            "Empty NAV history for %s from %s to %s",
            scheme_code,
            start_date,
            end,
        )
        return True

    default_ccy = asset.currency or MF_NAV_CURRENCY
    for row in rows:
        upsert_mutual_fund_nav(
            scheme_code=scheme_code,
            row_date=row.date,
            nav=row.nav,
            currency=row.currency or default_ccy,
            asset=asset,
        )
    return True


@dataclass
class MutualFundNavSyncResult:
    synced: int
    skipped: int
    failed: int

    @property
    def success(self) -> bool:
        return self.failed == 0


def _profiles_queryset(*, only_scheme_codes: Optional[set[str]] = None):
    qs = (
        MutualFundProfile.objects.select_related("asset")
        .filter(asset__asset_type=AssetType.MUTUAL_FUND, asset__is_active=True)
        .order_by("scheme_code")
    )
    if only_scheme_codes is not None:
        requested = {normalize_scheme_code(c) for c in only_scheme_codes if c}
        if not requested:
            return qs.none()
        qs = qs.filter(scheme_code__in=requested)
    return qs


def sync_mutual_fund_navs(
    *,
    only_scheme_codes: Optional[set[str]] = None,
    provider: MutualFundNavProvider | None = None,
    end: date | None = None,
) -> MutualFundNavSyncResult:
    """
    Incrementally sync NAV for all active MutualFundProfile rows in DB.

    Profiles without transaction/detail dates and without cached NAV are skipped.
    Provider failure for one scheme does not abort the batch.
    """
    provider = provider or default_mutual_fund_nav_provider()
    end = end or date.today()

    synced = 0
    skipped = 0
    failed = 0

    for profile in _profiles_queryset(only_scheme_codes=only_scheme_codes):
        scheme_code = normalize_scheme_code(profile.scheme_code)
        max_hist = _latest_mutual_fund_nav_date(scheme_code)
        if max_hist is None and _earliest_relevant_nav_date(scheme_code) is None:
            skipped += 1
            logger.info(
                "Skipped MF NAV sync for %s: no transaction/detail anchor date",
                scheme_code,
            )
            continue

        start_check = (
            max_hist + timedelta(days=1)
            if max_hist is not None
            else _earliest_relevant_nav_date(scheme_code)
        )
        if start_check is not None and start_check > end:
            synced += 1
            continue

        ok = sync_one_mutual_fund(profile, provider, end=end)
        if ok:
            synced += 1
        else:
            failed += 1

    return MutualFundNavSyncResult(synced=synced, skipped=skipped, failed=failed)
