"""MF-6 — mutual fund NAV validation helper and API tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from market_data.models import AssetType, HistoricalPrice
from transactions.mf_nav_validation import (
    MARKET_VALUE_TOLERANCE_INR,
    NAV_ABSOLUTE_TOLERANCE_INR,
    verify_mutual_fund_nav_inputs,
)
from transactions.models import NavVerificationStatus


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


def _cached_nav(scheme: str, d: str, close: str):
    HistoricalPrice.objects.create(
        asset_symbol=scheme,
        date=date.fromisoformat(d),
        close_price=Decimal(close),
        currency="INR",
        source="test",
        asset_type=AssetType.MUTUAL_FUND,
    )


@pytest.mark.django_db
def test_verify_matching_nav_returns_verified():
    _cached_nav("120503", "2026-03-15", "42.500000")
    result = verify_mutual_fund_nav_inputs(
        scheme_code="120503",
        nav_date=date(2026, 3, 15),
        entered_nav=Decimal("42.50"),
        units_allotted=Decimal("100"),
        market_value=Decimal("4250.00"),
    )
    assert result.status == NavVerificationStatus.VERIFIED
    assert result.message == ""


@pytest.mark.django_db
def test_verify_no_cached_nav_returns_nav_missing():
    result = verify_mutual_fund_nav_inputs(
        scheme_code="120503",
        nav_date=date(2026, 3, 15),
        entered_nav=Decimal("42.50"),
        units_allotted=Decimal("100"),
        market_value=Decimal("4250.00"),
    )
    assert result.status == NavVerificationStatus.NAV_MISSING
    assert "No cached NAV" in result.message


@pytest.mark.django_db
def test_verify_nav_outside_absolute_tolerance_returns_nav_mismatch():
    _cached_nav("120503", "2026-03-15", "42.500000")
    result = verify_mutual_fund_nav_inputs(
        scheme_code="120503",
        nav_date=date(2026, 3, 15),
        entered_nav=Decimal("42.52"),
        units_allotted=Decimal("100"),
        market_value=Decimal("4252.00"),
    )
    assert result.status == NavVerificationStatus.NAV_MISMATCH
    assert "differs from cached NAV" in result.message


@pytest.mark.django_db
def test_verify_nav_within_tolerance_but_market_value_mismatch():
    _cached_nav("120503", "2026-03-15", "42.500000")
    result = verify_mutual_fund_nav_inputs(
        scheme_code="120503",
        nav_date=date(2026, 3, 15),
        entered_nav=Decimal("42.500000"),
        units_allotted=Decimal("100"),
        market_value=Decimal("4300.00"),
    )
    assert result.status == NavVerificationStatus.VALUE_MISMATCH
    assert "market_value" in result.message


@pytest.mark.django_db
def test_verify_does_not_call_external_provider():
    with patch(
        "market_data.providers.mutual_fund_nav_provider.AmfiNavProvider.get_latest_nav",
        side_effect=AssertionError("no external provider"),
    ):
        verify_mutual_fund_nav_inputs(
            scheme_code="120503",
            nav_date=date(2026, 3, 15),
            entered_nav=Decimal("10"),
            units_allotted=Decimal("1"),
            market_value=Decimal("10"),
        )


@pytest.mark.django_db
def test_create_mf_with_matching_cached_nav_verified(api_client, seeded):
    _cached_nav("120503", "2026-03-15", "42.500000")
    response = api_client.post("/api/v1/transactions", _mf_payload(), format="json")
    assert response.status_code == 201
    assert response.json()["nav_verification_status"] == "VERIFIED"


@pytest.mark.django_db
def test_create_mf_without_cached_nav_nav_missing(api_client, seeded):
    response = api_client.post("/api/v1/transactions", _mf_payload(), format="json")
    assert response.status_code == 201
    data = response.json()
    assert data["nav_verification_status"] == "NAV_MISSING"
    assert data["nav_verification_message"]


@pytest.mark.django_db
def test_create_mf_nav_mismatch_still_saves(api_client, seeded):
    _cached_nav("120503", "2026-03-15", "42.500000")
    response = api_client.post(
        "/api/v1/transactions",
        _mf_payload(nav="43.000000", market_value="4300.00", paid_value="4305.00"),
        format="json",
    )
    assert response.status_code == 201
    data = response.json()
    assert data["nav_verification_status"] == "NAV_MISMATCH"
    assert "nav_verification_message" in data


@pytest.mark.django_db
def test_create_mf_value_mismatch_still_saves(api_client, seeded):
    _cached_nav("120503", "2026-03-15", "42.500000")
    response = api_client.post(
        "/api/v1/transactions",
        _mf_payload(market_value="5000.00", paid_value="5005.00"),
        format="json",
    )
    assert response.status_code == 201
    assert response.json()["nav_verification_status"] == "VALUE_MISMATCH"


@pytest.mark.django_db
def test_update_mf_recomputes_verification_status(api_client, seeded):
    created = api_client.post("/api/v1/transactions", _mf_payload(), format="json").json()
    assert created["nav_verification_status"] == "NAV_MISSING"

    _cached_nav("120503", "2026-03-15", "42.500000")
    updated = api_client.put(
        f"/api/v1/transactions/{created['id']}",
        _mf_payload(nav="42.500000", market_value="4250.00"),
        format="json",
    ).json()
    assert updated["nav_verification_status"] == "VERIFIED"


@pytest.mark.django_db
def test_tolerance_constants_documented_values():
    assert NAV_ABSOLUTE_TOLERANCE_INR == Decimal("0.01")
    assert MARKET_VALUE_TOLERANCE_INR == Decimal("1")
