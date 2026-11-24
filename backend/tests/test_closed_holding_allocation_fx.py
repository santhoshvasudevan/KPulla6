"""Closed holdings cannot add exposure after native/display FX conversion (#32)."""
from datetime import date
from decimal import Decimal

import pytest

from fx.services import upsert_fx_rate
from market_data.models import AssetType, HistoricalPrice
from tests.test_analytics_asset_metrics_api import _mf_payload
from tests.conftest import cached_mf_nav


@pytest.mark.django_db
@pytest.mark.parametrize("closed_kind", ["STOCK", "MUTUAL_FUND"])
@pytest.mark.parametrize("fx_available", [True, False])
def test_closed_holding_excluded_and_open_fx_coverage_preserved(
    api_client, legacy_seeded, monkeypatch, closed_kind, fx_available,
):
    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2026, 3, 20))
    cached_mf_nav("120503", "2026-03-01", "42.5")
    if closed_kind == "MUTUAL_FUND":
        cached_mf_nav("120504", "2026-03-02", "100")
    assert api_client.post("/api/v1/transactions", _mf_payload(
        investment_date="2026-03-01", nav_date="2026-03-01",
    ), format="json").status_code == 201
    symbol = "CLOSED" if closed_kind == "STOCK" else "120504"
    for kind in ("BUY", "SELL"):
        if closed_kind == "STOCK":
            payload = {"asset_symbol": symbol, "type": kind, "date": "2026-03-02",
                       "quantity": "10", "price_per_share": "100", "fees": "0", "currency": "INR"}
        else:
            payload = _mf_payload(scheme_code=symbol, type=kind, folio_number="CLOSED",
                investment_date="2026-03-02", nav_date="2026-03-02", nav="100",
                units_allotted="10", paid_value="1000", market_value="1000", fees="0")
        response = api_client.post("/api/v1/transactions", payload, format="json")
        assert response.status_code == 201, response.json()
    for code, price, kind in (("120503", "50", AssetType.MUTUAL_FUND), (symbol, "9999", closed_kind)):
        HistoricalPrice.objects.create(asset_symbol=code, date=date(2026, 3, 20),
            close_price=Decimal(price), currency="INR", asset_type=kind)
    if fx_available:
        upsert_fx_rate(from_currency="INR", to_currency="EUR", row_date=date(2026, 3, 20), rate=Decimal("0.01"))
    response = api_client.get("/api/v1/portfolio/summary", {
        "display_currency": "EUR", "include_timeseries": "false",
    })
    assert response.status_code == 200, response.json()
    summary = response.json()
    buckets = summary["allocation_buckets"]
    assert buckets["currency"] == "EUR"
    expected = 50 if fx_available else 0
    assert sum(row["value"] for row in buckets["buckets"]) == pytest.approx(expected)
    if fx_available:
        assert summary["current_value"] == pytest.approx(expected)
    else:
        assert summary["fx_status"] == "fx_unavailable"
    assert (buckets["fx_status"] == "fx_unavailable") is (not fx_available)
    holdings = api_client.get("/api/v1/portfolio/holdings", {"display_currency": "EUR"}).json()["holdings"]
    closed = next(row for row in holdings if row["asset_symbol"] == symbol)
    assert closed["holding_status"] == "closed"
    assert closed["quantity"] == 0
