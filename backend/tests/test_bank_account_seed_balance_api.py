from datetime import date
from decimal import Decimal

import pytest

from debt.models import CashMovement, CashMovementType, FixedDeposit
from debt.services import create_bank_account
from portfolios.seed import ensure_default_portfolio


def _seed_payload(**overrides):
    payload = dict(
        date="2024-01-01",
        amount="50000",
        reason="Historical balance seed for FD creation",
    )
    payload.update(overrides)
    return payload


@pytest.mark.django_db
def test_seed_balance_creates_manual_deposit_only(api_client, seeded, test_user):
    account = create_bank_account(
        test_user,
        name="Savings",
        institution_name="HDFC",
        account_number="SEED-1",
        currency="INR",
    )
    response = api_client.post(
        f"/api/v1/bank-accounts/{account.id}/seed-balance",
        _seed_payload(amount="75000"),
        format="json",
    )
    assert response.status_code == 201
    body = response.json()
    assert body["currency"] == "INR"
    assert body["as_of_date"] == "2024-01-01"
    assert body["balance_as_of_date"] == 75000.0
    movement = body["cash_movement"]
    assert movement["movement_type"] == "MANUAL_DEPOSIT"
    assert movement["direction"] == "CREDIT"
    assert movement["amount"] == 75000.0
    assert movement["portfolio_id"] is None
    assert "Historical balance seed" in movement["description"]

    assert CashMovement.objects.filter(bank_account=account).count() == 1
    assert FixedDeposit.objects.filter(user=test_user).count() == 0


@pytest.mark.django_db
def test_seed_balance_does_not_require_portfolio(api_client, seeded, test_user):
    account = create_bank_account(
        test_user,
        name="Unlinked",
        institution_name="HDFC",
        account_number="SEED-2",
        currency="INR",
    )
    response = api_client.post(
        f"/api/v1/bank-accounts/{account.id}/seed-balance",
        _seed_payload(),
        format="json",
    )
    assert response.status_code == 201
    assert response.json()["cash_movement"]["portfolio_id"] is None


@pytest.mark.django_db
def test_seed_balance_updates_as_of_balance(api_client, seeded, test_user):
    account = create_bank_account(
        test_user,
        name="Savings",
        institution_name="HDFC",
        account_number="SEED-3",
        currency="INR",
    )
    api_client.post(
        f"/api/v1/bank-accounts/{account.id}/seed-balance",
        _seed_payload(amount="100000", date="2023-09-24"),
        format="json",
    )
    balance = api_client.get(
        f"/api/v1/bank-accounts/{account.id}/balance?as_of=2023-09-24"
    )
    assert balance.status_code == 200
    assert balance.json()["balance_as_of_date"] == 100000.0


@pytest.mark.django_db
def test_seed_balance_rejects_invalid_amount(api_client, seeded, test_user):
    account = create_bank_account(
        test_user,
        name="Savings",
        institution_name="HDFC",
        account_number="SEED-4",
        currency="INR",
    )
    response = api_client.post(
        f"/api/v1/bank-accounts/{account.id}/seed-balance",
        _seed_payload(amount="0"),
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_seed_balance_blocks_other_users_account(
    api_client, seeded, test_user, other_user
):
    account = create_bank_account(
        other_user,
        name="Foreign",
        institution_name="HDFC",
        account_number="FOREIGN-SEED",
        currency="INR",
    )
    response = api_client.post(
        f"/api/v1/bank-accounts/{account.id}/seed-balance",
        _seed_payload(),
        format="json",
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_seed_balance_includes_optional_note(api_client, seeded, test_user):
    account = create_bank_account(
        test_user,
        name="Savings",
        institution_name="HDFC",
        account_number="SEED-5",
        currency="INR",
    )
    response = api_client.post(
        f"/api/v1/bank-accounts/{account.id}/seed-balance",
        _seed_payload(note="Backdated FD funding"),
        format="json",
    )
    assert response.status_code == 201
    assert "Backdated FD funding" in response.json()["cash_movement"]["description"]


@pytest.mark.django_db
def test_seed_balance_rejects_duplicate(api_client, seeded, test_user):
    account = create_bank_account(
        test_user,
        name="Savings",
        institution_name="HDFC",
        account_number="SEED-DUP",
        currency="INR",
    )
    payload = _seed_payload(amount="75000", date="2024-01-01")
    first = api_client.post(
        f"/api/v1/bank-accounts/{account.id}/seed-balance",
        payload,
        format="json",
    )
    assert first.status_code == 201
    second = api_client.post(
        f"/api/v1/bank-accounts/{account.id}/seed-balance",
        payload,
        format="json",
    )
    assert second.status_code == 409
    body = second.json()
    assert "already exists" in body["detail"].lower()
    assert body["existing_cash_movement_id"] == first.json()["cash_movement"]["id"]
    assert CashMovement.objects.filter(bank_account=account).count() == 1


@pytest.mark.django_db
def test_seed_then_fd_create_on_day_after_seed(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = create_bank_account(
        test_user,
        name="Savings",
        institution_name="HDFC",
        account_number="SEED-FD-1",
        currency="INR",
    )
    seed = api_client.post(
        f"/api/v1/bank-accounts/{bank.id}/seed-balance",
        _seed_payload(amount="150000", date="2024-01-01"),
        format="json",
    )
    assert seed.status_code == 201

    fd_response = api_client.post(
        "/api/v1/fixed-deposits",
        dict(
            portfolio_id=portfolio.id,
            bank_account_id=bank.id,
            institution_name="HDFC",
            deposit_account_number="FD-SEED-1",
            principal_amount=Decimal("100000"),
            currency="INR",
            interest_rate_percent=Decimal("7.0"),
            interest_payout_frequency="QUARTERLY",
            investment_date=date(2024, 1, 1),
            maturity_date=date(2026, 1, 1),
        ),
        format="json",
    )
    assert fd_response.status_code == 201
    assert fd_response.json()["portfolio_id"] == portfolio.id
    assert (
        CashMovement.objects.filter(
            bank_account=bank, movement_type=CashMovementType.FD_OPENING
        ).count()
        == 1
    )
    # Seed + FD opening only; no broker movements
    assert CashMovement.objects.filter(bank_account=bank).count() == 2
