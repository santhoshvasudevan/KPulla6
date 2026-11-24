"""Exact-date cache is authoritative on writes; historical cash is not backfilled by NAV edits."""
from datetime import date
from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile

from cash.models import CashLedgerEntry
from market_data.models import HistoricalPrice, AssetType
from tests.test_cash_aware_transactions_api import _mf_payload, _legacy_portfolio, _enable_cash_aware
from transactions.models import Transaction, MutualFundTransactionDetail


def cached(value="15.288500", day="2023-01-20", currency="INR"):
    return HistoricalPrice.objects.create(asset_type=AssetType.MUTUAL_FUND,
        asset_symbol="120503", date=date.fromisoformat(day), close_price=Decimal(value), currency=currency)


def payload(**overrides):
    return _mf_payload(investment_date="2023-01-20", nav_date="2023-01-20",
        nav="15.228500", units_allotted="65", paid_value="1000",
        market_value="989.8525", fees="10.1475", **overrides)


@pytest.mark.django_db
@pytest.mark.parametrize("kind", ["BUY", "SELL"])
def test_write_uses_cached_nav_and_preserves_statement_fields(api_client, legacy_seeded, kind):
    cached()
    response = api_client.post("/api/v1/transactions", payload(type=kind), format="json")
    assert response.status_code == 201, response.json()
    data = response.json()
    assert data["nav"] == data["price_per_share"] == 15.2885
    assert data["paid_value"] == 1000
    assert data["units_allotted"] == 65
    assert data["fees"] == 10.1475
    assert data["market_value"] == 989.8525
    assert data["nav_verification_status"] == "VALUE_MISMATCH"


@pytest.mark.django_db
@pytest.mark.parametrize("case", ["absent", "previous", "future", "zero", "currency"])
def test_write_requires_positive_exact_date_inr_nav(api_client, legacy_seeded, case):
    if case == "previous":
        cached(day="2023-01-19")
    elif case == "future":
        cached(day="2023-01-21")
    elif case == "zero":
        cached(value="0")
    elif case == "currency":
        cached(currency="EUR")
    response = api_client.post("/api/v1/transactions", payload(), format="json")
    assert response.status_code == 400
    assert "cached NAV" in str(response.json())
    assert not Transaction.objects.exists()
    assert not CashLedgerEntry.objects.exists()


@pytest.mark.django_db
def test_legacy_nav_only_correction_does_not_backfill_cash(api_client, seeded, test_user):
    portfolio = _legacy_portfolio(test_user)
    row = cached(value="15.228500")
    original = api_client.post("/api/v1/transactions", payload(portfolio_id=portfolio.id), format="json")
    assert original.status_code == 201, original.json()
    pk = original.json()["id"]
    _enable_cash_aware(portfolio)
    row.close_price = Decimal("15.288500")
    row.save()
    response = api_client.put(f"/api/v1/transactions/{pk}", payload(portfolio_id=portfolio.id), format="json")
    assert response.status_code == 200, response.json()
    assert response.json()["id"] == pk
    assert response.json()["nav"] == 15.2885
    assert Transaction.objects.count() == 1
    assert not CashLedgerEntry.objects.exists()
    # A cash-affecting edit still needs funding; failure rolls back the whole write.
    changed = payload(portfolio_id=portfolio.id)
    changed["paid_value"] = "1100"
    response = api_client.put(f"/api/v1/transactions/{pk}", changed, format="json")
    assert response.status_code == 400
    assert response.json()["detail"] == "Insufficient cash balance for purchase."
    assert MutualFundTransactionDetail.objects.get(transaction_id=pk).paid_value == Decimal("1000")
    assert not CashLedgerEntry.objects.exists()


@pytest.mark.django_db
def test_cached_nav_lookup_is_exact_and_authenticated(api_client, anon_client, legacy_seeded):
    cached()
    url = "/api/v1/nav/lookup"
    assert anon_client.get(url).status_code in (401, 403)
    response = api_client.get(url, {"scheme_code": "120503", "nav_date": "2023-01-20"})
    assert response.status_code == 200
    assert response.json()["nav"] == "15.288500"
    assert response.json()["status"] == "available"
    missing = api_client.get(url, {"scheme_code": "120503", "nav_date": "2023-01-21"})
    assert missing.json()["nav"] is None
    assert missing.json()["status"] == "missing"
    assert api_client.get(url, {"scheme_code": "120503", "nav_date": "not-a-date"}).status_code == 400


@pytest.mark.django_db
def test_historical_preview_is_read_only_and_user_scoped(api_client, legacy_seeded, test_user, other_user):
    row = cached(value="15.228500")
    created = api_client.post("/api/v1/transactions", payload(), format="json").json()
    row.close_price = Decimal("15.288500")
    row.save()
    output = StringIO()
    call_command("preview_mf_nav_corrections", user_id=test_user.id, stdout=output)
    assert str(created["id"]) in output.getvalue()
    assert "15.288500" in output.getvalue()
    assert Transaction.objects.get(pk=created["id"]).price_per_share == Decimal("15.228500")
    assert not CashLedgerEntry.objects.exists()
    other = StringIO()
    call_command("preview_mf_nav_corrections", user_id=other_user.id, stdout=other)
    assert "NAV_MISMATCH" not in other.getvalue()


@pytest.mark.django_db
@pytest.mark.parametrize("change", [
    {"units_allotted": "66"}, {"fees": "11"},
    {"investment_date": "2023-01-19"}, {"market_value": "990"},
    {"folio_number": "OTHER"}, {"type": "SELL"},
])
def test_nav_exception_is_not_used_for_statement_changes(api_client, seeded, test_user, change):
    portfolio = _legacy_portfolio(test_user)
    row = cached(value="15.228500")
    created = api_client.post("/api/v1/transactions", payload(portfolio_id=portfolio.id), format="json").json()
    _enable_cash_aware(portfolio)
    row.close_price = Decimal("15.288500")
    row.save()
    proposed = payload(portfolio_id=portfolio.id)
    proposed.update(change)
    response = api_client.put(f"/api/v1/transactions/{created['id']}", proposed, format="json")
    if change.get("type") == "SELL":
        assert response.status_code == 200
        assert CashLedgerEntry.objects.filter(linked_transaction_id=created["id"]).exists()
    else:
        assert response.status_code == 400, response.json()
        assert not CashLedgerEntry.objects.exists()
        assert Transaction.objects.get(pk=created["id"]).price_per_share == Decimal("15.228500")


@pytest.mark.django_db
def test_nav_only_funded_edit_reuses_settlement(api_client, seeded, test_user):
    from tests.test_cash_aware_transactions_api import _deposit
    portfolio = _enable_cash_aware(_legacy_portfolio(test_user))
    _deposit(portfolio, day="2023-01-19", amount="1000", currency="INR")
    row = cached(value="15.228500")
    created = api_client.post("/api/v1/transactions", payload(portfolio_id=portfolio.id), format="json").json()
    entry = CashLedgerEntry.objects.get(linked_transaction_id=created["id"])
    row.close_price = Decimal("15.288500")
    row.save()
    response = api_client.put(f"/api/v1/transactions/{created['id']}", payload(portfolio_id=portfolio.id), format="json")
    assert response.status_code == 200, response.json()
    entry.refresh_from_db()
    assert entry.amount == Decimal("-1000")
    assert list(CashLedgerEntry.objects.filter(linked_transaction_id=created["id"]).values_list("id", flat=True)) == [entry.id]


@pytest.mark.django_db
@pytest.mark.parametrize("have_cache", [True, False])
def test_csv_uses_cached_nav_or_blocks_before_cash_and_transactions(api_client, legacy_seeded, have_cache):
    if have_cache:
        cached()
    text = ("Action,Scheme Code,Scheme Name,Folio Number,Investment Date,NAV Date,NAV,Units Allotted,Paid Value,Market Value,Fees,Currency\n"
            "BUY,120503,Test Fund,F1,01/20/23,01/20/23,15.2285,65,1000,989.8525,10.1475,INR\n")
    response = api_client.post("/api/v1/transactions/import-csv", {
        "file": SimpleUploadedFile("test.csv", text.encode(), content_type="text/csv"),
    }, format="multipart")
    if have_cache:
        assert response.status_code == 200, response.json()
        assert Transaction.objects.get().price_per_share == Decimal("15.288500")
    else:
        assert response.status_code == 200, response.json()
        assert response.json()["success"] is False
        assert response.json()["imported_count"] == 0
        assert "cached NAV" in str(response.json())
        assert not Transaction.objects.exists()
    assert not CashLedgerEntry.objects.exists()


@pytest.mark.django_db
def test_missing_nav_blocks_confirmed_cash_import_and_preview(api_client, cash_aware_portfolio):
    cached()
    text = ("Action,Scheme Code,Scheme Name,Folio Number,Investment Date,NAV Date,NAV,Units Allotted,Paid Value,Market Value,Fees,Currency\n"
            "BUY,120503,Test Fund,F1,01/20/23,01/20/23,15.2285,65,1000,989.8525,10.1475,INR\n"
            "BUY,120503,Test Fund,F1,01/21/23,01/21/23,15.2285,65,1000,989.8525,10.1475,INR\n")
    for route in ("import-csv/preview-cash", "import-csv"):
        response = api_client.post(
            f"/api/v1/transactions/{route}?portfolio_id={cash_aware_portfolio.id}"
            "&create_cash_deposits=true&cash_preview_confirmed=true",
            {"file": SimpleUploadedFile("test.csv", text.encode(), content_type="text/csv")},
            format="multipart",
        )
        assert response.status_code == 200, response.json()
        assert response.json()["success"] is False
        assert response.json()["imported_count"] == 0
        assert "cached NAV" in str(response.json()["errors"])
        assert not Transaction.objects.exists()
        assert not CashLedgerEntry.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("other_cash", [False, True])
def test_nav_exception_does_not_bypass_noop_or_other_linked_cash(api_client, seeded, test_user, other_cash):
    from cash.models import CashEntryType
    portfolio = _legacy_portfolio(test_user)
    row = cached(value="15.228500")
    created = api_client.post("/api/v1/transactions", payload(portfolio_id=portfolio.id), format="json").json()
    _enable_cash_aware(portfolio)
    if other_cash:
        CashLedgerEntry.objects.create(portfolio=portfolio, linked_transaction_id=created["id"],
            entry_type=CashEntryType.CASH_DEPOSIT, date=date(2023, 1, 20), currency="INR", amount=Decimal("1"))
        row.close_price = Decimal("15.288500")
        row.save()
    before = list(CashLedgerEntry.objects.values_list("id", "amount", "entry_type"))
    response = api_client.put(f"/api/v1/transactions/{created['id']}", payload(portfolio_id=portfolio.id), format="json")
    assert response.status_code == 400, response.json()
    assert response.json()["detail"] == "Insufficient cash balance for purchase."
    assert list(CashLedgerEntry.objects.values_list("id", "amount", "entry_type")) == before
    assert Transaction.objects.get(pk=created["id"]).price_per_share == Decimal("15.228500")


@pytest.mark.django_db
def test_sell_fallback_uses_canonical_nav_for_cash_and_tax(api_client, cash_aware_portfolio):
    from cash.models import CashEntryType
    cached()
    proposed = payload(portfolio_id=cash_aware_portfolio.id, type="SELL")
    proposed.update(paid_value="0", actual_cash_received="980")
    response = api_client.post("/api/v1/transactions", proposed, format="json")
    assert response.status_code == 201, response.json()
    entries = {e.entry_type: e.amount for e in CashLedgerEntry.objects.filter(linked_transaction_id=response.json()["id"])}
    assert entries[CashEntryType.SELL_SETTLEMENT] == Decimal("983.6050")
    assert entries[CashEntryType.TAX_WITHHELD] == Decimal("-3.6050")
