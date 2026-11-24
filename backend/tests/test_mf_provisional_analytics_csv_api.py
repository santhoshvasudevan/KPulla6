"""#53 — provider-only fund analytics, read-only historical review, strict CSV."""
import io
import json
from datetime import date
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext

from cash.models import CashEntryType, CashLedgerEntry
from market_data.models import AssetType, BenchmarkIndexConfig, HistoricalPrice
from market_data.providers.mutual_fund_nav_provider import NavPoint
from portfolios.seed import ensure_default_portfolio
from tests.conftest import cached_mf_nav, historical_mf_transaction
from tests.test_mf_provisional_buy_api import (
    DAY,
    SCHEME,
    TODAY,
    TXN_URL,
    cache_payload,
    client_for,
    failed_attempt,
    provisional,
)
from tests.test_mutual_fund_nav_sync import MockNavProvider
from transactions.models import MutualFundTransactionDetail, Transaction
from transactions.services import TransactionValidationError

OTHER = "120504"
BENCH = "INR_TEST"
ASSET_URL = f"/api/v1/analytics/assets/{SCHEME}/performance-metrics"
COMPARE_URL = "/api/v1/analytics/compare"
IMPORT_URL = "/api/v1/transactions/import-csv"
PREVIEW_CASH_URL = "/api/v1/transactions/import-csv/preview-cash"
REFRESH_FACTORY = "market_data.services.mutual_fund_nav_sync.default_mutual_fund_nav_provider"
FUND_BLOCKS = ("metrics", "periodic_returns", "drawdown_periods", "drawdown_series",
               "coverage", "benchmark", "performance_basis", "fund_nav_source", "currency")
# Provider NAV observations around, but never on, the provisional DAY (2026-03-12).
SERIES = [("2026-03-02", "38"), ("2026-03-05", "39"), ("2026-03-09", "38.5"),
          ("2026-03-10", "40"), ("2026-03-13", "41"), ("2026-03-16", "40.5"),
          ("2026-03-18", "42"), ("2026-03-20", "43")]


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch):
    monkeypatch.setattr("portfolios.dates.current_date", lambda: TODAY)


def _seed_fund_and_benchmark_history():
    BenchmarkIndexConfig.objects.create(symbol=BENCH, display_name="INR test", currency="INR")
    for day, value in SERIES:
        cached_mf_nav(SCHEME, day, value)
        cached_mf_nav(OTHER, day, str(Decimal(value) + 1))
        HistoricalPrice.objects.create(asset_symbol=BENCH, asset_type=AssetType.INDEX,
                                       date=date.fromisoformat(day),
                                       close_price=Decimal(value) * 10, currency="INR")


def _price_rows():
    return list(HistoricalPrice.objects.order_by("asset_symbol", "date")
                .values_list("asset_symbol", "asset_type", "date", "close_price", "currency"))


def _fund_view(client):
    asset = client.get(ASSET_URL, {"range": "ALL", "display_currency": "INR",
                                   "benchmark": BENCH})
    compare = client.get(COMPARE_URL, {"subjects": f"asset:{SCHEME},asset:{OTHER}",
                                       "range": "ALL", "benchmark": BENCH})
    assert asset.status_code == 200, asset.json()
    assert compare.status_code == 200, compare.json()
    return asset.json(), compare.json()


def _fund_only(asset, compare):
    """Everything that describes the fund, excluding the personal position block."""
    return (
        {key: asset.get(key) for key in FUND_BLOCKS},
        {key: compare[key] for key in ("normalized_series", "common_start_date",
                                       "common_end_date", "common_point_count", "currency")},
        [{key: s.get(key) for key in FUND_BLOCKS} for s in compare["subjects"]],
    )


def _provisional_body(attempt, **overrides):
    body = dict(units_allotted="100", paid_value="4250", fees="0", provisional_nav="42.5")
    body.update(overrides)
    return provisional(attempt, **body)


# --- fund analytics isolation -------------------------------------------------


@pytest.mark.django_db
def test_fund_heatmap_compare_isolated_from_provisional_add_edit_remove(api_client, legacy_seeded):
    _seed_fund_and_benchmark_history()
    for scheme in (SCHEME, OTHER):
        assert api_client.post(TXN_URL, cache_payload("2026-03-10", scheme_code=scheme),
                               format="json").status_code == 201
    prices_before = _price_rows()
    asset, compare = _fund_view(api_client)
    baseline = _fund_only(asset, compare)
    assert asset["performance_basis"] == "nav" and asset["fund_nav_source"] == "PROVIDER_CACHE"
    assert asset["metrics"]["return"]["cumulative_return"] is not None
    assert asset["periodic_returns"]["monthly"] and asset["periodic_returns"]["yearly"]
    assert asset["benchmark"]["paired_count"] >= 2
    assert asset["personal_metrics"]["nav_provisional"] is False
    assert asset["personal_metrics"]["warnings"] == []
    # Same provider series: Compare subject equals the direct Asset Detail fund view.
    assert baseline[2][0] == {key: asset.get(key) for key in FUND_BLOCKS}

    created = api_client.post(TXN_URL, _provisional_body(failed_attempt(api_client)),
                              format="json")
    assert created.status_code == 201, created.json()
    # The personal portfolio series does use the provisional NAV on its date...
    summary = api_client.get("/api/v1/portfolio/summary", {"display_currency": "INR"}).json()
    point = next(p for p in summary["timeseries"] if p["date"] == DAY)
    assert point["nav_provisional"] is True
    assert point["portfolio_value"] == 200 * 42.5 + 100 * 41  # F1 120503 + OTHER carried
    # ...while fund analytics stay on the provider series.
    asset, compare = _fund_view(api_client)
    assert _fund_only(asset, compare) == baseline
    for payload in (asset, compare["subjects"][0]):
        assert payload["personal_metrics"]["nav_provisional"] is True
        assert any("provisional NAV" in w for w in payload["personal_metrics"]["warnings"])
    assert compare["subjects"][1]["personal_metrics"]["nav_provisional"] is False

    edited = api_client.put(f"{TXN_URL}/{created.json()['id']}",
                            _provisional_body(None, paid_value="4260", fees="10"), format="json")
    assert edited.status_code == 200, edited.json()
    assert _fund_only(*_fund_view(api_client)) == baseline

    assert api_client.delete(f"{TXN_URL}/{created.json()['id']}").status_code == 204
    asset, compare = _fund_view(api_client)
    assert _fund_only(asset, compare) == baseline
    assert asset["personal_metrics"]["nav_provisional"] is False
    assert _price_rows() == prices_before


@pytest.mark.django_db
def test_provisional_only_fund_invents_no_fund_or_benchmark_history(api_client, legacy_seeded):
    BenchmarkIndexConfig.objects.create(symbol=BENCH, display_name="INR test", currency="INR")
    assert api_client.post(TXN_URL, _provisional_body(failed_attempt(api_client)),
                           format="json").status_code == 201
    data = api_client.get(ASSET_URL, {"range": "ALL", "benchmark": BENCH}).json()
    assert data["performance_basis"] == "nav"
    assert data["coverage"]["start"] is None and data["coverage"]["incomplete"] is True
    assert data["metrics"]["return"]["cumulative_return"] is None
    assert data["periodic_returns"]["monthly"] == [] and data["drawdown_series"] == []
    assert data["personal_metrics"]["nav_provisional"] is True
    assert _price_rows() == []


# --- cache-later review --------------------------------------------------------


def _ledger_snapshot():
    txn = Transaction.objects.get()
    detail = txn.mutual_fund_detail
    return (
        (txn.price_per_share, txn.quantity, txn.fees, txn.date, txn.updated_at),
        (detail.nav, detail.units_allotted, detail.paid_value, detail.market_value,
         detail.nav_source, detail.provisional_attempt_id, detail.provisional_confirmed_at,
         detail.provisional_failure_reason, detail.updated_at),
        list(CashLedgerEntry.objects.order_by("id").values_list(
            "id", "entry_type", "date", "amount", "linked_transaction_id")),
    )


def _preview_rows(user_id):
    out = StringIO()
    call_command("preview_mf_nav_corrections", user_id=user_id, stdout=out)
    lines = out.getvalue().strip().splitlines()
    return [json.loads(line) for line in lines[:-1]], lines[-1]


@pytest.mark.django_db
def test_cache_later_exposes_review_without_rewriting_history(
    api_client, cash_aware_portfolio, test_user, other_user
):
    CashLedgerEntry.objects.create(portfolio=cash_aware_portfolio, date=date(2026, 3, 1),
                                   currency="INR", entry_type=CashEntryType.CASH_DEPOSIT,
                                   amount=Decimal("2000"))
    created = api_client.post(TXN_URL, provisional(failed_attempt(api_client),
                                                   portfolio_id=cash_aware_portfolio.id),
                              format="json")
    assert created.status_code == 201, created.json()
    listed = api_client.get(TXN_URL).json()["items"][0]
    assert listed["nav_review"] == {"review_class": "provisional", "reviewable": False,
                                    "cached_nav": None, "nav_difference": None}
    before = _ledger_snapshot()
    assert len(before[2]) == 2  # deposit + BUY settlement

    provider = MockNavProvider({SCHEME: [NavPoint(date.fromisoformat(DAY), Decimal("15.3"))]})
    with patch(REFRESH_FACTORY, return_value=provider):
        refreshed = api_client.post("/api/v1/nav/refresh", {"scheme_codes": [SCHEME]},
                                    format="json")
    assert refreshed.status_code == 202, refreshed.json()
    assert HistoricalPrice.objects.filter(asset_symbol=SCHEME, date=DAY).exists()
    assert _ledger_snapshot() == before

    with CaptureQueriesContext(connection) as queries:
        listed = api_client.get(TXN_URL).json()["items"][0]
        api_client.get("/api/v1/portfolio/holdings", {"display_currency": "INR"})
        api_client.get("/api/v1/portfolio/summary", {"display_currency": "INR"})
        rows, summary = _preview_rows(test_user.id)
    assert not any(q["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))
                   for q in queries.captured_queries)
    assert _ledger_snapshot() == before

    assert listed["nav"] == 15.2885 and listed["nav_source"] == "PROVISIONAL_USER"
    assert (listed["units_allotted"], listed["paid_value"], listed["fees"]) == (65.4321, 1005, 4.64)
    assert listed["provisional_superseded_by_cache"] is True
    review = listed["nav_review"]
    assert (review["review_class"], review["reviewable"], review["cached_nav"]) == (
        "cached_discrepancy", True, 15.3)
    assert review["nav_difference"] == pytest.approx(0.0115)

    assert len(rows) == 1
    assert rows[0]["transaction_id"] == created.json()["id"]
    assert (rows[0]["review_class"], rows[0]["nav_source"], rows[0]["status"]) == (
        "cached_discrepancy", "PROVISIONAL_USER", "NAV_MISMATCH")
    assert rows[0]["nav_difference"] == "0.011500"
    assert summary.endswith("No records changed.")

    other = client_for(other_user)
    assert other.get(TXN_URL).json()["items"] == []
    assert _preview_rows(other_user.id)[0] == []


@pytest.mark.django_db
def test_preview_distinguishes_provisional_legacy_missing_and_cached_discrepancy(
    api_client, legacy_seeded, test_user, other_user
):
    portfolio = ensure_default_portfolio(test_user)
    provisional_id = api_client.post(TXN_URL, _provisional_body(failed_attempt(api_client)),
                                     format="json").json()["id"]
    legacy = historical_mf_transaction(portfolio, cache_payload(
        "2026-03-03", scheme_code=OTHER, nav="40", folio_number="L1"))
    legacy_off = historical_mf_transaction(portfolio, cache_payload(
        "2026-03-05", nav="39", folio_number="L2"))
    cached_mf_nav(SCHEME, "2026-03-05", "39.5")
    missing_row = cached_mf_nav(SCHEME, "2026-03-10", "40")
    missing_id = api_client.post(TXN_URL, cache_payload("2026-03-10"), format="json").json()["id"]
    missing_row.delete()
    cached_mf_nav(SCHEME, "2026-03-16", "45")
    verified_id = api_client.post(TXN_URL, cache_payload(
        "2026-03-16", paid_value="4500", market_value="4500"), format="json").json()["id"]
    historical_mf_transaction(ensure_default_portfolio(other_user), cache_payload(
        "2026-03-03", scheme_code=OTHER, nav="40"))

    rows, summary = _preview_rows(test_user.id)
    by_id = {row["transaction_id"]: row for row in rows}
    assert verified_id not in by_id
    assert {txn_id: (r["review_class"], r["nav_source"], r["reviewable"], r["status"])
            for txn_id, r in by_id.items()} == {
        provisional_id: ("provisional", "PROVISIONAL_USER", False, "NAV_MISSING"),
        legacy.id: ("legacy", "UNKNOWN", False, "NAV_MISSING"),
        legacy_off.id: ("cached_discrepancy", "UNKNOWN", True, "NAV_MISMATCH"),
        missing_id: ("missing", "PROVIDER_CACHE", False, "NAV_MISSING"),
    }
    assert by_id[legacy_off.id]["nav_difference"] == "0.500000"
    assert summary == ("Review rows: 4 (provisional: 1, legacy: 1, missing: 1, "
                       "cached_discrepancy: 1). No records changed.")

    listed = {t["id"]: t["nav_review"] for t in api_client.get(TXN_URL).json()["items"]}
    assert listed[verified_id] is None
    assert listed[legacy.id]["review_class"] == "legacy"
    assert listed[missing_id]["review_class"] == "missing"
    assert listed[legacy_off.id]["cached_nav"] == 39.5

    with pytest.raises(TypeError):
        call_command("preview_mf_nav_corrections", user_id=test_user.id, apply=True)


# --- strict CSV ------------------------------------------------------------------

MF_HEADER = ("Action,Scheme Code,Scheme Name,Folio Number,Investment Date,NAV Date,NAV,"
             "Units Allotted,Paid Value,Market Value,Fees,Currency")


def _post_csv(client, url, text, **params):
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return client.post(f"{url}?{query}" if query else url,
                       {"file": io.BytesIO(text.encode("utf-8"))}, format="multipart")


def _assert_nothing_imported(cash_before):
    assert not Transaction.objects.exists()
    assert not MutualFundTransactionDetail.objects.exists()
    assert list(CashLedgerEntry.objects.values_list("id", flat=True)) == cash_before


@pytest.mark.django_db
@pytest.mark.parametrize("extra_header", [
    "Provisional NAV", "provisional_attempt_id", "Confirm Provisional NAV",
    "Confirm Paid Value", "NAV Source", "Attempt ID",
])
def test_csv_consent_columns_are_rejected_even_when_cache_exists(
    api_client, cash_aware_portfolio, extra_header
):
    cached_mf_nav(SCHEME, DAY, "15.2885")
    text = (f"{MF_HEADER},{extra_header}\n"
            f"BUY,{SCHEME},Test Fund,F1,03/12/26,03/12/26,15.2885,65.4321,1005,1000.36,4.64,INR,true\n")
    for url, params in ((PREVIEW_CASH_URL, {}),
                        (IMPORT_URL, {"create_cash_deposits": "true",
                                      "cash_preview_confirmed": "true"})):
        response = _post_csv(api_client, url, text, **params)
        assert response.status_code == 200, response.json()
        body = response.json()
        assert body["success"] is False and body["imported_count"] == 0
        assert body["errors"][0]["row"] == 1 and body["errors"][0]["field"] == "headers"
        assert "Provisional NAV columns are not accepted" in body["errors"][0]["message"]
    _assert_nothing_imported([])


@pytest.mark.django_db
def test_confirmed_cash_import_with_one_missing_row_aborts_without_deposits(
    api_client, cash_aware_portfolio
):
    cached_mf_nav(SCHEME, "2026-03-10", "40")
    failed_attempt(api_client)  # unsuccessful fetch evidence must not grant CSV consent
    text = (f"{MF_HEADER}\n"
            f"BUY,{SCHEME},Test Fund,F1,03/10/26,03/10/26,40,100,4000,4000,0,INR\n"
            f"BUY,{SCHEME},Test Fund,F1,03/12/26,03/12/26,42.5,100,4250,4250,0,INR\n")
    preview = _post_csv(api_client, PREVIEW_CASH_URL, text).json()
    assert preview["success"] is False and preview["errors"][0]["row"] == 3
    response = _post_csv(api_client, IMPORT_URL, text, create_cash_deposits="true",
                         cash_preview_confirmed="true")
    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["success"] is False and body["imported_count"] == 0
    assert [e["row"] for e in body["errors"]] == [3]
    assert "cached NAV" in body["errors"][0]["message"]
    _assert_nothing_imported([])


@pytest.mark.django_db
def test_row_failing_after_deposits_rolls_back_whole_confirmed_batch(
    api_client, cash_aware_portfolio
):
    from transactions import mutual_fund_services

    for day in ("2026-03-10", "2026-03-13"):
        cached_mf_nav(SCHEME, day, "40")
    text = (f"{MF_HEADER}\n"
            f"BUY,{SCHEME},Test Fund,F1,03/10/26,03/10/26,40,100,4000,4000,0,INR\n"
            f"BUY,{SCHEME},Test Fund,F1,03/13/26,03/13/26,40,100,4000,4000,0,INR\n")
    real_create = mutual_fund_services.create_mutual_fund_transaction
    calls = []

    def cache_vanishes_on_second_row(*args, **kwargs):
        calls.append(kwargs["validated_data"]["nav_date"])
        if len(calls) == 2:
            raise TransactionValidationError(
                f"Exact-date cached NAV is required for scheme {SCHEME} on 2026-03-13.")
        return real_create(*args, **kwargs)

    with patch.object(mutual_fund_services, "create_mutual_fund_transaction",
                      side_effect=cache_vanishes_on_second_row):
        response = _post_csv(api_client, IMPORT_URL, text, create_cash_deposits="true",
                             cash_preview_confirmed="true")
    assert len(calls) == 2
    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["success"] is False and body["imported_count"] == 0
    assert body["errors"] == [{"row": 3, "field": "NAV", "message": (
        f"Exact-date cached NAV is required for scheme {SCHEME} on 2026-03-13.")}]
    _assert_nothing_imported([])
