"""Unit tests for cash-aware portfolio XIRR / TWROR flow selection."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cash.models import CashEntryType, CashLedgerEntry, CashTransferGroup
from portfolios.cash_ledger_flows import (
    build_cash_aware_twror_external_flows,
    build_cash_aware_xirr_external_flows,
    is_cash_aware_external_ledger_entry,
)
from portfolios.external_flows_service import build_all_scope_external_flows
from portfolios.scope import ResolvedPortfolioScope
from portfolios.seed import ensure_default_portfolio
from portfolios.models import Portfolio


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
def test_tax_withheld_not_external(test_user):
    portfolio = ensure_default_portfolio(test_user)
    from transactions.models import Transaction, TransactionType

    txn = Transaction.objects.create(
        portfolio=portfolio,
        asset_symbol="AAPL",
        date=date(2026, 3, 1),
        type=TransactionType.SELL,
        quantity=Decimal("10"),
        price_per_share=Decimal("100"),
        currency="EUR",
        fees=Decimal("0"),
        actual_cash_received=Decimal("930"),
    )
    tax_row = CashLedgerEntry.objects.create(
        portfolio=portfolio,
        date=date(2026, 3, 1),
        currency="EUR",
        entry_type=CashEntryType.TAX_WITHHELD,
        amount=Decimal("-70"),
        linked_transaction=txn,
    )
    assert not is_cash_aware_external_ledger_entry(tax_row)
    twror_flows, _ = build_cash_aware_twror_external_flows(
        portfolio.id, calculation_currency="EUR"
    )
    assert twror_flows == {}
    xirr_flows, fx_missing = build_cash_aware_xirr_external_flows(
        portfolio.id, calculation_currency="EUR"
    )
    assert not fx_missing
    assert xirr_flows == {}


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


@pytest.mark.django_db
def test_transfer_entries_are_external_for_single_portfolio(test_user):
    source = ensure_default_portfolio(test_user)
    target = Portfolio.objects.create(
        user=test_user, name="Target", base_currency="EUR", is_active=True
    )
    group = CashTransferGroup.objects.create(
        date=date(2026, 3, 1),
        source_portfolio=source,
        target_portfolio=target,
        source_currency="EUR",
        target_currency="EUR",
        source_amount=Decimal("500"),
        target_amount=Decimal("500"),
        user_rate=Decimal("1"),
    )
    out_entry = CashLedgerEntry.objects.create(
        portfolio=source,
        date=date(2026, 3, 1),
        currency="EUR",
        entry_type=CashEntryType.TRANSFER_OUT,
        amount=Decimal("-500"),
        transfer_group=group,
    )
    in_entry = CashLedgerEntry.objects.create(
        portfolio=target,
        date=date(2026, 3, 1),
        currency="EUR",
        entry_type=CashEntryType.TRANSFER_IN,
        amount=Decimal("500"),
        transfer_group=group,
    )
    assert is_cash_aware_external_ledger_entry(out_entry)
    assert is_cash_aware_external_ledger_entry(in_entry)

    src_twror, _ = build_cash_aware_twror_external_flows(
        source.id, calculation_currency="EUR"
    )
    tgt_twror, _ = build_cash_aware_twror_external_flows(
        target.id, calculation_currency="EUR"
    )
    assert src_twror == {date(2026, 3, 1): Decimal("-500")}
    assert tgt_twror == {date(2026, 3, 1): Decimal("500")}

    src_xirr, _ = build_cash_aware_xirr_external_flows(
        source.id, calculation_currency="EUR"
    )
    tgt_xirr, _ = build_cash_aware_xirr_external_flows(
        target.id, calculation_currency="EUR"
    )
    assert src_xirr == {date(2026, 3, 1): Decimal("500")}
    assert tgt_xirr == {date(2026, 3, 1): Decimal("-500")}


@pytest.mark.django_db
def test_same_currency_transfer_neutral_in_all_scope_external_flows(test_user):
    source = ensure_default_portfolio(test_user)
    target = Portfolio.objects.create(
        user=test_user, name="Target", base_currency="EUR", is_active=True
    )
    source.cash_aware_enabled = True
    source.save(update_fields=["cash_aware_enabled", "updated_at"])
    target.cash_aware_enabled = True
    target.save(update_fields=["cash_aware_enabled", "updated_at"])

    group = CashTransferGroup.objects.create(
        date=date(2026, 3, 1),
        source_portfolio=source,
        target_portfolio=target,
        source_currency="EUR",
        target_currency="EUR",
        source_amount=Decimal("500"),
        target_amount=Decimal("500"),
        user_rate=Decimal("1"),
    )
    CashLedgerEntry.objects.create(
        portfolio=source,
        date=date(2026, 3, 1),
        currency="EUR",
        entry_type=CashEntryType.TRANSFER_OUT,
        amount=Decimal("-500"),
        transfer_group=group,
    )
    CashLedgerEntry.objects.create(
        portfolio=target,
        date=date(2026, 3, 1),
        currency="EUR",
        entry_type=CashEntryType.TRANSFER_IN,
        amount=Decimal("500"),
        transfer_group=group,
    )

    scope = ResolvedPortfolioScope(
        kind="all", portfolio_ids=[source.id, target.id]
    )
    flows, unknown = build_all_scope_external_flows(scope, "EUR")
    assert unknown is None
    assert flows.get(date(2026, 3, 1), Decimal("0")) == Decimal("0")
