"""
Regression tests: Metric Sheet analytics × stock splits × cached price history.

Invariant: split-adjusted FIFO quantities (build_split_adjusted_lot_snapshots) require
split-adjusted HistoricalPrice rows (yfinance Adj Close). Raw nominal pre-split prices
produce false value spikes and returns; analytics warns when detected.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

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


def _seed_adjusted_price_split_scenario(api_client):
    """Scenario A: yfinance-style split-adjusted price history (Adj Close constant)."""
    _buy(api_client)
    _split(api_client)
    _price("GOOG", "2024-06-01", "107.45")
    _price("GOOG", "2024-07-15", "107.45")
    _price("GOOG", "2026-03-15", "107.45")


def _seed_raw_nominal_price_split_scenario(api_client):
    """Scenario B: raw nominal pre-split price + post-split price (unsupported)."""
    api_client.post(
        "/api/v1/transactions",
        {
            "asset_symbol": "RAW",
            "date": "2026-01-01",
            "type": "BUY",
            "quantity": "1",
            "price_per_share": "100",
            "currency": "EUR",
            "fees": "0",
        },
        format="json",
    )
    api_client.post(
        "/api/v1/transactions",
        {
            "asset_symbol": "RAW",
            "date": "2026-01-10",
            "type": "STOCK_SPLIT",
            "split_from": "1",
            "split_to": "10",
            "currency": "EUR",
        },
        format="json",
    )
    _price("RAW", "2026-01-01", "100")
    _price("RAW", "2026-01-10", "10")
    _price("RAW", "2026-03-15", "10")


@pytest.mark.django_db
def test_asset_metrics_adjusted_prices_stable_around_split(api_client, seeded, today_patch):
    _seed_adjusted_price_split_scenario(api_client)
    data = api_client.get(
        "/api/v1/analytics/assets/GOOG/performance-metrics?range=ALL"
    ).json()
    ret = data["metrics"]["return"]
    assert ret["cumulative_return"] is not None
    assert abs(ret["cumulative_return"]) < 0.05
    assert ret["twror"] is None or abs(ret["twror"]) < 0.05
    assert not any("split-adjusted" in w.lower() for w in data["warnings"])


@pytest.mark.django_db
def test_portfolio_metrics_adjusted_prices_stable_around_split(api_client, seeded, today_patch):
    _seed_adjusted_price_split_scenario(api_client)
    data = api_client.get("/api/v1/analytics/performance-metrics?range=ALL").json()
    ret = data["metrics"]["return"]
    assert ret["cumulative_return"] is not None
    assert abs(ret["cumulative_return"]) < 0.05
    assert not any("split-adjusted" in w.lower() for w in data["warnings"])


@pytest.mark.django_db
def test_asset_metrics_raw_nominal_prices_warn(api_client, seeded, today_patch):
    _seed_raw_nominal_price_split_scenario(api_client)
    data = api_client.get(
        "/api/v1/analytics/assets/RAW/performance-metrics?range=ALL"
    ).json()
    assert any("split-adjusted" in w.lower() for w in data["warnings"])
    ret = data["metrics"]["return"]
    assert ret["cumulative_return"] is not None
    # Economic cumulative return can look flat when contributions track the split-distorted
    # terminal value; TWROR from daily returns still exposes the bad price history.
    assert ret["twror"] is not None
    assert ret["twror"] < -0.5


@pytest.mark.django_db
def test_portfolio_metrics_raw_nominal_prices_warn(api_client, seeded, today_patch):
    _seed_raw_nominal_price_split_scenario(api_client)
    data = api_client.get("/api/v1/analytics/performance-metrics?range=ALL").json()
    assert any("split-adjusted" in w.lower() for w in data["warnings"])


@pytest.mark.django_db
def test_asset_metrics_split_no_external_flow_neutral_twror(api_client, seeded, today_patch):
    _seed_adjusted_price_split_scenario(api_client)
    data = api_client.get(
        "/api/v1/analytics/assets/GOOG/performance-metrics?range=ALL"
    ).json()
    twror = data["metrics"]["return"]["twror"]
    assert twror is None or abs(twror) < 0.05


@pytest.mark.django_db
def test_asset_metrics_split_day_daily_returns_near_zero(api_client, seeded, today_patch):
    _seed_adjusted_price_split_scenario(api_client)
    data = api_client.get(
        "/api/v1/analytics/assets/GOOG/performance-metrics?range=ALL"
    ).json()
    periods = data["metrics"]["periods"]
    assert periods["best_day"] is not None
    assert abs(periods["best_day"]) < 0.05
    assert periods["worst_day"] is not None
    assert abs(periods["worst_day"]) < 0.05
