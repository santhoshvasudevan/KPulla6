"""#49 — explicit exact-date missing-NAV fetch: cache recheck, in-flight claim, cooldown."""
from datetime import date, datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.db import DatabaseError
from rest_framework.test import APIClient

from cash.models import CashLedgerEntry
from market_data.models import AssetType, HistoricalPrice, MutualFundNavFetchState
from market_data.providers.mutual_fund_nav_provider import (
    AmfiNavFetchError,
    AmfiNavProvider,
    AmfiNavTimeoutError,
    NavPoint,
)
from tests.test_mutual_fund_nav_sync import MockNavProvider
from transactions.models import Transaction

URL = "/api/v1/nav/fetch-missing"
SCHEME = "120503"
DAY = date(2023, 1, 20)
T0 = datetime(2026, 11, 24, 12, 0, tzinfo=dt_timezone.utc)


class Clock:
    def __init__(self, start=T0):
        self.value = start

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += timedelta(seconds=seconds)


@pytest.fixture
def clock():
    c = Clock()
    with patch("market_data.services.missing_nav_fetch._now", side_effect=c):
        yield c


def use_provider(provider):
    return patch(
        "market_data.services.missing_nav_fetch.default_mutual_fund_nav_provider",
        return_value=provider,
    )


def post(client, scheme=SCHEME, day=DAY.isoformat()):
    return client.post(URL, {"scheme_code": scheme, "nav_date": day}, format="json")


def mf_rows():
    return list(
        HistoricalPrice.objects.filter(asset_type=AssetType.MUTUAL_FUND)
        .order_by("asset_symbol", "date")
        .values_list("asset_symbol", "date", "close_price", "currency")
    )


class RaisingProvider(MockNavProvider):
    def __init__(self, exc):
        super().__init__()
        self.exc = exc

    def get_nav_history(self, scheme_code, start, end):
        self.history_calls.append((scheme_code, start, end))
        raise self.exc


@pytest.mark.django_db
def test_requires_authentication(anon_client):
    with use_provider(MockNavProvider()) as factory:
        assert post(anon_client).status_code in (401, 403)
    factory.assert_not_called()
    assert not MutualFundNavFetchState.objects.exists()


@pytest.mark.django_db
def test_requires_csrf_for_session_auth(test_user):
    client = APIClient(enforce_csrf_checks=True)
    client.login(username="testuser", password="testpass123")
    with use_provider(MockNavProvider()) as factory:
        response = post(client)
    assert response.status_code == 403
    assert "CSRF" in str(response.json())
    factory.assert_not_called()


@pytest.mark.django_db
def test_cache_hit_skips_provider_even_during_cooldown(api_client, test_user, clock):
    HistoricalPrice.objects.create(asset_type=AssetType.MUTUAL_FUND, asset_symbol=SCHEME,
        date=DAY, close_price=Decimal("15.288500"), currency="INR")
    MutualFundNavFetchState.objects.create(scheme_code=SCHEME, nav_date=DAY,
        cooldown_until=T0 + timedelta(seconds=30), last_outcome="provider_failure")
    provider = MockNavProvider()
    with use_provider(provider):
        response = post(api_client)
    assert response.status_code == 200
    assert response.json() == {
        "scheme_code": SCHEME, "nav_date": "2023-01-20", "outcome": "cache_hit",
        "nav": "15.288500", "status": "available", "retry_after_seconds": None,
        "failure_category": None, "attempt_id": None,
    }
    assert provider.history_calls == []


@pytest.mark.django_db
def test_first_time_fund_fetches_and_caches_only_exact_date(api_client, clock):
    provider = MockNavProvider({SCHEME: [
        NavPoint(DAY - timedelta(days=1), Decimal("15.1"), "INR"),
        NavPoint(DAY, Decimal("15.2885"), "INR"),
        NavPoint(DAY + timedelta(days=1), Decimal("15.4"), "INR"),
    ]})
    provider.get_nav_history = lambda s, start, end: (  # adjacent rows must be ignored
        provider.history_calls.append((s, start, end)) or provider.histories[s])
    with use_provider(provider):
        response = post(api_client)
    assert response.status_code == 200, response.json()
    data = response.json()
    assert data["outcome"] == "fetched"
    assert data["status"] == "available"
    assert Decimal(data["nav"]) == Decimal("15.2885")
    assert data["failure_category"] is None and data["retry_after_seconds"] is None
    assert provider.history_calls == [(SCHEME, DAY, DAY)]
    assert mf_rows() == [(SCHEME, DAY, Decimal("15.288500"), "INR")]
    state = MutualFundNavFetchState.objects.get(scheme_code=SCHEME, nav_date=DAY)
    assert state.last_outcome == "fetched"
    assert state.in_flight_until is None and state.cooldown_until is None
    lookup = api_client.get("/api/v1/nav/lookup", {"scheme_code": SCHEME, "nav_date": "2023-01-20"})
    assert lookup.json()["status"] == "available"


@pytest.mark.django_db
def test_adjacent_only_history_is_date_unavailable_without_cache_write(api_client, test_user, clock):
    neighbour = NavPoint(DAY - timedelta(days=1), Decimal("15.1"), "INR")
    provider = MockNavProvider()
    provider.get_nav_history = lambda s, start, end: [neighbour]
    with use_provider(provider):
        response = post(api_client)
    data = response.json()
    assert data["outcome"] == "date_unavailable"
    assert data["failure_category"] == "date_unavailable"
    assert data["status"] == "missing" and data["nav"] is None
    assert data["retry_after_seconds"] == 60
    assert data["attempt_id"]
    assert mf_rows() == []
    state = MutualFundNavFetchState.objects.get()
    assert str(state.last_attempt_id) == data["attempt_id"]
    assert state.last_attempt_user_id == test_user.id
    assert state.last_failure_category == "date_unavailable"
    assert state.in_flight_until is None


@pytest.mark.django_db
@pytest.mark.parametrize("exc, expected", [
    (AmfiNavTimeoutError("Timeout fetching x"), "timeout"),
    (AmfiNavFetchError("HTTP 500 for x"), "provider_failure"),
    (AmfiNavFetchError("MFAPI returned a different scheme for 120503"), "provider_failure"),
    (RuntimeError("boom"), "provider_failure"),
])
def test_provider_errors_are_classified(api_client, clock, exc, expected):
    with use_provider(RaisingProvider(exc)):
        data = post(api_client).json()
    assert data["outcome"] == expected
    assert data["failure_category"] == expected
    assert data["status"] == "missing"
    assert data["retry_after_seconds"] == 60
    assert mf_rows() == []


@pytest.mark.django_db
def test_http_timeout_raises_typed_timeout_error():
    def http_get(url, timeout):
        raise AmfiNavTimeoutError(f"Timeout fetching {url}")
    with pytest.raises(AmfiNavTimeoutError):
        AmfiNavProvider(http_get=http_get).get_nav_history(SCHEME, DAY, DAY)
    assert issubclass(AmfiNavTimeoutError, AmfiNavFetchError)


@pytest.mark.django_db
@pytest.mark.parametrize("points", [
    [NavPoint(DAY, Decimal("0"), "INR")],
    [NavPoint(DAY, Decimal("-1"), "INR")],
    [NavPoint(DAY, Decimal("15.2"), "EUR")],
    [NavPoint(DAY, Decimal("15.2"), "INR"), NavPoint(DAY, Decimal("15.3"), "INR")],
    None,
])
def test_invalid_provider_rows_are_not_cached(api_client, clock, points):
    provider = MockNavProvider()
    provider.get_nav_history = lambda s, start, end: points
    with use_provider(provider):
        data = post(api_client).json()
    assert data["outcome"] == "provider_failure"
    assert data["nav"] is None
    assert mf_rows() == []


@pytest.mark.django_db
def test_real_provider_mismatched_scheme_response_is_not_cached(api_client, clock):
    payload = {"status": "SUCCESS", "meta": {"scheme_code": 999999},
               "data": [{"date": "20-01-2023", "nav": "15.2885"}]}
    provider = AmfiNavProvider(http_get=lambda url, timeout: payload)
    with use_provider(provider):
        data = post(api_client).json()
    assert data["outcome"] == "provider_failure"
    assert mf_rows() == []


@pytest.mark.django_db
@pytest.mark.parametrize("body", [
    {"scheme_code": "", "nav_date": "2023-01-20"},
    {"scheme_code": "ABC123", "nav_date": "2023-01-20"},
    {"scheme_code": SCHEME, "nav_date": "not-a-date"},
    {"scheme_code": SCHEME},
    {"scheme_code": SCHEME, "nav_date": "2099-01-01"},
])
def test_invalid_requests_are_rejected_before_provider(api_client, clock, body):
    with use_provider(MockNavProvider()) as factory:
        response = api_client.post(URL, body, format="json")
    assert response.status_code == 400
    factory.assert_not_called()
    assert not MutualFundNavFetchState.objects.exists()


@pytest.mark.django_db
def test_does_not_overwrite_unrelated_non_mutual_fund_row(api_client, clock):
    HistoricalPrice.objects.create(asset_type=AssetType.STOCK, asset_symbol=SCHEME,
        date=DAY, close_price=Decimal("99"), currency="INR", source="yfinance")
    provider = MockNavProvider({SCHEME: [NavPoint(DAY, Decimal("15.2885"), "INR")]})
    with use_provider(provider):
        response = post(api_client)
    assert response.status_code == 409
    assert provider.history_calls == []
    row = HistoricalPrice.objects.get(asset_symbol=SCHEME, date=DAY)
    assert row.asset_type == AssetType.STOCK and row.close_price == Decimal("99")


@pytest.mark.django_db
def test_concurrent_request_during_in_flight_then_both_see_cache(api_client, other_user, clock):
    other = APIClient()
    other.force_authenticate(user=other_user)
    nested = {}
    provider = MockNavProvider()

    def slow_history(scheme, start, end):
        provider.history_calls.append((scheme, start, end))
        nested["response"] = post(other).json()
        return [NavPoint(DAY, Decimal("15.2885"), "INR")]

    provider.get_nav_history = slow_history
    with use_provider(provider):
        first = post(api_client).json()
    assert nested["response"]["outcome"] == "in_flight"
    assert nested["response"]["status"] == "missing"
    assert 0 < nested["response"]["retry_after_seconds"] <= 30
    assert nested["response"]["attempt_id"] is None
    assert first["outcome"] == "fetched"
    assert len(provider.history_calls) == 1
    with use_provider(provider):
        assert post(other).json()["outcome"] == "cache_hit"
        assert post(api_client).json()["outcome"] == "cache_hit"
    assert len(provider.history_calls) == 1


@pytest.mark.django_db
def test_cooldown_after_failure_then_retry_allowed_after_60s(api_client, other_user, clock):
    failing = RaisingProvider(AmfiNavFetchError("HTTP 502"))
    with use_provider(failing):
        first = post(api_client).json()
        clock.advance(10)
        second = post(api_client).json()
    assert first["outcome"] == "provider_failure"
    assert second["outcome"] == "cooldown"
    assert second["failure_category"] == "cooldown"
    assert second["retry_after_seconds"] == 50
    assert second["attempt_id"] == first["attempt_id"]
    assert len(failing.history_calls) == 1

    other = APIClient()
    other.force_authenticate(user=other_user)
    with use_provider(failing):
        assert post(other).json()["attempt_id"] is None  # evidence is bound to the attempting user

    clock.advance(50)
    ok = MockNavProvider({SCHEME: [NavPoint(DAY, Decimal("15.2885"), "INR")]})
    with use_provider(ok):
        third = post(api_client).json()
    assert third["outcome"] == "fetched"
    state = MutualFundNavFetchState.objects.get()
    assert state.cooldown_until is None and state.last_failure_category == ""


@pytest.mark.django_db
def test_stale_in_flight_claim_expires(api_client, clock):
    MutualFundNavFetchState.objects.create(scheme_code=SCHEME, nav_date=DAY,
        in_flight_until=T0 - timedelta(seconds=1))
    provider = MockNavProvider({SCHEME: [NavPoint(DAY, Decimal("15.2885"), "INR")]})
    with use_provider(provider):
        data = post(api_client).json()
    assert data["outcome"] == "fetched"
    assert MutualFundNavFetchState.objects.get().in_flight_until is None


@pytest.mark.django_db
def test_expired_claim_finishing_late_does_not_clobber_new_claim(api_client, clock):
    provider = MockNavProvider()

    def late_failure(scheme, start, end):
        state = MutualFundNavFetchState.objects.get()
        clock.advance(120)
        state.in_flight_until = clock() + timedelta(seconds=30)
        state.in_flight_token = "00000000-0000-0000-0000-000000000001"
        state.save()
        raise AmfiNavFetchError("HTTP 502")

    provider.get_nav_history = late_failure
    with use_provider(provider):
        data = post(api_client).json()
    assert data["outcome"] == "provider_failure"
    state = MutualFundNavFetchState.objects.get()
    assert str(state.in_flight_token) == "00000000-0000-0000-0000-000000000001"
    assert state.cooldown_until is None


@pytest.mark.django_db
def test_database_failure_is_not_treated_as_cache_miss(api_client, clock):
    provider = MockNavProvider()
    with use_provider(provider), patch(
        "market_data.services.missing_nav_fetch.cached_nav_for_date",
        side_effect=DatabaseError("db down"),
    ):
        with pytest.raises(DatabaseError):
            post(api_client)
    assert provider.history_calls == []
    assert not MutualFundNavFetchState.objects.exists()


@pytest.mark.django_db
def test_never_writes_transactions_or_cash(api_client, cash_aware_portfolio, clock):
    provider = MockNavProvider({SCHEME: [NavPoint(DAY, Decimal("15.2885"), "INR")]})
    with use_provider(provider):
        assert post(api_client).json()["outcome"] == "fetched"
    with use_provider(RaisingProvider(AmfiNavFetchError("x"))):
        assert post(api_client, day="2023-01-23").json()["outcome"] == "provider_failure"
    assert not Transaction.objects.exists()
    assert not CashLedgerEntry.objects.exists()


@pytest.mark.django_db
def test_lookup_remains_db_only(api_client):
    with patch(
        "market_data.providers.mutual_fund_nav_provider.AmfiNavProvider.get_nav_history",
    ) as history, patch(
        "market_data.services.missing_nav_fetch.default_mutual_fund_nav_provider",
    ) as factory:
        response = api_client.get("/api/v1/nav/lookup", {"scheme_code": SCHEME, "nav_date": "2023-01-20"})
    assert response.json()["status"] == "missing"
    history.assert_not_called()
    factory.assert_not_called()
    assert not MutualFundNavFetchState.objects.exists()
