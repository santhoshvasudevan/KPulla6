from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from fx.services import upsert_fx_rate
from market_data.models import AssetType, BenchmarkIndexConfig, HistoricalPrice
from portfolios.models import Portfolio
from portfolios.seed import ensure_default_portfolio

FIXED_TODAY = date(2026, 3, 15)


@pytest.fixture
def today_patch(monkeypatch):
    monkeypatch.setattr("portfolios.dates.current_date", lambda: FIXED_TODAY)
    return FIXED_TODAY


def _buy(api_client, **kwargs):
    payload = {
        "asset_symbol": "AAPL",
        "date": "2026-01-01",
        "type": "BUY",
        "quantity": "10",
        "price_per_share": "100",
        "currency": "EUR",
        "fees": "0",
    }
    payload.update(kwargs)
    return api_client.post("/api/v1/transactions", payload, format="json")


def _sell(api_client, **kwargs):
    payload = {
        "asset_symbol": "AAPL",
        "date": "2026-02-01",
        "type": "SELL",
        "quantity": "5",
        "price_per_share": "120",
        "currency": "EUR",
        "fees": "0",
    }
    payload.update(kwargs)
    return api_client.post("/api/v1/transactions", payload, format="json")


def _price(symbol: str, d: str, close: str, *, currency: str = "EUR", asset_type=AssetType.STOCK):
    HistoricalPrice.objects.create(
        asset_symbol=symbol,
        date=date.fromisoformat(d),
        close_price=Decimal(close),
        currency=currency,
        source="test",
        asset_type=asset_type,
    )


def _index_price(symbol: str, d: str, close: str, *, currency: str = "USD"):
    _price(symbol, d, close, currency=currency, asset_type=AssetType.INDEX)


def _asset_metrics_url(symbol: str, **params: str) -> str:
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    base = f"/api/v1/analytics/assets/{symbol}/performance-metrics"
    return f"{base}?{qs}" if qs else base


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


def _mf_buy(api_client, **kwargs):
    return api_client.post(
        "/api/v1/transactions",
        _mf_payload(type="BUY", **kwargs),
        format="json",
    )


def _mf_nav(scheme: str, d: str, close: str):
    HistoricalPrice.objects.create(
        asset_symbol=scheme,
        date=date.fromisoformat(d),
        close_price=Decimal(close),
        currency="INR",
        source="test",
        asset_type=AssetType.MUTUAL_FUND,
    )


@pytest.mark.django_db
def test_asset_metrics_basic_stock(api_client, seeded, today_patch):
    _buy(api_client)
    _price("AAPL", "2026-01-01", "100")
    _price("AAPL", "2026-01-02", "110")
    _price("AAPL", "2026-03-15", "120")
    r = api_client.get(_asset_metrics_url("AAPL", range="ALL"))
    assert r.status_code == 200
    data = r.json()
    assert data["subject"]["type"] == "asset"
    assert data["subject"]["asset_symbol"] == "AAPL"
    assert data["metrics"]["return"]["cumulative_return"] is not None
    assert data["metrics"]["return"]["xirr_scope"] == "full_scope"
    assert data["metrics"]["risk"]["volatility_annualized"] is not None or any(
        "Insufficient" in w for w in data["warnings"]
    )


@pytest.mark.django_db
def test_asset_buy_neutrality(api_client, seeded, today_patch):
    _buy(api_client, date="2026-01-01", quantity="1", price_per_share="100")
    _buy(api_client, date="2026-01-02", quantity="1", price_per_share="100")
    _price("AAPL", "2026-01-01", "100")
    _price("AAPL", "2026-01-02", "100")
    _price("AAPL", "2026-03-15", "100")
    data = api_client.get(_asset_metrics_url("AAPL", range="ALL")).json()
    twror = data["metrics"]["return"]["twror"]
    assert twror is not None
    assert abs(twror) < 0.05


@pytest.mark.django_db
def test_asset_sell_neutrality(api_client, seeded, today_patch):
    _buy(api_client, date="2026-01-01", quantity="10", price_per_share="100")
    _sell(api_client, date="2026-01-15", quantity="5", price_per_share="100")
    _price("AAPL", "2026-01-01", "100")
    _price("AAPL", "2026-01-15", "100")
    _price("AAPL", "2026-03-15", "100")
    data = api_client.get(_asset_metrics_url("AAPL", range="ALL")).json()
    cum = data["metrics"]["return"]["cumulative_return"]
    assert cum is not None
    assert abs(cum) < 0.05


@pytest.mark.django_db
def test_asset_stock_split_neutrality(api_client, seeded, today_patch):
    api_client.post(
        "/api/v1/transactions",
        {
            "asset_symbol": "AAPL",
            "date": "2026-01-01",
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
            "date": "2026-01-10",
            "type": "STOCK_SPLIT",
            "split_from": "1",
            "split_to": "20",
            "currency": "EUR",
        },
        format="json",
    )
    # Split-adjusted cached prices (yfinance Adj Close invariant); qty is split-adjusted too.
    _price("AAPL", "2026-01-01", "10")
    _price("AAPL", "2026-01-10", "10")
    _price("AAPL", "2026-03-15", "10")
    data = api_client.get(_asset_metrics_url("AAPL", range="ALL")).json()
    cum = data["metrics"]["return"]["cumulative_return"]
    assert cum is not None
    assert abs(cum) < 0.05


@pytest.mark.django_db
def test_asset_scoping_portfolio_id(api_client, seeded, today_patch, test_user):
    p1 = ensure_default_portfolio(test_user)
    p2 = Portfolio.objects.create(user=test_user, name="Scoped", base_currency="EUR", is_active=True)
    _buy(api_client, portfolio_id=p1.id, date="2026-01-01", quantity="10", price_per_share="100")
    _buy(api_client, portfolio_id=p2.id, date="2026-01-01", quantity="5", price_per_share="100")
    _price("AAPL", "2026-01-01", "100")
    _price("AAPL", "2026-03-15", "150")
    scoped = api_client.get(
        _asset_metrics_url("AAPL", range="ALL", portfolio_id=str(p2.id))
    ).json()
    all_data = api_client.get(
        _asset_metrics_url("AAPL", range="ALL", portfolio_scope="all")
    ).json()
    assert scoped["subject"]["portfolio_id"] == p2.id
    assert all_data["subject"]["portfolio_scope"] == "all"
    assert scoped["metrics"]["return"]["cumulative_return"] == pytest.approx(0.5, rel=1e-2)
    assert all_data["metrics"]["return"]["cumulative_return"] == pytest.approx(0.5, rel=1e-2)


@pytest.mark.django_db
def test_asset_missing_fx_warning(api_client, seeded, today_patch):
    _buy(api_client, date="2026-01-01", currency="EUR")
    _price("AAPL", "2026-01-01", "100", currency="USD")
    _price("AAPL", "2026-03-15", "100", currency="USD")
    data = api_client.get(_asset_metrics_url("AAPL", range="ALL")).json()
    assert any("FX" in w for w in data["warnings"])
    assert data["metrics"]["return"]["cumulative_return"] is None


@pytest.mark.django_db
def test_asset_missing_stock_price_warning(api_client, seeded, today_patch):
    _buy(api_client, date="2026-01-01")
    data = api_client.get(_asset_metrics_url("AAPL", range="ALL")).json()
    assert any("Cached prices are missing" in w for w in data["warnings"])


@pytest.mark.django_db
def test_asset_missing_mf_nav_warning(api_client, seeded, today_patch):
    _mf_buy(api_client, investment_date="2026-03-01", nav_date="2026-03-01")
    data = api_client.get(
        _asset_metrics_url(
            "120503",
            range="ALL",
            folio_number="FOLIO-12345",
        )
    ).json()
    assert any("No cached NAV is available" in w for w in data["warnings"])


@pytest.mark.django_db
def test_asset_mf_nav_no_warning_when_latest_nav_recent(api_client, seeded, today_patch):
    _mf_buy(api_client, investment_date="2026-03-01", nav_date="2026-03-01")
    _mf_nav("120503", "2026-03-13", "44.00")
    data = api_client.get(
        _asset_metrics_url(
            "120503",
            range="ALL",
            folio_number="FOLIO-12345",
        )
    ).json()
    assert not any("NAV" in w for w in data["warnings"])


@pytest.mark.django_db
def test_asset_mf_nav_stale_warning(api_client, seeded, today_patch):
    _mf_buy(api_client, investment_date="2026-03-01", nav_date="2026-03-01")
    _mf_nav("120503", "2026-03-01", "42.00")
    data = api_client.get(
        _asset_metrics_url(
            "120503",
            range="ALL",
            folio_number="FOLIO-12345",
        )
    ).json()
    assert any("Latest cached NAV is older than 5 days" in w for w in data["warnings"])


@pytest.mark.django_db
def test_asset_benchmark_metrics(api_client, seeded, today_patch):
    BenchmarkIndexConfig.objects.get_or_create(
        symbol="^GSPC",
        defaults={"display_name": "S&P 500", "enabled": True},
    )
    _buy(api_client)
    _price("AAPL", "2026-01-01", "100")
    _price("AAPL", "2026-01-02", "110")
    _price("AAPL", "2026-03-15", "120")
    _index_price("^GSPC", "2026-01-01", "1000")
    _index_price("^GSPC", "2026-01-02", "1010")
    _index_price("^GSPC", "2026-03-15", "1050")
    data = api_client.get(_asset_metrics_url("AAPL", range="ALL", benchmark="^GSPC")).json()
    assert data["benchmark"]["paired_count"] >= 2
    assert data["benchmark"]["metrics"]["beta"] is not None


@pytest.mark.django_db
def test_asset_unknown_symbol_404(api_client, seeded, today_patch):
    r = api_client.get(_asset_metrics_url("NOPE", range="ALL"))
    assert r.status_code == 404


@pytest.mark.django_db
def test_asset_mutual_fund_metrics(api_client, seeded, today_patch):
    _mf_buy(
        api_client,
        investment_date="2026-03-01",
        nav_date="2026-03-01",
    )
    for day in range(1, 16):
        _mf_nav("120503", f"2026-03-{day:02d}", str(42.50 + day * 0.1))
    r = api_client.get(
        _asset_metrics_url(
            "120503",
            range="ALL",
            folio_number="FOLIO-12345",
        )
    )
    assert r.status_code == 200
    data = r.json()
    assert data["subject"]["type"] == "asset"
    assert data["subject"]["folio_number"] == "FOLIO-12345"
    assert data["metrics"]["return"]["cumulative_return"] is not None


@pytest.mark.django_db
def test_asset_mf_multiple_folios_requires_folio_number(api_client, seeded, today_patch):
    _mf_buy(api_client, folio_number="FOLIO-A")
    _mf_buy(api_client, folio_number="FOLIO-B", investment_date="2026-03-11")
    r = api_client.get(_asset_metrics_url("120503", range="ALL"))
    assert r.status_code == 400


@pytest.mark.django_db
def test_asset_metrics_includes_periodic_returns_and_drawdown_periods(
    api_client, seeded, today_patch
):
    _buy(api_client)
    _price("AAPL", "2026-01-01", "100")
    _price("AAPL", "2026-01-02", "110")
    _price("AAPL", "2026-02-01", "105")
    _price("AAPL", "2026-03-15", "120")
    data = api_client.get(_asset_metrics_url("AAPL", range="ALL")).json()
    assert "periodic_returns" in data
    assert "drawdown_periods" in data
    assert isinstance(data["periodic_returns"]["monthly"], list)
    assert isinstance(data["drawdown_periods"]["worst"], list)
    assert "drawdown_series" in data
    series = data["drawdown_series"]
    assert isinstance(series, list)
    for pt in series:
        assert pt["drawdown"] <= 0
    for ep in data["drawdown_periods"]["worst"]:
        assert "rank" in ep


@pytest.mark.django_db
@patch("yfinance.Ticker")
def test_asset_metrics_no_yfinance_on_read(mock_ticker, api_client, seeded, today_patch):
    _buy(api_client)
    _price("AAPL", "2026-03-15", "100")
    r = api_client.get(_asset_metrics_url("AAPL", range="ALL"))
    assert r.status_code == 200
    mock_ticker.assert_not_called()
