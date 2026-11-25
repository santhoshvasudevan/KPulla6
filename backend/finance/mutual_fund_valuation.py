"""Mutual fund unit replay, per-unit NAV resolution and valuation (no Django imports).

Provider NAVs come from the cached history. Provisional NAVs are user-confirmed
per-unit values recorded on a specific folio's BUY or SELL when the exact-date provider
NAV was unavailable. They never enter the provider history; valuation overlays
them only for the folio that recorded them, from their NAV date until the next
provider NAV.

Callers load transactions and cached NAVs and adapt them to ``MutualFundUnitEvent``;
current holdings/summary values (``value_scoped_mutual_fund_holding``) and value
history (``daily_mutual_fund_values``) share the same ``valuation_legs``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable, Mapping, TypeVar

from finance.fifo import FifoCostBasisMetrics, calculate_fifo_cost_basis_metrics
from finance.types import Transaction, TransactionType

PROVIDER_CACHE = "PROVIDER_CACHE"
PROVISIONAL_USER = "PROVISIONAL_USER"
MIXED = "MIXED"

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


# --- unit replay -------------------------------------------------------------------


@dataclass(frozen=True)
class MutualFundUnitEvent:
    """A BUY or SELL on one folio; ``sequence`` orders events on the same trade date."""

    trade_date: date
    sequence: int
    folio_id: int
    type: TransactionType
    units: Decimal
    nav_date: date | None = None
    nav: Decimal | None = None
    provisional: bool = False


def provisional_navs_by_folio(
    events: Iterable[MutualFundUnitEvent],
) -> dict[int, dict[date, Decimal | None]]:
    observations: dict[int, list[tuple[date, Decimal]]] = {}
    for event in events:
        if event.provisional and event.type in (TransactionType.BUY, TransactionType.SELL):
            observations.setdefault(event.folio_id, []).append((event.nav_date, Decimal(event.nav)))
    return {
        folio_id: collapse_provisional_observations(obs) for folio_id, obs in observations.items()
    }


def replay_unit_timeline(events: Iterable[MutualFundUnitEvent]) -> dict[date, Decimal]:
    """Units held after each event date. A SELL beyond the units held floors at zero (FIFO lots)."""
    units = Decimal("0")
    timeline: dict[date, Decimal] = {}
    for event in sorted(events, key=lambda e: (e.trade_date, e.sequence)):
        if event.units > 0:
            if event.type == TransactionType.BUY:
                units += event.units
            elif event.type == TransactionType.SELL:
                units = max(Decimal("0"), units - event.units)
        timeline[event.trade_date] = units
    return timeline


def folio_unit_timelines(
    events: Iterable[MutualFundUnitEvent],
) -> dict[int, dict[date, Decimal]]:
    by_folio: dict[int, list[MutualFundUnitEvent]] = {}
    for event in events:
        by_folio.setdefault(event.folio_id, []).append(event)
    return {folio_id: replay_unit_timeline(evts) for folio_id, evts in by_folio.items()}


@dataclass(frozen=True)
class ValuationLeg:
    """A units timeline valued on the provider NAVs overlaid with ``provisional_navs``."""

    units: Mapping[date, Decimal]
    provisional_navs: Mapping[date, Decimal | None]

    @property
    def open_units(self) -> Decimal:
        return self.units[max(self.units)] if self.units else Decimal("0")


def valuation_legs(events: Iterable[MutualFundUnitEvent]) -> list[ValuationLeg]:
    """
    One leg for a provider-only holding; otherwise one leg per folio, so a provisional
    NAV never values another folio's units.
    """
    events = list(events)
    provisional = provisional_navs_by_folio(events)
    if not provisional:
        return [ValuationLeg(replay_unit_timeline(events), {})]
    return [
        ValuationLeg(units, provisional.get(folio_id, {}))
        for folio_id, units in folio_unit_timelines(events).items()
    ]


# --- current valuation ---------------------------------------------------------------


@dataclass(frozen=True)
class MutualFundHoldingValuation:
    """Effective NAV decision for one holding. ``current_value`` is None when unavailable."""

    nav: Decimal | None
    nav_date: date | None
    source: str | None
    current_value: Decimal | None
    provisional: bool = False
    conflict_dates: list[date] = field(default_factory=list)
    provisional_dates: list[date] = field(default_factory=list)


def value_mutual_fund_holding(
    legs: list[ValuationLeg],
    *,
    provider_point: tuple[date, Decimal] | None,
    qty: Decimal,
    as_of: date | None = None,
) -> MutualFundHoldingValuation:
    """Latest per-unit NAV and NAV × units for one holding (scheme + folio number)."""
    if not any(leg.provisional_navs for leg in legs):
        if provider_point is None:
            return MutualFundHoldingValuation(None, None, None, None)
        nav_date, nav = provider_point
        return MutualFundHoldingValuation(
            nav, nav_date, PROVIDER_CACHE, nav * qty if qty > 0 else Decimal("0")
        )

    points: list[NavPoint] = []
    total = Decimal("0")
    missing = False
    conflicts: list[date] = []
    for leg in legs:
        units = leg.open_units
        if units <= 0:
            continue
        point = resolve_nav_point(provider_point, leg.provisional_navs, as_of=as_of)
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


@dataclass(frozen=True)
class ScopedMutualFundValuation:
    """
    Current valuation shared by holdings and summary for one scoped holding.

    ``nav`` is the per-unit NAV used for display, cost-basis metrics and personal XIRR;
    it is None when folios disagree (``MIXED``) or the value is unavailable.
    ``overlaid`` means a provisional NAV or conflict, not the latest provider NAV, decides
    the value. ``current_value`` and ``unrealized_pl`` are None when an open folio has no
    usable NAV; a closed holding is a genuine zero.
    """

    valuation: MutualFundHoldingValuation
    fifo: FifoCostBasisMetrics
    nav: Decimal | None
    nav_available: bool
    overlaid: bool
    current_value: Decimal | None
    unrealized_pl: Decimal | None


def value_scoped_mutual_fund_holding(
    events: Iterable[MutualFundUnitEvent],
    fifo_transactions: Iterable[Transaction],
    *,
    provider_point: tuple[date, Decimal] | None,
    as_of: date | None = None,
) -> ScopedMutualFundValuation:
    """``fifo_transactions`` are the holding's BUY/SELL rows as finance DTOs for cost basis."""
    fifo_transactions = list(fifo_transactions)
    qty = calculate_fifo_cost_basis_metrics(fifo_transactions).cumulative_qty
    valuation = value_mutual_fund_holding(
        valuation_legs(events), provider_point=provider_point, qty=qty, as_of=as_of
    )
    # A newer conflicting provisional date leaves the folio unvalued; the older
    # provider NAV must not take over.
    overlaid = valuation.source not in (None, PROVIDER_CACHE) or bool(valuation.conflict_dates)
    if overlaid:
        nav = valuation.nav
        nav_available = valuation.current_value is not None
    else:
        nav = provider_point[1] if provider_point is not None else None
        nav_available = nav is not None
    fifo = calculate_fifo_cost_basis_metrics(fifo_transactions, current_price=nav)
    current_value = valuation.current_value
    return ScopedMutualFundValuation(
        valuation=valuation,
        fifo=fifo,
        nav=nav,
        nav_available=nav_available,
        overlaid=overlaid,
        current_value=current_value,
        unrealized_pl=(
            None if current_value is None else current_value - fifo.cumulative_invested_amount
        ),
    )


# --- value history -------------------------------------------------------------------


@dataclass(frozen=True)
class DailyMutualFundValue:
    """``value`` sums legs with a usable NAV; ``nav_missing`` flags an open leg without one."""

    value: Decimal
    nav_missing: bool
    provisional: bool


_V = TypeVar("_V")


def _last_on_or_before(mapping: Mapping[date, _V], as_of: date, default: _V) -> _V:
    result = default
    for key in sorted(mapping):
        if key > as_of:
            break
        result = mapping[key]
    return result


def daily_mutual_fund_values(
    legs: list[ValuationLeg],
    provider_navs: Mapping[date, Decimal],
    *,
    start: date,
    end: date,
) -> dict[date, DailyMutualFundValue]:
    """Units × effective NAV per day, carrying the last units and per-unit NAV forward."""
    tracks = []
    for leg in legs:
        nav_timeline = merge_nav_timeline(provider_navs, leg.provisional_navs)
        tracks.append(
            _LegTrack(
                units_timeline=leg.units,
                nav_timeline=nav_timeline,
                units=_last_on_or_before(leg.units, start, Decimal("0")),
                point=_last_on_or_before(nav_timeline, start, None),
            )
        )

    daily: dict[date, DailyMutualFundValue] = {}
    d = start
    while d <= end:
        value = Decimal("0")
        nav_missing = False
        provisional = False
        for track in tracks:
            track.advance(d)
            if track.units <= 0:
                continue
            if track.point is not None and track.point.nav is not None:
                value += track.units * track.point.nav
                provisional = provisional or track.point.source == PROVISIONAL_USER
            else:
                nav_missing = True
        daily[d] = DailyMutualFundValue(value, nav_missing, provisional)
        d += timedelta(days=1)
    return daily


@dataclass
class _LegTrack:
    units_timeline: Mapping[date, Decimal]
    nav_timeline: Mapping[date, NavPoint]
    units: Decimal
    point: NavPoint | None

    def advance(self, d: date) -> None:
        if d in self.units_timeline:
            self.units = self.units_timeline[d]
        if d in self.nav_timeline:
            self.point = self.nav_timeline[d]
