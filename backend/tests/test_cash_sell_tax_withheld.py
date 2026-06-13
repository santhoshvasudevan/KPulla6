"""CASH-SELL-1B — actual SELL proceeds with TAX_WITHHELD ledger row."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cash.ledger_details import build_ledger_entry_details
from cash.models import CashEntryType, CashLedgerEntry
from finance.cash import cash_balance_by_currency, cash_balance_on_date
from portfolios.models import Portfolio
from portfolios.seed import ensure_default_portfolio
from transactions.models import Transaction


def _stock_payload(**overrides):
    base = {
        "asset_symbol": "AAPL",
        "date": "2026-06-01",
        "type": "SELL",
        "quantity": "10",
        "price_per_share": "100",
        "currency": "EUR",
        "fees": "2",
    }
    base.update(overrides)
    return base


def _mf_payload(**overrides):
    base = {
        "asset_type": "MUTUAL_FUND",
        "scheme_code": "120503",
        "scheme_name": "Test Fund",
        "folio_number": "F1",
        "type": "SELL",
        "investment_date": "2026-03-10",
        "nav_date": "2026-03-15",
        "nav": "42.5",
        "units_allotted": "100",
        "paid_value": "4255.00",
        "market_value": "4250.00",
        "currency": "INR",
    }
    base.update(overrides)
    return base


def _enable_cash_aware(portfolio: Portfolio) -> Portfolio:
    portfolio.cash_aware_enabled = True
    portfolio.save(update_fields=["cash_aware_enabled", "updated_at"])
    return portfolio


def _legacy_portfolio(test_user) -> Portfolio:
    portfolio = ensure_default_portfolio(test_user)
    if portfolio.cash_aware_enabled:
        portfolio.cash_aware_enabled = False
        portfolio.save(update_fields=["cash_aware_enabled", "updated_at"])
    return portfolio


def _ledger_points(portfolio: Portfolio):
    from finance.cash import CashLedgerPoint

    return [
        CashLedgerPoint(date=e.date, currency=e.currency, amount=e.amount)
        for e in CashLedgerEntry.objects.filter(portfolio=portfolio)
    ]


@pytest.mark.django_db
def test_sell_without_actual_creates_only_sell_settlement(api_client, seeded, test_user):
    portfolio = _enable_cash_aware(ensure_default_portfolio(test_user))
    response = api_client.post(
        "/api/v1/transactions",
        _stock_payload(portfolio_id=portfolio.id),
        format="json",
    )
    assert response.status_code == 201
    txn_id = response.json()["id"]
    entries = CashLedgerEntry.objects.filter(linked_transaction_id=txn_id)
    assert entries.count() == 1
    entry = entries.get()
    assert entry.entry_type == CashEntryType.SELL_SETTLEMENT
    assert entry.amount == Decimal("998")


@pytest.mark.django_db
def test_sell_with_lower_actual_creates_tax_withheld(api_client, seeded, test_user):
    portfolio = _enable_cash_aware(ensure_default_portfolio(test_user))
    response = api_client.post(
        "/api/v1/transactions",
        _stock_payload(
            portfolio_id=portfolio.id,
            actual_cash_received="930",
            settlement_note="Capital gains tax",
        ),
        format="json",
    )
    assert response.status_code == 201
    data = response.json()
    assert data["actual_cash_received"] == 930.0
    assert data["settlement_note"] == "Capital gains tax"
    txn_id = data["id"]
    sell_entry = CashLedgerEntry.objects.get(
        linked_transaction_id=txn_id, entry_type=CashEntryType.SELL_SETTLEMENT
    )
    tax_entry = CashLedgerEntry.objects.get(
        linked_transaction_id=txn_id, entry_type=CashEntryType.TAX_WITHHELD
    )
    assert sell_entry.amount == Decimal("998")
    assert tax_entry.amount == Decimal("-68")
    assert tax_entry.date == sell_entry.date == date(2026, 6, 1)

    balances = cash_balance_on_date(_ledger_points(portfolio), date(2026, 6, 1))
    assert balances["EUR"] == Decimal("930")


@pytest.mark.django_db
def test_sell_actual_equal_calculated_no_tax_withheld(api_client, seeded, test_user):
    portfolio = _enable_cash_aware(ensure_default_portfolio(test_user))
    response = api_client.post(
        "/api/v1/transactions",
        _stock_payload(portfolio_id=portfolio.id, actual_cash_received="998"),
        format="json",
    )
    assert response.status_code == 201
    txn_id = response.json()["id"]
    assert CashLedgerEntry.objects.filter(linked_transaction_id=txn_id).count() == 1


def _error_text(response) -> str:
    body = response.json()
    if isinstance(body.get("detail"), str):
        return body["detail"]
    errors = body.get("non_field_errors") or []
    return " ".join(str(item) for item in errors)


@pytest.mark.django_db
def test_sell_actual_exceeds_calculated_rejected(api_client, seeded, test_user):
    portfolio = _enable_cash_aware(ensure_default_portfolio(test_user))
    response = api_client.post(
        "/api/v1/transactions",
        _stock_payload(portfolio_id=portfolio.id, actual_cash_received="1000"),
        format="json",
    )
    assert response.status_code == 400
    assert _error_text(response) == (
        "Actual cash received cannot exceed calculated proceeds."
    )


@pytest.mark.django_db
def test_update_actual_cash_received_updates_tax_withheld(api_client, seeded, test_user):
    portfolio = _enable_cash_aware(ensure_default_portfolio(test_user))
    created = api_client.post(
        "/api/v1/transactions",
        _stock_payload(portfolio_id=portfolio.id, actual_cash_received="930"),
        format="json",
    ).json()
    response = api_client.put(
        f"/api/v1/transactions/{created['id']}",
        _stock_payload(portfolio_id=portfolio.id, actual_cash_received="950"),
        format="json",
    )
    assert response.status_code == 200
    tax_entry = CashLedgerEntry.objects.get(
        linked_transaction_id=created["id"], entry_type=CashEntryType.TAX_WITHHELD
    )
    assert tax_entry.amount == Decimal("-48")
    balances = cash_balance_on_date(_ledger_points(portfolio), date(2026, 6, 1))
    assert balances["EUR"] == Decimal("950")


@pytest.mark.django_db
def test_clearing_actual_cash_received_removes_tax_withheld(api_client, seeded, test_user):
    portfolio = _enable_cash_aware(ensure_default_portfolio(test_user))
    created = api_client.post(
        "/api/v1/transactions",
        _stock_payload(portfolio_id=portfolio.id, actual_cash_received="930"),
        format="json",
    ).json()
    response = api_client.put(
        f"/api/v1/transactions/{created['id']}",
        _stock_payload(portfolio_id=portfolio.id),
        format="json",
    )
    assert response.status_code == 200
    assert not CashLedgerEntry.objects.filter(
        linked_transaction_id=created["id"], entry_type=CashEntryType.TAX_WITHHELD
    ).exists()
    balances = cash_balance_on_date(_ledger_points(portfolio), date(2026, 6, 1))
    assert balances["EUR"] == Decimal("998")


@pytest.mark.django_db
def test_delete_sell_removes_both_ledger_rows(api_client, seeded, test_user):
    portfolio = _enable_cash_aware(ensure_default_portfolio(test_user))
    created = api_client.post(
        "/api/v1/transactions",
        _stock_payload(portfolio_id=portfolio.id, actual_cash_received="930"),
        format="json",
    ).json()
    response = api_client.delete(f"/api/v1/transactions/{created['id']}")
    assert response.status_code == 204
    assert not CashLedgerEntry.objects.filter(linked_transaction_id=created["id"]).exists()


@pytest.mark.django_db
def test_delete_sell_with_tax_withheld_blocked_when_later_negative(
    api_client, seeded, test_user
):
    portfolio = _enable_cash_aware(ensure_default_portfolio(test_user))
    CashLedgerEntry.objects.create(
        portfolio=portfolio,
        date=date(2026, 6, 1),
        currency="EUR",
        entry_type=CashEntryType.CASH_DEPOSIT,
        amount=Decimal("1000"),
    )
    sell = api_client.post(
        "/api/v1/transactions",
        _stock_payload(
            portfolio_id=portfolio.id,
            actual_cash_received="930",
            date="2026-06-05",
        ),
        format="json",
    ).json()
    api_client.post(
        "/api/v1/transactions",
        {
            **_stock_payload(portfolio_id=portfolio.id, type="BUY", date="2026-06-10"),
            "quantity": "15",
            "price_per_share": "100",
            "fees": "0",
        },
        format="json",
    )
    response = api_client.delete(f"/api/v1/transactions/{sell['id']}")
    assert response.status_code == 409
    assert Transaction.objects.filter(pk=sell["id"]).exists()


@pytest.mark.django_db
def test_tax_withheld_ledger_details(api_client, seeded, test_user):
    portfolio = _enable_cash_aware(ensure_default_portfolio(test_user))
    created = api_client.post(
        "/api/v1/transactions",
        _stock_payload(
            portfolio_id=portfolio.id,
            actual_cash_received="930",
            settlement_note="Withholding",
        ),
        format="json",
    ).json()
    tax_entry = CashLedgerEntry.objects.get(
        linked_transaction_id=created["id"], entry_type=CashEntryType.TAX_WITHHELD
    )
    details = build_ledger_entry_details(tax_entry)
    assert "AAPL" in details
    assert "998" in details
    assert "930" in details
    assert "68" in details
    assert "Withholding" in details


@pytest.mark.django_db
def test_tax_withheld_not_manually_editable(api_client, seeded, test_user):
    portfolio = _enable_cash_aware(ensure_default_portfolio(test_user))
    created = api_client.post(
        "/api/v1/transactions",
        _stock_payload(portfolio_id=portfolio.id, actual_cash_received="930"),
        format="json",
    ).json()
    tax_entry = CashLedgerEntry.objects.get(
        linked_transaction_id=created["id"], entry_type=CashEntryType.TAX_WITHHELD
    )
    response = api_client.put(
        f"/api/v1/cash/ledger/{tax_entry.id}",
        {
            "date": "2026-06-02",
            "currency": "EUR",
            "amount": "10",
            "note": "",
            "source_of_funds": "",
        },
        format="json",
    )
    assert response.status_code == 409


@pytest.mark.django_db
def test_buy_rejects_actual_cash_received(api_client, seeded, test_user):
    portfolio = _enable_cash_aware(ensure_default_portfolio(test_user))
    CashLedgerEntry.objects.create(
        portfolio=portfolio,
        date=date(2026, 5, 1),
        currency="EUR",
        entry_type=CashEntryType.CASH_DEPOSIT,
        amount=Decimal("5000"),
    )
    response = api_client.post(
        "/api/v1/transactions",
        {
            **_stock_payload(type="BUY", portfolio_id=portfolio.id),
            "actual_cash_received": "900",
        },
        format="json",
    )
    assert response.status_code == 400
    assert "only allowed for SELL" in _error_text(response)


@pytest.mark.django_db
def test_mf_sell_with_actual_cash_received(api_client, seeded, test_user):
    portfolio = _enable_cash_aware(ensure_default_portfolio(test_user))
    response = api_client.post(
        "/api/v1/transactions",
        _mf_payload(portfolio_id=portfolio.id, actual_cash_received="4000"),
        format="json",
    )
    assert response.status_code == 201
    txn_id = response.json()["id"]
    sell_entry = CashLedgerEntry.objects.get(
        linked_transaction_id=txn_id, entry_type=CashEntryType.SELL_SETTLEMENT
    )
    tax_entry = CashLedgerEntry.objects.get(
        linked_transaction_id=txn_id, entry_type=CashEntryType.TAX_WITHHELD
    )
    assert sell_entry.amount == Decimal("4255")
    assert tax_entry.amount == Decimal("-255")
    assert sell_entry.date == date(2026, 3, 10)
    balances = cash_balance_by_currency(_ledger_points(portfolio))
    assert balances["INR"] == Decimal("4000")


@pytest.mark.django_db
def test_legacy_sell_stores_actual_cash_received_without_ledger_rows(
    api_client, seeded, test_user
):
    portfolio = _legacy_portfolio(test_user)
    response = api_client.post(
        "/api/v1/transactions",
        _stock_payload(portfolio_id=portfolio.id, actual_cash_received="930"),
        format="json",
    )
    assert response.status_code == 201
    data = response.json()
    assert data["actual_cash_received"] == 930.0
    assert not CashLedgerEntry.objects.filter(linked_transaction_id=data["id"]).exists()
    txn = Transaction.objects.get(pk=data["id"])
    assert txn.actual_cash_received == Decimal("930")
