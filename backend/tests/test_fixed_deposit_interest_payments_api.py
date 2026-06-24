from datetime import date
from decimal import Decimal

import pytest

from debt.interest_payment_services import create_fixed_deposit_interest_payment
from debt.models import (
    CashMovement,
    CashMovementDirection,
    CashMovementSource,
    CashMovementType,
    FixedDepositInterestPayment,
    FixedDepositStatus,
)
from debt.services import create_bank_account, create_fixed_deposit
from portfolios.models import Portfolio
from portfolios.seed import ensure_default_portfolio
from tests.debt_test_helpers import create_test_bank_account, fund_bank_account


def _bank(user, portfolio=None, **overrides):
    return create_test_bank_account(user, portfolio=portfolio, **overrides)



def _fd_payload(portfolio_id, bank_account_id, **overrides):
    payload = dict(
        portfolio_id=portfolio_id,
        bank_account_id=bank_account_id,
        institution_name="HDFC",
        deposit_account_number="FD-001",
        principal_amount=Decimal("100000"),
        currency="INR",
        interest_rate_percent=Decimal("7.0"),
        interest_payout_frequency="QUARTERLY",
        investment_date=date(2024, 1, 1),
        maturity_date=date(2026, 1, 1),
    )
    payload.update(overrides)
    return payload


def _create_fd(user, portfolio_id, bank, **overrides):
    fund_bank_account(user, bank, "200000")
    return create_fixed_deposit(user, **_fd_payload(portfolio_id, bank.id, **overrides))


def _interest_payload(**overrides):
    payload = dict(
        payment_date=date(2024, 4, 1),
        gross_interest=Decimal("1000"),
        tax_withheld=Decimal("100"),
    )
    payload.update(overrides)
    return payload


@pytest.mark.django_db
def test_create_interest_payment_creates_fd_interest_credit(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)
    bank.refresh_from_db()
    balance_before = bank.current_balance

    response = api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/interest-payments",
        _interest_payload(),
        format="json",
    )
    assert response.status_code == 201
    body = response.json()
    assert body["fixed_deposit_id"] == fd.id
    assert body["bank_account_id"] == bank.id
    assert body["bank_account_name"] == bank.name
    assert body["gross_interest"] == 1000.0
    assert body["tax_withheld"] == 100.0
    assert body["net_interest"] == 900.0
    assert body["currency"] == "INR"
    assert body["cash_movement_id"] is not None

    movement = CashMovement.objects.get(id=body["cash_movement_id"])
    assert movement.movement_type == CashMovementType.FD_INTEREST
    assert movement.direction == CashMovementDirection.CREDIT
    assert movement.amount == Decimal("900")
    assert movement.source == CashMovementSource.SYSTEM
    assert movement.linked_fixed_deposit_id == fd.id
    assert movement.portfolio_id == portfolio.id
    assert movement.bank_account_id == bank.id

    bank.refresh_from_db()
    assert bank.current_balance == balance_before + Decimal("900")


@pytest.mark.django_db
def test_interest_payment_stores_gross_tax_net(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)

    response = api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/interest-payments",
        _interest_payload(gross_interest=Decimal("2500"), tax_withheld=Decimal("250")),
        format="json",
    )
    assert response.status_code == 201
    payment = FixedDepositInterestPayment.objects.get(id=response.json()["id"])
    assert payment.gross_interest == Decimal("2500")
    assert payment.tax_withheld == Decimal("250")
    assert payment.net_interest == Decimal("2250")


@pytest.mark.django_db
def test_reject_tax_withheld_exceeds_gross(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)

    response = api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/interest-payments",
        _interest_payload(gross_interest=Decimal("1000"), tax_withheld=Decimal("1001")),
        format="json",
    )
    assert response.status_code == 400
    assert FixedDepositInterestPayment.objects.count() == 0
    assert CashMovement.objects.filter(movement_type=CashMovementType.FD_INTEREST).count() == 0


@pytest.mark.django_db
def test_reject_zero_gross_interest(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)

    response = api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/interest-payments",
        _interest_payload(gross_interest=Decimal("0")),
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_reject_negative_gross_interest(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)

    response = api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/interest-payments",
        _interest_payload(gross_interest=Decimal("-10")),
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_reject_foreign_fd(api_client, seeded, test_user, other_user):
    other_portfolio = Portfolio.objects.create(
        user=other_user, name="Other", base_currency="INR", is_active=True
    )
    other_bank = _bank(other_user, portfolio=other_portfolio, account_number="OTHER")
    other_fd = _create_fd(other_user, other_portfolio.id, other_bank)

    response = api_client.post(
        f"/api/v1/fixed-deposits/{other_fd.id}/interest-payments",
        _interest_payload(),
        format="json",
    )
    assert response.status_code == 404
    assert FixedDepositInterestPayment.objects.count() == 0


@pytest.mark.django_db
def test_reject_closed_fd_interest_payment(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank, status=FixedDepositStatus.CLOSED)

    response = api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/interest-payments",
        _interest_payload(),
        format="json",
    )
    assert response.status_code == 400
    assert "closed" in response.json()["detail"].lower()
    assert FixedDepositInterestPayment.objects.count() == 0
    assert CashMovement.objects.filter(movement_type=CashMovementType.FD_INTEREST).count() == 0


@pytest.mark.django_db
def test_compounded_fd_returns_warning_but_succeeds(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(
        test_user,
        portfolio.id,
        bank,
        interest_payout_frequency="COMPOUNDED",
    )

    response = api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/interest-payments",
        _interest_payload(),
        format="json",
    )
    assert response.status_code == 201
    body = response.json()
    assert "warning" in body
    assert "compounded" in body["warning"].lower()


@pytest.mark.django_db
def test_matured_fd_allows_interest_payment(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank, status=FixedDepositStatus.MATURED)

    response = api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/interest-payments",
        _interest_payload(),
        format="json",
    )
    assert response.status_code == 201


@pytest.mark.django_db
def test_list_interest_payments_for_fd(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)
    create_fixed_deposit_interest_payment(
        test_user,
        fd.id,
        payment_date=date(2024, 4, 1),
        gross_interest=Decimal("1000"),
        tax_withheld=Decimal("100"),
    )
    create_fixed_deposit_interest_payment(
        test_user,
        fd.id,
        payment_date=date(2024, 7, 1),
        gross_interest=Decimal("1200"),
        tax_withheld=Decimal("0"),
    )

    response = api_client.get(f"/api/v1/fixed-deposits/{fd.id}/interest-payments")
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 2
    assert items[0]["payment_date"] == "2024-07-01"


@pytest.mark.django_db
def test_list_returns_only_current_user_payments(api_client, seeded, test_user, other_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)
    create_fixed_deposit_interest_payment(
        test_user,
        fd.id,
        payment_date=date(2024, 4, 1),
        gross_interest=Decimal("1000"),
        tax_withheld=Decimal("0"),
    )

    other_portfolio = Portfolio.objects.create(
        user=other_user, name="Other", base_currency="INR", is_active=True
    )
    other_bank = _bank(other_user, portfolio=other_portfolio, account_number="OTHER")
    other_fd = _create_fd(other_user, other_portfolio.id, other_bank)
    other_payment = create_fixed_deposit_interest_payment(
        other_user,
        other_fd.id,
        payment_date=date(2024, 4, 1),
        gross_interest=Decimal("500"),
        tax_withheld=Decimal("0"),
    ).payment

    detail = api_client.get(
        f"/api/v1/fixed-deposit-interest-payments/{other_payment.id}"
    )
    assert detail.status_code == 404

    own = api_client.get(f"/api/v1/fixed-deposits/{fd.id}/interest-payments")
    assert own.status_code == 200
    assert len(own.json()) == 1


@pytest.mark.django_db
def test_interest_payment_detail_get(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)
    payment = create_fixed_deposit_interest_payment(
        test_user,
        fd.id,
        payment_date=date(2024, 4, 1),
        gross_interest=Decimal("1000"),
        tax_withheld=Decimal("50"),
    ).payment

    response = api_client.get(
        f"/api/v1/fixed-deposit-interest-payments/{payment.id}"
    )
    assert response.status_code == 200
    assert response.json()["net_interest"] == 950.0


@pytest.mark.django_db
def test_interest_payment_immutable_endpoints(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)
    payment = create_fixed_deposit_interest_payment(
        test_user,
        fd.id,
        payment_date=date(2024, 4, 1),
        gross_interest=Decimal("1000"),
        tax_withheld=Decimal("0"),
    ).payment

    for method, path in [
        ("put", f"/api/v1/fixed-deposit-interest-payments/{payment.id}"),
        ("patch", f"/api/v1/fixed-deposit-interest-payments/{payment.id}"),
        ("delete", f"/api/v1/fixed-deposit-interest-payments/{payment.id}"),
    ]:
        response = getattr(api_client, method)(path, {}, format="json")
        assert response.status_code == 405


@pytest.mark.django_db
def test_interest_payment_does_not_change_portfolio_summary(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)

    summary_before = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false&display_currency=INR"
    ).json()
    assert summary_before["current_value"] == 100000.0

    response = api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/interest-payments",
        _interest_payload(gross_interest=Decimal("5000"), tax_withheld=Decimal("500")),
        format="json",
    )
    assert response.status_code == 201

    summary_after = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false&display_currency=INR"
    ).json()
    assert summary_after["current_value"] == summary_before["current_value"]
    assert summary_after["total_invested"] == summary_before["total_invested"]


@pytest.mark.django_db
def test_backend_uses_fd_bank_account_only(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)

    response = api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/interest-payments",
        {
            **_interest_payload(),
            "bank_account_id": 99999,
        },
        format="json",
    )
    assert response.status_code == 201
    assert response.json()["bank_account_id"] == bank.id
