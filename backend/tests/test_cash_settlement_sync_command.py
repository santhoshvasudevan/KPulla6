"""CASH-HIST-1 — historical settlement backfill command and service."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from io import StringIO

import pytest

FIXED_TODAY = date(2026, 3, 15)


@pytest.fixture
def today_patch(monkeypatch):
    monkeypatch.setattr("portfolios.dates.current_date", lambda: FIXED_TODAY)
    return FIXED_TODAY
from django.core.management import call_command
from django.core.management.base import CommandError

from cash.models import CashEntryType, CashLedgerEntry
from diagnostics.settlement_integrity import check_settlement_integrity
from market_data.models import AssetType, HistoricalPrice
from portfolios.models import Portfolio
from portfolios.seed import ensure_default_portfolio
from transactions.cash_settlement_sync import (
    CashSettlementSyncBlockedError,
    CashSettlementSyncError,
    apply_cash_settlement_sync,
    plan_cash_settlement_sync,
)
from transactions.models import Folio, MutualFundTransactionDetail, Transaction, TransactionType


def _enable_cash_aware(portfolio: Portfolio) -> Portfolio:
    portfolio.cash_aware_enabled = True
    portfolio.save(update_fields=["cash_aware_enabled", "updated_at"])
    return portfolio


def _deposit(portfolio: Portfolio, *, day: str, amount: str, currency: str = "EUR"):
    CashLedgerEntry.objects.create(
        portfolio=portfolio,
        date=date.fromisoformat(day),
        currency=currency,
        entry_type=CashEntryType.CASH_DEPOSIT,
        amount=Decimal(amount),
    )


def _stock_buy(portfolio: Portfolio, **kwargs) -> Transaction:
    payload = {
        "asset_symbol": "AAPL",
        "date": date(2026, 1, 2),
        "type": TransactionType.BUY,
        "quantity": Decimal("10"),
        "price_per_share": Decimal("100"),
        "currency": "EUR",
        "fees": Decimal("0"),
    }
    payload.update(kwargs)
    return Transaction.objects.create(portfolio=portfolio, **payload)


def _stock_sell(portfolio: Portfolio, **kwargs) -> Transaction:
    payload = {
        "asset_symbol": "AAPL",
        "date": date(2026, 3, 15),
        "type": TransactionType.SELL,
        "quantity": Decimal("10"),
        "price_per_share": Decimal("110"),
        "currency": "EUR",
        "fees": Decimal("0"),
    }
    payload.update(kwargs)
    return Transaction.objects.create(portfolio=portfolio, **payload)


def _price(symbol: str, day: str, close: str):
    HistoricalPrice.objects.create(
        asset_symbol=symbol,
        date=date.fromisoformat(day),
        close_price=Decimal(close),
        currency="EUR",
        source="test",
    )


@pytest.mark.django_db
def test_diagnostic_reports_missing_settlement(cash_aware_portfolio):
    txn = _stock_buy(cash_aware_portfolio)
    issues = check_settlement_integrity([cash_aware_portfolio])
    assert any(
        i.code == "missing_settlement" and i.transaction_id == txn.id for i in issues
    )


@pytest.mark.django_db
def test_dry_run_reports_planned_settlement(cash_aware_portfolio):
    _deposit(cash_aware_portfolio, day="2026-01-01", amount="2000")
    txn = _stock_buy(cash_aware_portfolio)
    plan = plan_cash_settlement_sync(cash_aware_portfolio)
    assert plan.create_count == 1
    assert plan.to_create[0].transaction_id == txn.id
    assert plan.to_create[0].entry_type == CashEntryType.BUY_SETTLEMENT
    assert plan.to_create[0].amount == Decimal("-1000.0000")


@pytest.mark.django_db
def test_apply_creates_settlement(cash_aware_portfolio):
    _deposit(cash_aware_portfolio, day="2026-01-01", amount="2000")
    _stock_buy(cash_aware_portfolio)
    result = apply_cash_settlement_sync(cash_aware_portfolio)
    assert result["created_count"] == 1
    entry = CashLedgerEntry.objects.get(
        portfolio=cash_aware_portfolio,
        entry_type=CashEntryType.BUY_SETTLEMENT,
    )
    assert entry.amount == Decimal("-1000.0000")
    assert entry.linked_transaction_id is not None


@pytest.mark.django_db
def test_second_apply_creates_zero_rows(cash_aware_portfolio):
    _deposit(cash_aware_portfolio, day="2026-01-01", amount="2000")
    _stock_buy(cash_aware_portfolio)
    apply_cash_settlement_sync(cash_aware_portfolio)
    result = apply_cash_settlement_sync(cash_aware_portfolio)
    assert result["created_count"] == 0


@pytest.mark.django_db
def test_mismatch_reported_not_overwritten(cash_aware_portfolio):
    _deposit(cash_aware_portfolio, day="2026-01-01", amount="2000")
    txn = _stock_buy(cash_aware_portfolio)
    CashLedgerEntry.objects.create(
        portfolio=cash_aware_portfolio,
        date=txn.date,
        currency="EUR",
        entry_type=CashEntryType.BUY_SETTLEMENT,
        amount=Decimal("-1.0000"),
        linked_transaction=txn,
        note="wrong amount",
    )
    plan = plan_cash_settlement_sync(cash_aware_portfolio)
    assert plan.create_count == 0
    assert any(m.code == "settlement_amount_mismatch" for m in plan.mismatches)
    with pytest.raises(CashSettlementSyncError):
        apply_cash_settlement_sync(cash_aware_portfolio)


@pytest.mark.django_db
def test_apply_blocked_when_cash_would_go_negative(cash_aware_portfolio):
    _deposit(cash_aware_portfolio, day="2026-01-02", amount="100")
    _stock_buy(
        cash_aware_portfolio,
        date=date(2026, 1, 1),
        quantity=Decimal("10"),
        price_per_share=Decimal("100"),
    )
    with pytest.raises(CashSettlementSyncBlockedError) as exc:
        apply_cash_settlement_sync(cash_aware_portfolio)
    assert exc.value.impacts
    assert exc.value.impacts[0]["currency"] == "EUR"


@pytest.mark.django_db
def test_value_history_no_dip_after_sell_settlement_sync(
    api_client, seeded, test_user, today_patch, monkeypatch
):
    portfolio = ensure_default_portfolio(test_user)
    portfolio.cash_aware_enabled = False
    portfolio.save(update_fields=["cash_aware_enabled", "updated_at"])

    _deposit(portfolio, day="2026-01-01", amount="1000")
    buy = _stock_buy(portfolio, date=date(2026, 1, 1))
    _price("AAPL", "2026-01-01", "100")
    _price("AAPL", "2026-03-14", "110")
    _price("AAPL", "2026-03-15", "110")
    sell = _stock_sell(portfolio, date=date(2026, 3, 15))

    _enable_cash_aware(portfolio)
    apply_cash_settlement_sync(portfolio)

    assert CashLedgerEntry.objects.filter(
        linked_transaction_id=sell.id, entry_type=CashEntryType.SELL_SETTLEMENT
    ).exists()
    assert CashLedgerEntry.objects.filter(
        linked_transaction_id=buy.id, entry_type=CashEntryType.BUY_SETTLEMENT
    ).exists()

    resp = api_client.get(
        "/api/v1/portfolio/performance?metric=value&range=ALL&display_currency=EUR"
    )
    assert resp.status_code == 200
    points = {p["date"]: p["value"] for p in resp.json()}
    assert points["2026-03-14"] == pytest.approx(points["2026-03-15"], rel=0.02)


@pytest.mark.django_db
def test_mf_buy_settlement_uses_investment_date_and_paid_value(
    cash_aware_portfolio,
):
    from market_data.models import Asset

    asset = Asset.objects.create(
        asset_type=AssetType.MUTUAL_FUND,
        symbol="120503",
        display_name="Test MF",
        currency="INR",
    )
    folio = Folio.objects.create(
        portfolio=cash_aware_portfolio,
        asset=asset,
        folio_number="F1",
    )
    txn = Transaction.objects.create(
        portfolio=cash_aware_portfolio,
        asset_symbol="120503",
        date=date(2026, 3, 15),
        type=TransactionType.BUY,
        quantity=Decimal("100"),
        price_per_share=Decimal("42.5"),
        currency="INR",
    )
    MutualFundTransactionDetail.objects.create(
        transaction=txn,
        folio=folio,
        investment_date=date(2026, 3, 10),
        nav_date=date(2026, 3, 15),
        nav=Decimal("42.5"),
        units_allotted=Decimal("100"),
        paid_value=Decimal("4255"),
        market_value=Decimal("4250"),
    )
    _deposit(cash_aware_portfolio, day="2026-03-10", amount="5000", currency="INR")
    apply_cash_settlement_sync(cash_aware_portfolio)
    entry = CashLedgerEntry.objects.get(linked_transaction_id=txn.id)
    assert entry.date == date(2026, 3, 10)
    assert entry.amount == Decimal("-4255.0000")


@pytest.mark.django_db
def test_stock_split_creates_no_settlement(cash_aware_portfolio):
    Transaction.objects.create(
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
    plan = plan_cash_settlement_sync(cash_aware_portfolio)
    assert plan.create_count == 0
    assert plan.skipped_non_settlement == 1


@pytest.mark.django_db
def test_management_command_dry_run_default(cash_aware_portfolio):
    _deposit(cash_aware_portfolio, day="2026-01-01", amount="2000")
    _stock_buy(cash_aware_portfolio)
    out = StringIO()
    call_command(
        "sync_cash_settlements",
        f"--portfolio-id={cash_aware_portfolio.id}",
        stdout=out,
    )
    assert "would create 1 settlement" in out.getvalue().lower()
    assert CashLedgerEntry.objects.filter(
        entry_type=CashEntryType.BUY_SETTLEMENT
    ).count() == 0


@pytest.mark.django_db
def test_management_command_apply(cash_aware_portfolio):
    _deposit(cash_aware_portfolio, day="2026-01-01", amount="2000")
    _stock_buy(cash_aware_portfolio)
    out = StringIO()
    call_command(
        "sync_cash_settlements",
        f"--portfolio-id={cash_aware_portfolio.id}",
        "--apply",
        stdout=out,
    )
    assert "Created 1 settlement" in out.getvalue()
    assert CashLedgerEntry.objects.filter(
        entry_type=CashEntryType.BUY_SETTLEMENT
    ).count() == 1


@pytest.mark.django_db
def test_management_command_rejects_legacy_without_flag(test_user):
    portfolio = ensure_default_portfolio(test_user)
    portfolio.cash_aware_enabled = False
    portfolio.save(update_fields=["cash_aware_enabled", "updated_at"])
    with pytest.raises(CommandError, match="not cash-aware"):
        call_command("sync_cash_settlements", f"--portfolio-id={portfolio.id}")
