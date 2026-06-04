from datetime import date
from decimal import Decimal

import pytest

from portfolios.models import Portfolio
from portfolios.seed import ensure_default_portfolio
from transactions.models import Transaction, TransactionType


def _payload(**overrides):
    base = {
        "asset_symbol": "aapl",
        "date": "2026-05-01",
        "type": "BUY",
        "quantity": "10.5",
        "price_per_share": "150.00",
        "currency": "USD",
        "fees": "2.50",
    }
    base.update(overrides)
    return base


def _split_payload(**overrides):
    base = {
        "asset_symbol": "AAPL",
        "date": "2024-01-01",
        "type": "STOCK_SPLIT",
        "currency": "USD",
        "split_from": "1",
        "split_to": "20",
    }
    base.update(overrides)
    return base


@pytest.mark.django_db
def test_list_returns_paginated_response(api_client, seeded):
    api_client.post("/api/v1/transactions", _payload(), format="json")
    response = api_client.get("/api/v1/transactions")
    assert response.status_code == 200
    data = response.json()
    assert set(data.keys()) == {"items", "total", "page", "page_size", "pages"}
    assert data["page"] == 1
    assert data["page_size"] == 20
    assert data["total"] >= 1
    assert len(data["items"]) >= 1


@pytest.mark.django_db
def test_list_default_is_portfolio_scope_all(api_client, seeded, test_user):
    default = ensure_default_portfolio(test_user)
    other = Portfolio.objects.create(user=test_user, name="Other", base_currency="EUR", is_active=True)
    api_client.post("/api/v1/transactions", _payload(portfolio_id=default.id), format="json")
    api_client.post(
        "/api/v1/transactions",
        _payload(asset_symbol="MSFT", portfolio_id=other.id),
        format="json",
    )
    response = api_client.get("/api/v1/transactions?page_size=50")
    symbols = {item["asset_symbol"] for item in response.json()["items"]}
    assert symbols == {"AAPL", "MSFT"}


@pytest.mark.django_db
def test_list_portfolio_scope_all_active_portfolios(api_client, seeded, test_user):
    default = ensure_default_portfolio(test_user)
    inactive = Portfolio.objects.create(user=test_user, name="Inactive", is_active=False)
    api_client.post("/api/v1/transactions", _payload(portfolio_id=default.id), format="json")
    Transaction.objects.create(
        portfolio=inactive,
        asset_symbol="ZZZ",
        date=date(2026, 5, 2),
        type=TransactionType.BUY,
        quantity=Decimal("1"),
        price_per_share=Decimal("10"),
        currency="EUR",
        fees=Decimal("0"),
    )
    response = api_client.get("/api/v1/transactions?portfolio_scope=all&page_size=50")
    symbols = {item["asset_symbol"] for item in response.json()["items"]}
    assert "AAPL" in symbols
    assert "ZZZ" not in symbols


@pytest.mark.django_db
def test_list_portfolio_id_filter(api_client, seeded, test_user):
    default = ensure_default_portfolio(test_user)
    other = Portfolio.objects.create(user=test_user, name="Scoped", base_currency="EUR", is_active=True)
    api_client.post("/api/v1/transactions", _payload(portfolio_id=default.id), format="json")
    api_client.post(
        "/api/v1/transactions",
        _payload(asset_symbol="MSFT", portfolio_id=other.id),
        format="json",
    )
    response = api_client.get(f"/api/v1/transactions?portfolio_id={other.id}&page_size=50")
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["asset_symbol"] == "MSFT"
    assert items[0]["portfolio_id"] == other.id
    assert items[0]["portfolio_name"] == "Scoped"


@pytest.mark.django_db
def test_list_rejects_scope_and_portfolio_id(api_client, seeded):
    response = api_client.get("/api/v1/transactions?portfolio_scope=all&portfolio_id=1")
    assert response.status_code == 422


@pytest.mark.django_db
def test_list_unknown_portfolio_id_returns_404(api_client, seeded):
    response = api_client.get("/api/v1/transactions?portfolio_id=999999")
    assert response.status_code == 404


@pytest.mark.django_db
def test_list_inactive_portfolio_id_returns_404(api_client, seeded, test_user):
    inactive = Portfolio.objects.create(user=test_user, name="Inactive", is_active=False)
    response = api_client.get(f"/api/v1/transactions?portfolio_id={inactive.id}")
    assert response.status_code == 404


@pytest.mark.django_db
def test_list_asset_symbol_filter_case_insensitive(api_client, seeded):
    api_client.post("/api/v1/transactions", _payload(asset_symbol="aapl"), format="json")
    api_client.post(
        "/api/v1/transactions",
        _payload(asset_symbol="MSFT"),
        format="json",
    )
    response = api_client.get("/api/v1/transactions?asset_symbol=aApL&page_size=50")
    symbols = {item["asset_symbol"] for item in response.json()["items"]}
    assert symbols == {"AAPL"}


@pytest.mark.django_db
def test_post_creates_buy(api_client, seeded, test_user):
    default = ensure_default_portfolio(test_user)
    response = api_client.post(
        "/api/v1/transactions",
        _payload(portfolio_id=default.id),
        format="json",
    )
    assert response.status_code == 201
    data = response.json()
    assert data["type"] == "BUY"
    assert data["asset_symbol"] == "AAPL"
    assert data["portfolio_id"] == default.id
    assert data["portfolio_name"] == default.name


@pytest.mark.django_db
def test_post_creates_sell(api_client, seeded):
    response = api_client.post(
        "/api/v1/transactions",
        _payload(type="SELL"),
        format="json",
    )
    assert response.status_code == 201
    assert response.json()["type"] == "SELL"


@pytest.mark.django_db
def test_post_creates_dividend(api_client, seeded):
    response = api_client.post(
        "/api/v1/transactions",
        _payload(type="DIVIDEND", quantity="5", price_per_share="0"),
        format="json",
    )
    assert response.status_code == 201
    assert response.json()["type"] == "DIVIDEND"


@pytest.mark.django_db
def test_post_creates_stock_split(api_client, seeded, test_user):
    default = ensure_default_portfolio(test_user)
    response = api_client.post(
        "/api/v1/transactions",
        {**_split_payload(), "portfolio_id": default.id},
        format="json",
    )
    assert response.status_code == 201
    data = response.json()
    assert data["type"] == "STOCK_SPLIT"
    assert data["split_from"] == 1.0
    assert data["split_to"] == 20.0
    assert data["quantity"] == 0.0


@pytest.mark.django_db
def test_post_without_portfolio_id_assigns_default(api_client, seeded, test_user):
    default = ensure_default_portfolio(test_user)
    response = api_client.post("/api/v1/transactions", _payload(), format="json")
    assert response.status_code == 201
    assert response.json()["portfolio_id"] == default.id


@pytest.mark.django_db
def test_post_with_active_portfolio(api_client, seeded, test_user):
    portfolio = Portfolio.objects.create(user=test_user, name="Active", base_currency="EUR", is_active=True)
    response = api_client.post(
        "/api/v1/transactions",
        _payload(portfolio_id=portfolio.id),
        format="json",
    )
    assert response.status_code == 201
    assert response.json()["portfolio_id"] == portfolio.id


@pytest.mark.django_db
def test_post_rejects_unknown_or_inactive_portfolio(api_client, seeded, test_user):
    inactive = Portfolio.objects.create(user=test_user, name="Inactive", is_active=False)
    r1 = api_client.post(
        "/api/v1/transactions",
        _payload(portfolio_id=inactive.id),
        format="json",
    )
    assert r1.status_code == 404

    r2 = api_client.post(
        "/api/v1/transactions",
        _payload(portfolio_id=999999),
        format="json",
    )
    assert r2.status_code == 404


@pytest.mark.django_db
def test_post_rejects_missing_asset_symbol(api_client, seeded):
    payload = _payload()
    del payload["asset_symbol"]
    response = api_client.post("/api/v1/transactions", payload, format="json")
    assert response.status_code == 400


@pytest.mark.django_db
def test_post_rejects_invalid_date(api_client, seeded):
    response = api_client.post(
        "/api/v1/transactions",
        _payload(date="not-a-date"),
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_post_rejects_non_positive_quantity(api_client, seeded):
    response = api_client.post(
        "/api/v1/transactions",
        _payload(quantity="0"),
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_post_rejects_negative_price(api_client, seeded):
    response = api_client.post(
        "/api/v1/transactions",
        _payload(price_per_share="-1"),
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_post_defaults_fees_and_currency(api_client, seeded):
    payload = {
        "asset_symbol": "AAPL",
        "date": "2026-05-01",
        "type": "BUY",
        "quantity": "1",
        "price_per_share": "10",
    }
    response = api_client.post("/api/v1/transactions", payload, format="json")
    assert response.status_code == 201
    data = response.json()
    assert data["fees"] == 0.0
    assert data["currency"] == "EUR"


@pytest.mark.django_db
def test_post_normalizes_asset_symbol(api_client, seeded):
    response = api_client.post(
        "/api/v1/transactions",
        _payload(asset_symbol="msft"),
        format="json",
    )
    assert response.status_code == 201
    assert response.json()["asset_symbol"] == "MSFT"


@pytest.mark.django_db
def test_post_rejects_invalid_stock_split(api_client, seeded):
    r1 = api_client.post(
        "/api/v1/transactions",
        _split_payload(split_from="0"),
        format="json",
    )
    assert r1.status_code == 400

    r2 = api_client.post(
        "/api/v1/transactions",
        _split_payload(split_to="-1"),
        format="json",
    )
    assert r2.status_code == 400


@pytest.mark.django_db
def test_put_updates_fields(api_client, seeded):
    created = api_client.post("/api/v1/transactions", _payload(), format="json").json()
    response = api_client.put(
        f"/api/v1/transactions/{created['id']}",
        _payload(asset_symbol="msft", quantity="2", fees="1"),
        format="json",
    )
    assert response.status_code == 200
    data = response.json()
    assert data["asset_symbol"] == "MSFT"
    assert data["quantity"] == 2.0
    assert data["fees"] == 1.0


@pytest.mark.django_db
def test_put_omits_portfolio_id_preserves_assignment(api_client, seeded, test_user):
    p1 = Portfolio.objects.create(user=test_user, name="Keep", base_currency="EUR", is_active=True)
    p2 = Portfolio.objects.create(user=test_user, name="Other", base_currency="EUR", is_active=True)
    created = api_client.post(
        "/api/v1/transactions",
        _payload(portfolio_id=p1.id),
        format="json",
    ).json()
    payload = _payload(asset_symbol="MSFT")
    payload.pop("portfolio_id", None)
    response = api_client.put(
        f"/api/v1/transactions/{created['id']}",
        payload,
        format="json",
    )
    assert response.status_code == 200
    assert response.json()["portfolio_id"] == p1.id
    assert response.json()["portfolio_id"] != p2.id


@pytest.mark.django_db
def test_put_moves_to_another_active_portfolio(api_client, seeded, test_user):
    p1 = Portfolio.objects.create(user=test_user, name="P1", base_currency="EUR", is_active=True)
    p2 = Portfolio.objects.create(user=test_user, name="P2", base_currency="EUR", is_active=True)
    created = api_client.post(
        "/api/v1/transactions",
        _payload(portfolio_id=p1.id),
        format="json",
    ).json()
    response = api_client.put(
        f"/api/v1/transactions/{created['id']}",
        _payload(portfolio_id=p2.id),
        format="json",
    )
    assert response.status_code == 200
    assert response.json()["portfolio_id"] == p2.id


@pytest.mark.django_db
def test_put_rejects_unknown_or_inactive_portfolio(api_client, seeded, test_user):
    created = api_client.post("/api/v1/transactions", _payload(), format="json").json()
    inactive = Portfolio.objects.create(user=test_user, name="Inactive", is_active=False)

    r1 = api_client.put(
        f"/api/v1/transactions/{created['id']}",
        _payload(portfolio_id=inactive.id),
        format="json",
    )
    assert r1.status_code == 404

    r2 = api_client.put(
        f"/api/v1/transactions/{created['id']}",
        _payload(portfolio_id=999999),
        format="json",
    )
    assert r2.status_code == 404


@pytest.mark.django_db
def test_put_validates_stock_split(api_client, seeded):
    created = api_client.post(
        "/api/v1/transactions",
        _split_payload(),
        format="json",
    ).json()
    response = api_client.put(
        f"/api/v1/transactions/{created['id']}",
        _split_payload(split_from="0"),
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_put_unknown_transaction_returns_404(api_client, seeded):
    response = api_client.put(
        "/api/v1/transactions/999999",
        _payload(),
        format="json",
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_transaction_delete_hard_vs_portfolio_delete_soft(api_client, seeded, test_user):
    portfolio = Portfolio.objects.create(user=test_user, name="SoftDel", base_currency="EUR", is_active=True)
    created = api_client.post(
        "/api/v1/transactions",
        _payload(portfolio_id=portfolio.id),
        format="json",
    ).json()

    txn_delete = api_client.delete(f"/api/v1/transactions/{created['id']}")
    assert txn_delete.status_code == 204
    assert not Transaction.objects.filter(pk=created["id"]).exists()

    port_delete = api_client.delete(f"/api/v1/portfolios/{portfolio.id}")
    assert port_delete.status_code == 200
    assert port_delete.json()["is_active"] is False
    assert Portfolio.objects.filter(pk=portfolio.id).exists()


@pytest.mark.django_db
def test_delete_removes_transaction(api_client, seeded, test_user):
    default = ensure_default_portfolio(test_user)
    created = api_client.post("/api/v1/transactions", _payload(), format="json").json()
    response = api_client.delete(f"/api/v1/transactions/{created['id']}")
    assert response.status_code == 204
    assert not Transaction.objects.filter(pk=created["id"]).exists()
    assert Portfolio.objects.filter(pk=default.id).exists()


@pytest.mark.django_db
def test_delete_unknown_returns_404(api_client, seeded):
    response = api_client.delete("/api/v1/transactions/999999")
    assert response.status_code == 404


@pytest.mark.django_db
def test_delete_does_not_remove_other_transactions(api_client, seeded):
    first = api_client.post("/api/v1/transactions", _payload(), format="json").json()
    second = api_client.post(
        "/api/v1/transactions",
        _payload(asset_symbol="MSFT"),
        format="json",
    ).json()
    api_client.delete(f"/api/v1/transactions/{first['id']}")
    assert Transaction.objects.filter(pk=second["id"]).exists()
