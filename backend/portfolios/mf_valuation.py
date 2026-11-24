"""
Scoped mutual fund valuation with user-confirmed provisional NAV overlays (#50–#52).

Provider NAVs come from cached HistoricalPrice rows. A provisional NAV recorded on
a BUY or SELL applies only to that transaction's folio (portfolio + scheme + folio
number) from its NAV date until the next cached provider NAV. Reads loaded
transactions only.

Holdings, Summary and value history share this decision; series consumers report
``PROVISIONAL_SERIES_WARNING`` when an emitted point used a provisional NAV.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from finance.mutual_fund_valuation import (
    PROVIDER_CACHE,
    PROVISIONAL_USER,
    NavPoint,
    collapse_provisional_observations,
    resolve_nav_point,
)
from finance.types import TransactionType
from transactions.models import MutualFundNavSource

MIXED = "MIXED"
PROVISIONAL_SERIES_WARNING = (
    "Some portfolio values in this range use unverified provisional mutual fund NAVs; "
    "results are not fully verified."
)


def provisional_navs_by_folio(db_txns) -> dict[int, dict[date, Decimal | None]]:
    observations: dict[int, list[tuple[date, Decimal]]] = {}
    for txn in db_txns:
        detail = txn.mutual_fund_detail
        if txn.type not in (TransactionType.BUY.value, TransactionType.SELL.value):
            continue
        if detail.nav_source != MutualFundNavSource.PROVISIONAL_USER:
            continue
        observations.setdefault(detail.folio_id, []).append((detail.nav_date, Decimal(detail.nav)))
    return {
        folio_id: collapse_provisional_observations(obs)
        for folio_id, obs in observations.items()
    }


def _folio_units(db_txns) -> dict[int, Decimal]:
    units: dict[int, Decimal] = {}
    for txn in sorted(db_txns, key=lambda t: (t.date, t.id)):
        folio_id = txn.mutual_fund_detail.folio_id
        current = units.get(folio_id, Decimal("0"))
        if txn.type == TransactionType.BUY.value:
            current += txn.quantity
        elif txn.type == TransactionType.SELL.value:
            current = max(Decimal("0"), current - txn.quantity)
        units[folio_id] = current
    return units


@dataclass
class MutualFundHoldingValuation:
    nav: Decimal | None
    nav_date: date | None
    source: str | None
    current_value: Decimal | None
    provisional: bool = False
    conflict_dates: list[date] = field(default_factory=list)
    provisional_dates: list[date] = field(default_factory=list)


def value_mutual_fund_holding(
    db_txns,
    *,
    provider_point: tuple[date, Decimal] | None,
    qty: Decimal,
    as_of: date | None = None,
) -> MutualFundHoldingValuation:
    """Current per-unit NAV and value for one MF holding group (DB already loaded)."""
    provisional = provisional_navs_by_folio(db_txns)
    if not provisional:
        if provider_point is None:
            return MutualFundHoldingValuation(None, None, None, None)
        nav_date, nav = provider_point
        return MutualFundHoldingValuation(nav, nav_date, PROVIDER_CACHE, nav * qty if qty > 0 else Decimal("0"))

    points: list[NavPoint] = []
    total = Decimal("0")
    missing = False
    conflicts: list[date] = []
    for folio_id, units in _folio_units(db_txns).items():
        if units <= 0:
            continue
        point = resolve_nav_point(provider_point, provisional.get(folio_id, {}), as_of=as_of)
        if point is None or point.nav is None:
            missing = True
            if point is not None:
                conflicts.append(point.nav_date)
            continue
        points.append(point)
        total += units * point.nav

    distinct = {(p.nav, p.nav_date, p.source) for p in points}
    if len(distinct) == 1 and not missing:
        nav, nav_date, source = distinct.pop()
    elif points:
        nav, nav_date, source = None, max(p.nav_date for p in points), MIXED
    else:
        nav, nav_date, source = None, None, None
    provisional_dates = sorted({p.nav_date for p in points if p.source == PROVISIONAL_USER})
    return MutualFundHoldingValuation(
        nav=nav,
        nav_date=nav_date,
        source=source,
        current_value=None if missing else total,
        provisional=bool(provisional_dates),
        conflict_dates=sorted(set(conflicts)),
        provisional_dates=provisional_dates,
    )


def provisional_valuation_warnings(
    valuation: MutualFundHoldingValuation, *, scheme: str, folio_number: str
) -> list[str]:
    warnings = [
        f"Mutual fund {scheme} folio {folio_number} is valued with an unverified provisional NAV "
        f"from {d.isoformat()}"
        for d in valuation.provisional_dates
    ]
    warnings += [
        f"Mutual fund {scheme} folio {folio_number} has conflicting provisional NAVs on "
        f"{d.isoformat()}; value unavailable"
        for d in valuation.conflict_dates
    ]
    return warnings


def provisional_series_warnings(points, *, start_iso: str | None = None) -> list[str]:
    """Quality warning when any emitted value-series point used a provisional NAV."""
    if any(
        p.get("nav_provisional") and (start_iso is None or p["date"] >= start_iso)
        for p in points
    ):
        return [PROVISIONAL_SERIES_WARNING]
    return []
