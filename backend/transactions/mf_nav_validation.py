"""Mutual fund NAV/market-value verification against cached HistoricalPrice (DB only)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from market_data.models import AssetType, HistoricalPrice
from market_data.nav_lookup import normalize_scheme_code
from transactions.models import NavVerificationStatus

# MF-6 tolerances (INR); see docs/decisions.md
NAV_ABSOLUTE_TOLERANCE_INR = Decimal("0.01")
MARKET_VALUE_TOLERANCE_INR = Decimal("1")


@dataclass(frozen=True)
class MutualFundNavValidationResult:
    status: str
    message: str


def _cached_nav_for_date(*, scheme_code: str, nav_date: Any) -> Decimal | None:
    row = HistoricalPrice.objects.filter(
        asset_symbol=normalize_scheme_code(scheme_code),
        asset_type=AssetType.MUTUAL_FUND,
        date=nav_date,
    ).first()
    if row is None:
        return None
    cached = Decimal(row.close_price)
    if cached <= 0:
        return None
    return cached


def verify_mutual_fund_nav_inputs(
    *,
    scheme_code: str,
    nav_date: Any,
    entered_nav: Decimal,
    units_allotted: Decimal,
    market_value: Decimal,
) -> MutualFundNavValidationResult:
    """
    Compare entered NAV and market_value to cached NAV for scheme_code + nav_date.

    Reads HistoricalPrice (MUTUAL_FUND) only — never calls an external NAV provider.
    Does not raise when cache is missing; returns NAV_MISSING status instead.
    """
    scheme = normalize_scheme_code(scheme_code)
    cached_nav = _cached_nav_for_date(scheme_code=scheme, nav_date=nav_date)

    if cached_nav is None:
        return MutualFundNavValidationResult(
            status=NavVerificationStatus.NAV_MISSING,
            message=f"No cached NAV for scheme {scheme} on {nav_date}",
        )

    if abs(entered_nav - cached_nav) > NAV_ABSOLUTE_TOLERANCE_INR:
        return MutualFundNavValidationResult(
            status=NavVerificationStatus.NAV_MISMATCH,
            message=(
                f"Entered NAV {entered_nav} differs from cached NAV {cached_nav} "
                f"on {nav_date} (tolerance {NAV_ABSOLUTE_TOLERANCE_INR} INR)"
            ),
        )

    expected_market_value = entered_nav * units_allotted
    if abs(market_value - expected_market_value) > MARKET_VALUE_TOLERANCE_INR:
        return MutualFundNavValidationResult(
            status=NavVerificationStatus.VALUE_MISMATCH,
            message=(
                f"market_value {market_value} differs from NAV×units "
                f"{expected_market_value} (tolerance {MARKET_VALUE_TOLERANCE_INR} INR)"
            ),
        )

    return MutualFundNavValidationResult(
        status=NavVerificationStatus.VERIFIED,
        message="",
    )
