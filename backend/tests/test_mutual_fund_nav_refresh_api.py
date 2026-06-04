"""MF-9 — mutual fund NAV refresh API and combined market-data sync."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command

from market_data.models import AssetType, HistoricalPrice
from market_data.providers.mutual_fund_nav_provider import NavPoint
from market_data.services.market_data_sync import sync_all_market_data
from market_data.services.mutual_fund_nav_sync import MutualFundNavSyncResult
from tests.test_mutual_fund_nav_sync import MockNavProvider, _mf_buy_with_detail


def _nav_provider_with_history(scheme: str = "120503"):
    today = date.today()
    return MockNavProvider(
        {
            scheme: [
                NavPoint(today - timedelta(days=1), Decimal("42.5"), "INR"),
            ]
        }
    )


@pytest.mark.django_db
def test_nav_refresh_syncs_cached_navs(api_client, seeded, test_user):
    _mf_buy_with_detail(test_user, nav_date=date.today() - timedelta(days=3))
    provider = _nav_provider_with_history()
    with patch(
        "market_data.services.mutual_fund_nav_sync.default_mutual_fund_nav_provider",
        return_value=provider,
    ):
        r = api_client.post("/api/v1/nav/refresh", {}, format="json")
    assert r.status_code == 202
    data = r.json()
    assert data["synced"] >= 1
    assert data["failed"] == 0
    assert HistoricalPrice.objects.filter(
        asset_symbol="120503", asset_type=AssetType.MUTUAL_FUND
    ).exists()


@pytest.mark.django_db
def test_nav_refresh_filters_scheme_codes(api_client, seeded, test_user):
    _mf_buy_with_detail(test_user, nav_date=date.today() - timedelta(days=3))
    provider = _nav_provider_with_history()
    with patch(
        "market_data.services.mutual_fund_nav_sync.default_mutual_fund_nav_provider",
        return_value=provider,
    ):
        r = api_client.post(
            "/api/v1/nav/refresh",
            {"scheme_codes": ["120503"]},
            format="json",
        )
    assert r.status_code == 202
    assert r.json()["synced"] >= 1
    assert provider.history_calls
    assert provider.history_calls[0][0] == "120503"


@pytest.mark.django_db
def test_nav_refresh_handles_provider_failure_per_scheme(api_client, seeded, test_user):
    _mf_buy_with_detail(test_user, nav_date=date.today() - timedelta(days=3))
    provider = MockNavProvider(fail={"120503"})
    with patch(
        "market_data.services.mutual_fund_nav_sync.default_mutual_fund_nav_provider",
        return_value=provider,
    ):
        r = api_client.post("/api/v1/nav/refresh", {}, format="json")
    assert r.status_code == 202
    data = r.json()
    assert data["failed"] >= 1
    assert len(data.get("warnings", [])) >= 1


@pytest.mark.django_db
def test_sync_all_market_data_includes_mutual_funds(seeded, test_user):
    _mf_buy_with_detail(test_user, nav_date=date.today() - timedelta(days=3))
    provider = _nav_provider_with_history()
    with patch("market_data.services.market_data_sync.sync_stock_prices") as mock_prices:
        mock_prices.return_value = type("R", (), {"success": True})()
        with patch(
            "market_data.services.market_data_sync.sync_benchmark_prices",
            return_value=True,
        ):
            with patch("fx.services.sync_fx_rates") as mock_fx:
                mock_fx.return_value = type("R", (), {"success": True, "partial": False})()
                with patch(
                    "market_data.services.market_data_sync.sync_mutual_fund_navs",
                    return_value=MutualFundNavSyncResult(synced=1, skipped=0, failed=0),
                ) as mock_mf:
                    result = sync_all_market_data(run_mutual_funds=True)
    mock_mf.assert_called_once()
    assert result.mutual_funds_synced == 1


@pytest.mark.django_db
def test_sync_all_market_data_skips_mutual_funds_when_disabled(seeded):
    with patch("market_data.services.market_data_sync.sync_stock_prices") as mock_prices:
        mock_prices.return_value = type("R", (), {"success": True})()
        with patch(
            "market_data.services.market_data_sync.sync_benchmark_prices",
            return_value=True,
        ):
            with patch("fx.services.sync_fx_rates") as mock_fx:
                mock_fx.return_value = type("R", (), {"success": True, "partial": False})()
                with patch(
                    "market_data.services.market_data_sync.sync_mutual_fund_navs",
                ) as mock_mf:
                    sync_all_market_data(run_mutual_funds=False)
    mock_mf.assert_not_called()


@pytest.mark.django_db
def test_mf_nav_failure_does_not_fail_overall_sync_success(seeded):
    with patch("market_data.services.market_data_sync.sync_stock_prices") as mock_prices:
        mock_prices.return_value = type("R", (), {"success": True})()
        with patch(
            "market_data.services.market_data_sync.sync_benchmark_prices",
            return_value=True,
        ):
            with patch("fx.services.sync_fx_rates") as mock_fx:
                mock_fx.return_value = type("R", (), {"success": True, "partial": False})()
                with patch(
                    "market_data.services.market_data_sync.sync_mutual_fund_navs",
                    return_value=MutualFundNavSyncResult(synced=0, skipped=0, failed=2),
                ):
                    result = sync_all_market_data(run_mutual_funds=True)
    assert result.success is True
    assert result.mutual_funds_failed == 2
    assert result.mutual_funds_success is False


@pytest.mark.django_db
def test_prices_refresh_still_works(api_client, seeded):
    with patch("market_data.views.sync_stock_prices") as mock_sync:
        r = api_client.post("/api/v1/prices/refresh", {}, format="json")
    assert r.status_code == 202
    assert r.json()["message"] == "Price sync scheduled"
    mock_sync.assert_called_once()


@pytest.mark.django_db
def test_force_sync_still_works_and_includes_mutual_funds(api_client, seeded):
    with patch("market_data.views.sync_all_market_data") as mock_sync:
        mock_sync.return_value = type(
            "R",
            (),
            {
                "prices_success": True,
                "benchmarks_success": True,
                "fx_success": True,
                "fx_partial": False,
                "mutual_funds_synced": 1,
                "mutual_funds_skipped": 0,
                "mutual_funds_failed": 0,
                "success": True,
                "mutual_funds_success": True,
            },
        )()
        r = api_client.post("/api/v1/portfolio/force-sync", {}, format="json")
    assert r.status_code == 202
    assert r.json()["message"] == "Sync started in background"
    mock_sync.assert_called_once()
    assert mock_sync.call_args.kwargs.get("run_mutual_funds", True) is True


@pytest.mark.django_db
def test_holdings_read_does_not_call_nav_provider(api_client, seeded, test_user):
    _mf_buy_with_detail(test_user, nav_date=date.today() - timedelta(days=5))
    HistoricalPrice.objects.create(
        asset_symbol="120503",
        date=date.today() - timedelta(days=1),
        close_price=Decimal("42.5"),
        currency="INR",
        asset_type=AssetType.MUTUAL_FUND,
    )
    provider = MockNavProvider()
    with patch(
        "market_data.providers.mutual_fund_nav_provider.AmfiNavProvider.get_latest_nav",
        side_effect=provider.get_latest_nav,
    ):
        with patch(
            "market_data.providers.mutual_fund_nav_provider.AmfiNavProvider.get_nav_history",
            side_effect=provider.get_nav_history,
        ):
            r = api_client.get("/api/v1/portfolio/holdings?display_currency=INR")
    assert r.status_code == 200
    assert not provider.history_calls
    assert not provider.latest_calls


@pytest.mark.django_db
def test_sync_market_data_command_includes_mutual_funds(seeded):
    with patch("market_data.management.commands.sync_market_data.sync_all_market_data") as m:
        m.return_value = type(
            "R",
            (),
            {
                "prices_success": True,
                "benchmarks_success": True,
                "fx_success": True,
                "fx_partial": False,
                "mutual_funds_synced": 0,
                "mutual_funds_skipped": 0,
                "mutual_funds_failed": 0,
                "success": True,
                "mutual_funds_success": True,
            },
        )()
        call_command("sync_market_data", stdout=StringIO())
    m.assert_called_once()
    assert m.call_args.kwargs.get("run_mutual_funds") is True


@pytest.mark.django_db
def test_sync_market_data_command_warns_on_mutual_fund_failures(seeded):
    with patch("market_data.management.commands.sync_market_data.sync_all_market_data") as m:
        m.return_value = type(
            "R",
            (),
            {
                "prices_success": True,
                "benchmarks_success": True,
                "fx_success": True,
                "fx_partial": False,
                "mutual_funds_synced": 1,
                "mutual_funds_skipped": 0,
                "mutual_funds_failed": 2,
                "success": True,
                "mutual_funds_success": False,
            },
        )()
        out = StringIO()
        call_command("sync_market_data", stdout=out)
    text = out.getvalue()
    assert "failed=2" in text
    assert "mutual fund NAV failures" in text


@pytest.mark.django_db
def test_sync_market_data_command_skip_mutual_funds(seeded):
    with patch("market_data.management.commands.sync_market_data.sync_all_market_data") as m:
        m.return_value = type(
            "R",
            (),
            {
                "prices_success": True,
                "benchmarks_success": True,
                "fx_success": True,
                "fx_partial": False,
                "mutual_funds_synced": 0,
                "mutual_funds_skipped": 0,
                "mutual_funds_failed": 0,
                "success": True,
                "mutual_funds_success": True,
            },
        )()
        call_command("sync_market_data", "--skip-mutual-funds", stdout=StringIO())
    assert m.call_args.kwargs.get("run_mutual_funds") is False
