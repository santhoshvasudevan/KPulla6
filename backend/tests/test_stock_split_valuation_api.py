"""Regression tests for split-adjusted historical price × quantity valuation."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from market_data.models import AssetType, HistoricalPrice

FIXED_TODAY = date(2026, 3, 15)


@pytest.fixture
def today_patch(monkeypatch):
    monkeypatch.setattr("portfolios.dates.current_date", lambda: FIXED_TODAY)
    return FIXED_TODAY


def _price(symbol: str, d: str, close: str, *, currency: str = "EUR"):
    HistoricalPrice.objects.create(
        asset_symbol=symbol,
        date=date.fromisoformat(d),
        close_price=Decimal(close),
        currency=currency,
        source="test",
        asset_type=AssetType.STOCK,
    )


def _buy(api_client, **kwargs):
    payload = {
        "asset_symbol": "GOOG",
        "date": "2024-06-01",
        "type": "BUY",
        "quantity": "1",
        "price_per_share": "2149",
        "currency": "EUR",
        "fees": "0",
    }
    payload.update(kwargs)
    return api_client.post("/api/v1/transactions", payload, format="json")


def _split(api_client, **kwargs):
    payload = {
        "asset_symbol": "GOOG",
        "date": "2024-07-15",
        "type": "STOCK_SPLIT",
        "quantity": "0",
        "price_per_share": "0",
        "currency": "EUR",
        "split_from": "1",
        "split_to": "20",
        "fees": "0",
    }
    payload.update(kwargs)
    return api_client.post("/api/v1/transactions", payload, format="json")


def _seed_goog_split_scenario(api_client):
    _buy(api_client)
    _split(api_client)
    _price("GOOG", "2024-06-01", "107.45")
    _price("GOOG", "2024-07-15", "107.45")
    _price("GOOG", "2026-03-15", "107.45")


@pytest.mark.django_db
def test_summary_timeseries_goog_split_adjusted_value(api_client, legacy_seeded, today_patch):
    _seed_goog_split_scenario(api_client)
    data = api_client.get("/api/v1/portfolio/summary?include_timeseries=true").json()
    pt = next(p for p in data["timeseries"] if p["date"] == "2024-06-01")
    assert pt["portfolio_value"] == pytest.approx(2149.0, rel=1e-4)
    assert pt["portfolio_value"] != pytest.approx(107.45, rel=1e-4)
    assert data["current_value"] == pytest.approx(2149.0, rel=1e-4)
    assert data["total_invested"] == pytest.approx(2149.0, rel=1e-4)


@pytest.mark.django_db
def test_performance_value_goog_split_adjusted(api_client, legacy_seeded, today_patch):
    _seed_goog_split_scenario(api_client)
    pts = api_client.get(
        "/api/v1/portfolio/performance?metric=value&range=ALL"
    ).json()
    pt = next(p for p in pts if p["date"] == "2024-06-01")
    assert pt["value"] == pytest.approx(2149.0, rel=1e-4)


@pytest.mark.django_db
def test_cumulative_return_no_artificial_split_loss(api_client, legacy_seeded, today_patch):
    _seed_goog_split_scenario(api_client)
    pts = api_client.get(
        "/api/v1/portfolio/performance?metric=cumulative_return&range=ALL"
    ).json()
    by_date = {p["date"]: p for p in pts}
    assert by_date["2024-06-01"]["value"] == pytest.approx(0.0, abs=1e-4)
    split_day = by_date["2024-07-15"]["value"]
    assert split_day is not None
    assert split_day > -50.0


@pytest.mark.django_db
def test_twror_no_artificial_split_drop(api_client, legacy_seeded, today_patch):
    _seed_goog_split_scenario(api_client)
    pts = api_client.get(
        "/api/v1/portfolio/performance?metric=twror&range=ALL"
    ).json()
    split_pt = next(p for p in pts if p["date"] == "2024-07-15")
    assert split_pt["value"] is None or abs(split_pt["value"]) < 50.0


@pytest.mark.django_db
def test_split_does_not_adjust_post_split_buy(api_client, legacy_seeded, today_patch):
    api_client.post(
        "/api/v1/transactions",
        {
            "asset_symbol": "AAPL",
            "date": "2024-01-01",
            "type": "STOCK_SPLIT",
            "quantity": "0",
            "price_per_share": "0",
            "currency": "EUR",
            "split_from": "1",
            "split_to": "20",
            "fees": "0",
        },
        format="json",
    )
    api_client.post(
        "/api/v1/transactions",
        {
            "asset_symbol": "AAPL",
            "date": "2024-01-02",
            "type": "BUY",
            "quantity": "1",
            "price_per_share": "200",
            "currency": "EUR",
            "fees": "0",
        },
        format="json",
    )
    _price("AAPL", "2024-01-02", "200")
    data = api_client.get("/api/v1/portfolio/summary?include_timeseries=true").json()
    pt = next(p for p in data["timeseries"] if p["date"] == "2024-01-02")
    assert pt["portfolio_value"] == pytest.approx(200.0, rel=1e-4)
    holdings = api_client.get("/api/v1/portfolio/holdings").json()["holdings"][0]
    assert holdings["quantity"] == 1.0


@pytest.mark.django_db
def test_split_does_not_adjust_other_symbols(api_client, legacy_seeded, today_patch):
    api_client.post(
        "/api/v1/transactions",
        {
            "asset_symbol": "MSFT",
            "date": "2023-12-01",
            "type": "BUY",
            "quantity": "3",
            "price_per_share": "100",
            "currency": "EUR",
            "fees": "0",
        },
        format="json",
    )
    api_client.post(
        "/api/v1/transactions",
        {
            "asset_symbol": "AAPL",
            "date": "2023-12-01",
            "type": "BUY",
            "quantity": "1",
            "price_per_share": "200",
            "currency": "EUR",
            "fees": "0",
        },
        format="json",
    )
    api_client.post(
        "/api/v1/transactions",
        {
            "asset_symbol": "AAPL",
            "date": "2024-01-01",
            "type": "STOCK_SPLIT",
            "quantity": "0",
            "price_per_share": "0",
            "currency": "EUR",
            "split_from": "1",
            "split_to": "20",
            "fees": "0",
        },
        format="json",
    )
    _price("MSFT", "2023-12-01", "100")
    _price("AAPL", "2023-12-01", "10")
    data = api_client.get("/api/v1/portfolio/summary?include_timeseries=true").json()
    pt = next(p for p in data["timeseries"] if p["date"] == "2023-12-01")
    assert pt["portfolio_value"] == pytest.approx(500.0, rel=1e-4)


@pytest.mark.django_db
def test_split_valuation_missing_price_unchanged(api_client, legacy_seeded, today_patch):
    _buy(api_client)
    _split(api_client)
    data = api_client.get("/api/v1/portfolio/summary?include_timeseries=true").json()
    pt = next(p for p in data["timeseries"] if p["date"] == "2024-06-01")
    assert pt["portfolio_value"] in (None, 0.0)


@pytest.mark.django_db
def test_split_valuation_missing_fx_unchanged(api_client, legacy_seeded, today_patch):
    _buy(api_client, currency="EUR")
    _split(api_client)
    _price("GOOG", "2024-06-01", "107.45", currency="USD")
    ts = api_client.get(
        "/api/v1/portfolio/summary?display_currency=EUR"
    ).json()["timeseries"]
    pt = next(p for p in ts if p["date"] == "2024-06-01")
    assert pt["portfolio_value"] is None
    assert pt["fx_status"] == "fx_unavailable"


@pytest.mark.django_db
@patch("yfinance.Ticker")
def test_no_yfinance_on_summary_split_scenario(mock_ticker, api_client, legacy_seeded, today_patch):
    _seed_goog_split_scenario(api_client)
    r = api_client.get("/api/v1/portfolio/summary?include_timeseries=true")
    assert r.status_code == 200
    mock_ticker.assert_not_called()


@pytest.mark.django_db
@patch("yfinance.download")
def test_no_yfinance_on_performance_split_scenario(
    mock_dl, api_client, legacy_seeded, today_patch
):
    _seed_goog_split_scenario(api_client)
    api_client.get("/api/v1/portfolio/performance?metric=value&range=ALL")
    api_client.get("/api/v1/portfolio/performance?metric=cumulative_return&range=ALL")
    api_client.get("/api/v1/portfolio/performance?metric=twror&range=ALL")
    mock_dl.assert_not_called()
