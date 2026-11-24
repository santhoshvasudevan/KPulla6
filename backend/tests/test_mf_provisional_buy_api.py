"""#50 — confirmed provisional mutual-fund BUY: eligibility, write, valuation, isolation."""
import uuid
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError
from django.utils import timezone
from rest_framework.test import APIClient

from cash.models import CashEntryType, CashLedgerEntry
from market_data.models import AssetType, HistoricalPrice, MutualFundNavFetchState
from portfolios.models import Portfolio
from portfolios.seed import ensure_default_portfolio
from tests.conftest import cached_mf_nav, historical_mf_transaction
from tests.test_mutual_fund_nav_sync import MockNavProvider
from transactions.models import MutualFundTransactionDetail, Transaction
from transactions.mutual_fund_services import create_mutual_fund_transaction
from transactions.services import TransactionValidationError

SCHEME = "120503"
DAY = "2026-03-12"
TODAY = date(2026, 3, 20)
TXN_URL = "/api/v1/transactions"
PREVIEW_URL = "/api/v1/nav/provisional-preview"
FACTORY = "market_data.services.missing_nav_fetch.default_mutual_fund_nav_provider"


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch):
    monkeypatch.setattr("portfolios.dates.current_date", lambda: TODAY)


def failed_attempt(client, scheme=SCHEME, day=DAY):
    provider = MockNavProvider()
    with patch(FACTORY, return_value=provider):
        data = client.post("/api/v1/nav/fetch-missing",
                           {"scheme_code": scheme, "nav_date": day}, format="json").json()
    assert data["outcome"] == "date_unavailable", data
    return data["attempt_id"]


def provisional(attempt_id, **overrides):
    body = {
        "asset_type": "MUTUAL_FUND", "scheme_code": SCHEME, "scheme_name": "Test Fund",
        "folio_number": "F1", "type": "BUY", "investment_date": DAY, "nav_date": DAY,
        "units_allotted": "65.4321", "paid_value": "1005", "fees": "4.64", "currency": "INR",
        "provisional_nav": "15.2885", "provisional_attempt_id": attempt_id,
        "confirm_provisional_nav": True, "confirm_paid_value": True,
    }
    body.update(overrides)
    return {k: v for k, v in body.items() if v is not None}


def cache_payload(day, **overrides):
    body = {
        "asset_type": "MUTUAL_FUND", "scheme_code": SCHEME, "scheme_name": "Test Fund",
        "folio_number": "F1", "type": "BUY", "investment_date": day, "nav_date": day,
        "units_allotted": "100", "paid_value": "4000", "market_value": "4000", "fees": "0",
        "currency": "INR",
    }
    body.update(overrides)
    return body


def mf_cache_rows():
    return list(HistoricalPrice.objects.filter(asset_type=AssetType.MUTUAL_FUND)
                .order_by("date").values_list("date", "close_price"))


def assert_nothing_written(before_cache):
    assert not Transaction.objects.exists()
    assert not MutualFundTransactionDetail.objects.exists()
    assert not CashLedgerEntry.objects.exists()
    assert mf_cache_rows() == before_cache


def client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


# --- write path ---------------------------------------------------------------


@pytest.mark.django_db
def test_provisional_buy_preserves_statement_fields_and_stays_off_provider_cache(
    api_client, legacy_seeded, test_user
):
    attempt = failed_attempt(api_client)
    response = api_client.post(TXN_URL, provisional(attempt, market_value="999"), format="json")
    assert response.status_code == 201, response.json()
    data = response.json()
    assert data["nav"] == data["price_per_share"] == 15.2885
    assert data["units_allotted"] == 65.4321
    assert data["paid_value"] == 1005
    assert data["fees"] == 4.64
    assert data["market_value"] == 1000.3587  # 15.2885 × 65.4321 = 1000.35866085, half-up 4 dp
    assert data["nav_source"] == "PROVISIONAL_USER"
    assert data["nav_provisional"] is True
    assert data["provisional_failure_reason"] == "date_unavailable"
    assert data["provisional_superseded_by_cache"] is False
    assert data["nav_verification_status"] == "NAV_MISSING"
    detail = MutualFundTransactionDetail.objects.get()
    assert str(detail.provisional_attempt_id) == attempt
    assert detail.provisional_confirmed_by_id == test_user.id
    assert detail.provisional_confirmed_at is not None
    assert mf_cache_rows() == []


@pytest.mark.django_db
def test_cache_path_writes_record_provider_source_without_touching_existing_rows(
    api_client, legacy_seeded, test_user
):
    old = historical_mf_transaction(ensure_default_portfolio(test_user),
                                    cache_payload("2026-03-01", nav="40"))
    cached_mf_nav(SCHEME, "2026-03-10", "40")
    response = api_client.post(TXN_URL, cache_payload("2026-03-10"), format="json")
    assert response.status_code == 201, response.json()
    assert response.json()["nav_source"] == "PROVIDER_CACHE"
    assert response.json()["nav_provisional"] is False
    assert MutualFundTransactionDetail.objects.get(transaction=old).nav_source == "UNKNOWN"


def _other_users_attempt(api_client, other_user):
    return failed_attempt(client_for(other_user))


def _superseded_attempt(api_client, other_user):
    attempt = failed_attempt(api_client)
    MutualFundNavFetchState.objects.update(last_attempt_id=uuid.uuid4())
    return attempt


def _later_fetch_succeeded(api_client, other_user):
    attempt = failed_attempt(api_client)
    MutualFundNavFetchState.objects.update(last_outcome="fetched")
    return attempt


@pytest.mark.django_db
@pytest.mark.parametrize("make_attempt, overrides", [
    (lambda c, o: None, {}),
    (lambda c, o: str(uuid.uuid4()), {}),
    (lambda c, o: "not-a-uuid", {}),
    (_other_users_attempt, {}),
    (_superseded_attempt, {}),
    (_later_fetch_succeeded, {}),
    (lambda c, o: failed_attempt(c), {"nav_date": "2026-03-13", "investment_date": "2026-03-13"}),
    (lambda c, o: failed_attempt(c, scheme="120504"), {}),
    (lambda c, o: failed_attempt(c), {"confirm_provisional_nav": False}),
    (lambda c, o: failed_attempt(c), {"confirm_paid_value": None}),
    (lambda c, o: failed_attempt(c), {"confirm_provisional_nav": "yes-please"}),
    (lambda c, o: failed_attempt(c), {"fees": None}),
    (lambda c, o: failed_attempt(c), {"provisional_nav": "0"}),
    (lambda c, o: failed_attempt(c), {"type": "SELL"}),
], ids=["no-attempt", "forged-attempt", "malformed-attempt", "other-user", "superseded",
        "later-success", "wrong-date", "wrong-scheme", "no-nav-confirmation",
        "no-paid-confirmation", "non-boolean-confirmation", "fees-inferred", "zero-nav", "sell"])
def test_ineligible_provisional_writes_leave_no_artifacts(
    api_client, legacy_seeded, other_user, make_attempt, overrides
):
    attempt = make_attempt(api_client, other_user)
    response = api_client.post(TXN_URL, provisional(attempt, **overrides), format="json")
    assert response.status_code == 400, response.json()
    assert_nothing_written([])


@pytest.mark.django_db
def test_stale_attempt_is_rejected(api_client, legacy_seeded):
    attempt = failed_attempt(api_client)
    later = timezone.now() + timedelta(hours=25)
    with patch("transactions.mf_provisional._now", return_value=later):
        response = api_client.post(TXN_URL, provisional(attempt), format="json")
    assert response.status_code == 400
    assert "too old" in str(response.json())
    assert_nothing_written([])


@pytest.mark.django_db
def test_available_cache_cannot_be_bypassed_and_cache_path_still_works(api_client, legacy_seeded):
    attempt = failed_attempt(api_client)
    cached_mf_nav(SCHEME, DAY, "15.3")
    response = api_client.post(TXN_URL, provisional(attempt), format="json")
    assert response.status_code == 400
    assert "Cached NAV is now available" in str(response.json())
    assert_nothing_written([(date(2026, 3, 12), Decimal("15.300000"))])
    ok = api_client.post(TXN_URL, cache_payload(DAY, market_value="1530", paid_value="1530"), format="json")
    assert ok.status_code == 201
    assert ok.json()["nav"] == 15.3 and ok.json()["nav_source"] == "PROVIDER_CACHE"


@pytest.mark.django_db
def test_database_failure_during_eligibility_does_not_save(api_client, legacy_seeded):
    attempt = failed_attempt(api_client)
    with patch("transactions.mf_provisional.cached_nav_for_date", side_effect=DatabaseError("db down")):
        with pytest.raises(DatabaseError):
            api_client.post(TXN_URL, provisional(attempt), format="json")
    assert_nothing_written([])


@pytest.mark.django_db
def test_service_and_csv_paths_stay_strict(api_client, legacy_seeded, test_user):
    attempt = failed_attempt(api_client)
    with pytest.raises(TransactionValidationError, match="cached NAV"):
        create_mutual_fund_transaction(test_user, validated_data=provisional(attempt))
    text = ("Action,Scheme Code,Scheme Name,Folio Number,Investment Date,NAV Date,NAV,Units Allotted,"
            "Paid Value,Market Value,Fees,Currency,Provisional NAV,Provisional Attempt ID\n"
            f"BUY,{SCHEME},Test Fund,F1,03/12/26,03/12/26,15.2885,65.4321,1005,1000.36,4.64,INR,"
            f"15.2885,{attempt}\n")
    response = api_client.post("/api/v1/transactions/import-csv", {
        "file": SimpleUploadedFile("t.csv", text.encode(), content_type="text/csv")}, format="multipart")
    assert response.json()["success"] is False
    assert response.json()["imported_count"] == 0
    assert "cached NAV" in str(response.json())
    assert_nothing_written([])


@pytest.mark.django_db
def test_insufficient_cash_rolls_back_then_normal_settlement(api_client, cash_aware_portfolio):
    attempt = failed_attempt(api_client)
    CashLedgerEntry.objects.create(portfolio=cash_aware_portfolio, date=date(2026, 3, 1),
        currency="INR", entry_type=CashEntryType.CASH_DEPOSIT, amount=Decimal("1000"))
    response = api_client.post(TXN_URL, provisional(attempt, portfolio_id=cash_aware_portfolio.id),
                               format="json")
    assert response.status_code == 400
    assert response.json()["detail"] == "Insufficient cash balance for purchase."
    assert response.json()["shortfall"] == 5
    assert not Transaction.objects.exists() and not MutualFundTransactionDetail.objects.exists()
    assert CashLedgerEntry.objects.count() == 1
    CashLedgerEntry.objects.create(portfolio=cash_aware_portfolio, date=date(2026, 3, 1),
        currency="INR", entry_type=CashEntryType.CASH_DEPOSIT, amount=Decimal("5"))
    response = api_client.post(TXN_URL, provisional(attempt, portfolio_id=cash_aware_portfolio.id),
                               format="json")
    assert response.status_code == 201, response.json()
    settlement = CashLedgerEntry.objects.get(linked_transaction_id=response.json()["id"])
    assert settlement.amount == Decimal("-1005")
    assert settlement.date == date(2026, 3, 12)


# --- edits / revalidation -------------------------------------------------------


@pytest.mark.django_db
def test_unchanged_provisional_buy_edit_keeps_authority_without_new_fetch(api_client, legacy_seeded):
    attempt = failed_attempt(api_client)
    created = api_client.post(TXN_URL, provisional(attempt), format="json").json()
    MutualFundNavFetchState.objects.update(last_attempt_id=uuid.uuid4())  # evidence moved on
    edit = provisional(None, paid_value="1006", fees="5.64")
    response = api_client.put(f"{TXN_URL}/{created['id']}", edit, format="json")
    assert response.status_code == 200, response.json()
    assert response.json()["paid_value"] == 1006
    assert response.json()["nav_source"] == "PROVISIONAL_USER"
    assert str(MutualFundTransactionDetail.objects.get().provisional_attempt_id) == attempt


@pytest.mark.django_db
@pytest.mark.parametrize("change", [
    {"provisional_nav": "15.30"},
    {"nav_date": "2026-03-13", "investment_date": "2026-03-13"},
    {"confirm_paid_value": False},
])
def test_changed_provisional_edit_requires_revalidation(api_client, legacy_seeded, change):
    attempt = failed_attempt(api_client)
    created = api_client.post(TXN_URL, provisional(attempt), format="json").json()
    response = api_client.put(f"{TXN_URL}/{created['id']}", provisional(None, **change), format="json")
    assert response.status_code == 400, response.json()
    detail = MutualFundTransactionDetail.objects.get()
    assert detail.nav == Decimal("15.2885") and detail.nav_date == date(2026, 3, 12)


@pytest.mark.django_db
def test_cache_arrival_requires_cache_path_and_reads_do_not_mutate(api_client, legacy_seeded):
    attempt = failed_attempt(api_client)
    created = api_client.post(TXN_URL, provisional(attempt), format="json").json()
    cached_mf_nav(SCHEME, DAY, "15.3")
    listed = api_client.get(TXN_URL).json()["items"][0]
    assert listed["nav"] == 15.2885 and listed["nav_source"] == "PROVISIONAL_USER"
    assert listed["provisional_superseded_by_cache"] is True
    assert listed["nav_verification_status"] == "NAV_MISMATCH"
    assert MutualFundTransactionDetail.objects.get().nav == Decimal("15.2885")
    rejected = api_client.put(f"{TXN_URL}/{created['id']}", provisional(None), format="json")
    assert rejected.status_code == 400
    body = provisional(None, market_value="1000.3587")
    for key in ("provisional_nav", "provisional_attempt_id", "confirm_provisional_nav", "confirm_paid_value"):
        body.pop(key, None)
    response = api_client.put(f"{TXN_URL}/{created['id']}", body, format="json")
    assert response.status_code == 200, response.json()
    assert response.json()["nav"] == 15.3
    assert response.json()["nav_source"] == "PROVIDER_CACHE"


# --- preview --------------------------------------------------------------------


@pytest.mark.django_db
def test_preview_returns_backend_market_value_without_writes_or_provider(api_client, anon_client, legacy_seeded):
    attempt = failed_attempt(api_client)
    body = {"scheme_code": SCHEME, "nav_date": DAY, "provisional_nav": "15.2885",
            "units_allotted": "65.4321", "attempt_id": attempt}
    assert anon_client.post(PREVIEW_URL, body, format="json").status_code in (401, 403)
    with patch(FACTORY) as factory:
        response = api_client.post(PREVIEW_URL, body, format="json")
        forged = api_client.post(PREVIEW_URL, {**body, "attempt_id": str(uuid.uuid4())}, format="json")
        cached_mf_nav(SCHEME, DAY, "15.3")
        conflict = api_client.post(PREVIEW_URL, body, format="json")
    factory.assert_not_called()
    assert response.status_code == 200, response.json()
    assert response.json() == {
        "scheme_code": SCHEME, "nav_date": DAY, "nav": "15.288500", "units_allotted": "65.43210000",
        "market_value": "1000.3587", "nav_source": "PROVISIONAL_USER", "status": "provisional",
    }
    assert forged.status_code == 400 and forged.json()["code"] == "not_eligible"
    assert conflict.status_code == 409 and conflict.json()["code"] == "cache_available"
    assert not Transaction.objects.exists()


@pytest.mark.django_db
def test_preview_requires_csrf_for_session_auth(legacy_seeded):
    client = APIClient(enforce_csrf_checks=True)
    client.login(username="testuser", password="testpass123")
    response = client.post(PREVIEW_URL, {"scheme_code": SCHEME, "nav_date": DAY,
                                         "provisional_nav": "1", "units_allotted": "1"}, format="json")
    assert response.status_code == 403


# --- valuation ------------------------------------------------------------------


def _record_provisional_42_5(client, portfolio_id=None, folio="F1"):
    attempt = failed_attempt(client)
    response = client.post(TXN_URL, provisional(
        attempt, units_allotted="100", paid_value="4250", fees="0", provisional_nav="42.5",
        folio_number=folio, portfolio_id=portfolio_id), format="json")
    assert response.status_code == 201, response.json()
    assert response.json()["market_value"] == 4250
    return response.json()


def _holding(client, folio="F1", **params):
    data = client.get("/api/v1/portfolio/holdings", {"display_currency": "INR", **params}).json()
    return next(h for h in data["holdings"] if h.get("folio_number") == folio), data


def _summary(client, **params):
    response = client.get("/api/v1/portfolio/summary", {"display_currency": "INR", **params})
    assert response.status_code == 200, response.json()
    return response.json()


def _point(summary, day):
    return next(p for p in summary["timeseries"] if p["date"] == day)


@pytest.mark.django_db
@pytest.mark.parametrize("scope_kind", ["single", "all"])
def test_provisional_nav_carries_until_next_cached_nav(api_client, legacy_seeded, test_user, scope_kind):
    scope = ({"portfolio_id": ensure_default_portfolio(test_user).id} if scope_kind == "single"
             else {"portfolio_scope": "all"})
    cached_mf_nav(SCHEME, "2026-03-10", "40")
    _record_provisional_42_5(api_client)

    holding, holdings = _holding(api_client, **scope)
    assert holding["current_value"] == 4250
    assert holding["latest_nav"] == 42.5
    assert holding["nav_source"] == "PROVISIONAL_USER"
    assert holding["nav_provisional"] is True
    assert holding["unrealized_pl"] == 0
    assert any("provisional NAV from 2026-03-12" in w for w in holding["warnings"])
    alloc = next(a for a in holdings["allocation"] if a.get("folio_number") == "F1")
    assert alloc["current_value"] == 4250

    summary = _summary(api_client, **scope)
    assert summary["current_value"] == 4250
    assert summary["nav_provisional"] is True
    assert any("provisional NAV" in w for w in summary["warnings"])
    assert _point(summary, "2026-03-12")["portfolio_value"] == 4250
    assert _point(summary, "2026-03-12")["nav_provisional"] is True
    assert summary["timeseries"][-1]["date"] == "2026-03-20"
    assert summary["timeseries"][-1]["portfolio_value"] == summary["current_value"]

    cached_mf_nav(SCHEME, "2026-03-16", "45")
    holding, _ = _holding(api_client, **scope)
    assert holding["current_value"] == 4500
    assert holding["latest_nav"] == 45
    assert "nav_provisional" not in holding
    summary = _summary(api_client, **scope)
    assert summary["current_value"] == 4500
    assert "nav_provisional" not in summary
    assert _point(summary, "2026-03-15")["portfolio_value"] == 4250
    assert _point(summary, "2026-03-15")["nav_provisional"] is True
    assert _point(summary, "2026-03-16")["portfolio_value"] == 4500
    assert "nav_provisional" not in _point(summary, "2026-03-16")
    assert summary["timeseries"][-1]["portfolio_value"] == summary["current_value"]

    perf = api_client.get("/api/v1/portfolio/performance",
                          {"display_currency": "INR", "range": "ALL", **scope})
    assert perf.status_code == 200
    detail = MutualFundTransactionDetail.objects.get()
    assert detail.nav == Decimal("42.5") and detail.nav_source == "PROVISIONAL_USER"
    assert mf_cache_rows() == [(date(2026, 3, 10), Decimal("40.000000")),
                               (date(2026, 3, 16), Decimal("45.000000"))]


@pytest.mark.django_db
def test_first_time_fund_without_any_cache_is_valued_provisionally(api_client, legacy_seeded):
    _record_provisional_42_5(api_client)
    holding, _ = _holding(api_client)
    assert holding["current_value"] == 4250 and holding["nav_status"] == "ok"
    assert _summary(api_client)["current_value"] == 4250


@pytest.mark.django_db
def test_provisional_nav_does_not_reprice_other_folio_portfolio_or_user(
    api_client, legacy_seeded, test_user, other_user
):
    cached_mf_nav(SCHEME, "2026-03-10", "40")
    second = Portfolio.objects.create(user=test_user, name="Second", base_currency="INR")
    assert api_client.post(TXN_URL, cache_payload("2026-03-10", folio_number="F2"),
                           format="json").status_code == 201
    assert api_client.post(TXN_URL, cache_payload("2026-03-10", portfolio_id=second.id),
                           format="json").status_code == 201
    other_client = client_for(other_user)
    other_portfolio = ensure_default_portfolio(other_user)
    other_portfolio.cash_aware_enabled = False
    other_portfolio.save(update_fields=["cash_aware_enabled"])
    assert other_client.post(TXN_URL, cache_payload("2026-03-10"), format="json").status_code == 201

    _record_provisional_42_5(api_client)

    default_id = ensure_default_portfolio(test_user).id
    assert _holding(api_client, folio="F2", portfolio_id=default_id)[0]["current_value"] == 4000
    assert _holding(api_client, folio="F1", portfolio_id=default_id)[0]["current_value"] == 4250
    assert _summary(api_client, portfolio_id=default_id)["current_value"] == 8250
    assert _holding(api_client, portfolio_id=second.id)[0]["current_value"] == 4000
    assert _holding(other_client)[0]["current_value"] == 4000
    assert "nav_provisional" not in _holding(other_client)[0]
    assert _summary(api_client, portfolio_id=second.id)["current_value"] == 4000
    assert _summary(other_client)["current_value"] == 4000

    # All scope merges F1 across portfolios; each folio keeps its own NAV (no averaging).
    merged, _ = _holding(api_client, folio="F1", portfolio_scope="all")
    assert merged["current_value"] == 8250
    assert merged["nav_source"] == "MIXED"
    assert merged["latest_nav"] is None
    assert _summary(api_client, portfolio_scope="all")["current_value"] == 4000 + 4000 + 4250


@pytest.mark.django_db
def test_conflicting_same_date_provisional_navs_are_reported_not_averaged(api_client, legacy_seeded):
    _record_provisional_42_5(api_client)
    attempt = MutualFundNavFetchState.objects.get().last_attempt_id
    response = api_client.post(TXN_URL, provisional(
        str(attempt), units_allotted="100", paid_value="4300", fees="0", provisional_nav="43"),
        format="json")
    assert response.status_code == 201, response.json()
    holding, _ = _holding(api_client)
    assert holding["nav_status"] == "nav_missing"
    assert holding["current_value"] == 0
    assert any("conflicting provisional NAVs" in w for w in holding["warnings"])
    summary = _summary(api_client)
    assert any("conflicting provisional NAVs" in w for w in summary["warnings"])
    assert _point(summary, "2026-03-12")["portfolio_value"] is None


@pytest.mark.django_db
def test_fund_metrics_ignore_provisional_nav(api_client, legacy_seeded):
    for day, value in [("2026-03-02", "38"), ("2026-03-05", "39"), ("2026-03-10", "40")]:
        cached_mf_nav(SCHEME, day, value)
    assert api_client.post(TXN_URL, cache_payload("2026-03-10", folio_number="F2"),
                           format="json").status_code == 201
    url = f"/api/v1/analytics/assets/{SCHEME}/performance-metrics"
    params = {"range": "ALL", "display_currency": "INR"}
    before = api_client.get(url, params).json()
    _record_provisional_42_5(api_client)
    after = api_client.get(url, params).json()
    assert after["performance_basis"] == "nav"
    assert after["metrics"] == before["metrics"]
    assert after["periodic_returns"] == before["periodic_returns"]
    assert after["range"] == before["range"]


@pytest.mark.django_db
def test_reads_never_contact_providers(api_client, legacy_seeded):
    _record_provisional_42_5(api_client)
    with patch(FACTORY) as factory, patch(
        "market_data.providers.mutual_fund_nav_provider.AmfiNavProvider.get_nav_history"
    ) as history:
        _holding(api_client)
        _summary(api_client)
        api_client.get(TXN_URL)
        api_client.get("/api/v1/portfolio/performance", {"display_currency": "INR", "range": "ALL"})
    factory.assert_not_called()
    history.assert_not_called()
