"""Unit tests for cash-aware portfolio XIRR / TWROR flow selection."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cash.models import CashEntryType, CashLedgerEntry
from portfolios.cash_ledger_flows import (
    build_cash_aware_twror_external_flows,
    build_cash_aware_xirr_external_flows,
    is_cash_aware_external_ledger_entry,
)
from portfolios.seed import ensure_default_portfolio


@pytest.mark.django_db
def test_settlement_and_linked_rows_not_external(test_user):
    portfolio = ensure_default_portfolio(test_user)
    deposit = CashLedgerEntry.objects.create(
        portfolio=portfolio,
        date=date(2026, 1, 1),
        currency="EUR",
        entry_type=CashEntryType.CASH_DEPOSIT,
        amount=Decimal("1000"),
    )
    settlement = CashLedgerEntry.objects.create(
        portfolio=portfolio,
        date=date(2026, 1, 2),
        currency="EUR",
        entry_type=CashEntryType.BUY_SETTLEMENT,
        amount=Decimal("-1000"),
    )
    assert is_cash_aware_external_ledger_entry(deposit)
    assert not is_cash_aware_external_ledger_entry(settlement)

    twror_flows, unknown = build_cash_aware_twror_external_flows(
        portfolio.id, calculation_currency="EUR"
    )
    assert unknown is None
    assert twror_flows == {date(2026, 1, 1): Decimal("1000")}

    xirr_flows, fx_missing = build_cash_aware_xirr_external_flows(
        portfolio.id, calculation_currency="EUR"
    )
    assert not fx_missing
    assert xirr_flows == {date(2026, 1, 1): Decimal("-1000")}


@pytest.mark.django_db
def test_unlinked_adjustment_counts_as_external(test_user):
    portfolio = ensure_default_portfolio(test_user)
    CashLedgerEntry.objects.create(
        portfolio=portfolio,
        date=date(2026, 2, 1),
        currency="EUR",
        entry_type=CashEntryType.ADJUSTMENT,
        amount=Decimal("-50"),
    )
    twror_flows, _ = build_cash_aware_twror_external_flows(
        portfolio.id, calculation_currency="EUR"
    )
    assert twror_flows == {date(2026, 2, 1): Decimal("-50")}

    xirr_flows, _ = build_cash_aware_xirr_external_flows(
        portfolio.id, calculation_currency="EUR"
    )
    assert xirr_flows == {date(2026, 2, 1): Decimal("50")}
