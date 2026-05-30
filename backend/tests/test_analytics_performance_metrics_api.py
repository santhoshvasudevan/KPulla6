from __future__ import annotations

import ast
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest

from market_data.models import AssetType, BenchmarkIndexConfig, HistoricalPrice
from portfolios.models import Portfolio
from portfolios.seed import ensure_default_portfolio
from transactions.models import TransactionType

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


def _metrics_url(**params: str) -> str:
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    return f"/api/v1/analytics/performance-metrics?{qs}" if qs else "/api/v1/analytics/performance-metrics"


@pytest.mark.django_db
def test_analytics_basic_portfolio_metrics_fractions(api_client, seeded, today_patch):
    _buy(api_client)
    _price("AAPL", "2026-01-01", "100")
    _price("AAPL", "2026-01-02", "110")
    _price("AAPL", "2026-03-15", "120")
    r = api_client.get(_metrics_url(range="ALL"))
    assert r.status_code == 200
    data = r.json()
    assert data["subject"]["type"] == "portfolio"
    assert "metrics" in data
    ret = data["metrics"]["return"]
    assert ret["cumulative_return"] is not None
    assert ret["xirr_scope"] == "full_scope"
    assert -1.0 < ret["cumulative_return"] < 5.0
    assert data["metrics"]["risk"]["sharpe_ratio"] is not None or any(
        "Insufficient" in w for w in data["warnings"]
    )


def test_analytics_service_uses_public_xirr_helper():
    """Analytics must not import private _compute_scope_xirr from summary_service."""
    services_path = (
        Path(__file__).resolve().parents[1] / "analytics" / "services.py"
    )
    tree = ast.parse(services_path.read_text(encoding="utf-8"))
    imported_private: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "portfolios.summary_service":
            for alias in node.names:
                if alias.name == "_compute_scope_xirr":
                    imported_private.append(alias.name)
    assert imported_private == []
    source = services_path.read_text(encoding="utf-8")
    assert "compute_scope_xirr" in source
    assert "_compute_scope_xirr" not in source


@pytest.mark.django_db
def test_analytics_xirr_scope_full_scope_even_for_range_slice(api_client, seeded, today_patch):
    _buy(api_client, date="2026-01-01")
    _price("AAPL", "2026-01-01", "100")
    _price("AAPL", "2026-01-15", "105")
    _price("AAPL", "2026-03-15", "130")
    data = api_client.get(_metrics_url(range="30D")).json()
    assert data["range"]["code"] == "30D"
    assert data["metrics"]["return"]["xirr_scope"] == "full_scope"


@pytest.mark.django_db
def test_analytics_buy_contribution_neutrality(api_client, seeded, today_patch):
    _buy(api_client, date="2026-01-01", quantity="1", price_per_share="100")
    _buy(api_client, date="2026-01-02", quantity="1", price_per_share="100")
    _price("AAPL", "2026-01-01", "100")
    _price("AAPL", "2026-01-02", "100")
    data = api_client.get(_metrics_url(range="ALL")).json()
    twror = data["metrics"]["return"]["twror"]
    assert twror is not None
    assert abs(twror) < 0.05


@pytest.mark.django_db
def test_analytics_range_all_and_30d(api_client, seeded, today_patch):
    _buy(api_client, date="2026-01-01")
    _price("AAPL", "2026-01-01", "100")
    _price("AAPL", "2026-01-15", "105")
    _price("AAPL", "2026-03-15", "130")
    r_all = api_client.get(_metrics_url(range="ALL"))
    r_30d = api_client.get(_metrics_url(range="30D"))
    assert r_all.status_code == 200
    assert r_30d.status_code == 200
    assert r_all.json()["range"]["code"] == "ALL"
    assert r_30d.json()["range"]["code"] == "30D"
    assert r_30d.json()["range"]["start"] >= "2026-02-13"


@pytest.mark.django_db
def test_analytics_benchmark_metrics(api_client, seeded, today_patch):
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
    r = api_client.get(_metrics_url(range="ALL", benchmark="^GSPC"))
    assert r.status_code == 200
    data = r.json()
    assert "benchmark" in data
    assert data["benchmark"]["paired_count"] >= 2
    assert data["benchmark"]["metrics"] is not None
    assert data["benchmark"]["metrics"]["beta"] is not None


@pytest.mark.django_db
def test_analytics_unknown_benchmark_422(api_client, seeded, today_patch):
    _buy(api_client)
    _price("AAPL", "2026-03-15", "100")
    r = api_client.get(_metrics_url(benchmark="NOPE"))
    assert r.status_code == 422


@pytest.mark.django_db
def test_analytics_benchmark_missing_prices_warning(api_client, seeded, today_patch):
    BenchmarkIndexConfig.objects.get_or_create(
        symbol="^GSPC",
        defaults={"display_name": "S&P 500", "enabled": True},
    )
    _buy(api_client)
    _price("AAPL", "2026-03-15", "100")
    r = api_client.get(_metrics_url(range="ALL", benchmark="^GSPC"))
    assert r.status_code == 200
    data = r.json()
    assert data["benchmark"]["metrics"] is None
    assert any("Benchmark" in w for w in data["warnings"])


@pytest.mark.django_db
@patch("yfinance.Ticker")
def test_analytics_no_yfinance_on_read(mock_ticker, api_client, seeded, today_patch):
    _buy(api_client)
    _price("AAPL", "2026-03-15", "100")
    r = api_client.get(_metrics_url(range="ALL"))
    assert r.status_code == 200
    mock_ticker.assert_not_called()


@pytest.mark.django_db
def test_analytics_scope_all(api_client, seeded, today_patch):
    p1 = ensure_default_portfolio()
    p2 = Portfolio.objects.create(name="P2", base_currency="EUR", is_active=True)
    _buy(api_client, asset_symbol="AAA", portfolio_id=p1.id)
    _buy(api_client, asset_symbol="BBB", portfolio_id=p2.id)
    _price("AAA", "2026-03-15", "10")
    _price("BBB", "2026-03-15", "20")
    r = api_client.get(_metrics_url(portfolio_scope="all", range="ALL"))
    assert r.status_code == 200
    assert r.json()["subject"]["portfolio_scope"] == "all"


@pytest.mark.django_db
def test_analytics_portfolio_id_filter(api_client, seeded, today_patch):
    p1 = ensure_default_portfolio()
    p2 = Portfolio.objects.create(name="Scoped", base_currency="EUR", is_active=True)
    _buy(api_client, asset_symbol="AAA", portfolio_id=p1.id)
    _buy(api_client, asset_symbol="BBB", portfolio_id=p2.id)
    _price("AAA", "2026-03-15", "10")
    _price("BBB", "2026-03-15", "20")
    r = api_client.get(_metrics_url(range="ALL", portfolio_id=str(p2.id)))
    assert r.status_code == 200
    assert r.json()["subject"]["portfolio_id"] == p2.id


@pytest.mark.django_db
def test_analytics_scope_all_and_portfolio_id_422(api_client, seeded):
    p = ensure_default_portfolio()
    r = api_client.get(
        _metrics_url(portfolio_scope="all", portfolio_id=str(p.id))
    )
    assert r.status_code == 422


@pytest.mark.django_db
def test_analytics_portfolio_includes_periodic_returns_and_drawdown_periods(
    api_client, seeded, today_patch
):
    _buy(api_client)
    _price("AAPL", "2026-01-01", "100")
    _price("AAPL", "2026-01-02", "110")
    _price("AAPL", "2026-02-01", "105")
    _price("AAPL", "2026-03-15", "120")
    data = api_client.get(_metrics_url(range="ALL")).json()
    assert "periodic_returns" in data
    assert "drawdown_periods" in data
    monthly = data["periodic_returns"]["monthly"]
    yearly = data["periodic_returns"]["yearly"]
    assert isinstance(monthly, list)
    assert isinstance(yearly, list)
    if monthly:
        row = monthly[0]
        assert "period" in row
        assert "return" in row
        assert isinstance(row["return"], (int, float))
    worst = data["drawdown_periods"]["worst"]
    assert isinstance(worst, list)
    for ep in worst:
        assert "start_date" in ep
        assert "trough_date" in ep
        assert "drawdown" in ep
        assert "recovered" in ep


@pytest.mark.django_db
def test_analytics_portfolio_empty_data_returns_empty_periodic_and_drawdown_blocks(
    api_client, seeded, today_patch
):
    data = api_client.get(_metrics_url(range="ALL")).json()
    assert data["periodic_returns"] == {"monthly": [], "yearly": []}
    assert data["drawdown_periods"] == {"worst": []}
