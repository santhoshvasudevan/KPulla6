from decimal import Decimal

import pytest

from debt.models import BankAccount
from debt.services import (
    BankAccountNotFoundError,
    BankAccountValidationError,
    create_bank_account,
    deactivate_bank_account,
    list_active_bank_accounts,
    update_bank_account,
)


def _create_account(user, **overrides):
    payload = dict(
        name="Primary Savings",
        institution_name="HDFC Bank",
        account_number="12345678901234",
        currency="INR",
        opening_balance=Decimal("5000"),
        current_balance=Decimal("5000"),
        comment="Salary account",
    )
    payload.update(overrides)
    return create_bank_account(user, **payload)


@pytest.mark.django_db
def test_bank_account_model_stores_full_account_number(test_user):
    account = _create_account(test_user, account_number="ACCT-999888777")
    account.refresh_from_db()
    assert account.account_number == "ACCT-999888777"


@pytest.mark.django_db
def test_list_active_bank_accounts_user_scoped(seeded, test_user, other_user, api_client):
    _create_account(test_user)
    _create_account(other_user, name="Other Account", account_number="OTHER-1")

    response = api_client.get("/api/v1/bank-accounts")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["account_number"] == "12345678901234"


@pytest.mark.django_db
def test_create_bank_account(api_client, seeded, test_user):
    response = api_client.post(
        "/api/v1/bank-accounts",
        {
            "name": "NRE Account",
            "institution_name": "SBI",
            "account_number": "NRE-001",
            "currency": "INR",
            "opening_balance": "10000.00",
            "current_balance": "10000.00",
            "comment": "",
        },
        format="json",
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "NRE Account"
    assert body["account_number"] == "NRE-001"
    assert body["is_active"] is True


@pytest.mark.django_db
def test_update_bank_account(api_client, seeded, test_user):
    account = _create_account(test_user)
    response = api_client.put(
        f"/api/v1/bank-accounts/{account.id}",
        {"name": "Updated Name", "current_balance": "7500.00"},
        format="json",
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Updated Name"
    assert response.json()["current_balance"] == 7500.0


@pytest.mark.django_db
def test_delete_soft_deactivates_bank_account(api_client, seeded, test_user):
    account = _create_account(test_user)
    response = api_client.delete(f"/api/v1/bank-accounts/{account.id}")
    assert response.status_code == 200
    assert response.json()["is_active"] is False
    assert list_active_bank_accounts(test_user) == []


@pytest.mark.django_db
def test_cannot_access_other_users_bank_account(seeded, test_user, other_user, api_client):
    account = _create_account(other_user)
    response = api_client.get(f"/api/v1/bank-accounts/{account.id}")
    assert response.status_code == 404


@pytest.mark.django_db
def test_unauthenticated_bank_accounts_returns_401_or_403(anon_client):
    response = anon_client.get("/api/v1/bank-accounts")
    assert response.status_code in (401, 403)


@pytest.mark.django_db
def test_create_rejects_unsupported_currency(seeded, test_user):
    with pytest.raises(BankAccountValidationError):
        _create_account(test_user, currency="ZZZ")


@pytest.mark.django_db
def test_deactivated_account_not_in_list(seeded, test_user):
    account = _create_account(test_user)
    deactivate_bank_account(test_user, account.id)
    assert list_active_bank_accounts(test_user) == []


@pytest.mark.django_db
def test_get_inactive_account_returns_data(seeded, test_user, api_client):
    account = _create_account(test_user)
    deactivate_bank_account(test_user, account.id)
    response = api_client.get(f"/api/v1/bank-accounts/{account.id}")
    assert response.status_code == 200
    assert response.json()["is_active"] is False


@pytest.mark.django_db
def test_update_inactive_account_returns_404(seeded, test_user, api_client):
    account = _create_account(test_user)
    deactivate_bank_account(test_user, account.id)
    response = api_client.put(
        f"/api/v1/bank-accounts/{account.id}",
        {"name": "Should fail"},
        format="json",
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_model_validation_empty_name(seeded, test_user):
    with pytest.raises(BankAccountValidationError):
        create_bank_account(
            test_user,
            name="",
            institution_name="HDFC",
            account_number="1",
            currency="INR",
        )
