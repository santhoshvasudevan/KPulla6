from __future__ import annotations

from datetime import date
from typing import Iterable

from market_data.models import Asset, AssetType, HistoricalPrice
from market_data.nav_lookup import NavLookupResult, latest_nav_for_asset, normalize_scheme_code


def list_mutual_fund_navs_in_range(
    asset_or_code: Asset | str,
    start: date,
    end: date,
) -> list[HistoricalPrice]:
    """
    Cached MUTUAL_FUND HistoricalPrice rows for scheme_code in [start, end].

    Reads DB only — never calls an external NAV provider.
    """
    scheme_code = (
        normalize_scheme_code(asset_or_code.symbol)
        if isinstance(asset_or_code, Asset)
        else normalize_scheme_code(asset_or_code)
    )
    if not scheme_code:
        return []
    return list(
        HistoricalPrice.objects.filter(
            asset_symbol=scheme_code,
            asset_type=AssetType.MUTUAL_FUND,
            date__gte=start,
            date__lte=end,
        ).order_by("date")
    )


def list_mutual_fund_navs_for_schemes(
    scheme_codes: Iterable[str],
    start: date,
    end: date,
) -> list[HistoricalPrice]:
    """Cached NAV rows for multiple scheme codes in [start, end] (DB only)."""
    normalized = sorted({normalize_scheme_code(s) for s in scheme_codes if s})
    if not normalized:
        return []
    rows: list[HistoricalPrice] = []
    for scheme in normalized:
        rows.extend(list_mutual_fund_navs_in_range(scheme, start, end))
    return sorted(rows, key=lambda r: (r.asset_symbol, r.date))


def latest_mutual_fund_navs_by_scheme(
    scheme_codes: Iterable[str],
) -> dict[str, NavLookupResult]:
    out: dict[str, NavLookupResult] = {}
    for scheme in sorted({normalize_scheme_code(s) for s in scheme_codes if s}):
        result = latest_nav_for_asset(scheme)
        if result is not None:
            out[scheme] = result
    return out


def last_mutual_fund_navs_on_or_before(
    scheme_codes: Iterable[str], as_of: date
) -> list[HistoricalPrice]:
    """Latest cached NAV row per scheme with ``date <= as_of`` (for range bootstrap)."""
    normalized = sorted({normalize_scheme_code(s) for s in scheme_codes if s})
    rows: list[HistoricalPrice] = []
    for scheme in normalized:
        row = (
            HistoricalPrice.objects.filter(
                asset_symbol=scheme,
                asset_type=AssetType.MUTUAL_FUND,
                date__lte=as_of,
            )
            .order_by("-date", "-id")
            .first()
        )
        if row:
            rows.append(row)
    return rows
