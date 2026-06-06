"""Transactions page column filters — backend filter params and options."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from portfolios.models import Portfolio
from portfolios.seed import ensure_default_portfolio
from transactions.models import Transaction, TransactionType


def _stock(portfolio, symbol, d, *, currency="EUR", qty="10", price="100"):
    return Transaction.objects.create(
        portfolio=portfolio,
        asset_symbol=symbol,
        date=date.fromisoformat(d),
        type=TransactionType.BUY,
        quantity=Decimal(qty),
        price_per_share=Decimal(price),
        currency=currency,
        fees=Decimal("0"),
    )


def _mf_payload(**overrides):
    base = {
        "asset_type": "MUTUAL_FUND",
        "scheme_code": "120503",
        "scheme_name": "Test Direct Growth Fund",
        "folio_number": "FOLIO-12345",
        "type": "BUY",
        "investment_date": "2026-03-10",
        "nav_date": "2026-03-15",
        "nav": "42.500000",
        "units_allotted": "100.00000000",
        "paid_value": "4255.00",
        "market_value": "4250.00",
        "fund_house": "Test AMC",
    }
    base.update(overrides)
    return base


@pytest.mark.django_db
def test_filter_by_portfolio_id(api_client, legacy_seeded, test_user):
    default = ensure_default_portfolio(test_user)
    other = Portfolio.objects.create(user=test_user, name="Other", base_currency="EUR", is_active=True)
    _stock(default, "AAPL", "2026-01-01")
    _stock(other, "MSFT", "2026-01-02")

    response = api_client.get(f"/api/v1/transactions?portfolio_id={other.id}&page_size=50")
    assert response.status_code == 200
    symbols = {item["asset_symbol"] for item in response.json()["items"]}
    assert symbols == {"MSFT"}


@pytest.mark.django_db
def test_filter_by_asset_symbol_case_insensitive(api_client, legacy_seeded, test_user):
    default = ensure_default_portfolio(test_user)
    _stock(default, "AAPL", "2026-01-01")
    _stock(default, "MSFT", "2026-01-02")

    response = api_client.get("/api/v1/transactions?asset_symbol=aApL&page_size=50")
    symbols = {item["asset_symbol"] for item in response.json()["items"]}
    assert symbols == {"AAPL"}


@pytest.mark.django_db
def test_filter_by_symbols_multi_select(api_client, legacy_seeded, test_user):
    default = ensure_default_portfolio(test_user)
    _stock(default, "AAPL", "2026-01-01")
    _stock(default, "MSFT", "2026-01-02")
    _stock(default, "GOOG", "2026-01-03")

    response = api_client.get("/api/v1/transactions?symbols=aapl,goog&page_size=50")
    symbols = {item["asset_symbol"] for item in response.json()["items"]}
    assert symbols == {"AAPL", "GOOG"}


@pytest.mark.django_db
def test_filter_date_from(api_client, legacy_seeded, test_user):
    default = ensure_default_portfolio(test_user)
    _stock(default, "AAPL", "2026-01-01")
    _stock(default, "MSFT", "2026-06-01")

    response = api_client.get("/api/v1/transactions?date_from=2026-03-01&page_size=50")
    symbols = {item["asset_symbol"] for item in response.json()["items"]}
    assert symbols == {"MSFT"}


@pytest.mark.django_db
def test_filter_date_to(api_client, legacy_seeded, test_user):
    default = ensure_default_portfolio(test_user)
    _stock(default, "AAPL", "2026-01-01")
    _stock(default, "MSFT", "2026-06-01")

    response = api_client.get("/api/v1/transactions?date_to=2026-03-01&page_size=50")
    symbols = {item["asset_symbol"] for item in response.json()["items"]}
    assert symbols == {"AAPL"}


@pytest.mark.django_db
def test_filter_date_between(api_client, legacy_seeded, test_user):
    default = ensure_default_portfolio(test_user)
    _stock(default, "AAPL", "2026-01-01")
    _stock(default, "MSFT", "2026-03-15")
    _stock(default, "GOOG", "2026-06-01")

    response = api_client.get(
        "/api/v1/transactions?date_from=2026-02-01&date_to=2026-04-01&page_size=50"
    )
    symbols = {item["asset_symbol"] for item in response.json()["items"]}
    assert symbols == {"MSFT"}


@pytest.mark.django_db
def test_date_after_before_aliases(api_client, legacy_seeded, test_user):
    default = ensure_default_portfolio(test_user)
    _stock(default, "AAPL", "2026-01-01")
    _stock(default, "MSFT", "2026-06-01")

    later = api_client.get("/api/v1/transactions?date_after=2026-03-01&page_size=50")
    assert {i["asset_symbol"] for i in later.json()["items"]} == {"MSFT"}

    earlier = api_client.get("/api/v1/transactions?date_before=2026-03-01&page_size=50")
    assert {i["asset_symbol"] for i in earlier.json()["items"]} == {"AAPL"}


@pytest.mark.django_db
def test_filters_applied_before_pagination(api_client, legacy_seeded, test_user):
    default = ensure_default_portfolio(test_user)
    for i in range(5):
        _stock(default, "AAPL", f"2026-01-0{i + 1}")
    for i in range(3):
        _stock(default, "MSFT", f"2026-02-0{i + 1}")

    response = api_client.get("/api/v1/transactions?asset_symbol=AAPL&page=1&page_size=2")
    body = response.json()
    assert body["total"] == 5
    assert body["pages"] == 3
    assert len(body["items"]) == 2
    assert all(item["asset_symbol"] == "AAPL" for item in body["items"])


@pytest.mark.django_db
def test_invalid_date_returns_400(api_client, legacy_seeded):
    response = api_client.get("/api/v1/transactions?date_from=not-a-date")
    assert response.status_code == 400


@pytest.mark.django_db
def test_date_from_after_date_to_returns_400(api_client, legacy_seeded):
    response = api_client.get(
        "/api/v1/transactions?date_from=2026-06-01&date_to=2026-01-01"
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_filter_mutual_fund_scheme_code(api_client, legacy_seeded, test_user):
    default = ensure_default_portfolio(test_user)
    _stock(default, "AAPL", "2026-01-01")
    create = api_client.post(
        "/api/v1/transactions",
        _mf_payload(portfolio_id=default.id),
        format="json",
    )
    assert create.status_code == 201

    response = api_client.get("/api/v1/transactions?symbols=120503&page_size=50")
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["scheme_code"] == "120503"
    assert items[0]["asset_type"] == "MUTUAL_FUND"


@pytest.mark.django_db
def test_no_filters_returns_all_in_scope(api_client, legacy_seeded, test_user):
    default = ensure_default_portfolio(test_user)
    _stock(default, "AAPL", "2026-01-01")
    _stock(default, "MSFT", "2026-02-01")

    response = api_client.get("/api/v1/transactions?page_size=50")
    symbols = {item["asset_symbol"] for item in response.json()["items"]}
    assert symbols == {"AAPL", "MSFT"}


@pytest.mark.django_db
def test_filter_options_returns_scope_distinct_values(api_client, legacy_seeded, test_user):
    default = ensure_default_portfolio(test_user)
    other = Portfolio.objects.create(user=test_user, name="Aaa Other", base_currency="EUR", is_active=True)
    _stock(default, "AAPL", "2026-01-01")
    _stock(default, "AAPL", "2026-02-01")  # duplicate symbol across rows
    _stock(default, "MSFT", "2026-06-01")
    _stock(other, "GOOG", "2026-03-01")

    response = api_client.get("/api/v1/transactions/filter-options?portfolio_scope=all")
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"portfolios", "symbols", "types", "date_min", "date_max"}
    assert body["symbols"] == ["AAPL", "GOOG", "MSFT"]
    # Values must be distinct even though the base queryset is ordered.
    assert len(body["symbols"]) == len(set(body["symbols"]))
    assert len(body["types"]) == len(set(body["types"]))
    assert body["date_min"] == "2026-01-01"
    assert body["date_max"] == "2026-06-01"
    names = [p["name"] for p in body["portfolios"]]
    assert default.name in names
    assert "Aaa Other" in names


@pytest.mark.django_db
def test_filter_options_scoped_to_portfolio(api_client, legacy_seeded, test_user):
    default = ensure_default_portfolio(test_user)
    other = Portfolio.objects.create(user=test_user, name="Other", base_currency="EUR", is_active=True)
    _stock(default, "AAPL", "2026-01-01")
    _stock(other, "GOOG", "2026-03-01")

    response = api_client.get(
        f"/api/v1/transactions/filter-options?portfolio_id={other.id}"
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body["symbols"]) == {"GOOG"}
    # Portfolio dropdown still lists all active portfolios so scope can broaden.
    names = [p["name"] for p in body["portfolios"]]
    assert default.name in names and "Other" in names


@pytest.mark.django_db
def test_filter_options_excludes_inactive_portfolios(api_client, legacy_seeded, test_user):
    ensure_default_portfolio(test_user)
    Portfolio.objects.create(user=test_user, name="Inactive", is_active=False)
    response = api_client.get("/api/v1/transactions/filter-options?portfolio_scope=all")
    names = [p["name"] for p in response.json()["portfolios"]]
    assert "Inactive" not in names


@pytest.mark.django_db
def test_filter_options_unknown_portfolio_returns_404(api_client, legacy_seeded):
    response = api_client.get("/api/v1/transactions/filter-options?portfolio_id=999999")
    assert response.status_code == 404
