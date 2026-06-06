"""MF-5 — mutual fund summary and performance integration tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from fx.services import upsert_fx_rate
from market_data.models import AssetType, HistoricalPrice
from portfolios.seed import ensure_default_portfolio


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


def _mf_sell(api_client, **kwargs):
    return api_client.post(
        "/api/v1/transactions",
        _mf_payload(type="SELL", **kwargs),
        format="json",
    )


def _buy_stock(api_client, **kwargs):
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


def _stock_price(symbol: str, d: str, close: str, *, currency: str = "EUR"):
    HistoricalPrice.objects.create(
        asset_symbol=symbol,
        date=date.fromisoformat(d),
        close_price=Decimal(close),
        currency=currency,
        source="test",
        asset_type=AssetType.STOCK,
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
def test_summary_single_mf_buy_with_cached_nav(api_client, legacy_seeded):
    _mf_buy(api_client)
    _mf_nav("120503", "2026-03-20", "50.00")
    data = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false"
    ).json()
    assert data["current_value"] == pytest.approx(5000.0, rel=1e-2)
    assert data["total_invested"] == pytest.approx(4250.0, rel=1e-2)


@pytest.mark.django_db
def test_summary_stock_plus_mf_mixed(api_client, legacy_seeded, monkeypatch, test_user):
    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2026, 3, 20))
    default = ensure_default_portfolio(test_user)
    _buy_stock(api_client, portfolio_id=default.id)
    _mf_buy(api_client, portfolio_id=default.id)
    _stock_price("AAPL", "2026-03-20", "120")
    _mf_nav("120503", "2026-03-20", "50.00")
    upsert_fx_rate(
        from_currency="INR",
        to_currency="EUR",
        row_date=date(2026, 3, 20),
        rate=Decimal("0.01"),
    )
    data = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false"
    ).json()
    # Stock 10×120 EUR + MF 100×50 INR → 50 EUR at 0.01
    assert data["current_value"] == pytest.approx(1250.0, rel=1e-2)


@pytest.mark.django_db
def test_summary_mf_missing_nav_warning_and_zero_value(api_client, legacy_seeded):
    _mf_buy(api_client)
    data = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false"
    ).json()
    assert data["current_value"] == 0.0
    assert any("NAV" in w for w in data["warnings"])


@pytest.mark.django_db
def test_summary_mf_display_currency_inr_to_eur(api_client, legacy_seeded, monkeypatch):
    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2026, 3, 20))
    _mf_buy(api_client, investment_date="2026-03-10", nav_date="2026-03-15")
    _mf_nav("120503", "2026-03-20", "50.00")
    upsert_fx_rate(
        from_currency="INR",
        to_currency="EUR",
        row_date=date(2026, 3, 20),
        rate=Decimal("0.01"),
    )
    data = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false&display_currency=EUR"
    ).json()
    assert data["current_value"] == pytest.approx(50.0, rel=1e-2)
    assert data["fx_status"] == "ok"


@pytest.mark.django_db
def test_summary_timeseries_includes_mf_value(api_client, legacy_seeded):
    _mf_buy(api_client, nav_date="2026-03-15", investment_date="2026-03-10")
    _mf_nav("120503", "2026-03-15", "40.00")
    _mf_nav("120503", "2026-03-17", "45.00")
    ts = api_client.get("/api/v1/portfolio/summary?include_timeseries=true").json()[
        "timeseries"
    ]
    mar16 = next(p for p in ts if p["date"] == "2026-03-16")
    assert mar16["portfolio_value"] == pytest.approx(4000.0, rel=1e-2)


@pytest.mark.django_db
def test_summary_mf_nav_forward_fill(api_client, legacy_seeded):
    _mf_buy(api_client, nav_date="2026-03-15")
    _mf_nav("120503", "2026-03-15", "40.00")
    _mf_nav("120503", "2026-03-17", "44.00")
    ts = api_client.get("/api/v1/portfolio/summary?include_timeseries=true").json()[
        "timeseries"
    ]
    mar16 = next(p for p in ts if p["date"] == "2026-03-16")
    assert mar16["portfolio_value"] == pytest.approx(4000.0, rel=1e-2)


@pytest.mark.django_db
def test_summary_mf_xirr_uses_investment_date_and_paid_value(
    api_client, legacy_seeded, monkeypatch
):
    # Default summary scope is all_active with EUR display; INR MF flows need FX for XIRR.
    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2026, 3, 20))
    _mf_buy(
        api_client,
        investment_date="2025-06-01",
        nav_date="2025-06-10",
        paid_value="10000.00",
        market_value="10000.00",
        units_allotted="200.00000000",
        nav="50.000000",
    )
    _mf_nav("120503", "2026-03-20", "60.00")
    for d in (date(2025, 6, 1), date(2026, 3, 20)):
        upsert_fx_rate(
            from_currency="INR",
            to_currency="EUR",
            row_date=d,
            rate=Decimal("0.01"),
        )
    data = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false"
    ).json()
    assert data["xirr"] is not None


@pytest.mark.django_db
def test_summary_mf_sell_affects_realized_pl(api_client, legacy_seeded):
    _mf_buy(api_client, units_allotted="100.00000000")
    _mf_sell(
        api_client,
        units_allotted="50.00000000",
        nav="60.000000",
        paid_value="3000.00",
        market_value="3000.00",
        investment_date="2026-04-01",
        nav_date="2026-04-01",
    )
    _mf_nav("120503", "2026-03-20", "50.00")
    data = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false"
    ).json()
    assert data["realized_pl"] != 0.0
    assert data["current_value"] == pytest.approx(2500.0, rel=1e-2)


@pytest.mark.django_db
def test_performance_value_includes_mf(api_client, legacy_seeded, monkeypatch):
    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2026, 3, 20))
    _mf_buy(api_client, nav_date="2026-03-15")
    _mf_nav("120503", "2026-03-15", "50.00")
    _mf_nav("120503", "2026-03-20", "55.00")
    pts = api_client.get(
        "/api/v1/portfolio/performance?metric=value&range=ALL&display_currency=INR"
    ).json()
    last = [p for p in pts if p["date"] == "2026-03-20" and p["value"] is not None][-1]
    assert last["value"] == pytest.approx(5500.0, rel=1e-2)


@pytest.mark.django_db
def test_performance_cumulative_return_includes_mf(api_client, legacy_seeded, monkeypatch):
    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2026, 3, 20))
    _mf_buy(api_client, investment_date="2026-03-10", nav_date="2026-03-15")
    _mf_nav("120503", "2026-03-15", "45.00")
    _mf_nav("120503", "2026-03-20", "50.00")
    for d in (date(2026, 3, 10), date(2026, 3, 15), date(2026, 3, 20)):
        upsert_fx_rate(
            from_currency="INR",
            to_currency="EUR",
            row_date=d,
            rate=Decimal("0.01"),
        )
    pts = api_client.get(
        "/api/v1/portfolio/performance?metric=cumulative_return&range=ALL"
    ).json()
    last = [p for p in pts if p["date"] == "2026-03-20" and p["value"] is not None]
    assert last
    assert last[-1]["metric"] == "cumulative_return"


@pytest.mark.django_db
def test_performance_twror_includes_mf(api_client, legacy_seeded, monkeypatch):
    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2026, 3, 20))
    _mf_buy(api_client, investment_date="2026-03-10", nav_date="2026-03-15")
    _mf_nav("120503", "2026-03-15", "45.00")
    _mf_nav("120503", "2026-03-20", "50.00")
    for d in (date(2026, 3, 10), date(2026, 3, 15), date(2026, 3, 20)):
        upsert_fx_rate(
            from_currency="INR",
            to_currency="EUR",
            row_date=d,
            rate=Decimal("0.01"),
        )
    pts = api_client.get(
        "/api/v1/portfolio/performance?metric=twror&range=ALL"
    ).json()
    assert pts
    assert any(p["value"] is not None for p in pts)


@pytest.mark.django_db
def test_performance_benchmark_still_works_with_mf(api_client, legacy_seeded, monkeypatch):
    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2026, 3, 20))
    from market_data.models import BenchmarkIndexConfig

    BenchmarkIndexConfig.objects.get_or_create(
        symbol="^GSPC",
        defaults={"display_name": "S&P 500", "enabled": True},
    )
    _buy_stock(api_client)
    _mf_buy(api_client, nav_date="2026-03-15")
    _stock_price("AAPL", "2026-03-15", "100")
    _stock_price("AAPL", "2026-03-20", "110")
    _mf_nav("120503", "2026-03-15", "50.00")
    upsert_fx_rate(
        from_currency="INR",
        to_currency="EUR",
        row_date=date(2026, 3, 15),
        rate=Decimal("0.01"),
    )
    upsert_fx_rate(
        from_currency="INR",
        to_currency="EUR",
        row_date=date(2026, 3, 20),
        rate=Decimal("0.01"),
    )
    HistoricalPrice.objects.create(
        asset_symbol="^GSPC",
        date=date(2026, 3, 15),
        close_price=Decimal("5000"),
        currency="USD",
        source="test",
        asset_type=AssetType.INDEX,
    )
    HistoricalPrice.objects.create(
        asset_symbol="^GSPC",
        date=date(2026, 3, 20),
        close_price=Decimal("5100"),
        currency="USD",
        source="test",
        asset_type=AssetType.INDEX,
    )
    r = api_client.get(
        "/api/v1/portfolio/performance?metric=cumulative_return&range=ALL"
        "&benchmark=^GSPC"
    )
    assert r.status_code == 200
    body = r.json()
    assert "series" in body
    assert body["series"]


@pytest.mark.django_db
def test_summary_no_external_nav_provider(api_client, legacy_seeded):
    _mf_buy(api_client)
    _mf_nav("120503", "2026-03-20", "50.00")
    with patch(
        "market_data.providers.mutual_fund_nav_provider.AmfiNavProvider.get_latest_nav"
    ) as mocked:
        api_client.get("/api/v1/portfolio/summary?include_timeseries=false")
        mocked.assert_not_called()


@pytest.mark.django_db
def test_performance_no_external_nav_provider(api_client, legacy_seeded, monkeypatch):
    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2026, 3, 20))
    _mf_buy(api_client)
    _mf_nav("120503", "2026-03-20", "50.00")
    with patch(
        "market_data.providers.mutual_fund_nav_provider.AmfiNavProvider.get_latest_nav"
    ) as mocked:
        api_client.get("/api/v1/portfolio/performance?metric=value&range=ALL")
        mocked.assert_not_called()
