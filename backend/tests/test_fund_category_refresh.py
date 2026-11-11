from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command

from market_data.models import Asset, AssetType, MutualFundProfile
from market_data.providers.mutual_fund_nav_provider import AmfiNavProvider
from market_data.services.fund_categories import category_pair


def test_parser_preserves_internal_dashes():
    assert category_pair(" Equity Scheme – ELSS - Direct ") == ("Equity", "ELSS - Direct")
    assert category_pair("Other Scheme") == ("Other", "")


@pytest.mark.django_db
def test_preview_does_not_write_and_apply_is_fill_only():
    asset = Asset.objects.create(asset_type=AssetType.MUTUAL_FUND, symbol="123456")
    profile = MutualFundProfile.objects.create(asset=asset, scheme_code="123456", scheme_name="Example")
    metadata = {"scheme_category": "Equity Scheme - ELSS", "scheme_type": "Open Ended"}
    with patch.object(AmfiNavProvider, "get_category_metadata", return_value=metadata):
        output = StringIO()
        call_command("backfill_fund_categories", stdout=output)
        assert "subcategory='ELSS'" in output.getvalue()
        profile.refresh_from_db()
        assert not profile.scheme_category
        call_command("backfill_fund_categories", apply=True)
        call_command("backfill_fund_categories", apply=True)
    profile.refresh_from_db()
    assert profile.scheme_category == metadata["scheme_category"]
    assert profile.scheme_type == metadata["scheme_type"]


def test_provider_rejects_metadata_for_the_wrong_scheme():
    provider = AmfiNavProvider(http_get=lambda *_: {
        "status": "SUCCESS", "meta": {"scheme_code": 654321, "scheme_category": "Equity Scheme - ELSS"},
    })
    assert provider.get_category_metadata("123456") is None


@pytest.mark.django_db
def test_current_nav_still_fills_category_without_changing_asset_class():
    from datetime import date
    from decimal import Decimal

    from market_data.models import HistoricalPrice
    from market_data.mutual_fund_classification_bridge import classify_mutual_fund_asset
    from market_data.services.mutual_fund_nav_sync import sync_mutual_fund_navs

    asset = Asset.objects.create(asset_type=AssetType.MUTUAL_FUND, symbol="123456")
    profile = MutualFundProfile.objects.create(
        asset=asset, scheme_code="123456", scheme_name="Example",
        scheme_type="Previously recorded",
    )
    day = date(2025, 1, 1)
    HistoricalPrice.objects.create(asset=asset, asset_symbol=asset.symbol,
                                   asset_type=AssetType.MUTUAL_FUND, date=day,
                                   close_price=Decimal("10"), currency="INR", source="amfi")
    before = classify_mutual_fund_asset(asset, profile).primary_asset_class
    requests = []
    def get(url, _timeout):
        requests.append(url)
        return {"status": "SUCCESS", "meta": {
            "scheme_code": 123456, "scheme_category": "Equity Scheme - ELSS",
            "scheme_type": "Open Ended", "fund_house": "Example AMC",
        }}
    provider = AmfiNavProvider(http_get=get)
    assert sync_mutual_fund_navs(provider=provider, end=day).success
    assert sync_mutual_fund_navs(provider=provider, end=day).success
    profile.refresh_from_db()
    assert profile.scheme_category == "Equity Scheme - ELSS"
    assert profile.scheme_type == "Previously recorded"
    assert profile.fund_house == "Example AMC"
    assert classify_mutual_fund_asset(asset, profile).primary_asset_class == before
    assert len(requests) == 1 and requests[0].endswith("/latest")
    assert HistoricalPrice.objects.count() == 1
