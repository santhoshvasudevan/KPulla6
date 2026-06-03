from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from analytics.services import (
    MF_NAV_STALE_AFTER_DAYS,
    _WARN_MISSING_MF_NAVS,
    _WARN_STALE_MF_NAVS,
    _mf_nav_freshness_issue,
)
from market_data.models import AssetType, HistoricalPrice

FIXED_TODAY = date(2026, 3, 15)


@pytest.fixture
def today_patch(monkeypatch):
    monkeypatch.setattr("portfolios.dates.current_date", lambda: FIXED_TODAY)
    return FIXED_TODAY


def _mf_nav(scheme: str, d: str, close: str):
    HistoricalPrice.objects.create(
        asset_symbol=scheme,
        date=date.fromisoformat(d),
        close_price=Decimal(close),
        currency="INR",
        source="test",
        asset_type=AssetType.MUTUAL_FUND,
    )


def _mf_buy(api_client, **kwargs):
    payload = {
        "asset_type": "MUTUAL_FUND",
        "scheme_code": "120503",
        "scheme_name": "Test Direct Growth Fund",
        "folio_number": "FOLIO-12345",
        "type": "BUY",
        "investment_date": "2026-03-01",
        "nav_date": "2026-03-01",
        "nav": "42.500000",
        "units_allotted": "100.00000000",
        "paid_value": "4255.00",
        "market_value": "4250.00",
        "fund_house": "Test AMC",
    }
    payload.update(kwargs)
    return api_client.post("/api/v1/transactions", payload, format="json")


def _mf_txns(api_client):
    _mf_buy(api_client, investment_date="2026-03-01", nav_date="2026-03-01")
    from transactions.models import Transaction as TransactionModel

    return list(
        TransactionModel.objects.filter(asset_symbol="120503").order_by("date")
    )


@pytest.mark.django_db
def test_mf_nav_freshness_no_warning_for_recent_friday_nav_on_sunday_end(
    api_client, seeded, today_patch
):
    txns = _mf_txns(api_client)
    _mf_nav("120503", "2026-03-13", "44.00")

    assert (
        _mf_nav_freshness_issue("120503", txns, date(2026, 3, 1), FIXED_TODAY) is None
    )


@pytest.mark.django_db
def test_mf_nav_freshness_no_warning_within_five_calendar_days(
    api_client, seeded, today_patch
):
    txns = _mf_txns(api_client)
    _mf_nav("120503", "2026-03-11", "44.00")

    assert (
        _mf_nav_freshness_issue("120503", txns, date(2026, 3, 1), FIXED_TODAY) is None
    )


@pytest.mark.django_db
def test_mf_nav_freshness_stale_warning_when_latest_nav_older_than_five_days(
    api_client, seeded, today_patch
):
    txns = _mf_txns(api_client)
    _mf_nav("120503", "2026-03-01", "42.00")

    assert (
        _mf_nav_freshness_issue("120503", txns, date(2026, 3, 1), FIXED_TODAY)
        == "stale"
    )


@pytest.mark.django_db
def test_mf_nav_freshness_missing_warning_when_no_cached_nav(
    api_client, seeded, today_patch
):
    txns = _mf_txns(api_client)

    assert (
        _mf_nav_freshness_issue("120503", txns, date(2026, 3, 1), FIXED_TODAY)
        == "missing"
    )


def test_mf_nav_stale_after_days_constant():
    assert MF_NAV_STALE_AFTER_DAYS == 5


def test_mf_nav_warning_copy_constants():
    assert "older than 5 days" in _WARN_STALE_MF_NAVS
    assert "No cached NAV is available" in _WARN_MISSING_MF_NAVS
