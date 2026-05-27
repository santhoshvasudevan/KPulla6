"""MF-3 — mutual fund transaction API tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from market_data.models import Asset, AssetType, HistoricalPrice, MutualFundProfile
from portfolios.models import Portfolio
from portfolios.seed import ensure_default_portfolio
from transactions.models import Folio, MutualFundTransactionDetail, Transaction


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


@pytest.mark.django_db
def test_create_mf_buy_success(api_client, seeded):
    default = ensure_default_portfolio()
    response = api_client.post(
        "/api/v1/transactions",
        _mf_payload(portfolio_id=default.id),
        format="json",
    )
    assert response.status_code == 201
    data = response.json()
    assert data["asset_type"] == "MUTUAL_FUND"
    assert data["scheme_code"] == "120503"
    assert data["scheme_name"] == "Test Direct Growth Fund"
    assert data["folio_number"] == "FOLIO-12345"
    assert data["type"] == "BUY"
    assert data["date"] == "2026-03-15"
    assert data["nav_date"] == "2026-03-15"
    assert data["investment_date"] == "2026-03-10"
    assert data["nav"] == 42.5
    assert data["units_allotted"] == 100.0
    assert data["quantity"] == 100.0
    assert data["price_per_share"] == 42.5
    assert data["currency"] == "INR"
    assert data["paid_value"] == 4255.0
    assert data["market_value"] == 4250.0
    assert data["fees"] == 5.0
    assert data["portfolio_id"] == default.id

    txn = Transaction.objects.get(pk=data["id"])
    assert txn.asset_symbol == "120503"
    assert txn.date == date(2026, 3, 15)
    assert MutualFundTransactionDetail.objects.filter(transaction=txn).exists()
    assert Asset.objects.filter(asset_type=AssetType.MUTUAL_FUND, symbol="120503").exists()
    assert MutualFundProfile.objects.filter(scheme_code="120503").exists()
    assert Folio.objects.filter(folio_number="FOLIO-12345").exists()


@pytest.mark.django_db
def test_create_mf_sell_success(api_client, seeded):
    response = api_client.post(
        "/api/v1/transactions",
        _mf_payload(type="SELL"),
        format="json",
    )
    assert response.status_code == 201
    assert response.json()["type"] == "SELL"


@pytest.mark.django_db
def test_mf_folio_number_required(api_client, seeded):
    payload = _mf_payload()
    del payload["folio_number"]
    response = api_client.post("/api/v1/transactions", payload, format="json")
    assert response.status_code == 400


@pytest.mark.django_db
def test_mf_scheme_code_required(api_client, seeded):
    payload = _mf_payload(scheme_code="")
    response = api_client.post("/api/v1/transactions", payload, format="json")
    assert response.status_code == 400


@pytest.mark.django_db
def test_mf_nav_date_and_investment_date_required(api_client, seeded):
    r1 = api_client.post(
        "/api/v1/transactions",
        _mf_payload(nav_date=None),
        format="json",
    )
    assert r1.status_code == 400

    r2 = api_client.post(
        "/api/v1/transactions",
        _mf_payload(investment_date=None),
        format="json",
    )
    assert r2.status_code == 400


@pytest.mark.django_db
def test_mf_nav_and_units_must_be_positive(api_client, seeded):
    r1 = api_client.post(
        "/api/v1/transactions",
        _mf_payload(nav="0"),
        format="json",
    )
    assert r1.status_code == 400

    r2 = api_client.post(
        "/api/v1/transactions",
        _mf_payload(units_allotted="0"),
        format="json",
    )
    assert r2.status_code == 400


@pytest.mark.django_db
def test_mf_fees_computed_from_paid_and_market_value(api_client, seeded):
    response = api_client.post(
        "/api/v1/transactions",
        _mf_payload(paid_value="4300.00", market_value="4250.00"),
        format="json",
    )
    assert response.status_code == 201
    assert response.json()["fees"] == 50.0


@pytest.mark.django_db
def test_mf_rejects_negative_computed_fees(api_client, seeded):
    response = api_client.post(
        "/api/v1/transactions",
        _mf_payload(paid_value="4200.00", market_value="4250.00"),
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_mf_list_includes_detail_fields(api_client, seeded):
    api_client.post("/api/v1/transactions", _mf_payload(), format="json")
    response = api_client.get("/api/v1/transactions?page_size=50")
    mf_items = [i for i in response.json()["items"] if i.get("asset_type") == "MUTUAL_FUND"]
    assert len(mf_items) == 1
    item = mf_items[0]
    assert item["scheme_code"] == "120503"
    assert item["folio_number"] == "FOLIO-12345"
    assert item["nav_verification_status"] in {
        "NOT_VERIFIED",
        "VERIFIED",
        "NAV_MISSING",
        "NAV_MISMATCH",
        "VALUE_MISMATCH",
        "WARNING_ACCEPTED",
        "OK",
        "WARNING",
        "UNCHECKED",
    }


@pytest.mark.django_db
def test_mf_update_updates_transaction_and_detail(api_client, seeded):
    created = api_client.post("/api/v1/transactions", _mf_payload(), format="json").json()
    response = api_client.put(
        f"/api/v1/transactions/{created['id']}",
        _mf_payload(
            nav="43.000000",
            units_allotted="50.00000000",
            paid_value="2155.00",
            market_value="2150.00",
            folio_number="FOLIO-999",
        ),
        format="json",
    )
    assert response.status_code == 200
    data = response.json()
    assert data["nav"] == 43.0
    assert data["quantity"] == 50.0
    assert data["folio_number"] == "FOLIO-999"
    assert data["fees"] == 5.0

    detail = MutualFundTransactionDetail.objects.get(transaction_id=created["id"])
    assert detail.nav == Decimal("43.000000")
    assert detail.units_allotted == Decimal("50")


@pytest.mark.django_db
def test_mf_delete_removes_detail_keeps_asset_profile_folio(api_client, seeded):
    created = api_client.post("/api/v1/transactions", _mf_payload(), format="json").json()
    asset_id = Asset.objects.get(symbol="120503").id
    profile_id = MutualFundProfile.objects.get(scheme_code="120503").id
    folio_id = Folio.objects.get(folio_number="FOLIO-12345").id

    response = api_client.delete(f"/api/v1/transactions/{created['id']}")
    assert response.status_code == 204
    assert not Transaction.objects.filter(pk=created["id"]).exists()
    assert not MutualFundTransactionDetail.objects.filter(transaction_id=created["id"]).exists()
    assert Asset.objects.filter(pk=asset_id).exists()
    assert MutualFundProfile.objects.filter(pk=profile_id).exists()
    assert Folio.objects.filter(pk=folio_id).exists()


@pytest.mark.django_db
def test_mf_create_atomic_rollback_on_detail_failure(api_client, seeded):
    with patch(
        "transactions.mutual_fund_services.MutualFundTransactionDetail.objects.create",
        side_effect=RuntimeError("detail failed"),
    ):
        response = api_client.post("/api/v1/transactions", _mf_payload(), format="json")
    assert response.status_code == 400
    assert Transaction.objects.filter(asset_symbol="120503").count() == 0


@pytest.mark.django_db
def test_mf_create_does_not_call_external_nav_provider(api_client, seeded):
    with patch(
        "market_data.providers.mutual_fund_nav_provider.AmfiNavProvider.get_nav_history",
        side_effect=AssertionError("external NAV provider must not be called"),
    ):
        with patch(
            "market_data.providers.mutual_fund_nav_provider.AmfiNavProvider.get_latest_nav",
            side_effect=AssertionError("external NAV provider must not be called"),
        ):
            response = api_client.post("/api/v1/transactions", _mf_payload(), format="json")
    assert response.status_code == 201


@pytest.mark.django_db
def test_mf_nav_verification_uses_cached_db_only(api_client, seeded):
    HistoricalPrice.objects.create(
        asset_symbol="120503",
        date=date(2026, 3, 15),
        close_price=Decimal("42.500000"),
        currency="INR",
        asset_type=AssetType.MUTUAL_FUND,
        source="amfi",
    )
    response = api_client.post("/api/v1/transactions", _mf_payload(), format="json")
    assert response.status_code == 201
    assert response.json()["nav_verification_status"] == "VERIFIED"


@pytest.mark.django_db
def test_mf_put_portfolio_change_resolves_folio(api_client, seeded):
    p1 = Portfolio.objects.create(name="MF-P1", base_currency="INR", is_active=True)
    p2 = Portfolio.objects.create(name="MF-P2", base_currency="INR", is_active=True)
    created = api_client.post(
        "/api/v1/transactions",
        _mf_payload(portfolio_id=p1.id),
        format="json",
    ).json()
    response = api_client.put(
        f"/api/v1/transactions/{created['id']}",
        _mf_payload(portfolio_id=p2.id),
        format="json",
    )
    assert response.status_code == 200
    assert response.json()["portfolio_id"] == p2.id
    detail = MutualFundTransactionDetail.objects.get(transaction_id=created["id"])
    assert detail.folio.portfolio_id == p2.id


@pytest.mark.django_db
def test_stock_list_unchanged_without_mf_fields(api_client, seeded):
    api_client.post(
        "/api/v1/transactions",
        {
            "asset_symbol": "AAPL",
            "date": "2026-05-01",
            "type": "BUY",
            "quantity": "10",
            "price_per_share": "150",
        },
        format="json",
    )
    item = api_client.get("/api/v1/transactions?page_size=50").json()["items"][0]
    assert "asset_type" not in item
    assert item["asset_symbol"] == "AAPL"
