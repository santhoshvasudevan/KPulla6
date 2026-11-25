"""
Adapt loaded MF transactions to the scoped valuation in ``finance.mutual_fund_valuation``.

Provider NAVs come from cached HistoricalPrice rows. A provisional NAV recorded on
a BUY or SELL applies only to that transaction's folio (portfolio + scheme + folio
number) from its NAV date until the next cached provider NAV. Reads loaded
transactions only.

Holdings, Summary and value history share this decision; series consumers report
``PROVISIONAL_SERIES_WARNING`` when an emitted point used a provisional NAV.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from finance.mutual_fund_valuation import (
    MutualFundHoldingValuation,
    MutualFundUnitEvent,
    ScopedMutualFundValuation,
    ValuationLeg,
    valuation_legs,
    value_scoped_mutual_fund_holding,
)
from finance.types import TransactionType
from transactions.models import MutualFundNavSource

PROVISIONAL_SERIES_WARNING = (
    "Some portfolio values in this range use unverified provisional mutual fund NAVs; "
    "results are not fully verified."
)


def mutual_fund_unit_events(db_txns) -> list[MutualFundUnitEvent]:
    events: list[MutualFundUnitEvent] = []
    for txn in db_txns:
        if txn.type not in (TransactionType.BUY.value, TransactionType.SELL.value):
            continue
        detail = txn.mutual_fund_detail
        events.append(
            MutualFundUnitEvent(
                trade_date=txn.date,
                sequence=txn.id,
                folio_id=detail.folio_id,
                type=TransactionType(txn.type),
                units=Decimal(txn.quantity),
                nav_date=detail.nav_date,
                nav=Decimal(detail.nav),
                provisional=detail.nav_source == MutualFundNavSource.PROVISIONAL_USER,
            )
        )
    return events


def mutual_fund_valuation_legs(db_txns) -> list[ValuationLeg]:
    return valuation_legs(mutual_fund_unit_events(db_txns))


def scoped_mutual_fund_valuation(
    db_txns,
    finance_txns,
    *,
    provider_point: tuple[date, Decimal] | None,
) -> ScopedMutualFundValuation:
    """Current valuation for one MF holding group (DB already loaded)."""
    return value_scoped_mutual_fund_holding(
        mutual_fund_unit_events(db_txns), finance_txns, provider_point=provider_point
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
