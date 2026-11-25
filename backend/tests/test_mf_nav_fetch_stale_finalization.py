"""#60 — a fetch whose claim was superseded must not finalize cache, claim, cooldown or evidence.

Deterministic SQLite interleavings: the replacement request runs inside the original
request's provider call after the controlled clock expires the original claim. SQLite
ignores SELECT ... FOR UPDATE, so these tests prove the ownership fence, not
PostgreSQL row-lock serialization.
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from cash.models import CashLedgerEntry
from market_data.models import MutualFundNavFetchState
from market_data.providers.mutual_fund_nav_provider import AmfiNavFetchError, NavPoint
from market_data.services import missing_nav_fetch
from tests.test_mf_nav_fetch_missing_api import (  # noqa: F401 (clock is a fixture)
    DAY,
    SCHEME,
    T0,
    clock,
    mf_rows,
    post,
    use_provider,
)
from tests.test_mutual_fund_nav_sync import MockNavProvider
from transactions.models import Transaction

EXPIRE = missing_nav_fetch.IN_FLIGHT_TTL_SECONDS + 1


class ScriptedProvider(MockNavProvider):
    """Each provider call runs the next scripted step; a step returns rows or raises."""

    def __init__(self, *steps):
        super().__init__()
        self.steps = list(steps)

    def get_nav_history(self, scheme_code, start, end):
        self.history_calls.append((scheme_code, start, end))
        return self.steps.pop(0)()


def rows(nav):
    return [NavPoint(DAY, Decimal(nav), "INR")]


def fail():
    raise AmfiNavFetchError("HTTP 502")


def client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def state():
    return MutualFundNavFetchState.objects.get(scheme_code=SCHEME, nav_date=DAY)


@pytest.mark.django_db
@pytest.mark.parametrize("same_user", [True, False], ids=["duplicate_click", "other_user"])
def test_late_success_cannot_overwrite_replacement_cached_nav(
    api_client, test_user, other_user, clock, same_user,
):
    replacement_client = api_client if same_user else client_for(other_user)
    nested = {}

    def expire_then_replace_with_20():
        clock.advance(EXPIRE)
        nested["b"] = post(replacement_client).json()
        return rows("10")

    provider = ScriptedProvider(expire_then_replace_with_20, lambda: rows("20"))
    with use_provider(provider):
        a = post(api_client).json()

    assert nested["b"]["outcome"] == "fetched"
    assert Decimal(nested["b"]["nav"]) == Decimal("20")
    assert a["outcome"] == "cache_hit"
    assert Decimal(a["nav"]) == Decimal("20")
    assert a["attempt_id"] is None and a["failure_category"] is None
    assert mf_rows() == [(SCHEME, DAY, Decimal("20.000000"), "INR")]
    s = state()
    assert s.last_outcome == "fetched"
    assert s.in_flight_token is None and s.in_flight_until is None and s.cooldown_until is None

    with use_provider(provider):
        assert post(api_client).json()["outcome"] == "cache_hit"
        assert post(client_for(other_user)).json()["outcome"] == "cache_hit"
    assert len(provider.history_calls) == 2
    assert not Transaction.objects.exists()
    assert not CashLedgerEntry.objects.exists()


@pytest.mark.django_db
def test_late_success_while_replacement_running_then_replacement_succeeds(
    api_client, other_user, clock,
):
    claim = {}

    def expire_then_replacement_claims():
        clock.advance(EXPIRE)
        claim["token"], early = missing_nav_fetch._claim(SCHEME, DAY, other_user.id, clock())
        assert early is None
        return rows("10")

    provider = ScriptedProvider(expire_then_replacement_claims)
    with use_provider(provider):
        a = post(api_client).json()

    assert a["outcome"] == "in_flight"
    assert a["nav"] is None and a["status"] == "missing" and a["attempt_id"] is None
    assert 0 < a["retry_after_seconds"] <= missing_nav_fetch.IN_FLIGHT_TTL_SECONDS
    assert mf_rows() == []
    assert state().in_flight_token == claim["token"]

    b = missing_nav_fetch._finalize(
        SCHEME, DAY, claim["token"], "fetched", Decimal("20"), other_user.id, clock(),
    )
    assert b.outcome == "fetched" and b.nav == Decimal("20")
    assert mf_rows() == [(SCHEME, DAY, Decimal("20.000000"), "INR")]
    with use_provider(provider):
        follow_up = post(api_client).json()
    assert follow_up["outcome"] == "cache_hit" and Decimal(follow_up["nav"]) == Decimal("20")
    assert len(provider.history_calls) == 1


@pytest.mark.django_db
def test_late_success_while_replacement_running_then_replacement_fails(
    api_client, test_user, other_user, clock,
):
    claim = {}

    def expire_then_replacement_claims():
        clock.advance(EXPIRE)
        claim["token"], _ = missing_nav_fetch._claim(SCHEME, DAY, other_user.id, clock())
        return rows("10")

    with use_provider(ScriptedProvider(expire_then_replacement_claims)):
        a = post(api_client).json()
    assert a["outcome"] == "in_flight"

    b = missing_nav_fetch._finalize(
        SCHEME, DAY, claim["token"], "provider_failure", None, other_user.id, clock(),
    )
    assert mf_rows() == []
    s = state()
    assert s.last_attempt_id == b.attempt_id and s.last_attempt_user_id == other_user.id
    with use_provider(ScriptedProvider()):
        follow_up = post(api_client).json()
    assert follow_up["outcome"] == "cooldown"
    assert follow_up["attempt_id"] is None  # replacement evidence stays bound to its user


@pytest.mark.django_db
@pytest.mark.parametrize("same_user", [True, False], ids=["duplicate_click", "other_user"])
def test_late_success_after_replacement_failed_keeps_replacement_cooldown_and_evidence(
    api_client, other_user, clock, same_user,
):
    replacement_client = api_client if same_user else client_for(other_user)
    nested = {}

    def expire_then_replacement_fails():
        clock.advance(EXPIRE)
        nested["b"] = post(replacement_client).json()
        clock.advance(5)
        return rows("10")

    provider = ScriptedProvider(expire_then_replacement_fails, fail)
    with use_provider(provider):
        a = post(api_client).json()

    b = nested["b"]
    assert b["outcome"] == "provider_failure" and b["attempt_id"]
    assert a["outcome"] == "cooldown"
    assert a["nav"] is None and a["status"] == "missing"
    assert a["retry_after_seconds"] == missing_nav_fetch.COOLDOWN_SECONDS - 5
    assert a["attempt_id"] == (b["attempt_id"] if same_user else None)
    assert mf_rows() == []
    s = state()
    assert str(s.last_attempt_id) == b["attempt_id"]
    assert s.last_outcome == "provider_failure"
    assert s.cooldown_until == T0 + timedelta(seconds=EXPIRE + missing_nav_fetch.COOLDOWN_SECONDS)


@pytest.mark.django_db
def test_late_failure_after_replacement_cached_reports_cache(api_client, other_user, clock):
    nested = {}

    def expire_then_replace_with_20():
        clock.advance(EXPIRE)
        nested["b"] = post(client_for(other_user)).json()
        raise AmfiNavFetchError("HTTP 502")

    with use_provider(ScriptedProvider(expire_then_replace_with_20, lambda: rows("20"))):
        a = post(api_client).json()

    assert nested["b"]["outcome"] == "fetched"
    assert a["outcome"] == "cache_hit" and Decimal(a["nav"]) == Decimal("20")
    assert a["attempt_id"] is None and a["failure_category"] is None
    s = state()
    assert s.last_outcome == "fetched" and s.cooldown_until is None and s.last_attempt_id is None


@pytest.mark.django_db
def test_late_failure_after_replacement_failed_grants_no_new_attempt(
    api_client, other_user, clock,
):
    nested = {}

    def expire_then_replacement_fails():
        clock.advance(EXPIRE)
        nested["b"] = post(client_for(other_user)).json()
        raise AmfiNavFetchError("HTTP 502")

    with use_provider(ScriptedProvider(expire_then_replacement_fails, fail)):
        a = post(api_client).json()

    assert a["outcome"] == "cooldown" and a["attempt_id"] is None
    s = state()
    assert str(s.last_attempt_id) == nested["b"]["attempt_id"]
    assert s.last_attempt_user_id == other_user.id


@pytest.mark.django_db
def test_late_success_after_replacement_lease_lapsed_reports_retry_not_value(
    api_client, other_user, clock,
):
    claim = {}

    def replacement_claims_then_its_lease_lapses():
        clock.advance(EXPIRE)
        claim["token"], _ = missing_nav_fetch._claim(SCHEME, DAY, other_user.id, clock())
        clock.advance(EXPIRE)
        return rows("10")

    with use_provider(ScriptedProvider(replacement_claims_then_its_lease_lapses)):
        a = post(api_client).json()

    assert a["outcome"] == "in_flight"
    assert a["nav"] is None and a["retry_after_seconds"] == 1
    assert mf_rows() == []
    assert state().in_flight_token == claim["token"]


@pytest.mark.django_db
def test_expired_but_unreplaced_claim_still_finalizes(api_client, clock):
    def slow():
        clock.advance(EXPIRE)
        return rows("10")

    with use_provider(ScriptedProvider(slow)):
        a = post(api_client).json()
    assert a["outcome"] == "fetched" and Decimal(a["nav"]) == Decimal("10")
    assert mf_rows() == [(SCHEME, DAY, Decimal("10.000000"), "INR")]
    assert state().in_flight_token is None
