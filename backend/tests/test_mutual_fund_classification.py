"""MF-7 — mutual fund classification helper and API field tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from finance.mutual_fund_classification import (
    CLASS_COMMODITY,
    CLASS_DEBT,
    CLASS_EQUITY,
    CLASS_HYBRID,
    CLASS_LIQUID,
    CLASS_UNKNOWN,
    SOURCE_EXPLICIT,
    SOURCE_INFERRED,
    SOURCE_UNKNOWN,
    classify_mutual_fund,
)
from market_data.models import Asset, AssetType, MutualFundProfile, PrimaryAssetClass
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


@pytest.mark.parametrize(
    "category,name,expected",
    [
        ("Equity Scheme - Large Cap Fund", "ABC Large Cap Fund", CLASS_EQUITY),
        ("Debt Scheme - Corporate Bond", "XYZ Corporate Bond Fund", CLASS_DEBT),
        ("Hybrid Scheme - Aggressive Hybrid", "Balanced Advantage Fund", CLASS_HYBRID),
        ("Other Scheme - Gold Fund", "Sovereign Gold Bond Fund", CLASS_COMMODITY),
        ("Debt Scheme - Liquid Fund", "ABC Liquid Fund", CLASS_LIQUID),
        ("Debt Scheme - Overnight Fund", "Overnight Fund", CLASS_LIQUID),
        ("Other Scheme - FoF", "Global Nasdaq 100 Fund", CLASS_EQUITY),
        ("", "Random Unknown XYZ", CLASS_UNKNOWN),
    ],
)
def test_classify_inference_rules(category, name, expected):
    result = classify_mutual_fund(
        explicit_primary_asset_class=None,
        scheme_category=category,
        scheme_name=name,
    )
    assert result.primary_asset_class == expected
    if expected == CLASS_UNKNOWN:
        assert result.classification_source == SOURCE_UNKNOWN
    else:
        assert result.classification_source == SOURCE_INFERRED


def test_hybrid_not_classified_as_equity():
    result = classify_mutual_fund(
        explicit_primary_asset_class=None,
        scheme_category="Hybrid Scheme - Multi Asset Allocation",
        scheme_name="Multi Asset Fund of Funds",
    )
    assert result.primary_asset_class == CLASS_HYBRID
    assert result.primary_asset_class != CLASS_EQUITY


def test_explicit_primary_asset_class_preserved():
    result = classify_mutual_fund(
        explicit_primary_asset_class=CLASS_DEBT,
        scheme_category="Equity Scheme - Large Cap Fund",
        scheme_name="Should Not Override",
    )
    assert result.primary_asset_class == CLASS_DEBT
    assert result.classification_source == SOURCE_EXPLICIT


@pytest.mark.django_db
def test_mf_holdings_include_classification_fields(api_client, seeded):
    api_client.post(
        "/api/v1/transactions",
        _mf_payload(
            scheme_category="Equity Scheme - Large Cap Fund",
            scheme_name="Large Cap Direct Growth",
        ),
        format="json",
    )
    row = [
        h
        for h in api_client.get("/api/v1/portfolio/holdings").json()["holdings"]
        if h.get("asset_type") == "MUTUAL_FUND"
    ][0]
    assert row["primary_asset_class"] == CLASS_EQUITY
    # Persisted on Asset after create → EXPLICIT on read; INFERRED before save
    assert row["classification_source"] in {SOURCE_INFERRED, SOURCE_EXPLICIT}


@pytest.mark.django_db
def test_mf_asset_detail_includes_classification_fields(api_client, seeded):
    api_client.post(
        "/api/v1/transactions",
        _mf_payload(
            scheme_category="Hybrid Scheme - Conservative Hybrid Fund",
            scheme_name="Conservative Hybrid Plan",
        ),
        format="json",
    )
    data = api_client.get(
        "/api/v1/portfolio/assets/120503?folio_number=FOLIO-12345"
    ).json()
    assert data["primary_asset_class"] == CLASS_HYBRID
    assert data["classification_source"] in {SOURCE_INFERRED, SOURCE_EXPLICIT}


@pytest.mark.django_db
def test_explicit_asset_class_on_holdings(api_client, seeded):
    api_client.post(
        "/api/v1/transactions",
        _mf_payload(scheme_category="Equity Scheme - Mid Cap"),
        format="json",
    )
    asset = Asset.objects.get(symbol="120503", asset_type=AssetType.MUTUAL_FUND)
    asset.primary_asset_class = PrimaryAssetClass.COMMODITY
    asset.save(update_fields=["primary_asset_class"])

    row = [
        h
        for h in api_client.get("/api/v1/portfolio/holdings").json()["holdings"]
        if h.get("asset_type") == "MUTUAL_FUND"
    ][0]
    assert row["primary_asset_class"] == CLASS_COMMODITY
    assert row["classification_source"] == SOURCE_EXPLICIT


@pytest.mark.django_db
def test_create_upsert_sets_inferred_class_when_unknown(api_client, seeded):
    api_client.post(
        "/api/v1/transactions",
        _mf_payload(
            scheme_category="Debt Scheme - Long Duration Fund",
            scheme_name="Long Duration Bond Fund",
        ),
        format="json",
    )
    asset = Asset.objects.get(symbol="120503", asset_type=AssetType.MUTUAL_FUND)
    assert asset.primary_asset_class == PrimaryAssetClass.DEBT


@pytest.mark.django_db
def test_create_does_not_override_explicit_class(api_client, seeded):
    asset, _ = Asset.objects.get_or_create(
        asset_type=AssetType.MUTUAL_FUND,
        symbol="999888",
        defaults={
            "display_name": "Preset Fund",
            "currency": "INR",
            "primary_asset_class": PrimaryAssetClass.HYBRID,
        },
    )
    MutualFundProfile.objects.get_or_create(
        asset=asset,
        defaults={
            "scheme_code": "999888",
            "scheme_name": "Preset Fund",
            "scheme_category": "Equity Scheme - Large Cap Fund",
        },
    )
    api_client.post(
        "/api/v1/transactions",
        _mf_payload(
            scheme_code="999888",
            scheme_name="Preset Fund",
            scheme_category="Equity Scheme - Large Cap Fund",
        ),
        format="json",
    )
    asset.refresh_from_db()
    assert asset.primary_asset_class == PrimaryAssetClass.HYBRID


@pytest.mark.django_db
def test_stock_holdings_unchanged_without_classification(api_client, seeded, test_user):
    default = ensure_default_portfolio(test_user)
    api_client.post(
        "/api/v1/transactions",
        {
            "asset_symbol": "AAPL",
            "date": "2026-05-01",
            "type": "BUY",
            "quantity": "10",
            "price_per_share": "150",
            "portfolio_id": default.id,
        },
        format="json",
    )
    row = api_client.get("/api/v1/portfolio/holdings").json()["holdings"][0]
    assert "primary_asset_class" not in row
    assert "classification_source" not in row
