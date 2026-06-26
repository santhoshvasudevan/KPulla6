from datetime import date
from decimal import Decimal

import pytest

from debt.models import CashMovement, CashMovementDirection, CashMovementSource, CashMovementType, FixedDeposit
from debt.services import (
    FixedDepositValidationError,
    create_bank_account,
    create_fixed_deposit,
    deactivate_fixed_deposit,
    update_fixed_deposit,
)
from debt.bank_ledger_services import seed_opening_balance
from portfolios.models import Portfolio
from portfolios.seed import ensure_default_portfolio
from tests.debt_test_helpers import create_test_bank_account, fund_bank_account


def _bank(user, portfolio=None, **overrides):
    return create_test_bank_account(user, portfolio=portfolio, **overrides)


def _fd_payload(portfolio_id, bank_account_id, **overrides):
    payload = dict(
        bank_account_id=bank_account_id,
        institution_name="HDFC",
        deposit_account_number="FD-001",
        principal_amount=Decimal("100000"),
        currency="INR",
        interest_rate_percent=Decimal("7.0"),
        interest_payout_frequency="QUARTERLY",
        investment_date=date(2024, 1, 1),
        maturity_date=date(2026, 1, 1),
        nominee_name="Nominee",
        comment="Test FD",
    )
    if portfolio_id is not None:
        payload["portfolio_id"] = portfolio_id
    payload.update(overrides)
    return payload


@pytest.mark.django_db
def test_create_fixed_deposit(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fund_bank_account(test_user, bank, "150000")
    response = api_client.post(
        "/api/v1/fixed-deposits",
        _fd_payload(portfolio.id, bank.id),
        format="json",
    )
    assert response.status_code == 201
    body = response.json()
    assert body["principal_amount"] == 100000.0
    assert body["portfolio_id"] == portfolio.id
    assert body["bank_account_id"] == bank.id
    assert body["status"] == "ACTIVE"
    assert body["has_opening_cash_movement"] is True
    assert body["opening_cash_movement_id"] is not None

    movement = CashMovement.objects.get(id=body["opening_cash_movement_id"])
    assert movement.movement_type == CashMovementType.FD_OPENING
    assert movement.direction == CashMovementDirection.DEBIT
    assert movement.source == CashMovementSource.SYSTEM
    assert movement.linked_fixed_deposit_id == body["id"]
    assert movement.amount == Decimal("100000")

    bank.refresh_from_db()
    assert bank.current_balance == Decimal("50000")


@pytest.mark.django_db
def test_reject_invalid_maturity_date(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    response = api_client.post(
        "/api/v1/fixed-deposits",
        _fd_payload(
            portfolio.id,
            bank.id,
            investment_date=date(2026, 1, 1),
            maturity_date=date(2024, 1, 1),
        ),
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_reject_principal_zero(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    response = api_client.post(
        "/api/v1/fixed-deposits",
        _fd_payload(portfolio.id, bank.id, principal_amount=Decimal("0")),
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_reject_negative_interest_rate(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    response = api_client.post(
        "/api/v1/fixed-deposits",
        _fd_payload(portfolio.id, bank.id, interest_rate_percent=Decimal("-1")),
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_reject_inactive_bank_account(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    bank.is_active = False
    bank.save()
    response = api_client.post(
        "/api/v1/fixed-deposits",
        _fd_payload(portfolio.id, bank.id),
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_reject_foreign_bank_account(api_client, seeded, test_user, other_user):
    portfolio = ensure_default_portfolio(test_user)
    foreign_bank = _bank(other_user, account_number="FOREIGN")
    response = api_client.post(
        "/api/v1/fixed-deposits",
        _fd_payload(portfolio.id, foreign_bank.id),
        format="json",
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_reject_foreign_portfolio(api_client, seeded, test_user, other_user):
    portfolio = ensure_default_portfolio(test_user)
    other_portfolio = Portfolio.objects.create(
        user=other_user, name="Other PF", base_currency="EUR", is_active=True
    )
    bank = _bank(test_user, portfolio=portfolio)
    response = api_client.post(
        "/api/v1/fixed-deposits",
        _fd_payload(other_portfolio.id, bank.id),
        format="json",
    )
    assert response.status_code == 400
    body = response.json()
    assert body["bank_account_id"] == bank.id
    assert body["requested_portfolio_id"] == other_portfolio.id
    assert body["bank_account_portfolio_id"] == portfolio.id


@pytest.mark.django_db
def test_reject_currency_mismatch(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user, currency="INR")
    response = api_client.post(
        "/api/v1/fixed-deposits",
        _fd_payload(portfolio.id, bank.id, currency="EUR"),
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_list_user_owned_fds_only(api_client, seeded, test_user, other_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fund_bank_account(test_user, bank, "150000")
    create_fixed_deposit(test_user, **_fd_payload(portfolio.id, bank.id))

    other_portfolio = Portfolio.objects.create(
        user=other_user, name="Other", base_currency="INR", is_active=True
    )
    other_bank = _bank(other_user, portfolio=other_portfolio, account_number="OTHER")
    fund_bank_account(other_user, other_bank, "150000")
    create_fixed_deposit(other_user, **_fd_payload(other_portfolio.id, other_bank.id))

    response = api_client.get("/api/v1/fixed-deposits")
    assert response.status_code == 200
    assert len(response.json()) == 1


@pytest.mark.django_db
def test_list_filters_by_portfolio_id(api_client, seeded, test_user):
    p1 = ensure_default_portfolio(test_user)
    p2 = Portfolio.objects.create(
        user=test_user, name="Second", base_currency="INR", is_active=True
    )
    bank1 = _bank(test_user, portfolio=p1, account_number="BANK-P1")
    bank2 = _bank(test_user, portfolio=p2, account_number="BANK-P2")
    fund_bank_account(test_user, bank1, "150000")
    fund_bank_account(test_user, bank2, "150000")
    create_fixed_deposit(
        test_user, **_fd_payload(p1.id, bank1.id, deposit_account_number="FD-A")
    )
    create_fixed_deposit(
        test_user, **_fd_payload(p2.id, bank2.id, deposit_account_number="FD-B")
    )

    response = api_client.get(f"/api/v1/fixed-deposits?portfolio_id={p2.id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["deposit_account_number"] == "FD-B"


@pytest.mark.django_db
def test_soft_delete_deactivates_legacy_fd(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = create_fixed_deposit(
        test_user,
        **_fd_payload(portfolio.id, bank.id),
        skip_opening_debit=True,
    )
    response = api_client.delete(f"/api/v1/fixed-deposits/{fd.id}")
    assert response.status_code == 200
    assert response.json()["is_active"] is False


@pytest.mark.django_db
def test_soft_delete_blocks_ledger_backed_fd(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fund_bank_account(test_user, bank, "150000")
    fd = create_fixed_deposit(test_user, **_fd_payload(portfolio.id, bank.id))
    response = api_client.delete(f"/api/v1/fixed-deposits/{fd.id}")
    assert response.status_code == 409
    assert "Cancel FD" in response.json()["detail"]


@pytest.mark.django_db
def test_renewal_of_same_user(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fund_bank_account(test_user, bank, "250000")
    original = create_fixed_deposit(
        test_user, **_fd_payload(portfolio.id, bank.id, deposit_account_number="FD-OLD")
    )
    response = api_client.post(
        "/api/v1/fixed-deposits",
        _fd_payload(
            portfolio.id,
            bank.id,
            deposit_account_number="FD-NEW",
            renewal_of_id=original.id,
        ),
        format="json",
    )
    assert response.status_code == 201
    assert response.json()["renewal_of_id"] == original.id


@pytest.mark.django_db
def test_unauthenticated_fixed_deposits_returns_401_or_403(anon_client):
    response = anon_client.get("/api/v1/fixed-deposits")
    assert response.status_code in (401, 403)


@pytest.mark.django_db
def test_create_via_service_rejects_inactive_portfolio(seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user, portfolio=portfolio)
    fund_bank_account(test_user, bank, "150000")
    portfolio.is_active = False
    portfolio.save()
    with pytest.raises(FixedDepositValidationError):
        create_fixed_deposit(test_user, **_fd_payload(portfolio.id, bank.id))


@pytest.mark.django_db
def test_deactivated_fd_excluded_from_active_list(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = create_fixed_deposit(
        test_user,
        **_fd_payload(portfolio.id, bank.id),
        skip_opening_debit=True,
    )
    deactivate_fixed_deposit(test_user, fd.id)
    response = api_client.get("/api/v1/fixed-deposits")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.django_db
def test_create_fd_rejects_insufficient_bank_balance(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    response = api_client.post(
        "/api/v1/fixed-deposits",
        _fd_payload(portfolio.id, bank.id),
        format="json",
    )
    assert response.status_code == 400
    body = response.json()
    assert "Insufficient" in body["detail"]
    assert body["required"] == 100000.0
    assert body["available"] == 0.0
    assert body["available_as_of_date"] == 0.0
    assert body["current_balance"] == 0.0
    assert body["investment_date"] == "2024-01-01"
    assert body["shortfall"] > 0
    assert "hint" in body
    assert "backdated" in body["hint"].lower() or "investment date" in body["hint"].lower()
    assert FixedDeposit.objects.filter(user=test_user).count() == 0
    assert CashMovement.objects.filter(user=test_user).count() == 0


@pytest.mark.django_db
def test_create_fd_rejects_when_as_of_balance_insufficient_but_current_sufficient(
    api_client, seeded, test_user,
):
    """Deposit on 2023-09-24; FD on 2023-09-23 must fail despite higher current balance."""
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fund_bank_account(
        test_user,
        bank,
        "1109389",
        movement_date=date(2023, 9, 24),
    )
    bank.refresh_from_db()
    assert bank.current_balance == Decimal("1109389")

    response = api_client.post(
        "/api/v1/fixed-deposits",
        _fd_payload(
            portfolio.id,
            bank.id,
            principal_amount=Decimal("1109389"),
            investment_date=date(2023, 9, 23),
            maturity_date=date(2024, 9, 23),
        ),
        format="json",
    )
    assert response.status_code == 400
    body = response.json()
    assert body["required"] == 1109389.0
    assert body["available_as_of_date"] == 0.0
    assert body["current_balance"] == 1109389.0
    assert body["investment_date"] == "2023-09-23"
    assert body["shortfall"] == 1109389.0
    assert body["currency"] == "INR"
    assert "investment date" in body["hint"].lower()


@pytest.mark.django_db
def test_create_fd_succeeds_when_deposit_same_date_as_investment(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fund_bank_account(
        test_user,
        bank,
        "1109389",
        movement_date=date(2023, 9, 24),
    )
    response = api_client.post(
        "/api/v1/fixed-deposits",
        _fd_payload(
            portfolio.id,
            bank.id,
            principal_amount=Decimal("1109389"),
            investment_date=date(2023, 9, 24),
            maturity_date=date(2024, 9, 24),
        ),
        format="json",
    )
    assert response.status_code == 201


@pytest.mark.django_db
def test_create_fd_succeeds_when_deposit_before_investment_date(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fund_bank_account(
        test_user,
        bank,
        "1109389",
        movement_date=date(2023, 9, 24),
    )
    response = api_client.post(
        "/api/v1/fixed-deposits",
        _fd_payload(
            portfolio.id,
            bank.id,
            principal_amount=Decimal("500000"),
            investment_date=date(2023, 9, 25),
            maturity_date=date(2024, 9, 25),
        ),
        format="json",
    )
    assert response.status_code == 201


@pytest.mark.django_db
def test_create_fd_unseeded_opening_balance_not_usable_ledger_cash(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = create_bank_account(
        test_user,
        name="Savings",
        institution_name="HDFC",
        account_number="REF-ONLY",
        currency="INR",
        opening_balance=Decimal("250000"),
        current_balance=Decimal("250000"),
        portfolio_id=portfolio.id,
    )
    fund_bank_account(test_user, bank, "100000", movement_date=date(2024, 1, 1))
    response = api_client.post(
        "/api/v1/fixed-deposits",
        _fd_payload(
            portfolio.id,
            bank.id,
            principal_amount=Decimal("350000"),
            investment_date=date(2024, 1, 1),
        ),
        format="json",
    )
    assert response.status_code == 400
    body = response.json()
    assert body["available_as_of_date"] == 100000.0
    assert body["current_balance"] == 100000.0
    assert "seed" in body["hint"].lower()


@pytest.mark.django_db
def test_create_fd_uses_linked_bank_not_other_account_balance(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    funded = _bank(test_user, account_number="FUNDED-1")
    fund_bank_account(test_user, funded, "500000", movement_date=date(2024, 1, 1))
    empty = create_bank_account(
        test_user,
        name="Empty",
        institution_name="HDFC",
        account_number="EMPTY-1",
        currency="INR",
        portfolio_id=portfolio.id,
    )
    response = api_client.post(
        "/api/v1/fixed-deposits",
        _fd_payload(
            portfolio.id,
            empty.id,
            principal_amount=Decimal("100000"),
            investment_date=date(2024, 1, 1),
        ),
        format="json",
    )
    assert response.status_code == 400
    body = response.json()
    assert body["available_as_of_date"] == 0.0
    assert body["current_balance"] == 0.0


@pytest.mark.django_db
def test_create_fd_fails_when_opening_balance_not_seeded(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = create_bank_account(
        test_user,
        name="Savings",
        institution_name="HDFC",
        account_number="UNSEEDED-1",
        currency="INR",
        opening_balance=Decimal("250000"),
        current_balance=Decimal("250000"),
        portfolio_id=portfolio.id,
    )
    response = api_client.post(
        "/api/v1/fixed-deposits",
        _fd_payload(portfolio.id, bank.id, principal_amount=Decimal("100000")),
        format="json",
    )
    assert response.status_code == 400
    body = response.json()
    assert body["available"] == 0.0
    assert body["required"] == 100000.0
    assert body["shortfall"] == 100000.0
    assert "hint" in body
    assert "seed" in body["hint"].lower()
    assert FixedDeposit.objects.filter(user=test_user).count() == 0
    assert CashMovement.objects.filter(user=test_user).count() == 0


@pytest.mark.django_db
def test_create_fd_succeeds_after_opening_balance_seeded(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = create_bank_account(
        test_user,
        name="Savings",
        institution_name="HDFC",
        account_number="SEEDED-1",
        currency="INR",
        opening_balance=Decimal("250000"),
        current_balance=Decimal("250000"),
        portfolio_id=portfolio.id,
    )
    seed_opening_balance(test_user, bank.id, movement_date=date(2024, 1, 1))
    bank.refresh_from_db()
    from debt.bank_ledger_services import opening_balance_is_seeded

    assert bank.current_balance == Decimal("250000")
    assert opening_balance_is_seeded(bank)

    response = api_client.post(
        "/api/v1/fixed-deposits",
        _fd_payload(portfolio.id, bank.id, principal_amount=Decimal("100000")),
        format="json",
    )
    assert response.status_code == 201
    body = response.json()
    assert body["has_opening_cash_movement"] is True

    bank.refresh_from_db()
    assert bank.current_balance == Decimal("150000")
    assert CashMovement.objects.filter(
        bank_account=bank, movement_type=CashMovementType.OPENING_BALANCE
    ).count() == 1
    assert CashMovement.objects.filter(
        bank_account=bank, movement_type=CashMovementType.FD_OPENING
    ).count() == 1


@pytest.mark.django_db
def test_create_fd_and_opening_movement_atomic(seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fund_bank_account(test_user, bank, "100000")

    from unittest.mock import patch

    with patch(
        "debt.bank_ledger_services.create_fd_opening_cash_movement",
        side_effect=RuntimeError("movement failed"),
    ):
        with pytest.raises(RuntimeError):
            create_fixed_deposit(test_user, **_fd_payload(portfolio.id, bank.id))

    assert FixedDeposit.objects.filter(user=test_user).count() == 0


@pytest.mark.django_db
def test_fd_opening_movement_links_portfolio_and_date(seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fund_bank_account(test_user, bank, "150000")
    fd = create_fixed_deposit(
        test_user,
        **_fd_payload(
            portfolio.id,
            bank.id,
            investment_date=date(2025, 3, 15),
        ),
    )
    movement = CashMovement.objects.get(linked_fixed_deposit=fd)
    assert movement.portfolio_id == portfolio.id
    assert movement.movement_date == date(2025, 3, 15)
    assert "Fixed deposit opening:" in movement.description


@pytest.mark.django_db
def test_duplicate_fd_opening_rejected(seeded, test_user):
    from debt.bank_ledger_services import FdOpeningAlreadyRecordedError, create_fd_opening_cash_movement

    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fund_bank_account(test_user, bank, "150000")
    fd = create_fixed_deposit(test_user, **_fd_payload(portfolio.id, bank.id))

    with pytest.raises(FdOpeningAlreadyRecordedError):
        create_fd_opening_cash_movement(test_user, fd)


@pytest.mark.django_db
def test_update_fd_does_not_create_second_opening(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fund_bank_account(test_user, bank, "150000")
    fd = create_fixed_deposit(test_user, **_fd_payload(portfolio.id, bank.id))
    assert CashMovement.objects.filter(
        linked_fixed_deposit=fd, movement_type=CashMovementType.FD_OPENING
    ).count() == 1

    response = api_client.put(
        f"/api/v1/fixed-deposits/{fd.id}",
        {"interest_rate_percent": "7.5", "nominee_name": "Updated"},
        format="json",
    )
    assert response.status_code == 200
    assert CashMovement.objects.filter(
        linked_fixed_deposit=fd, movement_type=CashMovementType.FD_OPENING
    ).count() == 1


@pytest.mark.django_db
def test_update_rejects_principal_after_opening(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fund_bank_account(test_user, bank, "150000")
    fd = create_fixed_deposit(test_user, **_fd_payload(portfolio.id, bank.id))

    response = api_client.put(
        f"/api/v1/fixed-deposits/{fd.id}",
        {"principal_amount": "90000"},
        format="json",
    )
    assert response.status_code == 400
    assert "principal_amount" in response.json()["detail"]


@pytest.mark.django_db
def test_update_rejects_bank_account_after_opening(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    bank2 = _bank(test_user, portfolio=portfolio, account_number="222333444", name="NRE")
    fund_bank_account(test_user, bank, "150000")
    fd = create_fixed_deposit(test_user, **_fd_payload(portfolio.id, bank.id))

    response = api_client.put(
        f"/api/v1/fixed-deposits/{fd.id}",
        {"bank_account_id": bank2.id},
        format="json",
    )
    assert response.status_code == 400
    assert "bank_account_id" in response.json()["detail"]


@pytest.mark.django_db
def test_legacy_fd_without_opening_remains_editable(seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = FixedDeposit(
        user=test_user,
        portfolio=portfolio,
        bank_account=bank,
        institution_name="HDFC",
        deposit_account_number="LEGACY-1",
        principal_amount=Decimal("50000"),
        currency="INR",
        interest_rate_percent=Decimal("7"),
        interest_payout_frequency="QUARTERLY",
        investment_date=date(2023, 1, 1),
        maturity_date=date(2025, 1, 1),
        status="ACTIVE",
        is_active=True,
    )
    fd.save()

    updated = update_fixed_deposit(
        test_user,
        fd.id,
        principal_amount=Decimal("55000"),
    )
    assert updated.principal_amount == Decimal("55000")
    assert not CashMovement.objects.filter(linked_fixed_deposit=fd).exists()


@pytest.mark.django_db
def test_portfolio_summary_includes_fd_after_opening_debit(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fund_bank_account(test_user, bank, "150000")
    create_fixed_deposit(test_user, **_fd_payload(portfolio.id, bank.id))

    data = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false&display_currency=INR"
    ).json()
    assert data["current_value"] == 100000.0
    bank.refresh_from_db()
    assert bank.current_balance == Decimal("50000")


@pytest.mark.django_db
def test_create_fd_derives_portfolio_from_bank_account(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user, portfolio=portfolio)
    fund_bank_account(test_user, bank, "150000")
    payload = _fd_payload(None, bank.id)
    response = api_client.post("/api/v1/fixed-deposits", payload, format="json")
    assert response.status_code == 201
    assert response.json()["portfolio_id"] == portfolio.id


@pytest.mark.django_db
def test_create_fd_matching_portfolio_id_succeeds(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user, portfolio=portfolio)
    fund_bank_account(test_user, bank, "150000")
    response = api_client.post(
        "/api/v1/fixed-deposits",
        _fd_payload(portfolio.id, bank.id),
        format="json",
    )
    assert response.status_code == 201
    assert response.json()["portfolio_id"] == portfolio.id


@pytest.mark.django_db
def test_create_fd_conflicting_portfolio_id_fails(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    other = Portfolio.objects.create(
        user=test_user, name="IndianInvestments", base_currency="INR", is_active=True
    )
    bank = _bank(test_user, portfolio=portfolio)
    fund_bank_account(test_user, bank, "150000")
    response = api_client.post(
        "/api/v1/fixed-deposits",
        _fd_payload(other.id, bank.id),
        format="json",
    )
    assert response.status_code == 400
    body = response.json()
    assert body["bank_account_id"] == bank.id
    assert body["bank_account_portfolio_id"] == portfolio.id
    assert body["requested_portfolio_id"] == other.id
    assert body["portfolio_assignment_status"] == "ASSIGNED"
    assert "hint" in body


@pytest.mark.django_db
def test_create_fd_unassigned_bank_account_fails(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = create_bank_account(
        test_user,
        name="Unassigned",
        institution_name="HDFC",
        account_number="UNASSIGNED-1",
        currency="INR",
    )
    response = api_client.post(
        "/api/v1/fixed-deposits",
        _fd_payload(portfolio.id, bank.id),
        format="json",
    )
    assert response.status_code == 400
    body = response.json()
    assert body["bank_account_id"] == bank.id
    assert body["portfolio_assignment_status"] == "UNASSIGNED"
    assert "Assign this bank account" in body["detail"]


@pytest.mark.django_db
def test_create_fd_ambiguous_bank_account_fails(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    p2 = Portfolio.objects.create(
        user=test_user, name="Second", base_currency="INR", is_active=True
    )
    bank = create_bank_account(
        test_user,
        name="Ambiguous",
        institution_name="HDFC",
        account_number="AMBIG-1",
        currency="INR",
    )
    for dep_num, pf in (("SIG-1", portfolio), ("SIG-2", p2)):
        FixedDeposit(
            user=test_user,
            portfolio=pf,
            bank_account=bank,
            institution_name="HDFC",
            deposit_account_number=dep_num,
            principal_amount=Decimal("50000"),
            currency="INR",
            interest_rate_percent=Decimal("7"),
            interest_payout_frequency="QUARTERLY",
            investment_date=date(2023, 1, 1),
            maturity_date=date(2025, 1, 1),
            status="ACTIVE",
            is_active=True,
        ).save()
    fund_bank_account(test_user, bank, "300000")
    response = api_client.post(
        "/api/v1/fixed-deposits",
        _fd_payload(portfolio.id, bank.id, deposit_account_number="NEW-FD"),
        format="json",
    )
    assert response.status_code == 400
    body = response.json()
    assert body["portfolio_assignment_status"] == "AMBIGUOUS"


@pytest.mark.django_db
def test_legacy_fd_portfolio_mismatch_warning(api_client, seeded, test_user):
    p1 = ensure_default_portfolio(test_user)
    p2 = Portfolio.objects.create(
        user=test_user, name="Other PF", base_currency="INR", is_active=True
    )
    bank = _bank(test_user, portfolio=p2)
    fd = FixedDeposit(
        user=test_user,
        portfolio=p1,
        bank_account=bank,
        institution_name="HDFC",
        deposit_account_number="MISMATCH-1",
        principal_amount=Decimal("50000"),
        currency="INR",
        interest_rate_percent=Decimal("7"),
        interest_payout_frequency="QUARTERLY",
        investment_date=date(2023, 1, 1),
        maturity_date=date(2025, 1, 1),
        status="ACTIVE",
        is_active=True,
    )
    fd.save()
    response = api_client.get(f"/api/v1/fixed-deposits/{fd.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["portfolio_mismatch_warning"] is not None
    assert "differs from" in body["portfolio_mismatch_warning"]


@pytest.mark.django_db
def test_update_legacy_fd_rejects_portfolio_bank_mismatch(api_client, seeded, test_user):
    p1 = ensure_default_portfolio(test_user)
    p2 = Portfolio.objects.create(
        user=test_user, name="IndianInvestments", base_currency="INR", is_active=True
    )
    bank1 = _bank(test_user, portfolio=p1, account_number="B1")
    fd = FixedDeposit(
        user=test_user,
        portfolio=p1,
        bank_account=bank1,
        institution_name="HDFC",
        deposit_account_number="EDIT-1",
        principal_amount=Decimal("50000"),
        currency="INR",
        interest_rate_percent=Decimal("7"),
        interest_payout_frequency="QUARTERLY",
        investment_date=date(2023, 1, 1),
        maturity_date=date(2025, 1, 1),
        status="ACTIVE",
        is_active=True,
    )
    fd.save()
    response = api_client.put(
        f"/api/v1/fixed-deposits/{fd.id}",
        {"portfolio_id": p2.id},
        format="json",
    )
    assert response.status_code == 400
    assert response.json()["bank_account_portfolio_id"] == p1.id
    assert response.json()["requested_portfolio_id"] == p2.id


@pytest.mark.django_db
def test_relink_bank_derives_future_fd_portfolio(api_client, seeded, test_user):
    from debt.services import update_bank_account

    p1 = ensure_default_portfolio(test_user)
    p2 = Portfolio.objects.create(
        user=test_user, name="IndianInvestments", base_currency="INR", is_active=True
    )
    bank = _bank(test_user, portfolio=p1, account_number="RELINK-1")
    fund_bank_account(test_user, bank, "200000")

    update_bank_account(test_user, bank.id, portfolio_id=p2.id)

    response = api_client.post(
        "/api/v1/fixed-deposits",
        _fd_payload(p2.id, bank.id, deposit_account_number="FD-NEW-LINK"),
        format="json",
    )
    assert response.status_code == 201
    assert response.json()["portfolio_id"] == p2.id


@pytest.mark.django_db
def test_relink_does_not_rewrite_existing_fd(api_client, seeded, test_user):
    from debt.services import update_bank_account

    p1 = ensure_default_portfolio(test_user)
    p2 = Portfolio.objects.create(
        user=test_user, name="IndianInvestments", base_currency="INR", is_active=True
    )
    bank = _bank(test_user, portfolio=p1, account_number="RELINK-2")
    fund_bank_account(test_user, bank, "200000")
    fd = create_fixed_deposit(test_user, **_fd_payload(p1.id, bank.id, deposit_account_number="FD-OLD"))

    update_bank_account(test_user, bank.id, portfolio_id=p2.id)

    fd.refresh_from_db()
    assert fd.portfolio_id == p1.id
    assert fd.bank_account_id == bank.id
