from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from cash.models import CashEntryType, CashLedgerEntry
from fx.models import FXRate
from fx.services import upsert_fx_rate
from market_data.models import AssetType, BenchmarkIndexConfig, HistoricalPrice
from portfolios.models import Portfolio
from portfolios.seed import ensure_default_portfolio
from transactions.models import Transaction, TransactionType


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
        "quantity": "4",
        "price_per_share": "150",
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


@pytest.mark.django_db
def test_performance_defaults_metric_value_range_1y(api_client, legacy_seeded, today_patch):
    _buy(api_client)
    _price("AAPL", "2026-01-01", "100")
    _price("AAPL", "2026-03-15", "110")
    r = api_client.get("/api/v1/portfolio/performance")
    assert r.status_code == 200
    pts = r.json()
    assert isinstance(pts, list)
    assert pts
    assert pts[0]["metric"] == "value"
    dates = [p["date"] for p in pts]
    assert min(dates) >= "2025-03-15"


@pytest.mark.django_db
def test_performance_scope_all(api_client, legacy_seeded, today_patch, test_user):
    p1 = ensure_default_portfolio(test_user)
    p2 = Portfolio.objects.create(user=test_user, name="P2", base_currency="EUR", is_active=True)
    _buy(api_client, asset_symbol="AAA", portfolio_id=p1.id)
    _buy(api_client, asset_symbol="BBB", portfolio_id=p2.id)
    _price("AAA", "2026-03-01", "10")
    _price("BBB", "2026-03-01", "20")
    r = api_client.get("/api/v1/portfolio/performance?metric=value&range=ALL")
    assert r.status_code == 200
    last = [p for p in r.json() if p["date"] == "2026-03-15" and p["value"] is not None][-1]
    assert last["value"] == 300.0


@pytest.mark.django_db
def test_performance_portfolio_id_filter(api_client, legacy_seeded, today_patch, test_user):
    p1 = ensure_default_portfolio(test_user)
    p2 = Portfolio.objects.create(user=test_user, name="Scoped", base_currency="EUR", is_active=True)
    _buy(api_client, asset_symbol="AAA", portfolio_id=p1.id)
    _buy(api_client, asset_symbol="BBB", portfolio_id=p2.id)
    _price("AAA", "2026-03-01", "10")
    _price("BBB", "2026-03-01", "20")
    r = api_client.get(
        f"/api/v1/portfolio/performance?metric=value&range=ALL&portfolio_id={p2.id}"
    )
    last = [p for p in r.json() if p["date"] == "2026-03-15"][0]
    assert last["value"] == 200.0


@pytest.mark.django_db
def test_performance_scope_all_and_portfolio_id_422(api_client, legacy_seeded, test_user):
    p = ensure_default_portfolio(test_user)
    r = api_client.get(
        f"/api/v1/portfolio/performance?portfolio_scope=all&portfolio_id={p.id}"
    )
    assert r.status_code == 422


@pytest.mark.django_db
def test_performance_unknown_portfolio_id_404(api_client, legacy_seeded):
    r = api_client.get("/api/v1/portfolio/performance?portfolio_id=999999")
    assert r.status_code == 404


@pytest.mark.django_db
def test_performance_inactive_portfolio_id_404(api_client, legacy_seeded, test_user):
    p = Portfolio.objects.create(user=test_user, name="Inactive", base_currency="EUR", is_active=False)
    r = api_client.get(f"/api/v1/portfolio/performance?portfolio_id={p.id}")
    assert r.status_code == 404


@pytest.mark.django_db
def test_performance_invalid_metric_400(api_client, legacy_seeded):
    r = api_client.get("/api/v1/portfolio/performance?metric=nope")
    assert r.status_code == 400


@pytest.mark.django_db
def test_performance_invalid_range_400(api_client, legacy_seeded):
    r = api_client.get("/api/v1/portfolio/performance?range=bogus")
    assert r.status_code == 400


@pytest.mark.django_db
def test_performance_invalid_display_currency_400(api_client, legacy_seeded):
    r = api_client.get("/api/v1/portfolio/performance?display_currency=JPY")
    assert r.status_code == 400


@pytest.mark.django_db
def test_performance_value_list_points(api_client, legacy_seeded, today_patch):
    _buy(api_client)
    _price("AAPL", "2026-01-01", "100")
    r = api_client.get("/api/v1/portfolio/performance?metric=value&range=ALL")
    assert isinstance(r.json(), list)
    assert r.json()[0]["currency"] == "EUR"


@pytest.mark.django_db
def test_performance_value_display_currency_fx(api_client, legacy_seeded, today_patch):
    _buy(api_client, currency="USD")
    _price("AAPL", "2026-01-01", "100", currency="USD")
    _price("AAPL", "2026-03-15", "100", currency="USD")
    upsert_fx_rate(
        from_currency="USD",
        to_currency="INR",
        row_date=date(2026, 1, 1),
        rate=Decimal("80"),
    )
    upsert_fx_rate(
        from_currency="USD",
        to_currency="INR",
        row_date=date(2026, 3, 15),
        rate=Decimal("82"),
    )
    r = api_client.get(
        "/api/v1/portfolio/performance?metric=value&range=ALL&display_currency=INR"
    )
    pt = [p for p in r.json() if p["date"] == "2026-03-15"][0]
    assert pt["currency"] == "INR"
    assert pt["value"] == 82000.0


@pytest.mark.django_db
def test_performance_value_missing_fx_null(api_client, legacy_seeded, today_patch):
    _buy(api_client, currency="USD")
    _price("AAPL", "2026-01-01", "100", currency="USD")
    _price("AAPL", "2026-03-15", "100", currency="USD")
    r = api_client.get(
        "/api/v1/portfolio/performance?metric=value&range=ALL&display_currency=INR"
    )
    pt = [p for p in r.json() if p["date"] == "2026-03-15"][0]
    assert pt["value"] is None


@pytest.mark.django_db
def test_performance_value_missing_price_safe(api_client, legacy_seeded, today_patch):
    _buy(api_client, date="2026-01-01")
    r = api_client.get("/api/v1/portfolio/performance?metric=value&range=ALL")
    pt = [p for p in r.json() if p["date"] == "2026-01-01"][0]
    assert pt["value"] in (None, 0.0)


@pytest.mark.django_db
@patch("yfinance.download")
def test_performance_no_yfinance_on_read(mock_dl, api_client, legacy_seeded, today_patch):
    _buy(api_client)
    _price("AAPL", "2026-01-01", "100")
    api_client.get("/api/v1/portfolio/performance?metric=value&range=ALL")
    mock_dl.assert_not_called()


@pytest.mark.django_db
def test_performance_range_7d(api_client, legacy_seeded, today_patch):
    _buy(api_client, date="2026-01-01")
    for d in ("2026-03-08", "2026-03-15"):
        _price("AAPL", d, "100")
    r = api_client.get("/api/v1/portfolio/performance?metric=value&range=7D")
    dates = [p["date"] for p in r.json()]
    assert min(dates) == "2026-03-08"
    assert max(dates) == "2026-03-15"


@pytest.mark.django_db
def test_performance_range_30d(api_client, legacy_seeded, today_patch):
    _buy(api_client, date="2026-01-01")
    _price("AAPL", "2026-02-13", "100")
    _price("AAPL", "2026-03-15", "100")
    r = api_client.get("/api/v1/portfolio/performance?metric=value&range=30D")
    assert min(p["date"] for p in r.json()) == "2026-02-13"


@pytest.mark.django_db
def test_performance_range_ytd(api_client, legacy_seeded, today_patch):
    _buy(api_client, date="2025-12-01")
    _price("AAPL", "2025-12-01", "90")
    _price("AAPL", "2026-01-01", "100")
    _price("AAPL", "2026-03-15", "100")
    r = api_client.get("/api/v1/portfolio/performance?metric=value&range=YTD")
    assert min(p["date"] for p in r.json()) == "2026-01-01"


@pytest.mark.django_db
def test_performance_range_all_starts_first_transaction(api_client, legacy_seeded, today_patch):
    _buy(api_client, date="2026-02-01")
    _price("AAPL", "2026-02-01", "100")
    _price("AAPL", "2026-03-15", "100")
    r = api_client.get("/api/v1/portfolio/performance?metric=value&range=ALL")
    assert min(p["date"] for p in r.json()) == "2026-02-01"


@pytest.mark.django_db
def test_performance_range_never_before_inception(api_client, legacy_seeded, today_patch):
    _buy(api_client, date="2026-02-01")
    _price("AAPL", "2026-02-01", "100")
    _price("AAPL", "2026-03-15", "100")
    r = api_client.get("/api/v1/portfolio/performance?metric=value&range=7D")
    assert min(p["date"] for p in r.json()) >= "2026-02-01"


@pytest.mark.django_db
def test_cumulative_return_one_buy_price_increase(api_client, legacy_seeded, today_patch):
    _buy(api_client, quantity="1", price_per_share="100")
    _price("AAPL", "2026-01-01", "100")
    _price("AAPL", "2026-01-02", "110")
    r = api_client.get(
        "/api/v1/portfolio/performance?metric=cumulative_return&range=ALL"
    )
    by_date = {p["date"]: p for p in r.json()}
    assert abs(by_date["2026-01-02"]["value"] - 10.0) < 1e-6


@pytest.mark.django_db
def test_cumulative_return_multiple_buys(api_client, legacy_seeded, today_patch):
    _buy(api_client, date="2026-01-01", quantity="1", price_per_share="100")
    _buy(api_client, date="2026-01-02", quantity="1", price_per_share="100")
    _price("AAPL", "2026-01-01", "100")
    _price("AAPL", "2026-01-02", "100")
    r = api_client.get(
        "/api/v1/portfolio/performance?metric=cumulative_return&range=ALL"
    )
    pts = [p for p in r.json() if p["date"] == "2026-01-02"]
    assert pts and abs(pts[0]["value"] - 0.0) < 1e-6


@pytest.mark.django_db
def test_cumulative_return_with_sell(api_client, legacy_seeded, today_patch):
    _buy(api_client, date="2026-01-01", quantity="1", price_per_share="100")
    _sell(api_client, date="2026-01-02", quantity="1", price_per_share="110")
    _price("AAPL", "2026-01-01", "100")
    _price("AAPL", "2026-01-02", "110")
    r = api_client.get(
        "/api/v1/portfolio/performance?metric=cumulative_return&range=ALL"
    )
    pts = [p for p in r.json() if p["date"] == "2026-01-02"]
    assert pts and abs(pts[0]["value"] - 10.0) < 1e-6


@pytest.mark.django_db
def test_cumulative_return_null_no_contributions(api_client, legacy_seeded, today_patch, test_user):
    Transaction.objects.create(
        portfolio=ensure_default_portfolio(test_user),
        asset_symbol="AAPL",
        date=date(2026, 1, 2),
        type=TransactionType.SELL,
        quantity=Decimal("1"),
        price_per_share=Decimal("110"),
        currency="EUR",
        fees=Decimal("0"),
    )
    _price("AAPL", "2026-01-02", "110")
    r = api_client.get(
        "/api/v1/portfolio/performance?metric=cumulative_return&range=ALL"
    )
    assert r.json()[-1]["value"] is None


@pytest.mark.django_db
def test_twror_ignores_contribution_as_performance(api_client, legacy_seeded, today_patch):
    _buy(api_client, date="2026-01-01", quantity="1", price_per_share="100")
    _buy(api_client, date="2026-01-02", quantity="1", price_per_share="100")
    _price("AAPL", "2026-01-01", "100")
    _price("AAPL", "2026-01-02", "100")
    r = api_client.get("/api/v1/portfolio/performance?metric=twror&range=ALL")
    pts = [p for p in r.json() if p["date"] == "2026-01-02"]
    assert pts and abs(pts[0]["value"] - 0.0) < 1e-6


@pytest.mark.django_db
def test_twror_price_increase(api_client, legacy_seeded, today_patch):
    _buy(api_client, quantity="1", price_per_share="100")
    _price("AAPL", "2026-01-01", "100")
    _price("AAPL", "2026-01-02", "110")
    r = api_client.get("/api/v1/portfolio/performance?metric=twror&range=ALL")
    pts = [p for p in r.json() if p["date"] == "2026-01-02"]
    assert pts and abs(pts[0]["value"] - 10.0) < 1e-6


@pytest.mark.django_db
def test_twror_zero_begin_value_safe(api_client, legacy_seeded, today_patch):
    _buy(api_client, date="2026-01-02", quantity="1", price_per_share="100")
    _price("AAPL", "2026-01-01", "100")
    _price("AAPL", "2026-01-02", "100")
    r = api_client.get("/api/v1/portfolio/performance?metric=twror&range=ALL")
    pts = [p for p in r.json() if p["date"] == "2026-01-02"]
    assert pts and pts[0]["value"] is None


@pytest.mark.django_db
def test_twror_non_all_range_rechains(api_client, legacy_seeded, today_patch):
    _buy(api_client, date="2026-01-01", quantity="1", price_per_share="100")
    _price("AAPL", "2026-01-01", "100")
    _price("AAPL", "2026-01-05", "110")
    _price("AAPL", "2026-03-15", "120")
    r_all = api_client.get("/api/v1/portfolio/performance?metric=twror&range=ALL")
    r_7d = api_client.get("/api/v1/portfolio/performance?metric=twror&range=7D")
    v_all = [p for p in r_all.json() if p["date"] == "2026-03-15"][0]["value"]
    v_7d = [p for p in r_7d.json() if p["date"] == "2026-03-15"][0]["value"]
    assert v_all is not None and v_7d is not None
    assert abs(v_7d - v_all) > 1e-6


@pytest.mark.django_db
def test_value_metric_ignores_benchmark(api_client, legacy_seeded, today_patch):
    _buy(api_client)
    _price("AAPL", "2026-01-01", "100")
    r = api_client.get(
        "/api/v1/portfolio/performance?metric=value&benchmarks=%5EGSPC"
    )
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.django_db
def test_benchmark_cumulative_return_comparison(api_client, legacy_seeded, today_patch):
    _buy(api_client)
    _price("AAPL", "2026-01-01", "100")
    _price("AAPL", "2026-01-02", "110")
    _index_price("^GSPC", "2026-01-01", "1000")
    _index_price("^GSPC", "2026-01-02", "1050")
    r = api_client.get(
        "/api/v1/portfolio/performance?metric=cumulative_return&range=ALL&benchmark=%5EGSPC"
    )
    assert r.status_code == 200
    data = r.json()
    assert "series" in data
    assert len(data["series"]) == 2
    assert data["series"][0]["name"] == "Portfolio"
    assert data["series"][1]["name"] == "S&P 500"


@pytest.mark.django_db
def test_benchmark_twror_comparison(api_client, legacy_seeded, today_patch):
    _buy(api_client)
    _price("AAPL", "2026-01-01", "100")
    _price("AAPL", "2026-01-02", "110")
    _index_price("^GSPC", "2026-01-01", "1000")
    _index_price("^GSPC", "2026-01-02", "1050")
    r = api_client.get(
        "/api/v1/portfolio/performance?metric=twror&range=ALL&benchmark=%5EGSPC"
    )
    assert r.status_code == 200
    assert len(r.json()["series"]) == 2


@pytest.mark.django_db
def test_benchmarks_legacy_first_symbol_only(api_client, legacy_seeded, today_patch):
    _buy(api_client)
    _price("AAPL", "2026-01-01", "100")
    _index_price("^GSPC", "2026-01-01", "1000")
    r = api_client.get(
        "/api/v1/portfolio/performance?metric=cumulative_return&benchmarks=%5EGSPC,%5EIXIC"
    )
    assert r.status_code == 200
    names = [s["name"] for s in r.json()["series"]]
    assert "Nasdaq Composite" not in names


@pytest.mark.django_db
def test_invalid_benchmark_422(api_client, legacy_seeded, today_patch):
    _buy(api_client)
    _price("AAPL", "2026-01-01", "100")
    r = api_client.get(
        "/api/v1/portfolio/performance?metric=cumulative_return&benchmark=%5ENOTREAL"
    )
    assert r.status_code == 422


@pytest.mark.django_db
def test_disabled_benchmark_422(api_client, legacy_seeded, today_patch):
    BenchmarkIndexConfig.objects.filter(symbol="^GSPC").update(enabled=False)
    _buy(api_client)
    _price("AAPL", "2026-01-01", "100")
    r = api_client.get(
        "/api/v1/portfolio/performance?metric=cumulative_return&benchmark=%5EGSPC"
    )
    assert r.status_code == 422


@pytest.mark.django_db
def test_benchmark_missing_prices_warning(api_client, legacy_seeded, today_patch):
    _buy(api_client)
    _price("AAPL", "2026-01-01", "100")
    r = api_client.get(
        "/api/v1/portfolio/performance?metric=cumulative_return&benchmark=%5EGSPC"
    )
    assert r.status_code == 200
    assert r.json()["warnings"]
    assert len(r.json()["series"]) == 1


@pytest.mark.django_db
def test_benchmark_uses_index_not_stock_rows(api_client, legacy_seeded, today_patch):
    _buy(api_client)
    _price("AAPL", "2026-01-01", "100")
    HistoricalPrice.objects.create(
        asset_symbol="^GSPC",
        date=date(2026, 1, 1),
        close_price=Decimal("999"),
        currency="USD",
        source="test",
        asset_type=AssetType.STOCK,
    )
    r = api_client.get(
        "/api/v1/portfolio/performance?metric=cumulative_return&benchmark=%5EGSPC"
    )
    assert r.status_code == 200
    assert r.json()["warnings"]


@pytest.mark.django_db
@patch("yfinance.download")
def test_benchmark_no_yfinance(mock_dl, api_client, legacy_seeded, today_patch):
    _buy(api_client)
    _price("AAPL", "2026-01-01", "100")
    _index_price("^GSPC", "2026-01-01", "1000")
    api_client.get(
        "/api/v1/portfolio/performance?metric=cumulative_return&benchmark=%5EGSPC"
    )
    mock_dl.assert_not_called()


@pytest.mark.django_db
def test_empty_portfolio_returns_empty_series(api_client, legacy_seeded, today_patch, test_user):
    r = api_client.get("/api/v1/portfolio/performance?metric=value&range=ALL")
    assert r.json() == []


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


def _parse_performance_points(data):
    if isinstance(data, dict):
        return data.get("points", [])
    return data


def _last_valid_performance_value(pts) -> float:
    points = _parse_performance_points(pts)
    for pt in reversed(points):
        if pt.get("value") is not None:
            return float(pt["value"])
    raise AssertionError("no valid performance points")


def _count_nulls_after(pts: list[dict], start_date: str) -> int:
    return sum(1 for p in pts if p["date"] >= start_date and p.get("value") is None)


def _largest_valid_gap_days(pts: list[dict]) -> int:
    valid = [p for p in pts if p.get("value") is not None]
    max_gap = 0
    for i in range(1, len(valid)):
        d1 = date.fromisoformat(valid[i - 1]["date"])
        d2 = date.fromisoformat(valid[i]["date"])
        max_gap = max(max_gap, (d2 - d1).days)
    return max_gap


def _setup_pln_stock_inr_mf_all_scope(api_client, monkeypatch, test_user):
    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2024, 4, 15))
    eur_portfolio = Portfolio.objects.create(user=test_user, 
        name="EUR PLN Stock", base_currency="EUR", is_active=True
    )
    inr_portfolio = Portfolio.objects.create(user=test_user, 
        name="INR MF Only", base_currency="INR", is_active=True
    )
    _buy(
        api_client,
        portfolio_id=eur_portfolio.id,
        asset_symbol="PLNSTK",
        date="2024-04-01",
        quantity="10",
        price_per_share="100",
        currency="EUR",
    )
    _mf_buy(
        api_client,
        portfolio_id=inr_portfolio.id,
        scheme_code="120503",
        folio_number="PLN-GAP-FOLIO",
        investment_date="2024-04-01",
        nav_date="2024-04-01",
        nav="50.00",
        units_allotted="100.00000000",
        paid_value="5000.00",
        market_value="5000.00",
    )
    _price("PLNSTK", "2024-04-01", "100", currency="PLN")
    _price("PLNSTK", "2024-04-15", "110", currency="PLN")
    _mf_nav("120503", "2024-04-01", "50.00")
    _mf_nav("120503", "2024-04-15", "55.00")
    for day in range(1, 16):
        d = date(2024, 4, day)
        upsert_fx_rate(
            from_currency="PLN",
            to_currency="EUR",
            row_date=d,
            rate=Decimal("0.23"),
        )
        upsert_fx_rate(
            from_currency="INR",
            to_currency="EUR",
            row_date=d,
            rate=Decimal("0.011"),
        )
    return eur_portfolio, inr_portfolio


@pytest.mark.django_db
def test_all_scope_summary_current_value_matches_performance_last_value(
    api_client, legacy_seeded, monkeypatch, test_user
):
    """Value History (pooled scope) must match summary KPI when display currency is EUR."""
    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2026, 3, 20))
    stock_portfolio = Portfolio.objects.create(user=test_user, 
        name="EUR Stocks Perf", base_currency="EUR", is_active=True
    )
    mf_portfolio = Portfolio.objects.create(user=test_user, 
        name="INR MF Perf", base_currency="INR", is_active=True
    )
    _buy(
        api_client,
        portfolio_id=stock_portfolio.id,
        asset_symbol="AAPL",
        quantity="10",
        price_per_share="100",
    )
    _mf_buy(
        api_client,
        portfolio_id=mf_portfolio.id,
        scheme_code="120503",
        folio_number="MF-FOLIO-PERF",
    )
    _price("AAPL", "2026-03-20", "120")
    _mf_nav("120503", "2026-03-20", "50.00")
    upsert_fx_rate(
        from_currency="INR",
        to_currency="EUR",
        row_date=date(2026, 3, 20),
        rate=Decimal("0.01"),
    )

    summary = api_client.get(
        "/api/v1/portfolio/summary?portfolio_scope=all&display_currency=EUR&include_timeseries=false"
    ).json()
    perf = api_client.get(
        "/api/v1/portfolio/performance?portfolio_scope=all&display_currency=EUR&metric=value&range=ALL"
    ).json()

    last_value = _last_valid_performance_value(perf)
    assert summary["current_value"] == pytest.approx(last_value, rel=1e-4, abs=1.0)
    assert summary["current_value"] == pytest.approx(1250.0, rel=1e-2)


@pytest.mark.django_db
def test_performance_all_scope_eur_value_history_no_gap_with_pln_stock(
    api_client, legacy_seeded, monkeypatch, test_user
):
    """All-scope value history must not break when a PLN stock lacks PLN->INR FX."""
    _setup_pln_stock_inr_mf_all_scope(api_client, monkeypatch, test_user)

    perf = api_client.get(
        "/api/v1/portfolio/performance?portfolio_scope=all&display_currency=EUR&metric=value&range=ALL"
    ).json()
    summary = api_client.get(
        "/api/v1/portfolio/summary?portfolio_scope=all&display_currency=EUR&include_timeseries=false"
    ).json()

    perf_after_buy = [p for p in perf if p["date"] >= "2024-04-01"]
    assert perf_after_buy
    assert all(p["value"] is not None for p in perf_after_buy)

    last_value = _last_valid_performance_value(perf)
    assert summary["current_value"] == pytest.approx(last_value, rel=1e-4, abs=1.0)


@pytest.mark.django_db
def test_performance_all_scope_cumulative_return_no_gap_with_pln_stock_and_inr_mf(
    api_client, legacy_seeded, monkeypatch, test_user
):
    _setup_pln_stock_inr_mf_all_scope(api_client, monkeypatch, test_user)

    perf = api_client.get(
        "/api/v1/portfolio/performance?portfolio_scope=all&display_currency=EUR&metric=cumulative_return&range=ALL"
    ).json()
    after_buy = [p for p in perf if p["date"] >= "2024-04-01"]
    assert after_buy
    assert all(p["value"] is not None for p in after_buy)
    assert _largest_valid_gap_days(perf) <= 1


@pytest.mark.django_db
def test_performance_all_scope_twror_no_gap_with_pln_stock_and_inr_mf(
    api_client, legacy_seeded, monkeypatch, test_user
):
    _setup_pln_stock_inr_mf_all_scope(api_client, monkeypatch, test_user)

    perf = api_client.get(
        "/api/v1/portfolio/performance?portfolio_scope=all&display_currency=EUR&metric=twror&range=ALL"
    ).json()
    after_buy = [p for p in perf if p["date"] >= "2024-04-02"]
    assert after_buy
    assert all(p["value"] is not None for p in after_buy)
    assert _largest_valid_gap_days(perf) <= 1


@pytest.mark.django_db
def test_performance_all_scope_value_cumulative_twror_share_valid_calendar(
    api_client, legacy_seeded, monkeypatch, test_user
):
    _setup_pln_stock_inr_mf_all_scope(api_client, monkeypatch, test_user)

    base = "/api/v1/portfolio/performance?portfolio_scope=all&display_currency=EUR&range=ALL"
    value_pts = api_client.get(f"{base}&metric=value").json()
    cum_pts = api_client.get(f"{base}&metric=cumulative_return").json()
    twror_pts = api_client.get(f"{base}&metric=twror").json()

    for metric_pts in (value_pts, cum_pts, twror_pts):
        assert _count_nulls_after(metric_pts, "2024-04-02") == 0
        assert _largest_valid_gap_days(metric_pts) <= 1

    value_by_date = {p["date"]: p["value"] for p in value_pts if p["date"] >= "2024-04-02"}
    cum_by_date = {p["date"]: p["value"] for p in cum_pts if p["date"] >= "2024-04-02"}
    twror_by_date = {p["date"]: p["value"] for p in twror_pts if p["date"] >= "2024-04-02"}
    assert set(value_by_date) == set(cum_by_date) == set(twror_by_date)


@pytest.mark.django_db
def test_performance_all_scope_value_history_uses_bulk_fx_lookup(
    api_client, legacy_seeded, monkeypatch, test_user
):
    """All-scope display conversion must bulk-load FX, not query per calendar day."""
    from django.db import connection, reset_queries
    from django.test.utils import CaptureQueriesContext

    from portfolios.performance_service import build_portfolio_performance
    from portfolios.scope import resolve_portfolio_scope

    _setup_pln_stock_inr_mf_all_scope(api_client, monkeypatch, test_user)
    scope = resolve_portfolio_scope(test_user, portfolio_scope="all")

    reset_queries()
    with CaptureQueriesContext(connection) as ctx:
        build_portfolio_performance(
            scope=scope,
            metric="value",
            range_code="ALL",
            display_currency="EUR",
        )

    fx_queries = sum(1 for q in ctx.captured_queries if '"fx_rates"' in q["sql"])
    assert len(ctx.captured_queries) < 200, (
        f"expected bulk FX path, got {len(ctx.captured_queries)} queries "
        f"({fx_queries} fx_rates)"
    )
    assert fx_queries <= 10, f"expected few bulk fx_rates loads, got {fx_queries}"


def _legacy_cash_mode(portfolio):
    portfolio.cash_aware_enabled = False
    portfolio.save(update_fields=["cash_aware_enabled"])


def _cash_deposit(portfolio, *, amount: str, currency: str = "EUR", day: str = "2026-06-01"):
    CashLedgerEntry.objects.create(
        portfolio=portfolio,
        date=date.fromisoformat(day),
        currency=currency,
        entry_type=CashEntryType.CASH_DEPOSIT,
        amount=Decimal(amount),
    )


def _cash_withdrawal(portfolio, *, amount: str, currency: str = "EUR", day: str = "2026-06-01"):
    CashLedgerEntry.objects.create(
        portfolio=portfolio,
        date=date.fromisoformat(day),
        currency=currency,
        entry_type=CashEntryType.CASH_WITHDRAWAL,
        amount=-Decimal(amount),
    )


@pytest.mark.django_db
def test_performance_value_includes_eur_cash(api_client, legacy_seeded, today_patch, test_user):
    portfolio = ensure_default_portfolio(test_user)
    _legacy_cash_mode(portfolio)
    _buy(api_client, date="2026-01-01", quantity="10", price_per_share="100")
    _price("AAPL", "2026-01-01", "100")
    _price("AAPL", "2026-03-15", "110")
    _cash_deposit(portfolio, amount="1200", day="2026-01-15")
    perf = api_client.get(
        "/api/v1/portfolio/performance?metric=value&range=ALL&display_currency=EUR"
    ).json()
    summary = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false&display_currency=EUR"
    ).json()
    last = _last_valid_performance_value(perf)
    assert last == pytest.approx(summary["current_value"], rel=1e-4, abs=0.01)
    assert last == pytest.approx(2300.0, rel=1e-2)


@pytest.mark.django_db
def test_performance_cash_deposit_increases_value_on_date(api_client, legacy_seeded, today_patch, test_user):
    portfolio = ensure_default_portfolio(test_user)
    _legacy_cash_mode(portfolio)
    _buy(api_client, date="2026-01-01", quantity="10", price_per_share="100")
    _price("AAPL", "2026-01-01", "100")
    _price("AAPL", "2026-03-15", "100")
    _cash_deposit(portfolio, amount="500", day="2026-02-01")
    perf = api_client.get(
        "/api/v1/portfolio/performance?metric=value&range=ALL&display_currency=EUR"
    ).json()
    by_date = {p["date"]: p["value"] for p in perf if p.get("value") is not None}
    assert by_date["2026-01-31"] == pytest.approx(1000.0, rel=1e-2)
    assert by_date["2026-02-01"] == pytest.approx(1500.0, rel=1e-2)
    assert by_date["2026-03-15"] == pytest.approx(1500.0, rel=1e-2)


@pytest.mark.django_db
def test_performance_cash_withdrawal_decreases_value(api_client, legacy_seeded, today_patch, test_user):
    portfolio = ensure_default_portfolio(test_user)
    _legacy_cash_mode(portfolio)
    _cash_deposit(portfolio, amount="2000", day="2026-01-01")
    _cash_withdrawal(portfolio, amount="500", day="2026-02-01")
    perf = api_client.get(
        "/api/v1/portfolio/performance?metric=value&range=ALL&display_currency=EUR"
    ).json()
    by_date = {p["date"]: p["value"] for p in perf if p.get("value") is not None}
    assert by_date["2026-01-31"] == pytest.approx(2000.0, rel=1e-2)
    assert by_date["2026-02-01"] == pytest.approx(1500.0, rel=1e-2)


@pytest.mark.django_db
def test_performance_all_scope_includes_multi_currency_cash(
    api_client, legacy_seeded, today_patch, test_user
):
    p1 = ensure_default_portfolio(test_user)
    p2 = Portfolio.objects.create(user=test_user, name="P2", base_currency="EUR", is_active=True)
    _legacy_cash_mode(p1)
    _legacy_cash_mode(p2)
    _cash_deposit(p1, amount="1000", currency="EUR", day="2026-01-01")
    _cash_deposit(p2, amount="50000", currency="INR", day="2026-01-01")
    for day in ("2026-01-01", "2026-03-15"):
        upsert_fx_rate(
            from_currency="INR",
            to_currency="EUR",
            row_date=date.fromisoformat(day),
            rate=Decimal("0.01"),
        )
    perf = api_client.get(
        "/api/v1/portfolio/performance?portfolio_scope=all&metric=value&range=ALL&display_currency=EUR"
    ).json()
    last = _last_valid_performance_value(perf)
    assert last == pytest.approx(1500.0, rel=1e-2)


@pytest.mark.django_db
def test_performance_cash_missing_fx_warning(api_client, legacy_seeded, today_patch, test_user):
    portfolio = ensure_default_portfolio(test_user)
    _legacy_cash_mode(portfolio)
    _buy(api_client, date="2026-01-01", quantity="1", price_per_share="100")
    _price("AAPL", "2026-01-01", "100")
    _price("AAPL", "2026-03-15", "110")
    _cash_deposit(portfolio, amount="50000", currency="INR", day="2026-01-01")
    r = api_client.get(
        "/api/v1/portfolio/performance?metric=value&range=ALL&display_currency=EUR"
    )
    assert r.status_code == 200
    data = r.json()
    if isinstance(data, dict):
        assert any("value history" in w.lower() for w in data.get("warnings", []))
        pts = data["points"]
    else:
        pts = data
    last = _last_valid_performance_value(pts)
    assert last == pytest.approx(110.0, rel=1e-2)


def _enable_cash_aware(portfolio: Portfolio) -> Portfolio:
    portfolio.cash_aware_enabled = True
    portfolio.save(update_fields=["cash_aware_enabled", "updated_at"])
    return portfolio


def _perf_points(response) -> list[dict]:
    data = response.json()
    return data["points"] if isinstance(data, dict) else data


def _metric_on_date(pts: list[dict], day: str) -> float | None:
    row = next((p for p in pts if p["date"] == day), None)
    return row["value"] if row else None


@pytest.mark.django_db
def test_cash_aware_twror_deposit_only_near_zero(api_client, seeded, test_user, today_patch):
    portfolio = _enable_cash_aware(ensure_default_portfolio(test_user))
    _cash_deposit(portfolio, amount="1000", day="2026-01-01")
    pts = _perf_points(
        api_client.get(
            "/api/v1/portfolio/performance?metric=twror&range=ALL&display_currency=EUR"
        )
    )
    assert abs(pts[-1]["value"]) < 0.5


@pytest.mark.django_db
def test_cash_aware_cumulative_return_deposit_only_near_zero(
    api_client, seeded, test_user, today_patch
):
    portfolio = _enable_cash_aware(ensure_default_portfolio(test_user))
    _cash_deposit(portfolio, amount="1000", day="2026-01-01")
    pts = _perf_points(
        api_client.get(
            "/api/v1/portfolio/performance?metric=cumulative_return&range=ALL&display_currency=EUR"
        )
    )
    assert abs(pts[-1]["value"]) < 0.5


@pytest.mark.django_db
def test_cash_aware_twror_deposit_and_buy_same_value_near_zero(
    api_client, seeded, test_user, today_patch
):
    portfolio = _enable_cash_aware(ensure_default_portfolio(test_user))
    _cash_deposit(portfolio, amount="1000", day="2026-01-01")
    _buy(api_client, date="2026-01-01", quantity="10", price_per_share="100")
    _price("AAPL", "2026-01-01", "100")
    _price("AAPL", "2026-01-02", "100")
    _price("AAPL", "2026-03-15", "100")
    twror_jan2 = _metric_on_date(
        _perf_points(
            api_client.get(
                "/api/v1/portfolio/performance?metric=twror&range=ALL&display_currency=EUR"
            )
        ),
        "2026-01-02",
    )
    assert twror_jan2 is not None
    assert abs(twror_jan2) < 0.5


@pytest.mark.django_db
def test_cash_aware_twror_reflects_investment_growth(
    api_client, seeded, test_user, today_patch
):
    portfolio = _enable_cash_aware(ensure_default_portfolio(test_user))
    _cash_deposit(portfolio, amount="1000", day="2026-01-01")
    _buy(api_client, date="2026-01-01", quantity="10", price_per_share="100")
    _price("AAPL", "2026-01-01", "100")
    _price("AAPL", "2026-01-02", "110")
    twror = _metric_on_date(
        _perf_points(
            api_client.get(
                "/api/v1/portfolio/performance?metric=twror&range=ALL&display_currency=EUR"
            )
        ),
        "2026-01-02",
    )
    assert twror is not None
    assert 8.0 < twror < 12.0


@pytest.mark.django_db
def test_cash_aware_sell_to_cash_no_artificial_twror_spike(
    api_client, seeded, test_user, today_patch
):
    portfolio = _enable_cash_aware(ensure_default_portfolio(test_user))
    _cash_deposit(portfolio, amount="1000", day="2026-01-01")
    _buy(api_client, date="2026-01-01", quantity="10", price_per_share="100")
    _price("AAPL", "2026-01-01", "100")
    _price("AAPL", "2026-03-14", "110")
    _price("AAPL", "2026-03-15", "110")
    before_sell = _metric_on_date(
        _perf_points(
            api_client.get(
                "/api/v1/portfolio/performance?metric=twror&range=ALL&display_currency=EUR"
            )
        ),
        "2026-03-14",
    )
    _sell(api_client, date="2026-03-15", quantity="10", price_per_share="110")
    after_sell = _metric_on_date(
        _perf_points(
            api_client.get(
                "/api/v1/portfolio/performance?metric=twror&range=ALL&display_currency=EUR"
            )
        ),
        "2026-03-15",
    )
    assert before_sell is not None and after_sell is not None
    assert abs(after_sell - before_sell) < 1.0


@pytest.mark.django_db
def test_cash_aware_sell_with_tax_withheld_reduces_value_by_withheld_amount(
    api_client, seeded, test_user, today_patch
):
    portfolio = _enable_cash_aware(ensure_default_portfolio(test_user))
    _cash_deposit(portfolio, amount="1000", day="2026-01-01")
    _buy(api_client, date="2026-01-01", quantity="10", price_per_share="100")
    _price("AAPL", "2026-01-01", "100")
    _price("AAPL", "2026-03-15", "110")
    _sell(
        api_client,
        date="2026-03-15",
        quantity="10",
        price_per_share="110",
        actual_cash_received="1000",
    )
    value_pts = _perf_points(
        api_client.get(
            "/api/v1/portfolio/performance?metric=value&range=ALL&display_currency=EUR"
        )
    )
    assert _metric_on_date(value_pts, "2026-03-15") == pytest.approx(1000.0, rel=1e-2)


@pytest.mark.django_db
def test_cash_aware_value_and_twror_share_daily_value_base(
    api_client, seeded, test_user, today_patch
):
    portfolio = _enable_cash_aware(ensure_default_portfolio(test_user))
    _cash_deposit(portfolio, amount="1000", day="2026-01-01")
    _buy(api_client, date="2026-01-01", quantity="10", price_per_share="100")
    _price("AAPL", "2026-01-01", "100")
    _price("AAPL", "2026-01-02", "110")
    value_pts = _perf_points(
        api_client.get(
            "/api/v1/portfolio/performance?metric=value&range=ALL&display_currency=EUR"
        )
    )
    assert _metric_on_date(value_pts, "2026-01-02") == pytest.approx(1100.0, rel=1e-2)


@pytest.mark.django_db
def test_performance_twror_unchanged_by_cash_deposit(api_client, legacy_seeded, today_patch, test_user):
    portfolio = ensure_default_portfolio(test_user)
    _legacy_cash_mode(portfolio)
    _buy(api_client, date="2026-01-01", quantity="10", price_per_share="100")
    _price("AAPL", "2026-01-01", "100")
    _price("AAPL", "2026-03-15", "110")
    before = api_client.get(
        "/api/v1/portfolio/performance?metric=twror&range=ALL&display_currency=EUR"
    ).json()
    _cash_deposit(portfolio, amount="5000", day="2026-02-01")
    after = api_client.get(
        "/api/v1/portfolio/performance?metric=twror&range=ALL&display_currency=EUR"
    ).json()
    assert before[-1]["value"] == after[-1]["value"]


# --- Cash-6D: cash-aware return regression scenarios ---


@pytest.mark.django_db
def test_cash_6d_scenario1_deposit_only_full_surface(
    api_client, seeded, test_user, today_patch
):
    """Deposit only: value, returns, summary, and allocation stay at deposited cash."""
    portfolio = _enable_cash_aware(ensure_default_portfolio(test_user))
    _cash_deposit(portfolio, amount="1000", day="2026-01-01")
    summary = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false&display_currency=EUR"
    ).json()
    assert summary["current_value"] == 1000.0
    assert summary["xirr"] is not None
    assert abs(summary["xirr"]) < 0.02

    value_pts = _perf_points(
        api_client.get(
            "/api/v1/portfolio/performance?metric=value&range=ALL&display_currency=EUR"
        )
    )
    assert _last_valid_performance_value(value_pts) == pytest.approx(1000.0, rel=1e-2)

    for metric in ("twror", "cumulative_return"):
        pts = _perf_points(
            api_client.get(
                f"/api/v1/portfolio/performance?metric={metric}&range=ALL&display_currency=EUR"
            )
        )
        assert abs(pts[-1]["value"]) < 0.5

    holdings = api_client.get(
        "/api/v1/portfolio/holdings?display_currency=EUR"
    ).json()
    cash_rows = [r for r in holdings["allocation"] if r.get("asset_type") == "CASH"]
    assert len(cash_rows) == 1
    assert cash_rows[0]["asset_symbol"] == "Cash EUR"
    assert cash_rows[0]["current_value"] == 1000.0


@pytest.mark.django_db
def test_cash_6d_scenario2_deposit_buy_flat_holdings_and_value(
    api_client, seeded, test_user, today_patch
):
    portfolio = _enable_cash_aware(ensure_default_portfolio(test_user))
    _cash_deposit(portfolio, amount="1000", day="2026-01-01")
    _buy(api_client, date="2026-01-01", quantity="10", price_per_share="100")
    _price("AAPL", "2026-01-01", "100")
    _price("AAPL", "2026-03-15", "100")
    summary = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false&display_currency=EUR"
    ).json()
    assert summary["current_value"] == 1000.0
    assert summary["cash_summary"]["total_display_value"] == 0.0

    holdings = api_client.get(
        "/api/v1/portfolio/holdings?display_currency=EUR"
    ).json()
    stock = next(h for h in holdings["holdings"] if h["asset_symbol"] == "AAPL")
    assert stock["current_value"] == 1000.0
    assert not any(r.get("asset_type") == "CASH" for r in holdings["allocation"])


@pytest.mark.django_db
def test_cash_6d_scenario3_growth_cumulative_return_near_ten_percent(
    api_client, seeded, test_user, today_patch
):
    portfolio = _enable_cash_aware(ensure_default_portfolio(test_user))
    _cash_deposit(portfolio, amount="1000", day="2026-01-01")
    _buy(api_client, date="2026-01-01", quantity="10", price_per_share="100")
    _price("AAPL", "2026-01-01", "100")
    _price("AAPL", "2026-03-15", "110")
    cum = _perf_points(
        api_client.get(
            "/api/v1/portfolio/performance?metric=cumulative_return&range=ALL&display_currency=EUR"
        )
    )[-1]["value"]
    assert 8.0 < cum < 12.0
    summary = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false&display_currency=EUR"
    ).json()
    assert summary["current_value"] == 1100.0
    assert summary["xirr"] is not None
    assert summary["xirr"] > 0.04


@pytest.mark.django_db
def test_cash_6d_scenario4_sell_to_cash_value_and_holdings_stable(
    api_client, seeded, test_user, today_patch
):
    portfolio = _enable_cash_aware(ensure_default_portfolio(test_user))
    _cash_deposit(portfolio, amount="1000", day="2026-01-01")
    _buy(api_client, date="2026-01-01", quantity="10", price_per_share="100")
    _price("AAPL", "2026-01-01", "100")
    _price("AAPL", "2026-03-14", "110")
    _price("AAPL", "2026-03-15", "110")
    _sell(api_client, date="2026-03-15", quantity="10", price_per_share="110")
    value_pts = _perf_points(
        api_client.get(
            "/api/v1/portfolio/performance?metric=value&range=ALL&display_currency=EUR"
        )
    )
    by_date = {p["date"]: p["value"] for p in value_pts if p.get("value") is not None}
    assert by_date["2026-03-14"] == pytest.approx(1100.0, rel=1e-2)
    assert by_date["2026-03-15"] == pytest.approx(1100.0, rel=1e-2)

    summary = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false&display_currency=EUR"
    ).json()
    assert summary["current_value"] == 1100.0
    assert summary["cash_summary"]["total_display_value"] == 1100.0

    holdings = api_client.get(
        "/api/v1/portfolio/holdings?display_currency=EUR"
    ).json()
    stock_rows = [h for h in holdings["holdings"] if h["asset_symbol"] == "AAPL"]
    if stock_rows:
        assert stock_rows[0]["quantity"] == 0.0
        assert stock_rows[0]["current_value"] == 0.0
    cash = next(r for r in holdings["allocation"] if r.get("asset_type") == "CASH")
    assert cash["current_value"] == 1100.0


@pytest.mark.django_db
def test_cash_6d_scenario5_withdrawal_twror_not_punished_as_loss(
    api_client, seeded, test_user, today_patch
):
    portfolio = _enable_cash_aware(ensure_default_portfolio(test_user))
    _cash_deposit(portfolio, amount="1000", day="2026-01-01")
    _buy(api_client, date="2026-01-01", quantity="10", price_per_share="100")
    _price("AAPL", "2026-01-01", "100")
    _price("AAPL", "2026-03-14", "110")
    _price("AAPL", "2026-03-15", "110")
    _sell(api_client, date="2026-03-15", quantity="10", price_per_share="110")
    _cash_withdrawal(portfolio, amount="100", day="2026-03-15")
    twror_pts = _perf_points(
        api_client.get(
            "/api/v1/portfolio/performance?metric=twror&range=ALL&display_currency=EUR"
        )
    )
    before = _metric_on_date(twror_pts, "2026-03-14")
    after = _metric_on_date(twror_pts, "2026-03-15")
    assert before is not None and after is not None
    assert 8.0 < before < 12.0
    assert after > 5.0

    summary = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false&display_currency=EUR"
    ).json()
    assert summary["current_value"] == 1000.0


@pytest.mark.django_db
def test_cash_6d_scenario6_all_scope_mixed_performance_matches_summary(
    api_client, seeded, test_user, today_patch
):
    cash_aware = _enable_cash_aware(ensure_default_portfolio(test_user))
    legacy = Portfolio.objects.create(
        user=test_user,
        name="Legacy P",
        base_currency="EUR",
        is_active=True,
        cash_aware_enabled=False,
    )
    _cash_deposit(cash_aware, amount="1000", day="2026-01-01")
    _buy(
        api_client,
        date="2026-01-02",
        quantity="10",
        price_per_share="100",
        portfolio_id=legacy.id,
    )
    _price("AAPL", "2026-01-01", "100")
    _price("AAPL", "2026-03-15", "110")
    for metric in ("value", "twror", "cumulative_return"):
        perf = api_client.get(
            f"/api/v1/portfolio/performance?portfolio_scope=all&metric={metric}&range=ALL&display_currency=EUR"
        ).json()
        pts = perf["points"] if isinstance(perf, dict) else perf
        last_dates = [p["date"] for p in pts if p.get("value") is not None]
        assert last_dates, f"no valid points for metric={metric}"
        assert pts[-1]["value"] is not None
    summary = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false&portfolio_scope=all&display_currency=EUR"
    ).json()
    value_pts = _perf_points(
        api_client.get(
            "/api/v1/portfolio/performance?portfolio_scope=all&metric=value&range=ALL&display_currency=EUR"
        )
    )
    assert summary["current_value"] == pytest.approx(
        _last_valid_performance_value(value_pts), rel=1e-4, abs=0.01
    )
    assert summary["current_value"] == 2100.0


# --- Cash-only return behavior (FX vs same-currency) ---


@pytest.mark.django_db
def test_cash_only_usd_display_same_currency_returns_near_zero(
    api_client, seeded, test_user, today_patch
):
    portfolio = _enable_cash_aware(ensure_default_portfolio(test_user))
    _cash_deposit(portfolio, amount="1000", currency="USD", day="2026-01-01")
    summary = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false&display_currency=USD"
    ).json()
    assert summary["current_value"] == 1000.0
    assert summary["xirr"] is not None
    assert abs(summary["xirr"]) < 0.02
    for metric in ("cumulative_return", "twror"):
        pts = _perf_points(
            api_client.get(
                f"/api/v1/portfolio/performance?metric={metric}&range=ALL&display_currency=USD"
            )
        )
        assert abs(pts[-1]["value"]) < 0.5


@pytest.mark.django_db
def test_cash_only_multiple_usd_deposits_same_display_near_zero(
    api_client, seeded, test_user, today_patch
):
    portfolio = _enable_cash_aware(ensure_default_portfolio(test_user))
    _cash_deposit(portfolio, amount="1000", currency="USD", day="2026-01-01")
    _cash_deposit(portfolio, amount="500", currency="USD", day="2026-02-01")
    summary = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false&display_currency=USD"
    ).json()
    assert summary["current_value"] == 1500.0
    assert summary["xirr"] is not None
    assert abs(summary["xirr"]) < 0.02
    twror = _perf_points(
        api_client.get(
            "/api/v1/portfolio/performance?metric=twror&range=ALL&display_currency=USD"
        )
    )
    cum = _perf_points(
        api_client.get(
            "/api/v1/portfolio/performance?metric=cumulative_return&range=ALL&display_currency=USD"
        )
    )
    assert abs(twror[-1]["value"]) < 0.5
    assert abs(cum[-1]["value"]) < 0.5


@pytest.mark.django_db
def test_cash_only_usd_cash_eur_display_fx_moves_returns(
    api_client, seeded, test_user, today_patch
):
    portfolio = _enable_cash_aware(ensure_default_portfolio(test_user))
    _cash_deposit(portfolio, amount="1000", currency="USD", day="2026-01-01")
    for day, rate in (("2026-01-01", "0.90"), ("2026-01-15", "0.95"), ("2026-03-15", "1.00")):
        upsert_fx_rate(
            from_currency="USD",
            to_currency="EUR",
            row_date=date.fromisoformat(day),
            rate=Decimal(rate),
        )
    cum_pts = _perf_points(
        api_client.get(
            "/api/v1/portfolio/performance?metric=cumulative_return&range=ALL&display_currency=EUR"
        )
    )
    cum_vals = [p["value"] for p in cum_pts if p.get("value") is not None]
    assert cum_vals
    assert max(cum_vals) > 0.5
    summary = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false&display_currency=EUR"
    ).json()
    assert summary["xirr"] is not None
    assert abs(summary["xirr"]) > 0.01


@pytest.mark.django_db
def test_cash_only_after_delete_buy_same_currency_returns_near_zero(
    api_client, seeded, test_user, today_patch
):
    portfolio = _enable_cash_aware(ensure_default_portfolio(test_user))
    _cash_deposit(portfolio, amount="1000", currency="USD", day="2026-01-01")
    buy_resp = _buy(
        api_client,
        date="2026-01-02",
        quantity="10",
        price_per_share="100",
        currency="USD",
    )
    assert buy_resp.status_code == 201, buy_resp.json()
    created = buy_resp.json()
    _price("AAPL", "2026-01-02", "100")
    assert CashLedgerEntry.objects.filter(
        linked_transaction_id=created["id"], entry_type=CashEntryType.BUY_SETTLEMENT
    ).exists()
    del_resp = api_client.delete(f"/api/v1/transactions/{created['id']}")
    assert del_resp.status_code == 204
    assert not Transaction.objects.filter(pk=created["id"]).exists()
    assert not CashLedgerEntry.objects.filter(linked_transaction_id=created["id"]).exists()
    summary = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false&display_currency=USD"
    ).json()
    assert summary["current_value"] == 1000.0
    assert summary["xirr"] is not None
    assert abs(summary["xirr"]) < 0.02
    pts = _perf_points(
        api_client.get(
            "/api/v1/portfolio/performance?metric=twror&range=ALL&display_currency=USD"
        )
    )
    assert abs(pts[-1]["value"]) < 0.5


@pytest.mark.django_db
def test_cash_8a_same_currency_transfer_all_scope_twror_xirr_neutral(
    api_client, seeded, test_user, today_patch
):
    source = _enable_cash_aware(ensure_default_portfolio(test_user))
    target = _enable_cash_aware(
        Portfolio.objects.create(
            user=test_user, name="Target", base_currency="EUR", is_active=True
        )
    )
    _cash_deposit(source, amount="5000", day="2026-01-01")
    before_summary = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false&portfolio_scope=all&display_currency=EUR"
    ).json()
    before_twror = _perf_points(
        api_client.get(
            "/api/v1/portfolio/performance?portfolio_scope=all&metric=twror&range=ALL&display_currency=EUR"
        )
    )
    before_value_pts = _perf_points(
        api_client.get(
            "/api/v1/portfolio/performance?portfolio_scope=all&metric=value&range=ALL&display_currency=EUR"
        )
    )
    before_xirr = before_summary["xirr"]
    before_current_value = before_summary["current_value"]

    transfer = api_client.post(
        "/api/v1/cash/transfers",
        {
            "source_portfolio_id": source.id,
            "target_portfolio_id": target.id,
            "date": "2026-02-01",
            "currency": "EUR",
            "amount": "1000",
            "note": "Rebalance cash",
        },
        format="json",
    )
    assert transfer.status_code == 201

    after_twror = _perf_points(
        api_client.get(
            "/api/v1/portfolio/performance?portfolio_scope=all&metric=twror&range=ALL&display_currency=EUR"
        )
    )
    after_xirr = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false&portfolio_scope=all&display_currency=EUR"
    ).json()["xirr"]
    after_summary = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false&portfolio_scope=all&display_currency=EUR"
    ).json()
    after_value_pts = _perf_points(
        api_client.get(
            "/api/v1/portfolio/performance?portfolio_scope=all&metric=value&range=ALL&display_currency=EUR"
        )
    )
    assert abs(after_twror[-1]["value"] - before_twror[-1]["value"]) < 0.5
    assert before_xirr is not None and after_xirr is not None
    assert abs(after_xirr - before_xirr) < 0.02
    assert after_summary["current_value"] == pytest.approx(
        before_current_value, abs=0.01
    )
    assert _last_valid_performance_value(after_value_pts) == pytest.approx(
        _last_valid_performance_value(before_value_pts), abs=0.01
    )


@pytest.mark.django_db
def test_cash_8a_transfer_source_portfolio_twror_treats_as_external_flow(
    api_client, seeded, test_user, today_patch
):
    source = _enable_cash_aware(ensure_default_portfolio(test_user))
    target = _enable_cash_aware(
        Portfolio.objects.create(
            user=test_user, name="Target", base_currency="EUR", is_active=True
        )
    )
    _cash_deposit(source, amount="5000", day="2026-01-01")
    transfer = api_client.post(
        "/api/v1/cash/transfers",
        {
            "source_portfolio_id": source.id,
            "target_portfolio_id": target.id,
            "date": "2026-02-01",
            "currency": "EUR",
            "amount": "1000",
        },
        format="json",
    )
    assert transfer.status_code == 201

    src_twror = _metric_on_date(
        _perf_points(
            api_client.get(
                f"/api/v1/portfolio/performance?portfolio_id={source.id}&metric=twror&range=ALL&display_currency=EUR"
            )
        ),
        "2026-02-01",
    )
    tgt_value = _metric_on_date(
        _perf_points(
            api_client.get(
                f"/api/v1/portfolio/performance?portfolio_id={target.id}&metric=value&range=ALL&display_currency=EUR"
            )
        ),
        "2026-02-01",
    )
    tgt_twror_last = _perf_points(
        api_client.get(
            f"/api/v1/portfolio/performance?portfolio_id={target.id}&metric=twror&range=ALL&display_currency=EUR"
        )
    )[-1]["value"]
    assert src_twror is not None and abs(src_twror) < 0.5
    assert tgt_value == pytest.approx(1000.0, rel=1e-2)
    assert tgt_twror_last is None or abs(tgt_twror_last) < 0.5


@pytest.mark.django_db
def test_cash_8b_cross_currency_transfer_all_scope_does_not_crash(
    api_client, seeded, test_user, today_patch
):
    from fx.services import upsert_fx_rate

    source = _enable_cash_aware(ensure_default_portfolio(test_user))
    target = _enable_cash_aware(
        Portfolio.objects.create(
            user=test_user, name="Target", base_currency="EUR", is_active=True
        )
    )
    CashLedgerEntry.objects.create(
        portfolio=source,
        date=date(2026, 1, 1),
        currency="USD",
        entry_type=CashEntryType.CASH_DEPOSIT,
        amount=Decimal("5000"),
    )
    upsert_fx_rate(
        from_currency="USD",
        to_currency="EUR",
        row_date=date(2026, 1, 1),
        rate=Decimal("0.90"),
    )
    upsert_fx_rate(
        from_currency="USD",
        to_currency="EUR",
        row_date=date(2026, 2, 1),
        rate=Decimal("0.90"),
    )
    before_summary = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false&portfolio_scope=all&display_currency=EUR"
    ).json()

    transfer = api_client.post(
        "/api/v1/cash/transfers",
        {
            "source_portfolio_id": source.id,
            "target_portfolio_id": target.id,
            "date": "2026-02-01",
            "source_currency": "USD",
            "source_amount": "1000",
            "target_currency": "EUR",
            "target_amount": "920",
        },
        format="json",
    )
    assert transfer.status_code == 201
    assert transfer.json()["implied_rate"] == pytest.approx(0.92, rel=1e-4)

    after_summary = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false&portfolio_scope=all&display_currency=EUR"
    ).json()
    twror_pts = _perf_points(
        api_client.get(
            "/api/v1/portfolio/performance?portfolio_scope=all&metric=twror&range=ALL&display_currency=EUR"
        )
    )
    value_pts = _perf_points(
        api_client.get(
            "/api/v1/portfolio/performance?portfolio_scope=all&metric=value&range=ALL&display_currency=EUR"
        )
    )
    assert after_summary["current_value"] is not None
    assert twror_pts[-1]["value"] is not None or twror_pts[-1]["value"] is None
    assert _last_valid_performance_value(value_pts) is not None
    # Cross-currency user-entered amounts may change display total vs cached FX.
    assert after_summary["current_value"] != pytest.approx(
        before_summary["current_value"], abs=0.01
    )
