"""MF-4 — mutual fund holdings and asset detail API tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

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


def _nav(scheme: str, close: str, *, d: str = "2026-03-20"):
    HistoricalPrice.objects.create(
        asset_symbol=scheme,
        date=date.fromisoformat(d),
        close_price=Decimal(close),
        currency="INR",
        source="test",
        asset_type=AssetType.MUTUAL_FUND,
    )


@pytest.mark.django_db
def test_mf_buy_appears_in_holdings_grouped_by_scheme_and_folio(api_client, legacy_seeded, test_user):
    default = ensure_default_portfolio(test_user)
    _mf_buy(api_client, portfolio_id=default.id)
    _nav("120503", "50.00")
    holdings = api_client.get("/api/v1/portfolio/holdings").json()["holdings"]
    mf = [h for h in holdings if h.get("asset_type") == "MUTUAL_FUND"]
    assert len(mf) == 1
    row = mf[0]
    assert row["asset_symbol"] == "120503"
    assert row["scheme_code"] == "120503"
    assert row["folio_number"] == "FOLIO-12345"
    assert row["scheme_name"] == "Test Direct Growth Fund"
    assert row["holding_key"] == "120503:FOLIO-12345"
    assert row["quantity"] == 100.0
    assert row["units"] == 100.0
    assert row["currency"] == "INR"


@pytest.mark.django_db
def test_same_scheme_two_folios_two_holdings(api_client, legacy_seeded):
    _mf_buy(api_client, folio_number="FOLIO-A")
    _mf_buy(api_client, folio_number="FOLIO-B")
    _nav("120503", "50.00")
    mf = [h for h in api_client.get("/api/v1/portfolio/holdings").json()["holdings"] if h.get("asset_type") == "MUTUAL_FUND"]
    assert len(mf) == 2
    folios = {h["folio_number"] for h in mf}
    assert folios == {"FOLIO-A", "FOLIO-B"}


@pytest.mark.django_db
def test_same_scheme_same_folio_combines_transactions(api_client, legacy_seeded):
    _mf_buy(api_client, folio_number="FOLIO-ONE", units_allotted="50.00000000", paid_value="2125.00", market_value="2125.00")
    _mf_buy(
        api_client,
        folio_number="FOLIO-ONE",
        nav_date="2026-04-01",
        investment_date="2026-03-28",
        units_allotted="50.00000000",
        paid_value="2200.00",
        market_value="2200.00",
    )
    _nav("120503", "50.00")
    mf = [h for h in api_client.get("/api/v1/portfolio/holdings").json()["holdings"] if h.get("asset_type") == "MUTUAL_FUND"]
    assert len(mf) == 1
    assert mf[0]["folio_number"] == "FOLIO-ONE"
    assert mf[0]["quantity"] == 100.0


@pytest.mark.django_db
def test_mf_sell_reduces_units_and_invested(api_client, legacy_seeded):
    _mf_buy(api_client, units_allotted="100.00000000")
    _mf_sell(api_client, units_allotted="40.00000000", paid_value="2000.00", market_value="2000.00")
    _nav("120503", "50.00")
    row = [h for h in api_client.get("/api/v1/portfolio/holdings").json()["holdings"] if h.get("asset_type") == "MUTUAL_FUND"][0]
    assert row["quantity"] == 60.0
    assert row["invested_amount"] == pytest.approx(2553.0, rel=1e-2)


@pytest.mark.django_db
def test_fully_sold_mf_holding_closed(api_client, legacy_seeded):
    _mf_buy(api_client, units_allotted="100.00000000")
    _mf_sell(api_client, units_allotted="100.00000000", paid_value="5000.00", market_value="5000.00")
    _nav("120503", "50.00")
    row = [h for h in api_client.get("/api/v1/portfolio/holdings").json()["holdings"] if h.get("asset_type") == "MUTUAL_FUND"][0]
    assert row["quantity"] == 0.0
    assert row["holding_status"] == "closed"


@pytest.mark.django_db
def test_missing_nav_nav_missing_and_zero_current_value(api_client, legacy_seeded):
    _mf_buy(api_client)
    row = [h for h in api_client.get("/api/v1/portfolio/holdings").json()["holdings"] if h.get("asset_type") == "MUTUAL_FUND"][0]
    assert row["nav_status"] == "nav_missing"
    assert row["price_status"] == "price_missing"
    assert row["latest_nav"] is None
    assert row["current_value"] == 0.0
    assert any("nav" in w.lower() for w in row["warnings"])


@pytest.mark.django_db
def test_cached_nav_calculates_current_value(api_client, legacy_seeded):
    _mf_buy(api_client, units_allotted="100.00000000")
    _nav("120503", "55.25")
    row = [h for h in api_client.get("/api/v1/portfolio/holdings").json()["holdings"] if h.get("asset_type") == "MUTUAL_FUND"][0]
    assert row["nav_status"] == "ok"
    assert row["latest_nav"] == 55.25
    assert row["latest_price"] == 55.25
    assert row["current_value"] == pytest.approx(5525.0, rel=1e-2)


@pytest.mark.django_db
def test_mf_oversell_status_and_warning(api_client, legacy_seeded):
    _mf_buy(api_client, units_allotted="10.00000000")
    _mf_sell(api_client, units_allotted="15.00000000", paid_value="750.00", market_value="750.00")
    _nav("120503", "50.00")
    row = [h for h in api_client.get("/api/v1/portfolio/holdings").json()["holdings"] if h.get("asset_type") == "MUTUAL_FUND"][0]
    assert row["holding_status"] == "oversold"
    assert any("exceeded" in w.lower() for w in row["warnings"])


@pytest.mark.django_db
def test_mf_asset_detail_with_folio_number(api_client, legacy_seeded):
    _mf_buy(api_client, folio_number="FOLIO-X")
    _nav("120503", "48.00")
    r = api_client.get("/api/v1/portfolio/assets/120503?folio_number=FOLIO-X")
    assert r.status_code == 200
    data = r.json()
    assert data["asset_type"] == "MUTUAL_FUND"
    assert data["scheme_code"] == "120503"
    assert data["folio_number"] == "FOLIO-X"
    assert data["scheme_name"] == "Test Direct Growth Fund"
    assert data["latest_nav"] == 48.0
    assert data["nav_status"] == "ok"
    assert data["cumulative_qty"] == 100.0
    assert len(data["transactions"]) == 1
    assert data["transactions"][0]["folio_number"] == "FOLIO-X"
    assert data["transactions"][0]["nav_date"] == "2026-03-15"


@pytest.mark.django_db
def test_mf_asset_detail_single_folio_without_query_param(api_client, legacy_seeded):
    _mf_buy(api_client, folio_number="ONLY-FOLIO")
    _nav("120503", "48.00")
    r = api_client.get("/api/v1/portfolio/assets/120503")
    assert r.status_code == 200
    assert r.json()["folio_number"] == "ONLY-FOLIO"


@pytest.mark.django_db
def test_mf_asset_detail_multiple_folios_requires_folio_number(api_client, legacy_seeded):
    _mf_buy(api_client, folio_number="F1")
    _mf_buy(api_client, folio_number="F2", nav_date="2026-04-01", investment_date="2026-03-28")
    r = api_client.get("/api/v1/portfolio/assets/120503")
    assert r.status_code == 400
    assert "folio_number" in r.json()["detail"].lower()


@pytest.mark.django_db
def test_holdings_no_external_nav_provider(api_client, legacy_seeded):
    _mf_buy(api_client)
    _nav("120503", "50.00")
    with patch("market_data.providers.mutual_fund_nav_provider.AmfiNavProvider.get_latest_nav") as mocked:
        api_client.get("/api/v1/portfolio/holdings")
        mocked.assert_not_called()


@pytest.mark.django_db
def test_asset_detail_no_external_nav_provider(api_client, legacy_seeded):
    _mf_buy(api_client)
    _nav("120503", "50.00")
    with patch("market_data.providers.mutual_fund_nav_provider.AmfiNavProvider.get_latest_nav") as mocked:
        api_client.get("/api/v1/portfolio/assets/120503?folio_number=FOLIO-12345")
        mocked.assert_not_called()


@pytest.mark.django_db
def test_stock_holdings_unchanged_shape(api_client, legacy_seeded, test_user):
    default = ensure_default_portfolio(test_user)
    api_client.post(
        "/api/v1/transactions",
        {
            "asset_symbol": "AAPL",
            "date": "2026-01-01",
            "type": "BUY",
            "quantity": "10",
            "price_per_share": "100",
            "currency": "EUR",
            "fees": "0",
            "portfolio_id": default.id,
        },
        format="json",
    )
    HistoricalPrice.objects.create(
        asset_symbol="AAPL",
        date=date(2026, 3, 1),
        close_price=Decimal("120"),
        currency="EUR",
        source="test",
        asset_type=AssetType.STOCK,
    )
    row = api_client.get("/api/v1/portfolio/holdings").json()["holdings"][0]
    assert "asset_type" not in row
    assert row["asset_symbol"] == "AAPL"
    assert "folio_number" not in row
    assert "nav_status" not in row


@pytest.mark.django_db
def test_assets_overview_converts_hybrid_and_liquid_funds_in_selected_scope(
    api_client, legacy_seeded, test_user,
):
    from fx.services import upsert_fx_rate
    from portfolios import dates
    from portfolios.models import Portfolio

    selected = ensure_default_portfolio(test_user)
    other = Portfolio.objects.create(user=test_user, name="Other", cash_aware_enabled=False)
    for code, name, portfolio in (
        ("120503", "Test Balanced Advantage Fund", selected),
        ("120504", "Test Money Market Fund", selected),
        ("120505", "Other Equity Fund", other),
    ):
        assert _mf_buy(api_client, scheme_code=code, scheme_name=name,
                       portfolio_id=portfolio.id).status_code == 201
        _nav(code, "50.00")
    upsert_fx_rate(from_currency="INR", to_currency="EUR",
                   row_date=dates.current_date(), rate=Decimal("0.01"))
    url = f"/api/v1/portfolio/holdings?portfolio_id={selected.id}&display_currency=EUR"
    data = api_client.get(url).json()
    assert data["assets_overview"] == {"equity": 50, "debt": 50, "cash": 0}
    rows = {row["scheme_code"]: row for row in data["holdings"]}
    assert set(rows) == {"120503", "120504"}
    assert rows["120503"]["primary_asset_class"] == "HYBRID"
    assert rows["120503"]["overview_class"] == "equity"
    assert rows["120504"]["overview_class"] == "debt"
    assert rows["120504"]["currency"] == "INR"
    assert rows["120504"]["display_current_value"] == 50


@pytest.mark.django_db
def test_assets_reporting_groups_folios_and_uses_visible_fund_value(api_client, legacy_seeded):
    for folio in ("FOLIO-A", "FOLIO-B"):
        assert _mf_buy(api_client, folio_number=folio,
                       scheme_name="Test Equity Index Fund",
                       scheme_category="Equity Scheme - Index Funds").status_code == 201
    assert _mf_buy(api_client, scheme_code="120504", folio_number="FOLIO-A",
                   scheme_name="Test Liquid Fund").status_code == 201
    _nav("120503", "50.00")
    _nav("120504", "20.00")
    data = api_client.get("/api/v1/portfolio/holdings?display_currency=INR").json()
    report = data["assets_reports"]["MUTUAL_FUND"]
    assert [s["value"] for s in report["allocation"]["scheme"]] == [10000, 2000]
    assert len(report["allocation"]["folio"]) == 3
    folios = {row["name"]: row for row in report["funds"]["folios"]}
    assert len(folios["FOLIO-A"]["children"]) == 2
    assert folios["FOLIO-A"]["value"] == 7000
    assert report["funds"]["amc"] == [{
        "name": "Test AMC", "value": 12000, "weight": 1,
        "scheme_count": 2, "folio_count": 2,
    }]
    equity = data["assets_reports"]["equity"]["funds"]
    assert equity["total"] == 10000
    category = equity["categories"][0]
    assert category["name"] == "Equity"
    subcategory = category["children"][0]
    assert subcategory["name"] == "Index Funds"
    assert subcategory["children"][0]["units"] == 200
    assert subcategory["children"][0]["category_missing"] is False


@pytest.mark.django_db
def test_assets_breakdowns_keep_unknown_and_unvalued_funds_visible(api_client, legacy_seeded):
    assert _mf_buy(api_client, fund_house="", scheme_name="Test Fund").status_code == 201
    url = "/api/v1/portfolio/holdings?display_currency=INR"
    report = api_client.get(url).json()["assets_reports"]["all"]
    assert report["allocation"] == {"scheme": [], "incomplete": True}
    funds = report["funds"]
    assert funds["incomplete"] is True
    assert funds["total"] is None
    assert funds["amc"][0]["name"] == "Unknown AMC"
    assert funds["amc"][0]["weight"] is None
    category = funds["categories"][0]
    assert category["name"] == "Needs classification"
    assert "units" not in category
    scheme = category["children"][0]
    assert scheme["category_missing"] is True
    assert funds["missing_category_count"] == 1
    assert scheme["units"] == 100
    assert scheme["value"] is None


@pytest.mark.django_db
def test_personal_fund_category_is_scoped_and_can_reset(api_client, legacy_seeded):
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient

    assert _mf_buy(api_client, scheme_category="Other Scheme - Index Funds").status_code == 201
    url = "/api/v1/portfolio/fund-categories/120503"
    holdings_url = "/api/v1/portfolio/holdings?display_currency=INR"
    outsider = APIClient()
    outsider.force_authenticate(get_user_model().objects.create_user(username="outsider"))
    assert outsider.put(url, {"category": "Equity"}, format="json").status_code == 404
    assert api_client.put(url, {"category": " "}, format="json").status_code == 400
    assert api_client.put(url, {"classification": "Debt", "category": " Index Fund "}, format="json").status_code == 200
    data = api_client.get(holdings_url).json()
    assert data["holdings"][0]["overview_class"] == "equity"
    node = data["assets_reports"]["all"]["funds"]["categories"][0]
    assert node["name"] == "Debt"
    scheme = node["children"][0]["children"][0]
    assert scheme["provider_category"] == ["Other", "Index Funds"]
    assert scheme["personal_category"] == ["Index Fund", ""]
    assert api_client.delete(url).status_code == 204
    assert api_client.get(holdings_url).json()["assets_reports"]["all"]["funds"]["categories"][0]["name"] == "Equity"
