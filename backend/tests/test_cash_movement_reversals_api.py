"""FD-ACC-10B: manual cash movement reversal API tests."""

from datetime import date
from decimal import Decimal

import pytest

from debt.models import (
    CashMovement,
    CashMovementDirection,
    CashMovementSource,
    CashMovementType,
)
from debt.services import create_bank_account
from tests.debt_test_helpers import fund_bank_account


def _bank(user, **overrides):
    payload = dict(
        name="Savings",
        institution_name="HDFC",
        account_number="rev-1",
        currency="INR",
    )
    payload.update(overrides)
    return create_bank_account(user, **payload)


def _create_manual(api_client, account_id, movement_type, amount, **extra):
    payload = {
        "bank_account_id": account_id,
        "movement_type": movement_type,
        "amount": str(amount),
        "movement_date": "2026-06-01",
        **extra,
    }
    return api_client.post("/api/v1/cash-movements", payload, format="json")


def _reverse(api_client, movement_id, **extra):
    payload = {"reason": "Recorded in error", **extra}
    return api_client.post(
        f"/api/v1/cash-movements/{movement_id}/reverse",
        payload,
        format="json",
    )


@pytest.mark.django_db
def test_reverse_manual_deposit_creates_opposite_debit(seeded, test_user, api_client):
    account = _bank(test_user)
    create = _create_manual(api_client, account.id, "MANUAL_DEPOSIT", "1000")
    movement_id = create.json()["id"]

    response = _reverse(api_client, movement_id, reversal_date="2026-06-10")
    assert response.status_code == 201
    body = response.json()
    assert body["original"]["id"] == movement_id
    assert body["original"]["is_reversed"] is True
    assert body["reversal_cash_movement_id"] == body["reversed_by"]
    reversal = body["reversal"]
    assert reversal["movement_type"] == "REVERSAL"
    assert reversal["direction"] == "DEBIT"
    assert reversal["amount"] == 1000.0
    assert reversal["is_reversal"] is True
    assert reversal["reverses_id"] == movement_id
    assert reversal["reversal_reason"] == "Recorded in error"
    assert reversal["source"] == "SYSTEM"

    account.refresh_from_db()
    assert account.current_balance == Decimal("0")


@pytest.mark.django_db
def test_reverse_manual_withdrawal_creates_opposite_credit(seeded, test_user, api_client):
    account = _bank(test_user)
    fund_bank_account(test_user, account, "5000")
    create = _create_manual(api_client, account.id, "MANUAL_WITHDRAWAL", "1500")
    movement_id = create.json()["id"]

    response = _reverse(api_client, movement_id)
    assert response.status_code == 201
    assert response.json()["reversal"]["direction"] == "CREDIT"
    account.refresh_from_db()
    assert account.current_balance == Decimal("5000")


@pytest.mark.django_db
def test_reverse_adjustment_credit_and_debit(seeded, test_user, api_client):
    account = _bank(test_user)
    fund_bank_account(test_user, account, "1000")
    credit = _create_manual(
        api_client,
        account.id,
        "ADJUSTMENT",
        "200",
        direction="CREDIT",
    )
    debit = _create_manual(
        api_client,
        account.id,
        "ADJUSTMENT",
        "50",
        direction="DEBIT",
    )

    rev_credit = _reverse(api_client, credit.json()["id"])
    assert rev_credit.json()["reversal"]["direction"] == "DEBIT"

    rev_debit = _reverse(api_client, debit.json()["id"])
    assert rev_debit.json()["reversal"]["direction"] == "CREDIT"


@pytest.mark.django_db
def test_cannot_reverse_twice(seeded, test_user, api_client):
    account = _bank(test_user)
    movement_id = _create_manual(api_client, account.id, "MANUAL_DEPOSIT", "100").json()["id"]
    assert _reverse(api_client, movement_id).status_code == 201
    again = _reverse(api_client, movement_id)
    assert again.status_code == 400
    assert "already been reversed" in again.json()["detail"]


@pytest.mark.django_db
def test_cannot_reverse_a_reversal_row(seeded, test_user, api_client):
    account = _bank(test_user)
    movement_id = _create_manual(api_client, account.id, "MANUAL_DEPOSIT", "100").json()["id"]
    reversal_id = _reverse(api_client, movement_id).json()["reversal_cash_movement_id"]
    response = _reverse(api_client, reversal_id)
    assert response.status_code == 400
    assert "reversal movement" in response.json()["detail"]


@pytest.mark.django_db
def test_cannot_reverse_another_users_movement(
    seeded, test_user, other_user, api_client
):
    account = _bank(test_user)
    movement_id = _create_manual(api_client, account.id, "MANUAL_DEPOSIT", "100").json()["id"]
    api_client.force_authenticate(user=other_user)
    response = _reverse(api_client, movement_id)
    assert response.status_code == 404


@pytest.mark.django_db
def test_cannot_reverse_unsupported_system_movement(seeded, test_user, api_client):
    from debt.services import create_fixed_deposit
    from portfolios.seed import ensure_default_portfolio

    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user, account_number="fd-sys")
    fund_bank_account(test_user, bank, "200000")
    fd = create_fixed_deposit(
        test_user,
        portfolio_id=portfolio.id,
        bank_account_id=bank.id,
        institution_name="HDFC",
        deposit_account_number="FD-REV",
        principal_amount=Decimal("100000"),
        currency="INR",
        interest_rate_percent=Decimal("7"),
        interest_payout_frequency="QUARTERLY",
        investment_date=date(2024, 1, 1),
        maturity_date=date(2026, 1, 1),
    )
    opening = CashMovement.objects.get(
        linked_fixed_deposit_id=fd.id,
        movement_type=CashMovementType.FD_OPENING,
    )
    response = _reverse(api_client, opening.id)
    assert response.status_code == 400
    assert "cannot be reversed" in response.json()["detail"]


@pytest.mark.django_db
def test_reversal_reason_required(seeded, test_user, api_client):
    account = _bank(test_user)
    movement_id = _create_manual(api_client, account.id, "MANUAL_DEPOSIT", "100").json()["id"]
    response = api_client.post(
        f"/api/v1/cash-movements/{movement_id}/reverse",
        {"reason": "   "},
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_reversal_visible_in_list(seeded, test_user, api_client):
    account = _bank(test_user)
    movement_id = _create_manual(api_client, account.id, "MANUAL_DEPOSIT", "250").json()["id"]
    _reverse(api_client, movement_id)
    listing = api_client.get(f"/api/v1/cash-movements?bank_account_id={account.id}")
    items = listing.json()["items"]
    types = {item["movement_type"] for item in items}
    assert "REVERSAL" in types
    original = next(item for item in items if item["id"] == movement_id)
    assert original["is_reversed"] is True
