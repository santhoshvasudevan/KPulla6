from __future__ import annotations

import ast
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest

from fx.services import upsert_fx_rate
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


def _sell(api_client, **kwargs):
    payload = {
        "asset_symbol": "AAPL",
        "date": "2026-01-02",
        "type": "SELL",
        "quantity": "1",
        "price_per_share": "100",
        "currency": "EUR",
        "fees": "0",
    }
    payload.update(kwargs)
    return api_client.post("/api/v1/transactions", payload, format="json")


def _last_performance_fraction(api_client, *, metric: str, range_code: str) -> float | None:
    pts = api_client.get(
        f"/api/v1/portfolio/performance?metric={metric}&range={range_code}"
    ).json()
    if not pts:
        return None
    last = pts[-1]["value"]
    return None if last is None else last / 100.0


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
def test_analytics_scope_all_pln_stock_uses_display_currency_series(
    api_client, seeded, monkeypatch
):
    """Metric Sheet all-scope must not use pooled INR-base value/flow path."""
    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2024, 4, 15))
    eur_portfolio = Portfolio.objects.create(
        name="EUR PLN Analytics", base_currency="EUR", is_active=True
    )
    inr_portfolio = Portfolio.objects.create(
        name="INR MF Analytics", base_currency="INR", is_active=True
    )
    _buy(
        api_client,
        portfolio_id=eur_portfolio.id,
        asset_symbol="PLNAN",
        date="2024-04-01",
        quantity="10",
        price_per_share="100",
        currency="EUR",
    )
    api_client.post(
        "/api/v1/transactions",
        {
            "asset_type": "MUTUAL_FUND",
            "scheme_code": "120503",
            "scheme_name": "Test Fund",
            "folio_number": "AN-FOLIO",
            "type": "BUY",
            "investment_date": "2024-04-01",
            "nav_date": "2024-04-01",
            "nav": "50.00",
            "units_allotted": "100.00000000",
            "paid_value": "5000.00",
            "market_value": "5000.00",
            "portfolio_id": inr_portfolio.id,
        },
        format="json",
    )
    _price("PLNAN", "2024-04-01", "100", currency="PLN")
    _price("PLNAN", "2024-04-15", "110", currency="PLN")
    HistoricalPrice.objects.create(
        asset_symbol="120503",
        date=date(2024, 4, 1),
        close_price=Decimal("50.00"),
        currency="INR",
        source="test",
        asset_type=AssetType.MUTUAL_FUND,
    )
    HistoricalPrice.objects.create(
        asset_symbol="120503",
        date=date(2024, 4, 15),
        close_price=Decimal("55.00"),
        currency="INR",
        source="test",
        asset_type=AssetType.MUTUAL_FUND,
    )
    for day in range(1, 16):
        d = date(2024, 4, day)
        upsert_fx_rate(from_currency="PLN", to_currency="EUR", row_date=d, rate=Decimal("0.23"))
        upsert_fx_rate(from_currency="INR", to_currency="EUR", row_date=d, rate=Decimal("0.011"))

    r = api_client.get(
        _metrics_url(portfolio_scope="all", display_currency="EUR", range="ALL")
    )
    assert r.status_code == 200
    data = r.json()
    assert data["currency"] == "EUR"
    assert data["metrics"]["return"]["cumulative_return"] is not None
    assert not any("Insufficient daily returns" in w for w in data["warnings"])


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
        assert "rank" in ep
        assert "start_date" in ep
        assert "trough_date" in ep
        assert "drawdown" in ep
        assert "recovered" in ep
    if len(worst) >= 2:
        assert worst[0]["rank"] == 1
        assert worst[0]["drawdown"] <= worst[1]["drawdown"]


@pytest.mark.django_db
def test_analytics_portfolio_includes_drawdown_series(
    api_client, seeded, today_patch
):
    _buy(api_client)
    _price("AAPL", "2026-01-01", "100")
    _price("AAPL", "2026-01-02", "110")
    _price("AAPL", "2026-02-01", "105")
    _price("AAPL", "2026-03-15", "120")
    data = api_client.get(_metrics_url(range="ALL")).json()
    assert "drawdown_series" in data
    series = data["drawdown_series"]
    assert isinstance(series, list)
    assert len(series) >= 1
    for pt in series:
        assert "date" in pt
        assert "drawdown" in pt
        assert isinstance(pt["drawdown"], (int, float))
        assert pt["drawdown"] <= 0


@pytest.mark.django_db
def test_analytics_portfolio_yearly_returns_are_calendar_year_twror_compounded(
    api_client, seeded, today_patch
):
    _buy(api_client, date="2026-01-01", quantity="10", price_per_share="100")
    _buy(api_client, date="2026-02-01", quantity="10", price_per_share="150")
    _price("AAPL", "2026-01-01", "100")
    _price("AAPL", "2026-02-01", "150")
    _price("AAPL", "2026-03-15", "120")
    data = api_client.get(_metrics_url(range="ALL")).json()
    yearly = data["periodic_returns"]["yearly"]
    assert isinstance(yearly, list)
    if yearly:
        row = yearly[0]
        assert "period" in row
        assert "return" in row
        assert isinstance(row["return"], (int, float))


@pytest.mark.django_db
def test_analytics_portfolio_empty_data_returns_empty_periodic_and_drawdown_blocks(
    api_client, seeded, today_patch
):
    data = api_client.get(_metrics_url(range="ALL")).json()
    assert data["periodic_returns"] == {"monthly": [], "yearly": []}
    assert data["drawdown_periods"] == {"worst": []}
    assert data["drawdown_series"] == []


@pytest.mark.django_db
def test_metric_sheet_cumulative_return_matches_performance_api(api_client, seeded, today_patch):
    """Metric Sheet cumulative return must match performance chart terminal point."""
    _buy(api_client, date="2026-01-01", quantity="10", price_per_share="100")
    _buy(api_client, date="2026-02-01", quantity="10", price_per_share="150")
    _price("AAPL", "2026-01-01", "100")
    _price("AAPL", "2026-02-01", "150")
    _price("AAPL", "2026-03-15", "120")

    perf_cum = _last_performance_fraction(
        api_client, metric="cumulative_return", range_code="ALL"
    )
    metrics = api_client.get(_metrics_url(range="ALL")).json()["metrics"]["return"]
    assert perf_cum is not None
    assert metrics["cumulative_return"] == pytest.approx(perf_cum, rel=1e-6)


@pytest.mark.django_db
def test_metric_sheet_cumulative_return_differs_from_twror_with_staggered_buys(
    api_client, seeded, today_patch
):
    """Regression: Metric Sheet must not reuse TWROR for cumulative return or CAGR."""
    _buy(api_client, date="2026-01-01", quantity="10", price_per_share="100")
    _buy(api_client, date="2026-02-01", quantity="10", price_per_share="150")
    _price("AAPL", "2026-01-01", "100")
    _price("AAPL", "2026-02-01", "150")
    _price("AAPL", "2026-03-15", "120")

    perf_cum = _last_performance_fraction(
        api_client, metric="cumulative_return", range_code="ALL"
    )
    perf_twror = _last_performance_fraction(api_client, metric="twror", range_code="ALL")
    ret = api_client.get(_metrics_url(range="ALL")).json()["metrics"]["return"]

    assert perf_cum is not None and perf_twror is not None
    assert perf_cum != pytest.approx(perf_twror, abs=0.001)
    assert ret["cumulative_return"] == pytest.approx(perf_cum, rel=1e-6)
    assert ret["twror"] == pytest.approx(perf_twror, rel=1e-6)
    assert ret["cumulative_return"] != pytest.approx(ret["twror"], abs=0.001)
    assert ret["cagr"] is not None
    assert ret["cagr"] != pytest.approx(ret["twror"], abs=0.001)
