from datetime import date
from decimal import Decimal

import pytest

from debt.services import create_bank_account
from portfolios.models import Portfolio


def _create_bank(user, **kwargs):
    payload = dict(
        name="Primary",
        institution_name="HDFC",
        account_number="1234567890",
        currency="INR",
        opening_balance=Decimal("5000"),
        current_balance=Decimal("0"),
    )
    payload.update(kwargs)
    return create_bank_account(user, **payload)


@pytest.mark.django_db
def test_list_cash_movements_user_scoped(seeded, test_user, other_user, api_client):
    mine = _create_bank(test_user)
    theirs = _create_bank(other_user, account_number="OTHER-99")
    api_client.post(
        "/api/v1/cash-movements",
        {
            "bank_account_id": mine.id,
            "movement_type": "MANUAL_DEPOSIT",
            "amount": "100.00",
            "movement_date": "2026-06-01",
        },
        format="json",
    )
    api_client.force_authenticate(user=other_user)
    api_client.post(
        "/api/v1/cash-movements",
        {
            "bank_account_id": theirs.id,
            "movement_type": "MANUAL_DEPOSIT",
            "amount": "50.00",
            "movement_date": "2026-06-01",
        },
        format="json",
    )
    api_client.force_authenticate(user=test_user)
    response = api_client.get("/api/v1/cash-movements")
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["bank_account_id"] == mine.id


@pytest.mark.django_db
def test_list_filters_by_bank_account_id(seeded, test_user, api_client):
    a1 = _create_bank(test_user, account_number="A1")
    a2 = _create_bank(test_user, account_number="A2", name="Second")
    for acct, amt in ((a1, "100"), (a2, "200")):
        api_client.post(
            "/api/v1/cash-movements",
            {
                "bank_account_id": acct.id,
                "movement_type": "MANUAL_DEPOSIT",
                "amount": amt,
                "movement_date": "2026-06-01",
            },
            format="json",
        )
    response = api_client.get(f"/api/v1/cash-movements?bank_account_id={a2.id}")
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["amount"] == 200.0


@pytest.mark.django_db
def test_post_manual_deposit_updates_balance(seeded, test_user, api_client):
    account = _create_bank(test_user)
    response = api_client.post(
        "/api/v1/cash-movements",
        {
            "bank_account_id": account.id,
            "movement_type": "MANUAL_DEPOSIT",
            "amount": "1500.00",
            "movement_date": "2026-06-04",
            "description": "Salary",
        },
        format="json",
    )
    assert response.status_code == 201
    body = response.json()
    assert body["movement_type"] == "MANUAL_DEPOSIT"
    assert body["direction"] == "CREDIT"
    assert body["signed_amount"] == 1500.0

    detail = api_client.get(f"/api/v1/bank-accounts/{account.id}")
    assert detail.json()["current_balance"] == 1500.0
    assert detail.json()["balance_source"] == "ledger"
    assert detail.json()["has_ledger_entries"] is True


@pytest.mark.django_db
def test_post_withdrawal_rejects_overdraft(seeded, test_user, api_client):
    account = _create_bank(test_user)
    response = api_client.post(
        "/api/v1/cash-movements",
        {
            "bank_account_id": account.id,
            "movement_type": "MANUAL_WITHDRAWAL",
            "amount": "10.00",
            "movement_date": "2026-06-04",
        },
        format="json",
    )
    assert response.status_code == 400
    assert "Insufficient" in response.json()["detail"]


@pytest.mark.django_db
def test_reject_opening_balance_via_manual_api(seeded, test_user, api_client):
    account = _create_bank(test_user)
    response = api_client.post(
        "/api/v1/cash-movements",
        {
            "bank_account_id": account.id,
            "movement_type": "OPENING_BALANCE",
            "amount": "100.00",
            "movement_date": "2026-06-04",
        },
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_reject_foreign_bank_account(seeded, test_user, other_user, api_client):
    account = _create_bank(other_user, account_number="FOREIGN")
    response = api_client.post(
        "/api/v1/cash-movements",
        {
            "bank_account_id": account.id,
            "movement_type": "MANUAL_DEPOSIT",
            "amount": "100.00",
            "movement_date": "2026-06-04",
        },
        format="json",
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_reject_foreign_portfolio(seeded, test_user, other_user, api_client):
    account = _create_bank(test_user)
    other_pf = Portfolio.objects.create(
        user=other_user,
        name="Other Portfolio",
        base_currency="INR",
        is_active=True,
    )
    response = api_client.post(
        "/api/v1/cash-movements",
        {
            "bank_account_id": account.id,
            "movement_type": "MANUAL_DEPOSIT",
            "amount": "100.00",
            "movement_date": "2026-06-04",
            "portfolio_id": other_pf.id,
        },
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_seed_opening_balance_endpoint(seeded, test_user, api_client):
    account = _create_bank(test_user, opening_balance=Decimal("8000"))
    response = api_client.post(
        f"/api/v1/bank-accounts/{account.id}/seed-opening-balance"
    )
    assert response.status_code == 201
    data = response.json()
    assert data["cash_movement"]["movement_type"] == "OPENING_BALANCE"
    assert data["bank_account"]["current_balance"] == 8000.0
    assert data["bank_account"]["opening_balance_seeded"] is True

    again = api_client.post(
        f"/api/v1/bank-accounts/{account.id}/seed-opening-balance"
    )
    assert again.status_code == 409


@pytest.mark.django_db
def test_seed_zero_opening_balance_rejected(seeded, test_user, api_client):
    account = _create_bank(test_user, opening_balance=Decimal("0"))
    response = api_client.post(
        f"/api/v1/bank-accounts/{account.id}/seed-opening-balance"
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_update_current_balance_rejected_when_ledger_exists(
    seeded, test_user, api_client
):
    account = _create_bank(test_user)
    api_client.post(
        "/api/v1/cash-movements",
        {
            "bank_account_id": account.id,
            "movement_type": "MANUAL_DEPOSIT",
            "amount": "100.00",
            "movement_date": "2026-06-04",
        },
        format="json",
    )
    response = api_client.put(
        f"/api/v1/bank-accounts/{account.id}",
        {"name": account.name, "current_balance": "9999.00"},
        format="json",
    )
    assert response.status_code == 400
    assert "current_balance" in response.json()["detail"]


@pytest.mark.django_db
def test_update_without_current_balance_when_ledger_exists(
    seeded, test_user, api_client
):
    account = _create_bank(test_user)
    api_client.post(
        "/api/v1/cash-movements",
        {
            "bank_account_id": account.id,
            "movement_type": "MANUAL_DEPOSIT",
            "amount": "100.00",
            "movement_date": "2026-06-04",
        },
        format="json",
    )
    response = api_client.put(
        f"/api/v1/bank-accounts/{account.id}",
        {"name": "Renamed Account"},
        format="json",
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Renamed Account"


@pytest.mark.django_db
def test_cash_movement_delete_not_allowed(seeded, test_user, api_client):
    account = _create_bank(test_user)
    created = api_client.post(
        "/api/v1/cash-movements",
        {
            "bank_account_id": account.id,
            "movement_type": "MANUAL_DEPOSIT",
            "amount": "100.00",
            "movement_date": "2026-06-04",
        },
        format="json",
    )
    movement_id = created.json()["id"]
    response = api_client.delete(f"/api/v1/cash-movements/{movement_id}")
    assert response.status_code == 405


@pytest.mark.django_db
def test_get_cash_movement_detail(seeded, test_user, api_client):
    account = _create_bank(test_user)
    created = api_client.post(
        "/api/v1/cash-movements",
        {
            "bank_account_id": account.id,
            "movement_type": "MANUAL_DEPOSIT",
            "amount": "250.00",
            "movement_date": "2026-06-04",
        },
        format="json",
    )
    movement_id = created.json()["id"]
    response = api_client.get(f"/api/v1/cash-movements/{movement_id}")
    assert response.status_code == 200
    assert response.json()["id"] == movement_id


@pytest.mark.django_db
def test_bank_balance_not_in_portfolio_summary(seeded, test_user, api_client):
    account = _create_bank(test_user)
    summary_before = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false"
    )
    assert summary_before.status_code == 200
    value_before = summary_before.json()["current_value"]

    api_client.post(
        "/api/v1/cash-movements",
        {
            "bank_account_id": account.id,
            "movement_type": "MANUAL_DEPOSIT",
            "amount": "50000.00",
            "movement_date": "2026-06-04",
        },
        format="json",
    )

    summary_after = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false"
    )
    assert summary_after.status_code == 200
    assert summary_after.json()["current_value"] == value_before


@pytest.mark.django_db
def test_adjustment_credit_and_debit(seeded, test_user, api_client):
    account = _create_bank(test_user)
    api_client.post(
        "/api/v1/cash-movements",
        {
            "bank_account_id": account.id,
            "movement_type": "MANUAL_DEPOSIT",
            "amount": "1000.00",
            "movement_date": "2026-06-01",
        },
        format="json",
    )
    api_client.post(
        "/api/v1/cash-movements",
        {
            "bank_account_id": account.id,
            "movement_type": "ADJUSTMENT",
            "amount": "50.00",
            "movement_date": "2026-06-02",
            "direction": "DEBIT",
        },
        format="json",
    )
    detail = api_client.get(f"/api/v1/bank-accounts/{account.id}")
    assert detail.json()["current_balance"] == 950.0
