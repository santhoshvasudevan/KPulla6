from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

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
def test_performance_defaults_metric_value_range_1y(api_client, seeded, today_patch):
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
def test_performance_scope_all(api_client, seeded, today_patch):
    p1 = ensure_default_portfolio()
    p2 = Portfolio.objects.create(name="P2", base_currency="EUR", is_active=True)
    _buy(api_client, asset_symbol="AAA", portfolio_id=p1.id)
    _buy(api_client, asset_symbol="BBB", portfolio_id=p2.id)
    _price("AAA", "2026-03-01", "10")
    _price("BBB", "2026-03-01", "20")
    r = api_client.get("/api/v1/portfolio/performance?metric=value&range=ALL")
    assert r.status_code == 200
    last = [p for p in r.json() if p["date"] == "2026-03-15" and p["value"] is not None][-1]
    assert last["value"] == 300.0


@pytest.mark.django_db
def test_performance_portfolio_id_filter(api_client, seeded, today_patch):
    p1 = ensure_default_portfolio()
    p2 = Portfolio.objects.create(name="Scoped", base_currency="EUR", is_active=True)
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
def test_performance_scope_all_and_portfolio_id_422(api_client, seeded):
    p = ensure_default_portfolio()
    r = api_client.get(
        f"/api/v1/portfolio/performance?portfolio_scope=all&portfolio_id={p.id}"
    )
    assert r.status_code == 422


@pytest.mark.django_db
def test_performance_unknown_portfolio_id_404(api_client, seeded):
    r = api_client.get("/api/v1/portfolio/performance?portfolio_id=999999")
    assert r.status_code == 404


@pytest.mark.django_db
def test_performance_inactive_portfolio_id_404(api_client, seeded):
    p = Portfolio.objects.create(name="Inactive", base_currency="EUR", is_active=False)
    r = api_client.get(f"/api/v1/portfolio/performance?portfolio_id={p.id}")
    assert r.status_code == 404


@pytest.mark.django_db
def test_performance_invalid_metric_400(api_client, seeded):
    r = api_client.get("/api/v1/portfolio/performance?metric=nope")
    assert r.status_code == 400


@pytest.mark.django_db
def test_performance_invalid_range_400(api_client, seeded):
    r = api_client.get("/api/v1/portfolio/performance?range=bogus")
    assert r.status_code == 400


@pytest.mark.django_db
def test_performance_invalid_display_currency_400(api_client, seeded):
    r = api_client.get("/api/v1/portfolio/performance?display_currency=JPY")
    assert r.status_code == 400


@pytest.mark.django_db
def test_performance_value_list_points(api_client, seeded, today_patch):
    _buy(api_client)
    _price("AAPL", "2026-01-01", "100")
    r = api_client.get("/api/v1/portfolio/performance?metric=value&range=ALL")
    assert isinstance(r.json(), list)
    assert r.json()[0]["currency"] == "EUR"


@pytest.mark.django_db
def test_performance_value_display_currency_fx(api_client, seeded, today_patch):
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
def test_performance_value_missing_fx_null(api_client, seeded, today_patch):
    _buy(api_client, currency="USD")
    _price("AAPL", "2026-01-01", "100", currency="USD")
    _price("AAPL", "2026-03-15", "100", currency="USD")
    r = api_client.get(
        "/api/v1/portfolio/performance?metric=value&range=ALL&display_currency=INR"
    )
    pt = [p for p in r.json() if p["date"] == "2026-03-15"][0]
    assert pt["value"] is None


@pytest.mark.django_db
def test_performance_value_missing_price_safe(api_client, seeded, today_patch):
    _buy(api_client, date="2026-01-01")
    r = api_client.get("/api/v1/portfolio/performance?metric=value&range=ALL")
    pt = [p for p in r.json() if p["date"] == "2026-01-01"][0]
    assert pt["value"] in (None, 0.0)


@pytest.mark.django_db
@patch("yfinance.download")
def test_performance_no_yfinance_on_read(mock_dl, api_client, seeded, today_patch):
    _buy(api_client)
    _price("AAPL", "2026-01-01", "100")
    api_client.get("/api/v1/portfolio/performance?metric=value&range=ALL")
    mock_dl.assert_not_called()


@pytest.mark.django_db
def test_performance_range_7d(api_client, seeded, today_patch):
    _buy(api_client, date="2026-01-01")
    for d in ("2026-03-08", "2026-03-15"):
        _price("AAPL", d, "100")
    r = api_client.get("/api/v1/portfolio/performance?metric=value&range=7D")
    dates = [p["date"] for p in r.json()]
    assert min(dates) == "2026-03-08"
    assert max(dates) == "2026-03-15"


@pytest.mark.django_db
def test_performance_range_30d(api_client, seeded, today_patch):
    _buy(api_client, date="2026-01-01")
    _price("AAPL", "2026-02-13", "100")
    _price("AAPL", "2026-03-15", "100")
    r = api_client.get("/api/v1/portfolio/performance?metric=value&range=30D")
    assert min(p["date"] for p in r.json()) == "2026-02-13"


@pytest.mark.django_db
def test_performance_range_ytd(api_client, seeded, today_patch):
    _buy(api_client, date="2025-12-01")
    _price("AAPL", "2025-12-01", "90")
    _price("AAPL", "2026-01-01", "100")
    _price("AAPL", "2026-03-15", "100")
    r = api_client.get("/api/v1/portfolio/performance?metric=value&range=YTD")
    assert min(p["date"] for p in r.json()) == "2026-01-01"


@pytest.mark.django_db
def test_performance_range_all_starts_first_transaction(api_client, seeded, today_patch):
    _buy(api_client, date="2026-02-01")
    _price("AAPL", "2026-02-01", "100")
    _price("AAPL", "2026-03-15", "100")
    r = api_client.get("/api/v1/portfolio/performance?metric=value&range=ALL")
    assert min(p["date"] for p in r.json()) == "2026-02-01"


@pytest.mark.django_db
def test_performance_range_never_before_inception(api_client, seeded, today_patch):
    _buy(api_client, date="2026-02-01")
    _price("AAPL", "2026-02-01", "100")
    _price("AAPL", "2026-03-15", "100")
    r = api_client.get("/api/v1/portfolio/performance?metric=value&range=7D")
    assert min(p["date"] for p in r.json()) >= "2026-02-01"


@pytest.mark.django_db
def test_cumulative_return_one_buy_price_increase(api_client, seeded, today_patch):
    _buy(api_client, quantity="1", price_per_share="100")
    _price("AAPL", "2026-01-01", "100")
    _price("AAPL", "2026-01-02", "110")
    r = api_client.get(
        "/api/v1/portfolio/performance?metric=cumulative_return&range=ALL"
    )
    by_date = {p["date"]: p for p in r.json()}
    assert abs(by_date["2026-01-02"]["value"] - 10.0) < 1e-6


@pytest.mark.django_db
def test_cumulative_return_multiple_buys(api_client, seeded, today_patch):
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
def test_cumulative_return_with_sell(api_client, seeded, today_patch):
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
def test_cumulative_return_null_no_contributions(api_client, seeded, today_patch):
    Transaction.objects.create(
        portfolio=ensure_default_portfolio(),
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
def test_twror_ignores_contribution_as_performance(api_client, seeded, today_patch):
    _buy(api_client, date="2026-01-01", quantity="1", price_per_share="100")
    _buy(api_client, date="2026-01-02", quantity="1", price_per_share="100")
    _price("AAPL", "2026-01-01", "100")
    _price("AAPL", "2026-01-02", "100")
    r = api_client.get("/api/v1/portfolio/performance?metric=twror&range=ALL")
    pts = [p for p in r.json() if p["date"] == "2026-01-02"]
    assert pts and abs(pts[0]["value"] - 0.0) < 1e-6


@pytest.mark.django_db
def test_twror_price_increase(api_client, seeded, today_patch):
    _buy(api_client, quantity="1", price_per_share="100")
    _price("AAPL", "2026-01-01", "100")
    _price("AAPL", "2026-01-02", "110")
    r = api_client.get("/api/v1/portfolio/performance?metric=twror&range=ALL")
    pts = [p for p in r.json() if p["date"] == "2026-01-02"]
    assert pts and abs(pts[0]["value"] - 10.0) < 1e-6


@pytest.mark.django_db
def test_twror_zero_begin_value_safe(api_client, seeded, today_patch):
    _buy(api_client, date="2026-01-02", quantity="1", price_per_share="100")
    _price("AAPL", "2026-01-01", "100")
    _price("AAPL", "2026-01-02", "100")
    r = api_client.get("/api/v1/portfolio/performance?metric=twror&range=ALL")
    pts = [p for p in r.json() if p["date"] == "2026-01-02"]
    assert pts and pts[0]["value"] is None


@pytest.mark.django_db
def test_twror_non_all_range_rechains(api_client, seeded, today_patch):
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
def test_value_metric_ignores_benchmark(api_client, seeded, today_patch):
    _buy(api_client)
    _price("AAPL", "2026-01-01", "100")
    r = api_client.get(
        "/api/v1/portfolio/performance?metric=value&benchmarks=%5EGSPC"
    )
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.django_db
def test_benchmark_cumulative_return_comparison(api_client, seeded, today_patch):
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
def test_benchmark_twror_comparison(api_client, seeded, today_patch):
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
def test_benchmarks_legacy_first_symbol_only(api_client, seeded, today_patch):
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
def test_invalid_benchmark_422(api_client, seeded, today_patch):
    _buy(api_client)
    _price("AAPL", "2026-01-01", "100")
    r = api_client.get(
        "/api/v1/portfolio/performance?metric=cumulative_return&benchmark=%5ENOTREAL"
    )
    assert r.status_code == 422


@pytest.mark.django_db
def test_disabled_benchmark_422(api_client, seeded, today_patch):
    BenchmarkIndexConfig.objects.filter(symbol="^GSPC").update(enabled=False)
    _buy(api_client)
    _price("AAPL", "2026-01-01", "100")
    r = api_client.get(
        "/api/v1/portfolio/performance?metric=cumulative_return&benchmark=%5EGSPC"
    )
    assert r.status_code == 422


@pytest.mark.django_db
def test_benchmark_missing_prices_warning(api_client, seeded, today_patch):
    _buy(api_client)
    _price("AAPL", "2026-01-01", "100")
    r = api_client.get(
        "/api/v1/portfolio/performance?metric=cumulative_return&benchmark=%5EGSPC"
    )
    assert r.status_code == 200
    assert r.json()["warnings"]
    assert len(r.json()["series"]) == 1


@pytest.mark.django_db
def test_benchmark_uses_index_not_stock_rows(api_client, seeded, today_patch):
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
def test_benchmark_no_yfinance(mock_dl, api_client, seeded, today_patch):
    _buy(api_client)
    _price("AAPL", "2026-01-01", "100")
    _index_price("^GSPC", "2026-01-01", "1000")
    api_client.get(
        "/api/v1/portfolio/performance?metric=cumulative_return&benchmark=%5EGSPC"
    )
    mock_dl.assert_not_called()


@pytest.mark.django_db
def test_empty_portfolio_returns_empty_series(api_client, seeded, today_patch):
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


def _last_valid_performance_value(pts: list[dict]) -> float:
    for pt in reversed(pts):
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


def _setup_pln_stock_inr_mf_all_scope(api_client, monkeypatch):
    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2024, 4, 15))
    eur_portfolio = Portfolio.objects.create(
        name="EUR PLN Stock", base_currency="EUR", is_active=True
    )
    inr_portfolio = Portfolio.objects.create(
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
    api_client, seeded, monkeypatch
):
    """Value History (pooled scope) must match summary KPI when display currency is EUR."""
    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2026, 3, 20))
    stock_portfolio = Portfolio.objects.create(
        name="EUR Stocks Perf", base_currency="EUR", is_active=True
    )
    mf_portfolio = Portfolio.objects.create(
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
    api_client, seeded, monkeypatch
):
    """All-scope value history must not break when a PLN stock lacks PLN->INR FX."""
    _setup_pln_stock_inr_mf_all_scope(api_client, monkeypatch)

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
    api_client, seeded, monkeypatch
):
    _setup_pln_stock_inr_mf_all_scope(api_client, monkeypatch)

    perf = api_client.get(
        "/api/v1/portfolio/performance?portfolio_scope=all&display_currency=EUR&metric=cumulative_return&range=ALL"
    ).json()
    after_buy = [p for p in perf if p["date"] >= "2024-04-01"]
    assert after_buy
    assert all(p["value"] is not None for p in after_buy)
    assert _largest_valid_gap_days(perf) <= 1


@pytest.mark.django_db
def test_performance_all_scope_twror_no_gap_with_pln_stock_and_inr_mf(
    api_client, seeded, monkeypatch
):
    _setup_pln_stock_inr_mf_all_scope(api_client, monkeypatch)

    perf = api_client.get(
        "/api/v1/portfolio/performance?portfolio_scope=all&display_currency=EUR&metric=twror&range=ALL"
    ).json()
    after_buy = [p for p in perf if p["date"] >= "2024-04-02"]
    assert after_buy
    assert all(p["value"] is not None for p in after_buy)
    assert _largest_valid_gap_days(perf) <= 1


@pytest.mark.django_db
def test_performance_all_scope_value_cumulative_twror_share_valid_calendar(
    api_client, seeded, monkeypatch
):
    _setup_pln_stock_inr_mf_all_scope(api_client, monkeypatch)

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
    api_client, seeded, monkeypatch
):
    """All-scope display conversion must bulk-load FX, not query per calendar day."""
    from django.db import connection, reset_queries
    from django.test.utils import CaptureQueriesContext

    from portfolios.performance_service import build_portfolio_performance
    from portfolios.scope import resolve_portfolio_scope

    _setup_pln_stock_inr_mf_all_scope(api_client, monkeypatch)
    scope = resolve_portfolio_scope(portfolio_scope="all")

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
