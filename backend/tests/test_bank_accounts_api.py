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


@pytest.mark.django_db
def test_create_bank_account_with_portfolio(api_client, seeded, test_user):
    from portfolios.seed import ensure_default_portfolio

    portfolio = ensure_default_portfolio(test_user)
    response = api_client.post(
        "/api/v1/bank-accounts",
        {
            "name": "Linked",
            "institution_name": "SBI",
            "account_number": "LINK-1",
            "currency": "INR",
            "portfolio_id": portfolio.id,
        },
        format="json",
    )
    assert response.status_code == 201
    body = response.json()
    assert body["portfolio_id"] == portfolio.id
    assert body["portfolio_name"] == portfolio.name
    assert body["portfolio_assignment_status"] == "ASSIGNED"


@pytest.mark.django_db
def test_update_bank_account_portfolio(api_client, seeded, test_user):
    from portfolios.seed import ensure_default_portfolio

    portfolio = ensure_default_portfolio(test_user)
    account = _create_account(test_user)
    response = api_client.put(
        f"/api/v1/bank-accounts/{account.id}",
        {"portfolio_id": portfolio.id},
        format="json",
    )
    assert response.status_code == 200
    assert response.json()["portfolio_id"] == portfolio.id


@pytest.mark.django_db
def test_create_bank_account_rejects_other_users_portfolio(
    api_client, seeded, test_user, other_user
):
    from portfolios.models import Portfolio

    other_portfolio = Portfolio.objects.create(
        user=other_user, name="Other PF", base_currency="INR", is_active=True
    )
    response = api_client.post(
        "/api/v1/bank-accounts",
        {
            "name": "Bad link",
            "institution_name": "SBI",
            "account_number": "BAD",
            "currency": "INR",
            "portfolio_id": other_portfolio.id,
        },
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_null_portfolio_allowed_on_create(api_client, seeded, test_user):
    response = api_client.post(
        "/api/v1/bank-accounts",
        {
            "name": "Unlinked",
            "institution_name": "SBI",
            "account_number": "NULL-1",
            "currency": "INR",
        },
        format="json",
    )
    assert response.status_code == 201
    body = response.json()
    assert body["portfolio_id"] is None
    assert body["portfolio_assignment_status"] == "UNASSIGNED"


@pytest.mark.django_db
def test_bank_account_balance_endpoint_current_and_as_of(api_client, seeded, test_user):
    from datetime import date
    from tests.debt_test_helpers import fund_bank_account

    account = _create_account(test_user, opening_balance=Decimal("0"), current_balance=Decimal("0"))
    fund_bank_account(test_user, account, "1109389", movement_date=date(2023, 9, 24))

    current = api_client.get(f"/api/v1/bank-accounts/{account.id}/balance")
    assert current.status_code == 200
    body = current.json()
    assert body["current_balance"] == 1109389.0
    assert body["currency"] == "INR"

    as_of_before = api_client.get(
        f"/api/v1/bank-accounts/{account.id}/balance",
        {"as_of": "2023-09-23"},
    )
    assert as_of_before.status_code == 200
    as_of_body = as_of_before.json()
    assert as_of_body["balance_as_of_date"] == 0.0
    assert as_of_body["as_of_date"] == "2023-09-23"

    as_of_same = api_client.get(
        f"/api/v1/bank-accounts/{account.id}/balance",
        {"as_of": "2023-09-24"},
    )
    assert as_of_same.json()["balance_as_of_date"] == 1109389.0


@pytest.mark.django_db
def test_delink_bank_account(api_client, seeded, test_user):
    from portfolios.seed import ensure_default_portfolio

    portfolio = ensure_default_portfolio(test_user)
    account = _create_account(test_user)
    api_client.put(
        f"/api/v1/bank-accounts/{account.id}",
        {"portfolio_id": portfolio.id},
        format="json",
    )
    response = api_client.put(
        f"/api/v1/bank-accounts/{account.id}",
        {"portfolio_id": None},
        format="json",
    )
    assert response.status_code == 200
    body = response.json()
    assert body["portfolio_id"] is None
    assert body["portfolio_name"] is None
    assert body["portfolio_assignment_status"] == "UNASSIGNED"


@pytest.mark.django_db
def test_change_linked_portfolio(api_client, seeded, test_user):
    from portfolios.models import Portfolio
    from portfolios.seed import ensure_default_portfolio

    p1 = ensure_default_portfolio(test_user)
    p2 = Portfolio.objects.create(
        user=test_user, name="IndianInvestments", base_currency="INR", is_active=True
    )
    account = _create_account(test_user)
    api_client.put(
        f"/api/v1/bank-accounts/{account.id}",
        {"portfolio_id": p1.id},
        format="json",
    )
    response = api_client.put(
        f"/api/v1/bank-accounts/{account.id}",
        {"portfolio_id": p2.id},
        format="json",
    )
    assert response.status_code == 200
    body = response.json()
    assert body["portfolio_id"] == p2.id
    assert body["portfolio_name"] == "IndianInvestments"
    assert body["portfolio_assignment_status"] == "ASSIGNED"


@pytest.mark.django_db
def test_link_rejects_inactive_portfolio(api_client, seeded, test_user):
    from portfolios.seed import ensure_default_portfolio

    portfolio = ensure_default_portfolio(test_user)
    portfolio.is_active = False
    portfolio.save()
    account = _create_account(test_user)
    response = api_client.put(
        f"/api/v1/bank-accounts/{account.id}",
        {"portfolio_id": portfolio.id},
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_link_delink_creates_no_cash_movement(api_client, seeded, test_user):
    from debt.models import CashMovement
    from portfolios.models import Portfolio
    from portfolios.seed import ensure_default_portfolio
    from tests.debt_test_helpers import fund_bank_account

    p1 = ensure_default_portfolio(test_user)
    p2 = Portfolio.objects.create(
        user=test_user, name="Other", base_currency="INR", is_active=True
    )
    account = _create_account(test_user, opening_balance=Decimal("0"), current_balance=Decimal("0"))
    fund_bank_account(test_user, account, "50000")
    before = CashMovement.objects.filter(bank_account=account).count()

    api_client.put(
        f"/api/v1/bank-accounts/{account.id}",
        {"portfolio_id": p1.id},
        format="json",
    )
    api_client.put(
        f"/api/v1/bank-accounts/{account.id}",
        {"portfolio_id": p2.id},
        format="json",
    )
    api_client.put(
        f"/api/v1/bank-accounts/{account.id}",
        {"portfolio_id": None},
        format="json",
    )

    assert CashMovement.objects.filter(bank_account=account).count() == before


@pytest.mark.django_db
def test_link_delink_does_not_change_balance(api_client, seeded, test_user):
    from portfolios.seed import ensure_default_portfolio
    from tests.debt_test_helpers import fund_bank_account

    portfolio = ensure_default_portfolio(test_user)
    account = _create_account(test_user, opening_balance=Decimal("0"), current_balance=Decimal("0"))
    fund_bank_account(test_user, account, "1359389")
    account.refresh_from_db()
    balance_before = account.current_balance

    api_client.put(
        f"/api/v1/bank-accounts/{account.id}",
        {"portfolio_id": portfolio.id},
        format="json",
    )
    api_client.put(
        f"/api/v1/bank-accounts/{account.id}",
        {"portfolio_id": None},
        format="json",
    )

    account.refresh_from_db()
    assert account.current_balance == balance_before
