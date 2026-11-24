"""Mutual fund per-unit NAV resolution and market value (no Django imports).

Provider NAVs come from the cached history. Provisional NAVs are user-confirmed
per-unit values recorded on a specific holding's BUY when the exact-date provider
NAV was unavailable. They never enter the provider history; valuation overlays
them only for the holding that recorded them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable, Mapping

PROVIDER_CACHE = "PROVIDER_CACHE"
PROVISIONAL_USER = "PROVISIONAL_USER"

MARKET_VALUE_QUANT = Decimal("0.0001")


def calculate_mutual_fund_market_value(nav: Decimal, units: Decimal) -> Decimal:
    """NAV × units rounded half-up to the stored market_value precision (4 dp)."""
    nav = Decimal(nav)
    units = Decimal(units)
    if not nav.is_finite() or nav <= 0:
        raise ValueError("nav must be a positive finite number")
    if not units.is_finite() or units <= 0:
        raise ValueError("units must be a positive finite number")
    return (nav * units).quantize(MARKET_VALUE_QUANT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class NavPoint:
    """Effective per-unit NAV from ``nav_date``. ``nav`` is None for an unresolved conflict."""

    nav_date: date
    nav: Decimal | None
    source: str

    @property
    def conflict(self) -> bool:
        return self.nav is None


def collapse_provisional_observations(
    observations: Iterable[tuple[date, Decimal]],
) -> dict[date, Decimal | None]:
    """One provisional NAV per date; differing values on a date become a conflict (None)."""
    out: dict[date, Decimal | None] = {}
    for nav_date, nav in observations:
        nav = Decimal(nav)
        if nav_date not in out:
            out[nav_date] = nav
        elif out[nav_date] is not None and out[nav_date] != nav:
            out[nav_date] = None
    return out


def merge_nav_timeline(
    provider_navs: Mapping[date, Decimal],
    provisional_navs: Mapping[date, Decimal | None],
) -> dict[date, NavPoint]:
    """Union of observations; a provider NAV on the same date supersedes the provisional one."""
    timeline: dict[date, NavPoint] = {
        d: NavPoint(d, nav, PROVISIONAL_USER) for d, nav in provisional_navs.items()
    }
    for d, nav in provider_navs.items():
        timeline[d] = NavPoint(d, Decimal(nav), PROVIDER_CACHE)
    return timeline


def resolve_nav_point(
    provider_point: tuple[date, Decimal] | None,
    provisional_navs: Mapping[date, Decimal | None],
    *,
    as_of: date | None = None,
) -> NavPoint | None:
    """
    Latest effective NAV given the latest provider observation (already bounded by ``as_of``).

    A provisional observation wins only when it is strictly newer than the provider one,
    so valuation resumes on the next cached provider NAV.
    """
    best: NavPoint | None = None
    if provider_point is not None:
        best = NavPoint(provider_point[0], Decimal(provider_point[1]), PROVIDER_CACHE)
    for d, nav in provisional_navs.items():
        if as_of is not None and d > as_of:
            continue
        if best is None or d > best.nav_date:
            best = NavPoint(d, nav, PROVISIONAL_USER)
    return best
