"""FIX-2 — All Portfolios summary aggregates per-portfolio converted values."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from fx.services import upsert_fx_rate
from market_data.models import AssetType, HistoricalPrice
from portfolios.models import Portfolio
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


def _summary(api_client, *, portfolio_id=None, portfolio_scope=None, display_currency="EUR"):
    params = f"display_currency={display_currency}&include_timeseries=false"
    if portfolio_id is not None:
        params = f"portfolio_id={portfolio_id}&{params}"
    elif portfolio_scope:
        params = f"portfolio_scope={portfolio_scope}&{params}"
    return api_client.get(f"/api/v1/portfolio/summary?{params}").json()


def _sum_individual_fields(api_client, portfolio_ids, display_currency="EUR"):
    totals = {
        "current_value": 0.0,
        "total_invested": 0.0,
        "realized_pl": 0.0,
        "unrealized_pl": 0.0,
        "total_pl": 0.0,
    }
    rows = []
    for pid in portfolio_ids:
        data = _summary(api_client, portfolio_id=pid, display_currency=display_currency)
        rows.append(data)
        for key in totals:
            totals[key] += float(data[key])
    return totals, rows


def _assert_all_matches_sum(api_client, portfolio_ids, display_currency="EUR"):
    totals, _ = _sum_individual_fields(api_client, portfolio_ids, display_currency)
    all_data = _summary(
        api_client, portfolio_scope="all", display_currency=display_currency
    )
    for key in totals:
        assert all_data[key] == pytest.approx(totals[key], rel=1e-4, abs=1e-2), key
    assert all_data["display_currency"] == display_currency
    assert all_data["base_currency"] == display_currency
    return all_data, totals


@pytest.mark.django_db
def test_all_scope_mixed_eur_stock_and_inr_mf(api_client, seeded, monkeypatch):
    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2026, 3, 20))
    stock_portfolio = Portfolio.objects.create(
        name="EUR Stocks", base_currency="EUR", is_active=True
    )
    mf_portfolio = Portfolio.objects.create(
        name="INR MF", base_currency="INR", is_active=True
    )
    _buy_stock(api_client, portfolio_id=stock_portfolio.id, asset_symbol="AAPL")
    _mf_buy(
        api_client,
        portfolio_id=mf_portfolio.id,
        scheme_code="120503",
        folio_number="MF-FOLIO-1",
    )
    _stock_price("AAPL", "2026-03-20", "120")
    _mf_nav("120503", "2026-03-20", "50.00")
    upsert_fx_rate(
        from_currency="INR",
        to_currency="EUR",
        row_date=date(2026, 3, 20),
        rate=Decimal("0.01"),
    )

    portfolio_ids = [stock_portfolio.id, mf_portfolio.id]
    stock = _summary(api_client, portfolio_id=stock_portfolio.id, display_currency="EUR")
    mf = _summary(api_client, portfolio_id=mf_portfolio.id, display_currency="EUR")
    all_data, totals = _assert_all_matches_sum(api_client, portfolio_ids, "EUR")

    assert stock["current_value"] == pytest.approx(1200.0, rel=1e-2)
    assert mf["current_value"] == pytest.approx(50.0, rel=1e-2)
    assert all_data["current_value"] == pytest.approx(
        stock["current_value"] + mf["current_value"], rel=1e-4
    )
    assert totals["current_value"] == pytest.approx(1250.0, rel=1e-2)


@pytest.mark.django_db
def test_all_scope_two_inr_mf_portfolios_same_scheme_folio(api_client, seeded, monkeypatch):
    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2026, 3, 20))
    p1 = Portfolio.objects.create(name="MF One", base_currency="INR", is_active=True)
    p2 = Portfolio.objects.create(name="MF Two", base_currency="INR", is_active=True)
    _mf_buy(
        api_client,
        portfolio_id=p1.id,
        scheme_code="120504",
        folio_number="FOLIO-P1",
        units_allotted="100.00000000",
        paid_value="4255.00",
    )
    _mf_buy(
        api_client,
        portfolio_id=p2.id,
        scheme_code="120505",
        folio_number="FOLIO-P2",
        units_allotted="50.00000000",
        paid_value="2127.50",
    )
    _mf_nav("120504", "2026-03-20", "50.00")
    _mf_nav("120505", "2026-03-20", "40.00")
    upsert_fx_rate(
        from_currency="INR",
        to_currency="EUR",
        row_date=date(2026, 3, 20),
        rate=Decimal("0.01"),
    )

    portfolio_ids = [p1.id, p2.id]
    _assert_all_matches_sum(api_client, portfolio_ids, "EUR")


@pytest.mark.django_db
def test_all_scope_display_currency_inr(api_client, seeded, monkeypatch):
    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2026, 3, 20))
    stock_portfolio = Portfolio.objects.create(
        name="EUR Stocks", base_currency="EUR", is_active=True
    )
    mf_portfolio = Portfolio.objects.create(
        name="INR MF", base_currency="INR", is_active=True
    )
    _buy_stock(api_client, portfolio_id=stock_portfolio.id)
    _mf_buy(api_client, portfolio_id=mf_portfolio.id, folio_number="INR-F1")
    _stock_price("AAPL", "2026-03-20", "120")
    _mf_nav("120503", "2026-03-20", "50.00")
    upsert_fx_rate(
        from_currency="EUR",
        to_currency="INR",
        row_date=date(2026, 3, 20),
        rate=Decimal("90"),
    )

    portfolio_ids = [stock_portfolio.id, mf_portfolio.id]
    _assert_all_matches_sum(api_client, portfolio_ids, "INR")


@pytest.mark.django_db
def test_all_scope_excludes_inactive_portfolio(api_client, seeded):
    active = Portfolio.objects.create(name="Active", base_currency="EUR", is_active=True)
    inactive = Portfolio.objects.create(
        name="Inactive", base_currency="EUR", is_active=False
    )
    _buy_stock(api_client, portfolio_id=active.id, asset_symbol="AAA", quantity="1", price_per_share="100")
    _buy_stock(api_client, portfolio_id=inactive.id, asset_symbol="ZZZ", quantity="1", price_per_share="999")
    _stock_price("AAA", "2026-03-01", "110")
    _stock_price("ZZZ", "2026-03-01", "999")

    all_data = _summary(api_client, portfolio_scope="all", display_currency="EUR")
    active_data = _summary(api_client, portfolio_id=active.id, display_currency="EUR")

    assert all_data["current_value"] == pytest.approx(active_data["current_value"], rel=1e-4)
    assert all_data["current_value"] == pytest.approx(110.0, rel=1e-2)


@pytest.mark.django_db
def test_all_scope_includes_default_portfolio_once(api_client, seeded):
    default = ensure_default_portfolio()
    extra = Portfolio.objects.create(name="Extra", base_currency="EUR", is_active=True)
    _buy_stock(api_client, portfolio_id=default.id, asset_symbol="AAA", quantity="1", price_per_share="10")
    _buy_stock(api_client, portfolio_id=extra.id, asset_symbol="BBB", quantity="1", price_per_share="20")
    _stock_price("AAA", "2026-03-01", "10")
    _stock_price("BBB", "2026-03-01", "20")

    _assert_all_matches_sum(api_client, [default.id, extra.id], "EUR")


@pytest.mark.django_db
def test_all_scope_monetary_fields_equal_sum(api_client, seeded, monkeypatch):
    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2026, 3, 20))
    p1 = Portfolio.objects.create(name="P1", base_currency="EUR", is_active=True)
    p2 = Portfolio.objects.create(name="P2", base_currency="INR", is_active=True)
    _buy_stock(api_client, portfolio_id=p1.id, asset_symbol="MSFT", quantity="2", price_per_share="50")
    _mf_buy(api_client, portfolio_id=p2.id, folio_number="MF-P2")
    _stock_price("MSFT", "2026-03-20", "60")
    _mf_nav("120503", "2026-03-20", "50.00")
    upsert_fx_rate(
        from_currency="INR",
        to_currency="EUR",
        row_date=date(2026, 3, 20),
        rate=Decimal("0.01"),
    )

    totals, _ = _sum_individual_fields(api_client, [p1.id, p2.id], "EUR")
    all_data = _summary(api_client, portfolio_scope="all", display_currency="EUR")

    assert all_data["total_invested"] == pytest.approx(totals["total_invested"], rel=1e-4)
    assert all_data["realized_pl"] == pytest.approx(totals["realized_pl"], rel=1e-4)
    assert all_data["unrealized_pl"] == pytest.approx(totals["unrealized_pl"], rel=1e-4)
    assert all_data["total_pl"] == pytest.approx(totals["total_pl"], rel=1e-4)


@pytest.mark.django_db
def test_all_scope_fx_status_worst_child(api_client, seeded):
    ok_portfolio = Portfolio.objects.create(name="OK", base_currency="EUR", is_active=True)
    _buy_stock(api_client, portfolio_id=ok_portfolio.id, asset_symbol="AAA", quantity="1", price_per_share="100")
    _stock_price("AAA", "2026-03-01", "100")

    all_data = _summary(api_client, portfolio_scope="all", display_currency="EUR")
    assert all_data["fx_status"] == "ok"

    bad_portfolio = Portfolio.objects.create(name="Bad FX", base_currency="EUR", is_active=True)
    _buy_stock(api_client, portfolio_id=bad_portfolio.id, asset_symbol="BBB", quantity="1", price_per_share="100")
    _stock_price("BBB", "2026-03-01", "100", currency="USD")

    all_data = _summary(api_client, portfolio_scope="all", display_currency="EUR")
    assert all_data["fx_status"] == "fx_unavailable"


@pytest.mark.django_db
def test_all_scope_fx_status_filled_when_child_filled(api_client, seeded, monkeypatch):
    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2026, 3, 20))
    p = Portfolio.objects.create(name="Filled", base_currency="INR", is_active=True)
    _mf_buy(api_client, portfolio_id=p.id, investment_date="2026-03-01", nav_date="2026-03-10")
    _mf_nav("120503", "2026-03-20", "50.00")
    upsert_fx_rate(
        from_currency="INR",
        to_currency="EUR",
        row_date=date(2026, 3, 19),
        rate=Decimal("0.01"),
    )

    all_data = _summary(api_client, portfolio_scope="all", display_currency="EUR")
    assert all_data["fx_status"] in {"ok", "filled"}
