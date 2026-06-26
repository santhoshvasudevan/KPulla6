"""CASH-CORR-1A: broker cash ledger reversal API tests."""

from datetime import date
from decimal import Decimal

import pytest

from cash.models import CashEntryType, CashLedgerEntry, CashTransferGroup
from cash.overview_service import build_cash_overview, cash_overview_to_response_dict
from cash.services import cash_balances_for_scope
from debt.models import CashMovement
from debt.services import create_bank_account
from portfolios.models import Portfolio
from portfolios.scope import resolve_portfolio_scope
from portfolios.seed import ensure_default_portfolio
from tests.debt_test_helpers import fund_bank_account


def _deposit(portfolio, *, amount: str, day: str = "2023-09-24", note: str = ""):
    return CashLedgerEntry.objects.create(
        portfolio=portfolio,
        date=date.fromisoformat(day),
        currency="INR",
        entry_type=CashEntryType.CASH_DEPOSIT,
        amount=Decimal(amount),
        source_of_funds="salary",
        note=note,
    )


def _reverse(api_client, entry_id, **extra):
    payload = {"reason": "Recorded in broker ledger by mistake", **extra}
    return api_client.post(
        f"/api/v1/cash/ledger/{entry_id}/reverse",
        payload,
        format="json",
    )


@pytest.mark.django_db
def test_reverse_manual_deposit_creates_opposite_withdrawal_and_zero_balance(
    api_client, seeded, test_user
):
    portfolio = Portfolio.objects.create(
        user=test_user,
        name="IndianInvestments",
        base_currency="INR",
        is_active=True,
    )
    entry = _deposit(portfolio, amount="1109389")

    response = _reverse(api_client, entry.id, reversal_date="2026-06-26")
    assert response.status_code == 201
    body = response.json()
    assert body["original"]["id"] == entry.id
    assert body["original"]["is_reversed"] is True
    assert body["reversal"]["entry_type"] == "CASH_WITHDRAWAL"
    assert body["reversal"]["amount"] == pytest.approx(-1109389.0)
    assert body["reversal"]["is_reversal"] is True
    assert body["reversal"]["reverses_id"] == entry.id
    assert body["reversal"]["reversal_reason"] == "Recorded in broker ledger by mistake"
    assert body["broker_cash_balance"]["current_balance"] == pytest.approx(0.0)

    entry.refresh_from_db()
    assert entry.amount == Decimal("1109389")
    assert CashLedgerEntry.objects.filter(pk=entry.id).exists()

    scope = resolve_portfolio_scope(test_user, portfolio_id=portfolio.id)
    balances = cash_balances_for_scope(scope)
    assert balances.balances == [("INR", Decimal("0"))]


@pytest.mark.django_db
def test_reverse_manual_withdrawal_creates_opposite_deposit(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    CashLedgerEntry.objects.create(
        portfolio=portfolio,
        date=date(2026, 6, 1),
        currency="EUR",
        entry_type=CashEntryType.CASH_DEPOSIT,
        amount=Decimal("5000"),
    )
    withdrawal = CashLedgerEntry.objects.create(
        portfolio=portfolio,
        date=date(2026, 6, 2),
        currency="EUR",
        entry_type=CashEntryType.CASH_WITHDRAWAL,
        amount=Decimal("-1500"),
    )

    response = _reverse(api_client, withdrawal.id)
    assert response.status_code == 201
    reversal = response.json()["reversal"]
    assert reversal["entry_type"] == "CASH_DEPOSIT"
    assert reversal["amount"] == pytest.approx(1500.0)


@pytest.mark.django_db
def test_cannot_reverse_linked_settlement(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    entry = CashLedgerEntry.objects.create(
        portfolio=portfolio,
        date=date(2026, 6, 1),
        currency="EUR",
        entry_type=CashEntryType.BUY_SETTLEMENT,
        amount=Decimal("-100"),
    )
    response = _reverse(api_client, entry.id)
    assert response.status_code == 400
    assert "cannot be reversed" in response.json()["detail"].lower()


@pytest.mark.django_db
def test_cannot_reverse_transfer_entry(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    other = Portfolio.objects.create(
        user=test_user, name="Other PF", base_currency="EUR", is_active=True
    )
    group = CashTransferGroup.objects.create(
        date=date(2026, 6, 1),
        source_portfolio=portfolio,
        target_portfolio=other,
        source_currency="EUR",
        target_currency="EUR",
        source_amount=Decimal("100"),
        target_amount=Decimal("100"),
    )
    entry = CashLedgerEntry.objects.create(
        portfolio=portfolio,
        date=date(2026, 6, 1),
        currency="EUR",
        entry_type=CashEntryType.TRANSFER_OUT,
        amount=Decimal("-100"),
        transfer_group=group,
    )
    response = _reverse(api_client, entry.id)
    assert response.status_code == 400


@pytest.mark.django_db
def test_cannot_reverse_already_reversed_entry(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    entry = _deposit(portfolio, amount="1000", day="2026-06-01")
    first = _reverse(api_client, entry.id)
    assert first.status_code == 201
    second = _reverse(api_client, entry.id)
    assert second.status_code == 400
    assert "already been reversed" in second.json()["detail"].lower()


@pytest.mark.django_db
def test_cannot_reverse_a_reversal_row(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    entry = _deposit(portfolio, amount="500", day="2026-06-01")
    reversal_id = _reverse(api_client, entry.id).json()["reversal_entry_id"]
    response = _reverse(api_client, reversal_id)
    assert response.status_code == 400
    assert "reversal entry" in response.json()["detail"].lower()


@pytest.mark.django_db
def test_reversal_reason_required(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    entry = _deposit(portfolio, amount="100", day="2026-06-01")
    response = api_client.post(
        f"/api/v1/cash/ledger/{entry.id}/reverse",
        {"reason": "   "},
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_reversal_user_scoped(api_client, seeded, test_user, other_user):
    portfolio = ensure_default_portfolio(test_user)
    entry = _deposit(portfolio, amount="100", day="2026-06-01")
    from rest_framework.test import APIClient

    other_client = APIClient()
    other_client.force_authenticate(user=other_user)
    response = _reverse(other_client, entry.id)
    assert response.status_code == 404


@pytest.mark.django_db
def test_overview_updates_after_reversal(api_client, seeded, test_user):
    portfolio = Portfolio.objects.create(
        user=test_user,
        name="IndianInvestments",
        base_currency="INR",
        is_active=True,
    )
    entry = _deposit(portfolio, amount="1109389")
    scope = resolve_portfolio_scope(test_user, portfolio_id=portfolio.id)

    before = cash_overview_to_response_dict(
        build_cash_overview(test_user, scope, display_currency="INR")
    )
    assert before["totals"]["broker_cash_display"] == pytest.approx(1109389.0)

    assert _reverse(api_client, entry.id).status_code == 201

    after = cash_overview_to_response_dict(
        build_cash_overview(test_user, scope, display_currency="INR")
    )
    assert after["totals"]["broker_cash_display"] == pytest.approx(0.0)
    broker_rows = [r for r in after["rows"] if r["ledger_type"] == "BROKER_CASH"]
    assert sum(r["balance"] for r in broker_rows) == pytest.approx(0.0)


@pytest.mark.django_db
def test_reversal_does_not_change_bank_cash_movements(api_client, seeded, test_user):
    portfolio = Portfolio.objects.create(
        user=test_user,
        name="IndianInvestments",
        base_currency="INR",
        is_active=True,
    )
    bank = create_bank_account(
        test_user,
        name="HDFC NRE",
        institution_name="HDFC BANK",
        account_number="ACC-1",
        currency="INR",
        portfolio_id=portfolio.id,
    )
    fund_bank_account(test_user, bank, "1109389", movement_date=date(2023, 9, 24))
    entry = _deposit(portfolio, amount="1109389")
    before_count = CashMovement.objects.filter(bank_account=bank).count()
    before_sum = sum(m.amount for m in CashMovement.objects.filter(bank_account=bank))

    assert _reverse(api_client, entry.id).status_code == 201

    assert CashMovement.objects.filter(bank_account=bank).count() == before_count
    after_sum = sum(m.amount for m in CashMovement.objects.filter(bank_account=bank))
    assert after_sum == before_sum


@pytest.mark.django_db
def test_ledger_lists_reversal_fields(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    entry = _deposit(portfolio, amount="250", day="2026-06-01")
    _reverse(api_client, entry.id)

    response = api_client.get(
        "/api/v1/cash/ledger", {"portfolio_id": portfolio.id}
    )
    assert response.status_code == 200
    original = next(i for i in response.json()["items"] if i["id"] == entry.id)
    reversal = next(i for i in response.json()["items"] if i["is_reversal"])
    assert original["is_reversed"] is True
    assert original["is_reversible"] is False
    assert reversal["reverses_id"] == entry.id
