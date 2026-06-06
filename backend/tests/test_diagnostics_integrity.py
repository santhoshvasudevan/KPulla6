"""Lightweight tests for read-only diagnostics helpers (STAB-4)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cash.models import CashEntryType, CashLedgerEntry
from diagnostics.negative_cash import check_negative_cash
from diagnostics.settlement_integrity import check_settlement_integrity
from diagnostics.summary_vs_performance import (
    check_summary_vs_performance,
    mismatch_detected,
)
from market_data.models import AssetType, HistoricalPrice
from portfolios.models import Portfolio
from portfolios.scope import ResolvedPortfolioScope
from portfolios.seed import ensure_default_portfolio
from transactions.models import Transaction, TransactionType


@pytest.fixture
def legacy_portfolio(seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    if portfolio.cash_aware_enabled:
        portfolio.cash_aware_enabled = False
        portfolio.save(update_fields=["cash_aware_enabled", "updated_at"])
    return portfolio


@pytest.fixture
def cash_aware_portfolio(seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    if not portfolio.cash_aware_enabled:
        portfolio.cash_aware_enabled = True
        portfolio.save(update_fields=["cash_aware_enabled", "updated_at"])
    return portfolio


def _stock_buy(portfolio: Portfolio, **kwargs) -> Transaction:
    payload = {
        "asset_symbol": "AAPL",
        "date": date(2026, 1, 2),
        "type": TransactionType.BUY,
        "quantity": Decimal("1"),
        "price_per_share": Decimal("100"),
        "currency": "EUR",
        "fees": Decimal("0"),
    }
    payload.update(kwargs)
    return Transaction.objects.create(portfolio=portfolio, **payload)


@pytest.mark.django_db
def test_settlement_integrity_missing_buy_settlement(cash_aware_portfolio):
    txn = _stock_buy(cash_aware_portfolio)
    issues = check_settlement_integrity([cash_aware_portfolio])
    codes = {i.code for i in issues}
    assert "missing_settlement" in codes
    assert any(i.transaction_id == txn.id for i in issues)


@pytest.mark.django_db
def test_settlement_integrity_split_must_not_have_settlement(cash_aware_portfolio):
    txn = Transaction.objects.create(
        portfolio=cash_aware_portfolio,
        asset_symbol="AAPL",
        date=date(2026, 2, 1),
        type=TransactionType.STOCK_SPLIT,
        quantity=Decimal("0"),
        price_per_share=Decimal("0"),
        currency="EUR",
        split_from=Decimal("1"),
        split_to=Decimal("2"),
    )
    CashLedgerEntry.objects.create(
        portfolio=cash_aware_portfolio,
        date=date(2026, 2, 1),
        currency="EUR",
        entry_type=CashEntryType.BUY_SETTLEMENT,
        amount=Decimal("-10"),
        linked_transaction=txn,
    )
    issues = check_settlement_integrity([cash_aware_portfolio])
    assert any(i.code == "split_has_settlement" for i in issues)


@pytest.mark.django_db
def test_negative_cash_detects_running_deficit(cash_aware_portfolio):
    CashLedgerEntry.objects.create(
        portfolio=cash_aware_portfolio,
        date=date(2026, 1, 1),
        currency="EUR",
        entry_type=CashEntryType.CASH_DEPOSIT,
        amount=Decimal("50"),
    )
    CashLedgerEntry.objects.create(
        portfolio=cash_aware_portfolio,
        date=date(2026, 1, 2),
        currency="EUR",
        entry_type=CashEntryType.BUY_SETTLEMENT,
        amount=Decimal("-100"),
    )
    issues = check_negative_cash([cash_aware_portfolio])
    assert len(issues) == 1
    assert issues[0].currency == "EUR"
    assert issues[0].lowest_balance < 0


@pytest.mark.django_db
def test_summary_vs_performance_match(api_client, legacy_portfolio, test_user, monkeypatch):
    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2026, 3, 20))
    api_client.post(
        "/api/v1/transactions",
        {
            "asset_symbol": "AAPL",
            "date": "2026-01-01",
            "type": "BUY",
            "quantity": "10",
            "price_per_share": "100",
            "currency": "EUR",
            "fees": "0",
        },
        format="json",
    )
    HistoricalPrice.objects.create(
        asset_symbol="AAPL",
        date=date(2026, 3, 20),
        close_price=Decimal("110"),
        currency="EUR",
        source="test",
        asset_type=AssetType.STOCK,
    )
    scope = ResolvedPortfolioScope(
        kind="single", portfolio_ids=[legacy_portfolio.id]
    )
    result = check_summary_vs_performance(
        user=test_user,
        scope=scope,
        display_currency="EUR",
        tolerance=0.01,
    )
    assert not mismatch_detected(result)
    assert result.difference is not None
    assert result.difference <= 0.01


@pytest.mark.django_db
def test_dashboard_read_profile_runs(api_client, legacy_portfolio, test_user):
    from portfolios.scope import ResolvedPortfolioScope
    from diagnostics.dashboard_read_profile import profile_dashboard_read_paths

    scope = ResolvedPortfolioScope(kind="single", portfolio_ids=[legacy_portfolio.id])
    profiles = profile_dashboard_read_paths(
        scope=scope,
        display_currency="EUR",
        user=test_user,
    )
    assert len(profiles) >= 8
    assert all(p.elapsed_ms >= 0 for p in profiles)
    assert all(p.sql_query_count >= 0 for p in profiles)


@pytest.mark.django_db
def test_diagnostics_modules_import():
    from diagnostics import (  # noqa: F401
        fx_coverage,
        nav_coverage,
        negative_cash,
        settlement_integrity,
        summary_vs_performance,
    )
