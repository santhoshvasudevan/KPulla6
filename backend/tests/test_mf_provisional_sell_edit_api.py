"""#51 — provisional mutual-fund SELLs and transaction edits: proceeds, tax, settlements, rollback."""
import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError

from cash.models import CashEntryType, CashLedgerEntry
from market_data.models import MutualFundNavFetchState
from portfolios.models import Portfolio
from portfolios.seed import ensure_default_portfolio
from tests.conftest import cached_mf_nav
from tests.test_mf_provisional_buy_api import (
    DAY,
    FACTORY,
    PREVIEW_URL,
    SCHEME,
    TXN_URL,
    cache_payload,
    client_for,
    failed_attempt,
    mf_cache_rows,
    provisional,
)
from transactions.models import MutualFundTransactionDetail, Transaction
from transactions.mutual_fund_services import create_mutual_fund_transaction
from transactions.services import TransactionValidationError

TODAY = date(2026, 3, 20)
BUY_DAY = "2026-03-10"


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch):
    monkeypatch.setattr("portfolios.dates.current_date", lambda: TODAY)


def sell(attempt_id, **overrides):
    """Provisional redemption of 40 units at 42.5: Market Value 1700.0000."""
    body = {"type": "SELL", "units_allotted": "40", "paid_value": "1700", "fees": "2",
            "provisional_nav": "42.5"}
    body.update(overrides)
    return provisional(attempt_id, **body)


def without_provisional(body):
    return {k: v for k, v in body.items() if k not in (
        "provisional_nav", "provisional_attempt_id", "confirm_provisional_nav", "confirm_paid_value")}


def deposit(portfolio, day, amount):
    return CashLedgerEntry.objects.create(portfolio=portfolio, date=date.fromisoformat(day),
        currency="INR", entry_type=CashEntryType.CASH_DEPOSIT, amount=Decimal(amount))


def withdraw(portfolio, day, amount):
    return CashLedgerEntry.objects.create(portfolio=portfolio, date=date.fromisoformat(day),
        currency="INR", entry_type=CashEntryType.CASH_WITHDRAWAL, amount=-Decimal(amount))


def cached_buy(client, portfolio=None, **overrides):
    """Cache-path BUY of 100 units at 40 on BUY_DAY (paid 4000)."""
    cached_mf_nav(SCHEME, BUY_DAY, "40")
    body = cache_payload(BUY_DAY, **overrides)
    if portfolio is not None:
        body["portfolio_id"] = portfolio.id
    response = client.post(TXN_URL, body, format="json")
    assert response.status_code == 201, response.json()
    return response.json()


def funded_portfolio(test_user):
    portfolio = ensure_default_portfolio(test_user)
    portfolio.cash_aware_enabled = True
    portfolio.save(update_fields=["cash_aware_enabled", "updated_at"])
    deposit(portfolio, "2026-03-01", "4000")
    return portfolio


def linked(txn_id):
    return {e.entry_type: e for e in CashLedgerEntry.objects.filter(linked_transaction_id=txn_id)}


def ledger_state():
    return sorted(CashLedgerEntry.objects.values_list(
        "id", "portfolio_id", "date", "entry_type", "amount", "linked_transaction_id"))


def detail_state(txn_id):
    d = MutualFundTransactionDetail.objects.select_related("transaction").get(transaction_id=txn_id)
    t = d.transaction
    return (t.portfolio_id, t.type, t.date, t.quantity, t.price_per_share, t.fees,
            t.actual_cash_received, d.nav, d.nav_date, d.investment_date, d.units_allotted,
            d.paid_value, d.market_value, d.nav_source, d.provisional_attempt_id)


def _holding(client, folio="F1", **params):
    data = client.get("/api/v1/portfolio/holdings", {"display_currency": "INR", **params}).json()
    return next((h for h in data["holdings"] if h.get("folio_number") == folio), None)


def _summary(client, **params):
    response = client.get("/api/v1/portfolio/summary", {"display_currency": "INR", **params})
    assert response.status_code == 200, response.json()
    return response.json()


def _point(summary, day):
    return next(p for p in summary["timeseries"] if p["date"] == day)


# --- create ---------------------------------------------------------------------


@pytest.mark.django_db
def test_provisional_sell_preserves_proceeds_and_settles_without_provider(api_client, seeded, test_user):
    portfolio = funded_portfolio(test_user)
    cached_buy(api_client, portfolio)
    attempt = failed_attempt(api_client)
    with patch(FACTORY) as factory:
        response = api_client.post(TXN_URL, sell(attempt, market_value="1"), format="json")
    factory.assert_not_called()
    assert response.status_code == 201, response.json()
    data = response.json()
    assert data["type"] == "SELL"
    assert data["nav"] == data["price_per_share"] == 42.5
    assert data["units_allotted"] == 40 and data["paid_value"] == 1700 and data["fees"] == 2
    assert data["market_value"] == 1700  # backend-owned; client "1" ignored
    assert data["nav_source"] == "PROVISIONAL_USER" and data["nav_provisional"] is True
    assert data["provisional_failure_reason"] == "date_unavailable"
    detail = MutualFundTransactionDetail.objects.get(transaction_id=data["id"])
    assert str(detail.provisional_attempt_id) == attempt
    assert detail.provisional_confirmed_by_id == test_user.id
    entries = linked(data["id"])
    assert set(entries) == {CashEntryType.SELL_SETTLEMENT}
    assert entries[CashEntryType.SELL_SETTLEMENT].amount == Decimal("1700.0000")
    assert entries[CashEntryType.SELL_SETTLEMENT].date == date(2026, 3, 12)
    assert mf_cache_rows() == [(date(2026, 3, 10), Decimal("40.000000"))]


@pytest.mark.django_db
@pytest.mark.parametrize("cash_aware", [False, True], ids=["legacy", "cash-aware"])
def test_zero_paid_value_fallback_uses_provisional_nav(api_client, seeded, test_user, cash_aware):
    portfolio = ensure_default_portfolio(test_user)
    portfolio.cash_aware_enabled = cash_aware
    portfolio.save(update_fields=["cash_aware_enabled", "updated_at"])
    deposit(portfolio, "2026-03-01", "4000")
    cached_buy(api_client, portfolio)  # cached 40 must not leak into the fallback
    attempt = failed_attempt(api_client)
    response = api_client.post(TXN_URL, sell(attempt, paid_value="0"), format="json")
    assert response.status_code == 201, response.json()
    assert response.json()["paid_value"] == 0
    entries = linked(response.json()["id"])
    if cash_aware:
        # 40 × 42.5 − 2 (not 40 × 40 − 2 = 1598)
        assert entries[CashEntryType.SELL_SETTLEMENT].amount == Decimal("1698.0000")
        assert set(entries) == {CashEntryType.SELL_SETTLEMENT}
    else:
        assert entries == {}


@pytest.mark.django_db
@pytest.mark.parametrize("paid, actual, expected", [
    ("1700", "1650", {CashEntryType.SELL_SETTLEMENT: "1700", CashEntryType.TAX_WITHHELD: "-50"}),
    ("1700", "1750", {CashEntryType.SELL_SETTLEMENT: "1700", CashEntryType.TAX_RELEASED: "50"}),
    ("0", "1690", {CashEntryType.SELL_SETTLEMENT: "1698", CashEntryType.TAX_WITHHELD: "-8"}),
    ("0", "1700", {CashEntryType.SELL_SETTLEMENT: "1698", CashEntryType.TAX_RELEASED: "2"}),
], ids=["paid-withheld", "paid-released", "fallback-withheld", "fallback-released"])
def test_provisional_sell_tax_withheld_and_released(api_client, seeded, test_user, paid, actual, expected):
    portfolio = funded_portfolio(test_user)
    cached_buy(api_client, portfolio)
    attempt = failed_attempt(api_client)
    response = api_client.post(TXN_URL, sell(attempt, paid_value=paid, actual_cash_received=actual,
                                             settlement_note="TDS"), format="json")
    assert response.status_code == 201, response.json()
    assert response.json()["actual_cash_received"] == float(actual)
    entries = linked(response.json()["id"])
    assert {k: e.amount for k, e in entries.items()} == {k: Decimal(v) for k, v in expected.items()}


@pytest.mark.django_db
@pytest.mark.parametrize("make_attempt, overrides", [
    (lambda c, o: None, {}),
    (lambda c, o: str(uuid.uuid4()), {}),
    (lambda c, o: failed_attempt(client_for(o)), {}),
    (lambda c, o: failed_attempt(c), {"confirm_paid_value": False}),
    (lambda c, o: failed_attempt(c), {"fees": None}),
    (lambda c, o: failed_attempt(c), {"nav_date": "2026-03-13", "investment_date": "2026-03-13"}),
], ids=["no-attempt", "forged", "other-user", "no-proceeds-confirmation", "fees-inferred", "wrong-date"])
def test_ineligible_provisional_sell_leaves_no_artifacts(
    api_client, seeded, test_user, other_user, make_attempt, overrides
):
    portfolio = funded_portfolio(test_user)
    bought = cached_buy(api_client, portfolio)
    before = ledger_state()
    attempt = make_attempt(api_client, other_user)
    response = api_client.post(TXN_URL, sell(attempt, **overrides), format="json")
    assert response.status_code == 400, response.json()
    assert list(Transaction.objects.values_list("id", flat=True)) == [bought["id"]]
    assert ledger_state() == before


@pytest.mark.django_db
def test_available_cache_cannot_be_overridden_for_sell(api_client, legacy_seeded):
    attempt = failed_attempt(api_client)
    cached_mf_nav(SCHEME, DAY, "42")
    response = api_client.post(TXN_URL, sell(attempt), format="json")
    assert response.status_code == 400
    assert "Cached NAV is now available" in str(response.json())
    assert not Transaction.objects.exists()


@pytest.mark.django_db
def test_sell_service_and_csv_paths_stay_strict(api_client, legacy_seeded, test_user):
    attempt = failed_attempt(api_client)
    with pytest.raises(TransactionValidationError, match="cached NAV"):
        create_mutual_fund_transaction(test_user, validated_data=sell(attempt))
    text = ("Action,Scheme Code,Scheme Name,Folio Number,Investment Date,NAV Date,NAV,Units Allotted,"
            "Paid Value,Market Value,Fees,Currency,Provisional NAV,Provisional Attempt ID\n"
            f"SELL,{SCHEME},Test Fund,F1,03/12/26,03/12/26,42.5,40,1700,1700,2,INR,42.5,{attempt}\n")
    response = api_client.post("/api/v1/transactions/import-csv", {
        "file": SimpleUploadedFile("t.csv", text.encode(), content_type="text/csv")}, format="multipart")
    assert response.json()["success"] is False and response.json()["imported_count"] == 0
    assert not Transaction.objects.exists()


# --- position / history -----------------------------------------------------------


@pytest.mark.django_db
def test_partial_redemption_values_remaining_units_provisionally_until_cache(api_client, legacy_seeded):
    cached_buy(api_client)
    attempt = failed_attempt(api_client)
    assert api_client.post(TXN_URL, sell(attempt), format="json").status_code == 201

    holding = _holding(api_client)
    assert holding["quantity"] == 60
    assert holding["current_value"] == 2550  # 60 × 42.5
    assert holding["nav_provisional"] is True
    assert any("provisional NAV from 2026-03-12" in w for w in holding["warnings"])
    summary = _summary(api_client)
    assert summary["current_value"] == 2550 and summary["nav_provisional"] is True
    assert _point(summary, "2026-03-11")["portfolio_value"] == 4000
    assert _point(summary, "2026-03-12")["portfolio_value"] == 2550
    assert _point(summary, "2026-03-12")["nav_provisional"] is True

    cached_mf_nav(SCHEME, "2026-03-16", "45")
    holding = _holding(api_client)
    assert holding["current_value"] == 2700 and "nav_provisional" not in holding
    summary = _summary(api_client)
    assert summary["current_value"] == 2700 and "nav_provisional" not in summary
    assert _point(summary, "2026-03-15")["nav_provisional"] is True
    assert "nav_provisional" not in _point(summary, "2026-03-16")


@pytest.mark.django_db
def test_full_redemption_leaves_no_provisional_value(api_client, legacy_seeded):
    cached_buy(api_client)
    attempt = failed_attempt(api_client)
    response = api_client.post(TXN_URL, sell(attempt, units_allotted="100", paid_value="4250"),
                               format="json")
    assert response.status_code == 201, response.json()
    assert response.json()["market_value"] == 4250
    holding = _holding(api_client)
    assert holding is None or holding["current_value"] == 0
    summary = _summary(api_client)
    assert summary["current_value"] == 0
    assert "nav_provisional" not in summary
    assert not any("provisional" in w for w in summary.get("warnings", []))
    assert _point(summary, "2026-03-11")["portfolio_value"] == 4000
    assert "nav_provisional" not in _point(summary, "2026-03-12")


# --- edits ------------------------------------------------------------------------


@pytest.mark.django_db
def test_same_nav_sell_edit_reuses_authority_and_updates_settlements_in_place(
    api_client, seeded, test_user
):
    portfolio = funded_portfolio(test_user)
    cached_buy(api_client, portfolio)
    attempt = failed_attempt(api_client)
    created = api_client.post(TXN_URL, sell(attempt), format="json").json()
    settlement_id = linked(created["id"])[CashEntryType.SELL_SETTLEMENT].id
    MutualFundNavFetchState.objects.update(last_attempt_id=uuid.uuid4())  # evidence moved on

    with patch(FACTORY) as factory:
        withheld = api_client.put(f"{TXN_URL}/{created['id']}",
                                  sell(None, paid_value="1720", actual_cash_received="1700"), format="json")
    factory.assert_not_called()
    assert withheld.status_code == 200, withheld.json()
    assert withheld.json()["id"] == created["id"]
    assert withheld.json()["nav_source"] == "PROVISIONAL_USER"
    entries = linked(created["id"])
    assert entries[CashEntryType.SELL_SETTLEMENT].id == settlement_id
    assert entries[CashEntryType.SELL_SETTLEMENT].amount == Decimal("1720")
    assert entries[CashEntryType.TAX_WITHHELD].amount == Decimal("-20")

    released = api_client.put(f"{TXN_URL}/{created['id']}", sell(None, paid_value="1690"), format="json")
    assert released.status_code == 200, released.json()
    entries = linked(created["id"])
    assert set(entries) == {CashEntryType.SELL_SETTLEMENT}
    assert entries[CashEntryType.SELL_SETTLEMENT].id == settlement_id
    assert entries[CashEntryType.SELL_SETTLEMENT].amount == Decimal("1690")
    assert Transaction.objects.filter(type="SELL").count() == 1
    assert str(MutualFundTransactionDetail.objects.get(transaction_id=created["id"]).provisional_attempt_id) == attempt


@pytest.mark.django_db
@pytest.mark.parametrize("change", [
    {"provisional_nav": "43"},
    {"nav_date": "2026-03-13", "investment_date": "2026-03-13"},
    {"type": "BUY"},
], ids=["nav", "date", "type"])
def test_changed_provisional_sell_edit_requires_fresh_attempt(api_client, legacy_seeded, change):
    cached_buy(api_client)
    attempt = failed_attempt(api_client)
    created = api_client.post(TXN_URL, sell(attempt), format="json").json()
    before = detail_state(created["id"])
    response = api_client.put(f"{TXN_URL}/{created['id']}", sell(None, **change), format="json")
    assert response.status_code == 400, response.json()
    assert detail_state(created["id"]) == before


@pytest.mark.django_db
def test_new_date_with_fresh_attempt_moves_settlement_in_place(api_client, seeded, test_user):
    portfolio = funded_portfolio(test_user)
    cached_buy(api_client, portfolio)
    created = api_client.post(TXN_URL, sell(failed_attempt(api_client)), format="json").json()
    settlement_id = linked(created["id"])[CashEntryType.SELL_SETTLEMENT].id
    new_attempt = failed_attempt(api_client, day="2026-03-13")
    response = api_client.put(f"{TXN_URL}/{created['id']}", sell(
        new_attempt, nav_date="2026-03-13", investment_date="2026-03-13", provisional_nav="43"),
        format="json")
    assert response.status_code == 200, response.json()
    assert response.json()["id"] == created["id"] and response.json()["nav"] == 43
    assert response.json()["market_value"] == 1720
    entry = linked(created["id"])[CashEntryType.SELL_SETTLEMENT]
    assert entry.id == settlement_id and entry.date == date(2026, 3, 13)
    assert str(MutualFundTransactionDetail.objects.get(transaction_id=created["id"]).provisional_attempt_id) == new_attempt


@pytest.mark.django_db
def test_cache_arrival_switches_sell_edit_to_cache_path_and_resettles(api_client, seeded, test_user):
    portfolio = funded_portfolio(test_user)
    cached_buy(api_client, portfolio)
    created = api_client.post(TXN_URL, sell(failed_attempt(api_client), paid_value="0"),
                              format="json").json()
    settlement_id = linked(created["id"])[CashEntryType.SELL_SETTLEMENT].id
    cached_mf_nav(SCHEME, DAY, "43")

    rejected = api_client.put(f"{TXN_URL}/{created['id']}", sell(None, paid_value="0"), format="json")
    assert rejected.status_code == 400
    assert "Cached NAV is now available" in str(rejected.json())

    body = without_provisional(sell(None, paid_value="0", market_value="1720"))
    response = api_client.put(f"{TXN_URL}/{created['id']}", body, format="json")
    assert response.status_code == 200, response.json()
    assert response.json()["nav"] == 43 and response.json()["nav_source"] == "PROVIDER_CACHE"
    assert response.json()["nav_provisional"] is False
    detail = MutualFundTransactionDetail.objects.get(transaction_id=created["id"])
    assert detail.provisional_attempt_id is None and detail.provisional_confirmed_at is None
    assert detail.provisional_confirmed_by_id is None and detail.provisional_failure_reason == ""
    entry = linked(created["id"])[CashEntryType.SELL_SETTLEMENT]
    assert entry.id == settlement_id
    assert entry.amount == Decimal("1718.0000")  # 40 × 43 − 2 from the cached NAV


@pytest.mark.django_db
def test_legacy_created_provisional_sell_gains_settlement_on_first_cash_aware_edit(
    api_client, seeded, test_user
):
    portfolio = ensure_default_portfolio(test_user)
    portfolio.cash_aware_enabled = False
    portfolio.save(update_fields=["cash_aware_enabled", "updated_at"])
    cached_buy(api_client, portfolio)
    created = api_client.post(TXN_URL, sell(failed_attempt(api_client)), format="json").json()
    assert linked(created["id"]) == {}
    portfolio.cash_aware_enabled = True
    portfolio.save(update_fields=["cash_aware_enabled", "updated_at"])
    response = api_client.put(f"{TXN_URL}/{created['id']}", sell(None), format="json")
    assert response.status_code == 200, response.json()
    assert linked(created["id"])[CashEntryType.SELL_SETTLEMENT].amount == Decimal("1700")


@pytest.mark.django_db
def test_provisional_buy_edit_never_uses_nav_only_exception(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    portfolio.cash_aware_enabled = False
    portfolio.save(update_fields=["cash_aware_enabled", "updated_at"])
    created = api_client.post(TXN_URL, provisional(failed_attempt(api_client)), format="json").json()
    portfolio.cash_aware_enabled = True
    portfolio.save(update_fields=["cash_aware_enabled", "updated_at"])
    before = detail_state(created["id"])
    response = api_client.put(f"{TXN_URL}/{created['id']}", provisional(None), format="json")
    assert response.status_code == 400, response.json()
    assert response.json()["detail"] == "Insufficient cash balance for purchase."
    assert detail_state(created["id"]) == before
    assert not CashLedgerEntry.objects.exists()


# --- cash safeguards and rollback --------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("change", [
    {"paid_value": "1000"},
    {"actual_cash_received": "1000"},
    {"investment_date": "2026-03-15"},
], ids=["lower-proceeds", "higher-withheld", "later-date"])
def test_sell_edit_that_breaks_later_balance_rolls_back(api_client, seeded, test_user, change):
    portfolio = funded_portfolio(test_user)
    cached_buy(api_client, portfolio)
    created = api_client.post(TXN_URL, sell(failed_attempt(api_client)), format="json").json()
    withdraw(portfolio, "2026-03-14", "1700")  # spends the redemption proceeds
    before_ledger, before_detail = ledger_state(), detail_state(created["id"])
    response = api_client.put(f"{TXN_URL}/{created['id']}", sell(None, **change), format="json")
    assert response.status_code == 409, response.json()
    body = response.json()
    assert body["detail"] == "This transaction change would make future cash balance negative."
    assert body["currency"] == "INR" and body["earliest_negative_date"] == "2026-03-14"
    assert ledger_state() == before_ledger
    assert detail_state(created["id"]) == before_detail


@pytest.mark.django_db
def test_sell_moved_to_another_portfolio_checks_the_source_ledger(api_client, seeded, test_user):
    portfolio = funded_portfolio(test_user)
    second = Portfolio.objects.create(user=test_user, name="Second", base_currency="INR",
                                      cash_aware_enabled=True)
    cached_buy(api_client, portfolio)
    created = api_client.post(TXN_URL, sell(failed_attempt(api_client)), format="json").json()
    withdraw(portfolio, "2026-03-14", "1700")
    before_ledger, before_detail = ledger_state(), detail_state(created["id"])
    response = api_client.put(f"{TXN_URL}/{created['id']}", sell(None, portfolio_id=second.id),
                              format="json")
    assert response.status_code == 409, response.json()
    assert ledger_state() == before_ledger
    assert detail_state(created["id"]) == before_detail


@pytest.mark.django_db
def test_unrelated_sell_edit_with_unchanged_settlement_is_not_blocked(api_client, seeded, test_user):
    portfolio = funded_portfolio(test_user)
    cached_buy(api_client, portfolio)
    created = api_client.post(TXN_URL, sell(failed_attempt(api_client)), format="json").json()
    withdraw(portfolio, "2026-03-14", "1700")
    response = api_client.put(f"{TXN_URL}/{created['id']}", sell(None, scheme_name="Renamed Fund"),
                              format="json")
    assert response.status_code == 200, response.json()


@pytest.mark.django_db
def test_sell_to_buy_with_fresh_attempt_needs_cash_and_rolls_back(api_client, seeded, test_user):
    portfolio = funded_portfolio(test_user)
    cached_buy(api_client, portfolio)  # spends the 4000 deposit
    attempt = failed_attempt(api_client)
    created = api_client.post(TXN_URL, sell(attempt), format="json").json()
    before_ledger, before_detail = ledger_state(), detail_state(created["id"])
    response = api_client.put(f"{TXN_URL}/{created['id']}", sell(attempt, type="BUY"), format="json")
    assert response.status_code in (400, 409), response.json()
    assert ledger_state() == before_ledger
    assert detail_state(created["id"]) == before_detail


@pytest.mark.django_db
def test_provisional_buy_edit_insufficient_cash_rolls_back_without_orphans(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    portfolio.cash_aware_enabled = True
    portfolio.save(update_fields=["cash_aware_enabled", "updated_at"])
    deposit(portfolio, "2026-03-01", "1005")
    created = api_client.post(TXN_URL, provisional(failed_attempt(api_client)), format="json").json()
    before_ledger, before_detail = ledger_state(), detail_state(created["id"])
    response = api_client.put(f"{TXN_URL}/{created['id']}", provisional(None, paid_value="1100"),
                              format="json")
    assert response.status_code == 400
    assert response.json()["shortfall"] == 95
    assert ledger_state() == before_ledger
    assert detail_state(created["id"]) == before_detail
    assert Transaction.objects.count() == 1


@pytest.mark.django_db
def test_database_failure_during_edit_eligibility_does_not_save(api_client, legacy_seeded):
    cached_buy(api_client)
    created = api_client.post(TXN_URL, sell(failed_attempt(api_client)), format="json").json()
    before = detail_state(created["id"])
    with patch("transactions.mf_provisional.cached_nav_for_date", side_effect=DatabaseError("db down")):
        with pytest.raises(DatabaseError):
            api_client.put(f"{TXN_URL}/{created['id']}", sell(None, paid_value="1690"), format="json")
    assert detail_state(created["id"]) == before


# --- isolation ----------------------------------------------------------------------


@pytest.mark.django_db
def test_cross_user_edits_and_previews_are_rejected(api_client, seeded, test_user, other_user):
    portfolio = funded_portfolio(test_user)
    cached_buy(api_client, portfolio)
    created = api_client.post(TXN_URL, sell(failed_attempt(api_client)), format="json").json()
    other_client = client_for(other_user)
    other_portfolio = ensure_default_portfolio(other_user)
    before_ledger, before_detail = ledger_state(), detail_state(created["id"])

    assert other_client.put(f"{TXN_URL}/{created['id']}", sell(None), format="json").status_code == 404
    moved = api_client.put(f"{TXN_URL}/{created['id']}", sell(None, portfolio_id=other_portfolio.id),
                           format="json")
    assert moved.status_code == 404
    other_attempt = failed_attempt(other_client, day="2026-03-13")
    stolen = api_client.put(f"{TXN_URL}/{created['id']}", sell(
        other_attempt, nav_date="2026-03-13", investment_date="2026-03-13"), format="json")
    assert stolen.status_code == 400
    preview = other_client.post(PREVIEW_URL, {
        "scheme_code": SCHEME, "nav_date": DAY, "provisional_nav": "42.5", "units_allotted": "40",
        "type": "SELL", "transaction_id": created["id"]}, format="json")
    assert preview.status_code == 404
    assert ledger_state() == before_ledger
    assert detail_state(created["id"]) == before_detail


# --- preview ------------------------------------------------------------------------


@pytest.mark.django_db
def test_sell_preview_returns_backend_proceeds_and_tax_without_writes(api_client, legacy_seeded):
    attempt = failed_attempt(api_client)
    base = {"scheme_code": SCHEME, "nav_date": DAY, "provisional_nav": "42.5", "units_allotted": "40",
            "attempt_id": attempt, "type": "SELL"}
    with patch(FACTORY) as factory:
        mv_only = api_client.post(PREVIEW_URL, base, format="json")
        paid = api_client.post(PREVIEW_URL, {**base, "paid_value": "1700", "fees": "2",
                                             "actual_cash_received": "1650"}, format="json")
        fallback = api_client.post(PREVIEW_URL, {**base, "paid_value": "0", "fees": "2",
                                                 "actual_cash_received": "1700"}, format="json")
        negative = api_client.post(PREVIEW_URL, {**base, "paid_value": "0", "fees": "5000"}, format="json")
    factory.assert_not_called()
    assert mv_only.status_code == 200, mv_only.json()
    assert mv_only.json()["market_value"] == "1700.0000"
    assert "calculated_proceeds" not in mv_only.json()
    assert paid.json()["calculated_proceeds"] == "1700.0000"
    assert paid.json()["tax_withheld"] == "50.0000" and paid.json()["tax_released"] == "0.0000"
    assert fallback.json()["calculated_proceeds"] == "1698.0000"
    assert fallback.json()["tax_released"] == "2.0000"
    assert negative.status_code == 200 and negative.json()["calculated_proceeds"] is None
    assert not Transaction.objects.exists()


@pytest.mark.django_db
def test_preview_reuses_existing_sell_authority_only_for_same_type(api_client, legacy_seeded):
    cached_buy(api_client)
    created = api_client.post(TXN_URL, sell(failed_attempt(api_client)), format="json").json()
    base = {"scheme_code": SCHEME, "nav_date": DAY, "provisional_nav": "42.5", "units_allotted": "30",
            "transaction_id": created["id"]}
    same = api_client.post(PREVIEW_URL, {**base, "type": "SELL"}, format="json")
    assert same.status_code == 200, same.json()
    assert same.json()["market_value"] == "1275.0000"
    other_type = api_client.post(PREVIEW_URL, base, format="json")  # defaults to BUY
    assert other_type.status_code == 400 and other_type.json()["code"] == "not_eligible"
