"""MF-10 — live AmfiNavProvider and MFAPI parsing tests (mocked HTTP only)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest

from market_data.models import AssetType, HistoricalPrice
from market_data.providers.amfi_nav_parser import (
    filter_nav_rows_by_range,
    normalize_api_scheme_code,
    parse_mfapi_date,
    parse_mfapi_latest_nav,
    parse_mfapi_nav_decimal,
    parse_mfapi_nav_entries,
)
from market_data.providers.mutual_fund_nav_provider import (
    AmfiNavFetchError,
    AmfiNavProvider,
)
from market_data.services.mutual_fund_nav_sync import sync_one_mutual_fund
from tests.test_mutual_fund_nav_sync import MockNavProvider, _mf_buy_with_detail, _mf_asset, _mf_profile


def _success_payload(*rows: tuple[str, str]) -> dict:
    return {
        "status": "SUCCESS",
        "meta": {"scheme_code": 120503},
        "data": [{"date": d, "nav": n} for d, n in rows],
    }


class TestMfapiParser:
    def test_parse_mfapi_date_dd_mm_yyyy(self):
        assert parse_mfapi_date("15-03-2026") == date(2026, 3, 15)

    def test_parse_mfapi_date_iso(self):
        assert parse_mfapi_date("2026-03-15") == date(2026, 3, 15)

    def test_parse_mfapi_date_invalid(self):
        assert parse_mfapi_date("not-a-date") is None

    def test_parse_mfapi_nav_decimal(self):
        assert parse_mfapi_nav_decimal("42.50000") == Decimal("42.50000")
        assert parse_mfapi_nav_decimal("0") is None
        assert parse_mfapi_nav_decimal("bad") is None

    def test_parse_mfapi_nav_entries_success(self):
        payload = _success_payload(("15-03-2026", "42.5"), ("16-03-2026", "43.0"))
        rows = parse_mfapi_nav_entries(payload)
        assert len(rows) == 2
        assert rows[0][1] == Decimal("42.5")

    def test_parse_mfapi_nav_entries_malformed(self):
        assert parse_mfapi_nav_entries({"status": "SUCCESS", "data": "nope"}) == []
        assert parse_mfapi_nav_entries({"status": "ERROR", "data": []}) == []
        assert parse_mfapi_nav_entries(
            {"status": "SUCCESS", "data": [{"date": "bad", "nav": "1"}]}
        ) == []

    def test_parse_mfapi_latest_nav(self):
        payload = _success_payload(("14-03-2026", "41.0"), ("15-03-2026", "42.5"))
        latest = parse_mfapi_latest_nav(payload)
        assert latest is not None
        assert latest[0] == date(2026, 3, 15)
        assert latest[1] == Decimal("42.5")

    def test_normalize_api_scheme_code(self):
        assert normalize_api_scheme_code(" 120503 ") == "120503"
        assert normalize_api_scheme_code("") is None
        assert normalize_api_scheme_code("ABC") is None

    def test_filter_nav_rows_by_range(self):
        rows = [
            (date(2026, 3, 14), Decimal("41")),
            (date(2026, 3, 15), Decimal("42")),
            (date(2026, 3, 16), Decimal("43")),
        ]
        filtered = filter_nav_rows_by_range(rows, date(2026, 3, 15), date(2026, 3, 16))
        assert [r[0] for r in filtered] == [date(2026, 3, 15), date(2026, 3, 16)]


class TestAmfiNavProvider:
    def test_get_latest_nav_success(self):
        provider = AmfiNavProvider(
            base_url="https://example.test",
            http_get=lambda url, timeout: _success_payload(("15-03-2026", "42.50000")),
        )
        point = provider.get_latest_nav("120503")
        assert point is not None
        assert point.nav == Decimal("42.50000")
        assert point.currency == "INR"

    def test_get_latest_nav_invalid_scheme(self):
        provider = AmfiNavProvider(http_get=lambda url, timeout: _success_payload())
        assert provider.get_latest_nav("INVALID") is None

    def test_get_latest_nav_empty_response(self):
        provider = AmfiNavProvider(
            http_get=lambda url, timeout: {"status": "SUCCESS", "data": []},
        )
        assert provider.get_latest_nav("120503") is None

    def test_get_latest_nav_malformed_response(self):
        provider = AmfiNavProvider(
            http_get=lambda url, timeout: {"status": "SUCCESS", "data": "bad"},
        )
        assert provider.get_latest_nav("120503") is None

    def test_get_latest_nav_network_error(self):
        def fail(url, timeout):
            raise AmfiNavFetchError("timeout")

        provider = AmfiNavProvider(http_get=fail)
        assert provider.get_latest_nav("120503") is None

    def test_get_nav_history_success(self):
        captured: list[str] = []

        def http_get(url, timeout):
            captured.append(url)
            return _success_payload(("14-03-2026", "41.0"), ("15-03-2026", "42.5"))

        provider = AmfiNavProvider(base_url="https://example.test", http_get=http_get)
        rows = provider.get_nav_history("120503", date(2026, 3, 15), date(2026, 3, 15))
        assert len(rows) == 1
        assert rows[0].nav == Decimal("42.5")
        assert "startDate=2026-03-15" in captured[0]
        assert "endDate=2026-03-15" in captured[0]

    def test_get_nav_history_empty_response(self):
        provider = AmfiNavProvider(
            http_get=lambda url, timeout: {"status": "SUCCESS", "data": []},
        )
        assert (
            provider.get_nav_history("120503", date(2026, 3, 1), date(2026, 3, 2)) == []
        )

    def test_get_nav_history_raises_on_network_error(self):
        def fail(url, timeout):
            raise AmfiNavFetchError("timeout")

        provider = AmfiNavProvider(http_get=fail)
        with pytest.raises(AmfiNavFetchError):
            provider.get_nav_history("120503", date(2026, 3, 1), date(2026, 3, 2))


@pytest.mark.django_db
def test_sync_stores_parsed_nav_rows_from_live_provider(seeded, test_user):
    today = date.today()
    asset = _mf_asset(scheme_code="120503")
    profile = _mf_profile(asset)
    _mf_buy_with_detail(test_user, scheme_code="120503", nav_date=today - timedelta(days=5))

    def http_get(url, timeout):
        return _success_payload(
            (f"{(today - timedelta(days=4)).strftime('%d-%m-%Y')}", "43.00"),
            (f"{(today - timedelta(days=3)).strftime('%d-%m-%Y')}", "43.50"),
        )

    provider = AmfiNavProvider(http_get=http_get)
    assert sync_one_mutual_fund(profile, provider) is True
    rows = HistoricalPrice.objects.filter(
        asset_symbol="120503",
        asset_type=AssetType.MUTUAL_FUND,
    )
    assert rows.count() == 2
    assert rows.order_by("date").first().close_price == Decimal("43.00")


@pytest.mark.django_db
def test_nav_refresh_api_with_mocked_live_provider(api_client, seeded, test_user):
    today = date.today()
    _mf_buy_with_detail(test_user, scheme_code="120503", nav_date=today - timedelta(days=3))

    def http_get(url, timeout):
        return _success_payload((f"{(today - timedelta(days=2)).strftime('%d-%m-%Y')}", "44.00"))

    with patch(
        "market_data.services.mutual_fund_nav_sync.default_mutual_fund_nav_provider",
        return_value=AmfiNavProvider(http_get=http_get),
    ):
        r = api_client.post("/api/v1/nav/refresh", {}, format="json")
    assert r.status_code == 202
    assert r.json()["synced"] >= 1
    assert HistoricalPrice.objects.filter(
        asset_symbol="120503", asset_type=AssetType.MUTUAL_FUND
    ).exists()


@pytest.mark.django_db
def test_holdings_read_does_not_call_live_provider(api_client, seeded, test_user):
    today = date.today()
    _mf_buy_with_detail(test_user, scheme_code="120503", nav_date=today - timedelta(days=5))
    HistoricalPrice.objects.create(
        asset_symbol="120503",
        date=today - timedelta(days=1),
        close_price=Decimal("42.5"),
        currency="INR",
        asset_type=AssetType.MUTUAL_FUND,
    )

    def fail(url, timeout):
        raise AssertionError("read API must not call NAV provider")

    with patch(
        "market_data.services.mutual_fund_nav_sync.default_mutual_fund_nav_provider",
        return_value=AmfiNavProvider(http_get=fail),
    ):
        r = api_client.get("/api/v1/portfolio/holdings?display_currency=INR")
    assert r.status_code == 200
