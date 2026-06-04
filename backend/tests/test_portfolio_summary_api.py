from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.test.utils import CaptureQueriesContext
from django.db import connection

from fx.models import FXRate
from fx.services import upsert_fx_rate
from market_data.models import AssetType, HistoricalPrice
from portfolios.models import Portfolio
from portfolios.seed import ensure_default_portfolio
from transactions.models import Transaction, TransactionType


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


def _price(symbol: str, d: str, close: str, *, currency: str = "EUR"):
    HistoricalPrice.objects.create(
        asset_symbol=symbol,
        date=date.fromisoformat(d),
        close_price=Decimal(close),
        currency=currency,
        source="test",
        asset_type=AssetType.STOCK,
    )


@pytest.mark.django_db
def test_summary_defaults_to_scope_all(api_client, seeded):
    r = api_client.get("/api/v1/portfolio/summary?include_timeseries=false")
    assert r.status_code == 200
    assert "total_invested" in r.json()


@pytest.mark.django_db
def test_summary_scope_all_includes_active_portfolios(api_client, seeded, test_user):
    p1 = ensure_default_portfolio(test_user)
    p2 = Portfolio.objects.create(user=test_user, name="P2", base_currency="EUR", is_active=True)
    _buy(api_client, asset_symbol="AAA", portfolio_id=p1.id)
    _buy(api_client, asset_symbol="BBB", portfolio_id=p2.id)
    _price("AAA", "2026-03-01", "10")
    _price("BBB", "2026-03-01", "20")
    r = api_client.get("/api/v1/portfolio/summary?include_timeseries=false&portfolio_scope=all")
    assert r.status_code == 200
    assert r.json()["current_value"] == 300.0


@pytest.mark.django_db
def test_summary_portfolio_id_filter(api_client, seeded, test_user):
    p1 = ensure_default_portfolio(test_user)
    p2 = Portfolio.objects.create(user=test_user, name="Scoped", base_currency="EUR", is_active=True)
    _buy(api_client, asset_symbol="AAA", portfolio_id=p1.id)
    _buy(api_client, asset_symbol="BBB", portfolio_id=p2.id)
    _price("AAA", "2026-03-01", "10")
    _price("BBB", "2026-03-01", "20")
    r = api_client.get(
        f"/api/v1/portfolio/summary?include_timeseries=false&portfolio_id={p2.id}"
    )
    assert r.json()["current_value"] == 200.0


@pytest.mark.django_db
def test_summary_scope_all_and_portfolio_id_422(api_client, seeded, test_user):
    p = ensure_default_portfolio(test_user)
    r = api_client.get(
        f"/api/v1/portfolio/summary?portfolio_scope=all&portfolio_id={p.id}"
    )
    assert r.status_code == 422


@pytest.mark.django_db
def test_summary_unknown_portfolio_id_404(api_client, seeded):
    r = api_client.get("/api/v1/portfolio/summary?portfolio_id=999999")
    assert r.status_code == 404


@pytest.mark.django_db
def test_summary_inactive_portfolio_id_404(api_client, seeded, test_user):
    p = Portfolio.objects.create(user=test_user, name="Inactive", base_currency="EUR", is_active=False)
    r = api_client.get(f"/api/v1/portfolio/summary?portfolio_id={p.id}")
    assert r.status_code == 404


@pytest.mark.django_db
def test_summary_invalid_display_currency_400(api_client, seeded):
    r = api_client.get("/api/v1/portfolio/summary?display_currency=JPY")
    assert r.status_code == 400


@pytest.mark.django_db
def test_include_timeseries_false_returns_empty(api_client, seeded):
    _buy(api_client)
    _price("AAPL", "2026-03-01", "110")
    r = api_client.get("/api/v1/portfolio/summary?include_timeseries=false")
    assert r.json()["timeseries"] == []


@pytest.mark.django_db
def test_include_timeseries_true_returns_points(api_client, seeded):
    _buy(api_client, date="2026-01-01")
    _price("AAPL", "2026-01-01", "100")
    _price("AAPL", "2026-01-02", "105")
    r = api_client.get("/api/v1/portfolio/summary?include_timeseries=true")
    assert len(r.json()["timeseries"]) >= 2


@pytest.mark.django_db
def test_buy_only_summary_metrics(api_client, seeded):
    _buy(api_client, quantity="10", price_per_share="100")
    _price("AAPL", "2026-03-01", "120")
    r = api_client.get("/api/v1/portfolio/summary?include_timeseries=false")
    data = r.json()
    assert data["total_invested"] == 1000.0
    assert data["current_value"] == 1200.0
    assert data["unrealized_pl"] == 200.0


@pytest.mark.django_db
def test_buy_sell_fifo_remaining_invested(api_client, seeded):
    _buy(api_client, date="2026-01-01", quantity="10", price_per_share="100")
    _sell(
        api_client,
        date="2026-01-15",
        quantity="8",
        price_per_share="130",
    )
    for d in ("2026-01-01", "2026-01-15", "2026-03-01"):
        _price("AAPL", d, "130")
    r = api_client.get("/api/v1/portfolio/summary?include_timeseries=false")
    data = r.json()
    assert data["total_invested"] == 200.0
    assert data["realized_pl"] == 240.0


@pytest.mark.django_db
def test_realized_pl_profitable_sell(api_client, seeded):
    _buy(api_client, date="2026-01-01", quantity="10", price_per_share="100")
    _sell(api_client, date="2026-01-10", quantity="5", price_per_share="150")
    _price("AAPL", "2026-03-01", "100")
    r = api_client.get("/api/v1/portfolio/summary?include_timeseries=false")
    assert r.json()["realized_pl"] == 250.0


@pytest.mark.django_db
def test_realized_pl_loss_sell(api_client, seeded):
    _buy(api_client, date="2026-01-01", quantity="10", price_per_share="100")
    _sell(api_client, date="2026-01-10", quantity="5", price_per_share="50")
    _price("AAPL", "2026-03-01", "100")
    r = api_client.get("/api/v1/portfolio/summary?include_timeseries=false")
    assert r.json()["realized_pl"] == -250.0


@pytest.mark.django_db
def test_total_pl_equals_realized_plus_unrealized(api_client, seeded):
    _buy(api_client, quantity="10", price_per_share="100")
    _price("AAPL", "2026-03-01", "115")
    data = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false"
    ).json()
    assert data["total_pl"] == pytest.approx(
        data["realized_pl"] + data["unrealized_pl"]
    )


@pytest.mark.django_db
def test_fully_sold_asset_zero_current_value(api_client, seeded):
    _buy(api_client, date="2026-01-01", quantity="10", price_per_share="100")
    _sell(api_client, date="2026-01-10", quantity="10", price_per_share="120")
    _price("AAPL", "2026-03-01", "200")
    data = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false"
    ).json()
    assert data["current_value"] == 0.0
    assert data["total_invested"] == 0.0


@pytest.mark.django_db
def test_stock_split_affects_summary(api_client, seeded):
    _buy(api_client, date="2026-01-01", quantity="10", price_per_share="100")
    api_client.post(
        "/api/v1/transactions",
        {
            "asset_symbol": "AAPL",
            "date": "2026-02-01",
            "type": "STOCK_SPLIT",
            "quantity": "0",
            "price_per_share": "0",
            "currency": "EUR",
            "split_from": "1",
            "split_to": "2",
            "fees": "0",
        },
        format="json",
    )
    _price("AAPL", "2026-03-01", "50")
    data = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false"
    ).json()
    assert data["current_value"] == 1000.0


@pytest.mark.django_db
def test_oversell_warning_in_summary(api_client, seeded):
    _buy(api_client, quantity="5", price_per_share="100")
    _sell(api_client, quantity="10", price_per_share="100")
    _price("AAPL", "2026-03-01", "100")
    data = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false"
    ).json()
    assert "warnings" in data
    assert any("Oversell" in w for w in data["warnings"])


@pytest.mark.django_db
def test_timeseries_forward_fill_weekend(api_client, seeded):
    _buy(api_client, date="2026-01-01", quantity="10", price_per_share="100")
    _price("AAPL", "2026-01-01", "100")
    _price("AAPL", "2026-01-03", "110")
    ts = api_client.get("/api/v1/portfolio/summary").json()["timeseries"]
    jan2 = next(p for p in ts if p["date"] == "2026-01-02")
    assert jan2["portfolio_value"] == 1000.0


@pytest.mark.django_db
def test_timeseries_missing_fx_null_value(api_client, seeded):
    _buy(api_client, date="2026-01-01", currency="EUR")
    _price("AAPL", "2026-01-01", "100", currency="USD")
    ts = api_client.get(
        "/api/v1/portfolio/summary?display_currency=EUR"
    ).json()["timeseries"]
    pt = next(p for p in ts if p["date"] == "2026-01-01")
    assert pt["portfolio_value"] is None
    assert pt["fx_status"] == "fx_unavailable"


@pytest.mark.django_db
def test_display_currency_same_fx_ok(api_client, seeded):
    _buy(api_client, currency="EUR")
    _price("AAPL", "2026-03-01", "110", currency="EUR")
    assert (
        api_client.get(
            "/api/v1/portfolio/summary?include_timeseries=false&display_currency=EUR"
        ).json()["fx_status"]
        == "ok"
    )


@pytest.mark.django_db
def test_display_currency_converted_with_fx(api_client, seeded):
    today = date.today().isoformat()
    _buy(api_client, currency="EUR", date="2026-01-01")
    _price("AAPL", today, "100", currency="USD")
    upsert_fx_rate(
        from_currency="USD",
        to_currency="EUR",
        row_date=date.today(),
        rate=Decimal("0.5"),
    )
    data = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false&display_currency=EUR"
    ).json()
    assert data["current_value"] == 500.0
    assert data["fx_status"] == "ok"


@pytest.mark.django_db
def test_display_currency_missing_fx_unavailable(api_client, seeded):
    _buy(api_client, currency="INR")
    _price("AAPL", "2026-03-01", "100", currency="USD")
    data = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false&display_currency=EUR"
    ).json()
    assert data["fx_status"] == "fx_unavailable"


@pytest.mark.django_db
def test_xirr_returned_when_calculable(api_client, seeded):
    _buy(api_client, date="2026-01-01", quantity="10", price_per_share="100")
    _price("AAPL", "2026-03-01", "150")
    data = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false"
    ).json()
    assert data["xirr"] is not None


@pytest.mark.django_db
def test_xirr_null_when_no_transactions(api_client, seeded):
    data = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false"
    ).json()
    assert data["xirr"] is None


@pytest.mark.django_db
def test_no_yfinance_on_summary(api_client, seeded):
    _buy(api_client)
    _price("AAPL", "2026-03-01", "100")
    with patch("yfinance.Ticker") as mock_ticker:
        r = api_client.get("/api/v1/portfolio/summary?include_timeseries=false")
    assert r.status_code == 200
    mock_ticker.assert_not_called()


@pytest.mark.django_db
def test_include_timeseries_false_fewer_price_queries(api_client, seeded):
    _buy(api_client, date="2026-01-01")
    _price("AAPL", "2026-01-01", "100")
    _price("AAPL", "2026-01-02", "101")
    with CaptureQueriesContext(connection) as ctx_false:
        api_client.get("/api/v1/portfolio/summary?include_timeseries=false")
    false_count = len(ctx_false.captured_queries)

    with CaptureQueriesContext(connection) as ctx_true:
        api_client.get("/api/v1/portfolio/summary?include_timeseries=true")
    true_count = len(ctx_true.captured_queries)

    assert false_count < true_count


@pytest.mark.django_db
def test_fifo_timeseries_invested_amount(api_client, seeded):
    _buy(api_client, date="2026-01-01", quantity="10", price_per_share="100")
    _buy(api_client, date="2026-01-05", quantity="5", price_per_share="120")
    _sell(api_client, date="2026-01-10", quantity="8", price_per_share="130")
    for d in ("2026-01-01", "2026-01-05", "2026-01-10", "2026-01-15"):
        _price("AAPL", d, "130")
    ts = api_client.get("/api/v1/portfolio/summary").json()["timeseries"]
    d10 = next(p for p in ts if p["date"] == "2026-01-10")
    assert d10["invested_amount"] == 800.0


@pytest.mark.django_db
def test_timeseries_fx_small_gap_filled_status(api_client, seeded):
    _buy(api_client, date="2026-01-01", quantity="1", currency="INR")
    _price("AAPL", "2026-01-01", "100", currency="USD")
    upsert_fx_rate(
        from_currency="USD",
        to_currency="INR",
        row_date=date(2026, 1, 1),
        rate=Decimal("80"),
    )
    ts = api_client.get("/api/v1/portfolio/summary").json()["timeseries"]
    jan2 = next(p for p in ts if p["date"] == "2026-01-02")
    assert jan2["portfolio_value"] == 8000.0
    assert jan2["fx_status"] == "filled"
