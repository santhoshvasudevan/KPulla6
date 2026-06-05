"""Cash-4A — cash-aware BUY/SELL settlement on asset transactions."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cash.models import CashEntryType, CashLedgerEntry
from portfolios.models import Portfolio
from portfolios.seed import ensure_default_portfolio
from transactions.models import MutualFundTransactionDetail, Transaction, TransactionType


def _stock_payload(**overrides):
    base = {
        "asset_symbol": "AAPL",
        "date": "2026-06-01",
        "type": "BUY",
        "quantity": "10",
        "price_per_share": "100",
        "currency": "EUR",
        "fees": "5",
    }
    base.update(overrides)
    return base


def _mf_payload(**overrides):
    base = {
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
    }
    base.update(overrides)
    return base


def _enable_cash_aware(portfolio: Portfolio) -> Portfolio:
    portfolio.cash_aware_enabled = True
    portfolio.save(update_fields=["cash_aware_enabled", "updated_at"])
    return portfolio


def _legacy_portfolio(test_user) -> Portfolio:
    """Simulate a pre–Cash-4A.1 portfolio row (cash_aware_enabled=false)."""
    portfolio = ensure_default_portfolio(test_user)
    if portfolio.cash_aware_enabled:
        portfolio.cash_aware_enabled = False
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


@pytest.mark.django_db
def test_legacy_buy_creates_no_settlement(api_client, seeded, test_user):
    portfolio = _legacy_portfolio(test_user)
    assert portfolio.cash_aware_enabled is False
    response = api_client.post(
        "/api/v1/transactions",
        _stock_payload(portfolio_id=portfolio.id),
        format="json",
    )
    assert response.status_code == 201
    txn_id = response.json()["id"]
    assert not CashLedgerEntry.objects.filter(linked_transaction_id=txn_id).exists()


@pytest.mark.django_db
def test_legacy_sell_creates_no_settlement(api_client, seeded, test_user):
    portfolio = _legacy_portfolio(test_user)
    response = api_client.post(
        "/api/v1/transactions",
        _stock_payload(type="SELL", portfolio_id=portfolio.id),
        format="json",
    )
    assert response.status_code == 201
    assert not CashLedgerEntry.objects.filter(
        linked_transaction_id=response.json()["id"]
    ).exists()


@pytest.mark.django_db
def test_cash_aware_buy_creates_settlement(api_client, seeded, test_user):
    portfolio = _enable_cash_aware(ensure_default_portfolio(test_user))
    _deposit(portfolio, day="2026-05-01", amount="2000")
    response = api_client.post(
        "/api/v1/transactions",
        _stock_payload(portfolio_id=portfolio.id),
        format="json",
    )
    assert response.status_code == 201
    txn_id = response.json()["id"]
    entry = CashLedgerEntry.objects.get(linked_transaction_id=txn_id)
    assert entry.entry_type == CashEntryType.BUY_SETTLEMENT
    assert entry.amount == Decimal("-1005")
    assert entry.date == date(2026, 6, 1)
    assert entry.currency == "EUR"
    assert "AAPL" in entry.note


@pytest.mark.django_db
def test_cash_aware_buy_insufficient_cash(api_client, seeded, test_user):
    portfolio = _enable_cash_aware(ensure_default_portfolio(test_user))
    _deposit(portfolio, day="2026-05-01", amount="500")
    response = api_client.post(
        "/api/v1/transactions",
        _stock_payload(portfolio_id=portfolio.id),
        format="json",
    )
    assert response.status_code == 400
    data = response.json()
    assert data["detail"] == "Insufficient cash balance for purchase."
    assert data["required"] == 1005.0
    assert data["available"] == 500.0
    assert data["shortfall"] == 505.0
    assert data["currency"] == "EUR"
    assert Transaction.objects.filter(asset_symbol="AAPL").count() == 0
    assert CashLedgerEntry.objects.filter(entry_type=CashEntryType.BUY_SETTLEMENT).count() == 0


@pytest.mark.django_db
def test_cash_aware_sell_creates_settlement(api_client, seeded, test_user):
    portfolio = _enable_cash_aware(ensure_default_portfolio(test_user))
    response = api_client.post(
        "/api/v1/transactions",
        _stock_payload(type="SELL", portfolio_id=portfolio.id),
        format="json",
    )
    assert response.status_code == 201
    entry = CashLedgerEntry.objects.get(
        linked_transaction_id=response.json()["id"]
    )
    assert entry.entry_type == CashEntryType.SELL_SETTLEMENT
    assert entry.amount == Decimal("995")


@pytest.mark.django_db
def test_cash_aware_sell_rejects_non_positive_proceeds(api_client, seeded, test_user):
    portfolio = _enable_cash_aware(ensure_default_portfolio(test_user))
    response = api_client.post(
        "/api/v1/transactions",
        _stock_payload(
            type="SELL",
            quantity="10",
            price_per_share="1",
            fees="20",
            portfolio_id=portfolio.id,
        ),
        format="json",
    )
    assert response.status_code == 400
    assert "proceeds" in response.json()["detail"].lower()


@pytest.mark.django_db
def test_cash_aware_stock_split_no_settlement(api_client, seeded, test_user):
    portfolio = _enable_cash_aware(ensure_default_portfolio(test_user))
    response = api_client.post(
        "/api/v1/transactions",
        {
            "portfolio_id": portfolio.id,
            "asset_symbol": "AAPL",
            "date": "2026-06-01",
            "type": "STOCK_SPLIT",
            "currency": "EUR",
            "split_from": "1",
            "split_to": "2",
        },
        format="json",
    )
    assert response.status_code == 201
    assert not CashLedgerEntry.objects.filter(
        linked_transaction_id=response.json()["id"]
    ).exists()


@pytest.mark.django_db
def test_cash_aware_buy_update_changes_settlement(api_client, seeded, test_user):
    portfolio = _enable_cash_aware(ensure_default_portfolio(test_user))
    _deposit(portfolio, day="2026-05-01", amount="5000")
    created = api_client.post(
        "/api/v1/transactions",
        _stock_payload(portfolio_id=portfolio.id, quantity="5"),
        format="json",
    ).json()
    entry = CashLedgerEntry.objects.get(linked_transaction_id=created["id"])
    assert entry.amount == Decimal("-505")

    response = api_client.put(
        f"/api/v1/transactions/{created['id']}",
        _stock_payload(portfolio_id=portfolio.id, quantity="8"),
        format="json",
    )
    assert response.status_code == 200
    entry.refresh_from_db()
    assert entry.amount == Decimal("-805")


@pytest.mark.django_db
def test_cash_aware_buy_update_blocked_insufficient(api_client, seeded, test_user):
    portfolio = _enable_cash_aware(ensure_default_portfolio(test_user))
    _deposit(portfolio, day="2026-05-01", amount="2000")
    created = api_client.post(
        "/api/v1/transactions",
        _stock_payload(portfolio_id=portfolio.id, quantity="5"),
        format="json",
    ).json()

    response = api_client.put(
        f"/api/v1/transactions/{created['id']}",
        _stock_payload(portfolio_id=portfolio.id, quantity="25"),
        format="json",
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Insufficient cash balance for purchase."
    entry = CashLedgerEntry.objects.get(linked_transaction_id=created["id"])
    assert entry.amount == Decimal("-505")


@pytest.mark.django_db
def test_cash_aware_delete_buy_removes_settlement(api_client, seeded, test_user):
    portfolio = _enable_cash_aware(ensure_default_portfolio(test_user))
    _deposit(portfolio, day="2026-05-01", amount="2000")
    created = api_client.post(
        "/api/v1/transactions",
        _stock_payload(portfolio_id=portfolio.id),
        format="json",
    ).json()
    entry_id = CashLedgerEntry.objects.get(linked_transaction_id=created["id"]).id

    response = api_client.delete(f"/api/v1/transactions/{created['id']}")
    assert response.status_code == 204
    assert not Transaction.objects.filter(pk=created["id"]).exists()
    assert not CashLedgerEntry.objects.filter(pk=entry_id).exists()


@pytest.mark.django_db
def test_cash_aware_delete_sell_blocked_when_later_negative(
    api_client, seeded, test_user
):
    portfolio = _enable_cash_aware(ensure_default_portfolio(test_user))
    _deposit(portfolio, day="2026-06-01", amount="1000")
    sell = api_client.post(
        "/api/v1/transactions",
        _stock_payload(
            type="SELL",
            date="2026-06-05",
            quantity="10",
            price_per_share="100",
            fees="0",
            portfolio_id=portfolio.id,
        ),
        format="json",
    ).json()
    api_client.post(
        "/api/v1/transactions",
        _stock_payload(
            date="2026-06-10",
            quantity="15",
            price_per_share="100",
            fees="0",
            portfolio_id=portfolio.id,
        ),
        format="json",
    )

    response = api_client.delete(f"/api/v1/transactions/{sell['id']}")
    assert response.status_code == 400
    assert "negative" in response.json()["detail"].lower()
    assert Transaction.objects.filter(pk=sell["id"]).exists()


@pytest.mark.django_db
def test_cash_aware_mf_buy_settlement(api_client, seeded, test_user):
    portfolio = _enable_cash_aware(ensure_default_portfolio(test_user))
    _deposit(portfolio, day="2026-03-01", amount="10000", currency="INR")
    response = api_client.post(
        "/api/v1/transactions",
        _mf_payload(portfolio_id=portfolio.id),
        format="json",
    )
    assert response.status_code == 201
    entry = CashLedgerEntry.objects.get(
        linked_transaction_id=response.json()["id"]
    )
    assert entry.entry_type == CashEntryType.BUY_SETTLEMENT
    assert entry.amount == Decimal("-4255")
    assert entry.date == date(2026, 3, 10)
    assert entry.currency == "INR"


@pytest.mark.django_db
def test_cash_aware_mf_buy_insufficient_inr(api_client, seeded, test_user):
    portfolio = _enable_cash_aware(ensure_default_portfolio(test_user))
    _deposit(portfolio, day="2026-03-01", amount="1000", currency="INR")
    response = api_client.post(
        "/api/v1/transactions",
        _mf_payload(portfolio_id=portfolio.id),
        format="json",
    )
    assert response.status_code == 400
    assert response.json()["currency"] == "INR"
    assert not MutualFundTransactionDetail.objects.filter(
        transaction__asset_symbol="120503"
    ).exists()


@pytest.mark.django_db
def test_cash_aware_mf_sell_settlement_uses_paid_value(api_client, seeded, test_user):
    portfolio = _enable_cash_aware(ensure_default_portfolio(test_user))
    response = api_client.post(
        "/api/v1/transactions",
        _mf_payload(type="SELL", paid_value="5000.00", portfolio_id=portfolio.id),
        format="json",
    )
    assert response.status_code == 201
    entry = CashLedgerEntry.objects.get(
        linked_transaction_id=response.json()["id"]
    )
    assert entry.entry_type == CashEntryType.SELL_SETTLEMENT
    assert entry.amount == Decimal("5000")
    assert entry.date == date(2026, 3, 10)


@pytest.mark.django_db
def test_legacy_mf_buy_no_settlement(api_client, seeded, test_user):
    portfolio = _legacy_portfolio(test_user)
    assert portfolio.cash_aware_enabled is False
    response = api_client.post(
        "/api/v1/transactions",
        _mf_payload(portfolio_id=portfolio.id),
        format="json",
    )
    assert response.status_code == 201
    assert not CashLedgerEntry.objects.filter(
        linked_transaction_id=response.json()["id"]
    ).exists()


@pytest.mark.django_db
def test_linked_settlement_not_manually_editable(api_client, seeded, test_user):
    portfolio = _enable_cash_aware(ensure_default_portfolio(test_user))
    _deposit(portfolio, day="2026-05-01", amount="5000")
    created = api_client.post(
        "/api/v1/transactions",
        _stock_payload(portfolio_id=portfolio.id),
        format="json",
    ).json()
    entry = CashLedgerEntry.objects.get(linked_transaction_id=created["id"])
    response = api_client.put(
        f"/api/v1/cash/ledger/{entry.id}",
        {
            "date": "2026-06-02",
            "currency": "EUR",
            "amount": "100",
            "note": "",
            "source_of_funds": "",
        },
        format="json",
    )
    assert response.status_code == 409


def _balances_by_currency(api_client, portfolio: Portfolio) -> dict[str, float]:
    response = api_client.get(
        "/api/v1/cash/balances", {"portfolio_id": portfolio.id}
    )
    assert response.status_code == 200
    return {
        row["currency"]: row["balance"]
        for row in response.json()["balances"]
    }


@pytest.mark.django_db
def test_cash_aware_eur_buy_ignores_usd_only_deposit(api_client, seeded, test_user):
    """Same-currency enforcement: USD cash does not fund a EUR stock BUY."""
    portfolio = _enable_cash_aware(ensure_default_portfolio(test_user))
    _deposit(portfolio, day="2026-05-01", amount="50000", currency="USD")
    response = api_client.post(
        "/api/v1/transactions",
        _stock_payload(portfolio_id=portfolio.id),
        format="json",
    )
    assert response.status_code == 400
    data = response.json()
    assert data["detail"] == "Insufficient cash balance for purchase."
    assert data["required"] == 1005.0
    assert data["available"] == 0.0
    assert data["shortfall"] == 1005.0
    assert data["currency"] == "EUR"
    assert Transaction.objects.filter(asset_symbol="AAPL").count() == 0
    assert CashLedgerEntry.objects.filter(entry_type=CashEntryType.BUY_SETTLEMENT).count() == 0
    balances = _balances_by_currency(api_client, portfolio)
    assert balances.get("USD") == 50000.0
    assert balances.get("EUR") is None


@pytest.mark.django_db
def test_cash_aware_eur_buy_uses_partial_eur_only(api_client, seeded, test_user):
    """EUR BUY considers EUR ledger only; USD balance is ignored for sufficiency."""
    portfolio = _enable_cash_aware(ensure_default_portfolio(test_user))
    _deposit(portfolio, day="2026-05-01", amount="50000", currency="USD")
    _deposit(portfolio, day="2026-05-02", amount="500", currency="EUR")
    response = api_client.post(
        "/api/v1/transactions",
        _stock_payload(portfolio_id=portfolio.id),
        format="json",
    )
    assert response.status_code == 400
    data = response.json()
    assert data["currency"] == "EUR"
    assert data["required"] == 1005.0
    assert data["available"] == 500.0
    assert data["shortfall"] == 505.0
    assert Transaction.objects.filter(asset_symbol="AAPL").count() == 0
    balances = _balances_by_currency(api_client, portfolio)
    assert balances.get("USD") == 50000.0
    assert balances.get("EUR") == 500.0


@pytest.mark.django_db
def test_cash_aware_eur_buy_succeeds_usd_unchanged(api_client, seeded, test_user):
    """Sufficient EUR funds BUY; USD balance is not consumed or altered."""
    portfolio = _enable_cash_aware(ensure_default_portfolio(test_user))
    _deposit(portfolio, day="2026-05-01", amount="25000", currency="USD")
    _deposit(portfolio, day="2026-05-02", amount="2000", currency="EUR")
    response = api_client.post(
        "/api/v1/transactions",
        _stock_payload(portfolio_id=portfolio.id),
        format="json",
    )
    assert response.status_code == 201
    txn_id = response.json()["id"]
    entry = CashLedgerEntry.objects.get(linked_transaction_id=txn_id)
    assert entry.entry_type == CashEntryType.BUY_SETTLEMENT
    assert entry.currency == "EUR"
    assert entry.amount == Decimal("-1005")
    balances = _balances_by_currency(api_client, portfolio)
    assert balances.get("USD") == 25000.0
    assert balances.get("EUR") == 995.0
