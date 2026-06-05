"""Cash-5 — CSV import cash shortfall preview and confirmed deposits."""

from __future__ import annotations

import io
from datetime import date
from decimal import Decimal

import pytest

from cash.models import CashEntryType, CashLedgerEntry
from portfolios.models import Portfolio
from portfolios.seed import ensure_default_portfolio
from transactions.models import Transaction, TransactionType

STOCK_HEADER = "Action,Date,ASSET SYMBOL,Qty,Price/Share,FEES\n"
MF_HEADER = (
    "Action,Scheme Code,Scheme Name,Folio Number,Investment Date,NAV Date,"
    "NAV,Units Allotted,Paid Value,Market Value,Fees,Currency\n"
)


def _enable_cash_aware(portfolio: Portfolio) -> Portfolio:
    if not portfolio.cash_aware_enabled:
        portfolio.cash_aware_enabled = True
        portfolio.save(update_fields=["cash_aware_enabled", "updated_at"])
    return portfolio


def _deposit(portfolio: Portfolio, *, day: str, amount: str, currency: str = "EUR"):
    CashLedgerEntry.objects.create(
        portfolio=portfolio,
        date=date.fromisoformat(day),
        currency=currency,
        entry_type=CashEntryType.CASH_DEPOSIT,
        amount=Decimal(amount),
    )


def _preview(api_client, csv_text, portfolio_id=None):
    url = "/api/v1/transactions/import-csv/preview-cash"
    if portfolio_id is not None:
        url = f"{url}?portfolio_id={portfolio_id}"
    return api_client.post(
        url,
        {"file": io.BytesIO(csv_text.encode("utf-8"))},
        format="multipart",
    )


def _import(
    api_client,
    csv_text,
    portfolio_id=None,
    *,
    create_cash_deposits=False,
    cash_preview_confirmed=False,
):
    url = "/api/v1/transactions/import-csv"
    params = []
    if portfolio_id is not None:
        params.append(f"portfolio_id={portfolio_id}")
    if create_cash_deposits:
        params.append("create_cash_deposits=true")
    if cash_preview_confirmed:
        params.append("cash_preview_confirmed=true")
    if params:
        url = f"{url}?{'&'.join(params)}"
    return api_client.post(
        url,
        {"file": io.BytesIO(csv_text.encode("utf-8"))},
        format="multipart",
    )


@pytest.mark.django_db
def test_legacy_portfolio_preview_not_cash_aware(legacy_seeded, api_client):
    csv_text = STOCK_HEADER + "Buy,06/04/26,AAPL,10,100.00,5\n"
    data = _preview(api_client, csv_text).json()
    assert data["cash_aware"] is False
    assert data["can_import_without_deposits"] is True
    assert data["shortfalls"] == []
    assert data["proposed_deposits"] == []


@pytest.mark.django_db
def test_legacy_import_unchanged(legacy_seeded, api_client):
    csv_text = STOCK_HEADER + "Buy,06/04/26,AAPL,10,100.00,5\n"
    before = Transaction.objects.count()
    response = _import(api_client, csv_text)
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert Transaction.objects.count() == before + 1
    assert not CashLedgerEntry.objects.filter(entry_type=CashEntryType.BUY_SETTLEMENT).exists()


@pytest.mark.django_db
def test_cash_aware_sufficient_cash_imports_without_deposits(api_client, seeded, test_user):
    portfolio = _enable_cash_aware(ensure_default_portfolio(test_user))
    _deposit(portfolio, day="2026-06-01", amount="5000")
    csv_text = STOCK_HEADER + "Buy,06/04/26,AAPL,10,100.00,5\n"
    preview = _preview(api_client, csv_text).json()
    assert preview["cash_aware"] is True
    assert preview["can_import_without_deposits"] is True
    assert preview["proposed_deposits"] == []

    response = _import(api_client, csv_text)
    assert response.status_code == 200
    assert response.json()["success"] is True
    txn = Transaction.objects.get(asset_symbol="AAPL")
    assert CashLedgerEntry.objects.filter(
        linked_transaction_id=txn.id, entry_type=CashEntryType.BUY_SETTLEMENT
    ).exists()


@pytest.mark.django_db
def test_cash_aware_insufficient_returns_409_without_confirm(api_client, seeded, test_user):
    portfolio = _enable_cash_aware(ensure_default_portfolio(test_user))
    assert portfolio.cash_aware_enabled
    csv_text = STOCK_HEADER + "Buy,06/04/26,AAPL,10,100.00,5\n"
    preview = _preview(api_client, csv_text).json()
    assert preview["cash_aware"] is True
    assert preview["can_import_without_deposits"] is False
    assert len(preview["shortfalls"]) == 1
    assert preview["shortfalls"][0]["currency"] == "EUR"
    assert preview["shortfalls"][0]["shortfall"] == 1005.0

    before_txn = Transaction.objects.count()
    before_dep = CashLedgerEntry.objects.filter(
        entry_type=CashEntryType.CASH_DEPOSIT
    ).count()
    response = _import(api_client, csv_text)
    assert response.status_code == 409
    body = response.json()
    assert body["can_import_without_deposits"] is False
    assert Transaction.objects.count() == before_txn
    assert (
        CashLedgerEntry.objects.filter(entry_type=CashEntryType.CASH_DEPOSIT).count()
        == before_dep
    )


@pytest.mark.django_db
def test_usd_cash_does_not_fund_eur_csv_buy(api_client, seeded, test_user):
    portfolio = _enable_cash_aware(ensure_default_portfolio(test_user))
    _deposit(portfolio, day="2026-06-01", amount="50000", currency="USD")
    csv_text = STOCK_HEADER + "Buy,06/04/26,AAPL,10,100.00,5\n"
    preview = _preview(api_client, csv_text).json()
    assert preview["shortfalls"][0]["currency"] == "EUR"
    assert preview["shortfalls"][0]["available_before"] == 0.0
    assert preview["proposed_deposits"][0]["currency"] == "EUR"


@pytest.mark.django_db
def test_confirmed_import_creates_deposit_settlement_and_transaction(
    api_client, seeded, test_user
):
    _enable_cash_aware(ensure_default_portfolio(test_user))
    csv_text = STOCK_HEADER + "Buy,06/04/26,AAPL,10,100.00,5\n"
    response = _import(
        api_client,
        csv_text,
        create_cash_deposits=True,
        cash_preview_confirmed=True,
    )
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert CashLedgerEntry.objects.filter(
        entry_type=CashEntryType.CASH_DEPOSIT, amount=Decimal("1005")
    ).exists()
    txn = Transaction.objects.get(asset_symbol="AAPL")
    settlement = CashLedgerEntry.objects.get(linked_transaction_id=txn.id)
    assert settlement.entry_type == CashEntryType.BUY_SETTLEMENT
    assert settlement.currency == "EUR"
    assert settlement.amount == Decimal("-1005")


@pytest.mark.django_db
def test_sell_increases_simulated_cash_for_later_buy(api_client, seeded, test_user):
    portfolio = _enable_cash_aware(ensure_default_portfolio(test_user))
    csv_text = (
        STOCK_HEADER
        + "Sell,06/01/26,MSFT,5,200.00,0\n"
        + "Buy,06/04/26,MSFT,5,100.00,0\n"
    )
    preview = _preview(api_client, csv_text).json()
    assert preview["can_import_without_deposits"] is True
    assert preview["proposed_deposits"] == []

    response = _import(api_client, csv_text)
    assert response.json()["success"] is True
    assert Transaction.objects.filter(asset_symbol="MSFT").count() == 2


@pytest.mark.django_db
def test_stock_split_no_cash_effect_in_preview(api_client, seeded, test_user):
    _enable_cash_aware(ensure_default_portfolio(test_user))
    csv_text = STOCK_HEADER + "STOCK_SPLIT,06/04/26,AAPL,1,2,0\n"
    preview = _preview(api_client, csv_text).json()
    assert preview["can_import_without_deposits"] is True
    assert preview["shortfalls"] == []


@pytest.mark.django_db
def test_mf_buy_uses_paid_value_and_investment_date(api_client, seeded, test_user):
    _enable_cash_aware(ensure_default_portfolio(test_user))
    mf_row = (
        "BUY,120503,Test Fund,F1,03/10/26,03/15/26,42.50,100,4255.00,4250.00,5.00,INR\n"
    )
    csv_text = MF_HEADER + mf_row
    preview = _preview(api_client, csv_text).json()
    assert preview["shortfalls"][0]["currency"] == "INR"
    assert preview["shortfalls"][0]["shortfall"] == 4255.0
    assert preview["proposed_deposits"][0]["date"] == "2026-03-10"
    assert preview["proposed_deposits"][0]["amount"] == 4255.0


@pytest.mark.django_db
def test_confirmed_import_atomic_on_transaction_failure(api_client, seeded, test_user):
    """Deposits roll back when a later row fails during import."""
    from unittest.mock import patch

    from transactions.services import TransactionValidationError, create_transaction

    _enable_cash_aware(ensure_default_portfolio(test_user))
    csv_text = (
        STOCK_HEADER
        + "Buy,06/04/26,AAPL,10,100.00,5\n"
        + "Buy,06/05/26,MSFT,5,50.00,0\n"
    )
    before_dep = CashLedgerEntry.objects.filter(
        entry_type=CashEntryType.CASH_DEPOSIT
    ).count()
    before_txn = Transaction.objects.count()
    calls = {"n": 0}

    def flaky_create(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise TransactionValidationError("Simulated import failure")
        return create_transaction(*args, **kwargs)

    api_client.raise_request_exception = False
    with patch(
        "transactions.services.create_transaction", side_effect=flaky_create
    ):
        response = _import(
            api_client,
            csv_text,
            create_cash_deposits=True,
            cash_preview_confirmed=True,
        )
    assert response.status_code >= 400

    assert (
        CashLedgerEntry.objects.filter(entry_type=CashEntryType.CASH_DEPOSIT).count()
        == before_dep
    )
    assert Transaction.objects.count() == before_txn
