"""Cash-7A — read-only legacy cash backfill preview API."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cash.models import CashEntryType, CashLedgerEntry
from portfolios.models import Portfolio
from portfolios.seed import ensure_default_portfolio
from transactions.models import Transaction, TransactionType

URL = "/api/v1/cash/backfill-preview"


def _legacy(portfolio: Portfolio) -> Portfolio:
    if portfolio.cash_aware_enabled:
        portfolio.cash_aware_enabled = False
        portfolio.save(update_fields=["cash_aware_enabled", "updated_at"])
    return portfolio


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


def _buy(api_client, portfolio_id: int, **kwargs):
    payload = {
        "asset_symbol": "AAPL",
        "date": "2026-01-01",
        "type": "BUY",
        "quantity": "10",
        "price_per_share": "100",
        "currency": "EUR",
        "fees": "0",
        "portfolio_id": portfolio_id,
    }
    payload.update(kwargs)
    return api_client.post("/api/v1/transactions", payload, format="json")


def _sell(api_client, portfolio_id: int, **kwargs):
    payload = {
        "asset_symbol": "AAPL",
        "date": "2026-02-01",
        "type": "SELL",
        "quantity": "10",
        "price_per_share": "150",
        "currency": "EUR",
        "fees": "0",
        "portfolio_id": portfolio_id,
    }
    payload.update(kwargs)
    return api_client.post("/api/v1/transactions", payload, format="json")


def _mf_buy(api_client, portfolio_id: int, **kwargs):
    payload = {
        "asset_type": "MUTUAL_FUND",
        "scheme_code": "120503",
        "scheme_name": "Test Fund",
        "folio_number": "F1",
        "type": "BUY",
        "investment_date": "2026-03-10",
        "nav_date": "2026-03-15",
        "nav": "42.5",
        "units_allotted": "100",
        "paid_value": "4255.00",
        "market_value": "4250.00",
        "currency": "INR",
        "portfolio_id": portfolio_id,
    }
    payload.update(kwargs)
    return api_client.post("/api/v1/transactions", payload, format="json")


def _preview(api_client, portfolio_id: int, **body):
    payload = {"portfolio_id": portfolio_id, "mode": "shortfall"}
    payload.update(body)
    return api_client.post(URL, payload, format="json")


@pytest.mark.django_db
def test_legacy_first_buy_proposes_deposit(api_client, seeded, test_user):
    portfolio = _legacy(ensure_default_portfolio(test_user))
    _buy(api_client, portfolio.id, date="2026-01-01", quantity="10", price_per_share="100")
    before_entries = CashLedgerEntry.objects.filter(portfolio=portfolio).count()
    before_txns = Transaction.objects.filter(portfolio=portfolio).count()
    data = _preview(api_client, portfolio.id).json()
    assert data["cash_aware_enabled"] is False
    assert data["summary"]["proposed_deposit_count"] == 1
    assert len(data["proposed_deposits"]) == 1
    dep = data["proposed_deposits"][0]
    assert dep["currency"] == "EUR"
    assert dep["amount"] == 1000.0
    assert dep["source_of_funds"] == "Backfill deposit"
    assert "BUY AAPL" in dep["note"]
    assert data["shortfalls"][0]["shortfall"] == 1000.0
    assert CashLedgerEntry.objects.filter(portfolio=portfolio).count() == before_entries
    assert Transaction.objects.filter(portfolio=portfolio).count() == before_txns


@pytest.mark.django_db
def test_multiple_buys_same_day_currency_merged(api_client, seeded, test_user):
    portfolio = _legacy(ensure_default_portfolio(test_user))
    _buy(
        api_client,
        portfolio.id,
        date="2026-01-01",
        asset_symbol="AAA",
        quantity="1",
        price_per_share="100",
    )
    _buy(
        api_client,
        portfolio.id,
        date="2026-01-01",
        asset_symbol="BBB",
        quantity="2",
        price_per_share="50",
    )
    data = _preview(api_client, portfolio.id).json()
    assert len(data["proposed_deposits"]) == 1
    assert data["proposed_deposits"][0]["amount"] == 200.0
    assert data["proposed_deposits"][0]["date"] == "2026-01-01"


@pytest.mark.django_db
def test_sell_proceeds_fund_later_buy(api_client, seeded, test_user):
    portfolio = _legacy(ensure_default_portfolio(test_user))
    _deposit(portfolio, day="2026-01-01", amount="500")
    _buy(
        api_client,
        portfolio.id,
        date="2026-01-01",
        quantity="5",
        price_per_share="100",
    )
    _sell(api_client, portfolio.id, date="2026-01-02", quantity="5", price_per_share="200")
    _buy(api_client, portfolio.id, date="2026-01-03", quantity="5", price_per_share="100")
    data = _preview(api_client, portfolio.id).json()
    assert data["proposed_deposits"] == []


@pytest.mark.django_db
def test_usd_cash_does_not_fund_eur_buy(api_client, seeded, test_user):
    portfolio = _legacy(ensure_default_portfolio(test_user))
    _deposit(portfolio, day="2026-01-01", amount="5000", currency="USD")
    _buy(api_client, portfolio.id, date="2026-01-02", currency="EUR")
    data = _preview(api_client, portfolio.id).json()
    assert len(data["proposed_deposits"]) == 1
    assert data["proposed_deposits"][0]["currency"] == "EUR"
    assert data["proposed_deposits"][0]["amount"] == 1000.0


@pytest.mark.django_db
def test_existing_eur_deposit_reduces_proposed(api_client, seeded, test_user):
    portfolio = _legacy(ensure_default_portfolio(test_user))
    _deposit(portfolio, day="2026-01-01", amount="600")
    _buy(api_client, portfolio.id, date="2026-01-01", quantity="10", price_per_share="100")
    data = _preview(api_client, portfolio.id).json()
    assert len(data["proposed_deposits"]) == 1
    assert data["proposed_deposits"][0]["amount"] == 400.0


@pytest.mark.django_db
def test_mf_buy_uses_paid_value_and_investment_date(api_client, seeded, test_user):
    portfolio = _legacy(ensure_default_portfolio(test_user))
    _mf_buy(api_client, portfolio.id)
    data = _preview(
        api_client,
        portfolio.id,
        start_date="2026-03-01",
        end_date="2026-03-31",
    ).json()
    assert len(data["proposed_deposits"]) == 1
    dep = data["proposed_deposits"][0]
    assert dep["currency"] == "INR"
    assert dep["amount"] == 4255.0
    assert dep["date"] == "2026-03-10"
    assert "BUY 120503" in dep["note"]


@pytest.mark.django_db
def test_stock_split_no_cash_requirement(api_client, seeded, test_user):
    portfolio = _legacy(ensure_default_portfolio(test_user))
    _buy(api_client, portfolio.id, date="2026-01-01")
    api_client.post(
        "/api/v1/transactions",
        {
            "portfolio_id": portfolio.id,
            "asset_symbol": "AAPL",
            "date": "2026-02-01",
            "type": "STOCK_SPLIT",
            "quantity": "20",
            "split_from": "10",
            "split_to": "20",
            "currency": "EUR",
        },
        format="json",
    )
    data = _preview(api_client, portfolio.id).json()
    assert len(data["proposed_deposits"]) == 1
    assert data["proposed_deposits"][0]["amount"] == 1000.0


@pytest.mark.django_db
def test_cash_aware_consistent_ledger_no_proposed_deposits(
    api_client, seeded, test_user
):
    portfolio = _enable_cash_aware(ensure_default_portfolio(test_user))
    _deposit(portfolio, day="2026-01-01", amount="5000")
    assert _buy(api_client, portfolio.id, date="2026-01-02").status_code == 201
    data = _preview(api_client, portfolio.id).json()
    assert data["proposed_deposits"] == []
    assert data["can_enable_cash_aware_after_apply"] is True
    assert any("already cash-aware" in w.lower() for w in data["warnings"])


@pytest.mark.django_db
def test_unknown_portfolio_404(api_client, seeded, test_user):
    portfolio = _legacy(ensure_default_portfolio(test_user))
    response = _preview(api_client, portfolio.id + 99999)
    assert response.status_code == 404


@pytest.mark.django_db
def test_invalid_date_range_400(api_client, seeded, test_user):
    portfolio = _legacy(ensure_default_portfolio(test_user))
    response = _preview(
        api_client,
        portfolio.id,
        start_date="2026-06-01",
        end_date="2026-01-01",
    )
    assert response.status_code == 400
