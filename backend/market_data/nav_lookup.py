from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from market_data.models import Asset, AssetType, HistoricalPrice


def normalize_scheme_code(scheme_code: str) -> str:
    """AMFI scheme_code: strip whitespace only (do not uppercase numeric codes)."""
    return (scheme_code or "").strip()


def _resolve_scheme_code(asset_or_code: Asset | str) -> str:
    if isinstance(asset_or_code, Asset):
        return normalize_scheme_code(asset_or_code.symbol)
    return normalize_scheme_code(asset_or_code)


@dataclass(frozen=True)
class NavLookupResult:
    scheme_code: str
    nav: Decimal | None
    date: date | None
    currency: str
    status: str  # "ok" | "nav_missing"


def latest_nav_for_asset(asset_or_code: Asset | str) -> NavLookupResult | None:
    """
    Latest cached NAV from HistoricalPrice (MUTUAL_FUND rows only).

    Reads DB only — never calls an external NAV provider.
    """
    scheme_code = _resolve_scheme_code(asset_or_code)
    if not scheme_code:
        return None

    row = (
        HistoricalPrice.objects.filter(
            asset_symbol=scheme_code,
            asset_type=AssetType.MUTUAL_FUND,
        )
        .order_by("-date", "-id")
        .first()
    )
    if row is None:
        return NavLookupResult(
            scheme_code=scheme_code,
            nav=None,
            date=None,
            currency="INR",
            status="nav_missing",
        )
    return NavLookupResult(
        scheme_code=scheme_code,
        nav=Decimal(row.close_price),
        date=row.date,
        currency=(row.currency or "INR").strip().upper() or "INR",
        status="ok",
    )
