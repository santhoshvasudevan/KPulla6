from datetime import date
from decimal import Decimal

import pytest

from debt.interest_payment_services import create_fixed_deposit_interest_payment
from debt.models import CashMovement, FixedDepositStatus
from debt.services import create_fixed_deposit
from portfolios.seed import ensure_default_portfolio
from tests.debt_test_helpers import create_test_bank_account, fund_bank_account


def _fd_payload(portfolio_id, bank_account_id, **overrides):
    payload = dict(
        portfolio_id=portfolio_id,
        bank_account_id=bank_account_id,
        institution_name="HDFC",
        deposit_account_number="FD-DETAIL",
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
    fund_bank_account(user, bank, "300000")
    return create_fixed_deposit(user, **_fd_payload(portfolio_id, bank.id, **overrides))


@pytest.mark.django_db
def test_fd_detail_endpoint_returns_schedule_and_summary(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = create_test_bank_account(test_user, portfolio=portfolio)
    fd = _create_fd(test_user, portfolio.id, bank)

    response = api_client.get(f"/api/v1/fixed-deposits/{fd.id}/detail")
    assert response.status_code == 200
    body = response.json()
    assert body["fixed_deposit"]["id"] == fd.id
    assert len(body["expected_interest_schedule"]) == 8
    assert body["term_totals"]["expected_gross_interest"] > 0
    assert body["detailed_calculation"]["day_count_method"] == "Actual/365"
    assert body["financial_year_options"]


@pytest.mark.django_db
def test_compounded_fd_detail_has_maturity_row_only(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = create_test_bank_account(test_user, portfolio=portfolio)
    fd = _create_fd(
        test_user,
        portfolio.id,
        bank,
        interest_payout_frequency="COMPOUNDED",
    )

    response = api_client.get(f"/api/v1/fixed-deposits/{fd.id}/detail")
    body = response.json()
    assert len(body["expected_interest_schedule"]) == 1
    assert body["expected_interest_schedule"][0]["schedule_row_type"] == "MATURITY_ACCRUAL"


@pytest.mark.django_db
def test_fd_detail_financial_year_filter(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = create_test_bank_account(test_user, portfolio=portfolio)
    fd = _create_fd(test_user, portfolio.id, bank)
    create_fixed_deposit_interest_payment(
        test_user,
        fd.id,
        payment_date=date(2024, 4, 5),
        gross_interest=Decimal("1750"),
        tax_withheld=Decimal("175"),
    )

    response = api_client.get(
        f"/api/v1/fixed-deposits/{fd.id}/detail?financial_year=2024-25"
    )
    assert response.status_code == 200
    fy = response.json()["financial_year_summary"]
    assert fy["financial_year"] == "2024-25"
    assert fy["actual_gross_interest_fy"] == 1750.0
    assert fy["tax_withheld_fy"] == 175.0
    assert fy["actual_net_interest_fy"] == 1575.0


@pytest.mark.django_db
def test_fd_detail_matches_actual_payment_to_schedule_row(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = create_test_bank_account(test_user, portfolio=portfolio)
    fd = _create_fd(test_user, portfolio.id, bank)
    payment = create_fixed_deposit_interest_payment(
        test_user,
        fd.id,
        payment_date=date(2024, 4, 1),
        gross_interest=Decimal("1750"),
        tax_withheld=Decimal("0"),
    ).payment

    response = api_client.get(f"/api/v1/fixed-deposits/{fd.id}/detail")
    first_row = response.json()["expected_interest_schedule"][0]
    assert first_row["status"] == "RECORDED"
    assert first_row["matched_payment_id"] == payment.id


@pytest.mark.django_db
def test_update_interest_payment_adjusts_cash_movement(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = create_test_bank_account(test_user, portfolio=portfolio)
    fd = _create_fd(test_user, portfolio.id, bank)
    payment = create_fixed_deposit_interest_payment(
        test_user,
        fd.id,
        payment_date=date(2024, 4, 1),
        gross_interest=Decimal("1000"),
        tax_withheld=Decimal("100"),
    ).payment
    movement_id = payment.cash_movement_id
    bank.refresh_from_db()
    balance_before = bank.current_balance

    response = api_client.patch(
        f"/api/v1/fixed-deposit-interest-payments/{payment.id}",
        {
            "gross_interest": "1200",
            "tax_withheld": "120",
            "payment_date": "2024-04-02",
        },
        format="json",
    )
    assert response.status_code == 200
    body = response.json()
    assert body["gross_interest"] == 1200.0
    assert body["tax_withheld"] == 120.0
    assert body["net_interest"] == 1080.0

    movement = CashMovement.objects.get(id=movement_id)
    assert movement.amount == Decimal("1080")
    assert movement.movement_date == date(2024, 4, 2)
    bank.refresh_from_db()
    assert bank.current_balance == balance_before + Decimal("180")


@pytest.mark.django_db
def test_interest_payment_tax_cannot_exceed_gross(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = create_test_bank_account(test_user, portfolio=portfolio)
    fd = _create_fd(test_user, portfolio.id, bank)
    payment = create_fixed_deposit_interest_payment(
        test_user,
        fd.id,
        payment_date=date(2024, 4, 1),
        gross_interest=Decimal("1000"),
        tax_withheld=Decimal("0"),
    ).payment

    response = api_client.patch(
        f"/api/v1/fixed-deposit-interest-payments/{payment.id}",
        {"tax_withheld": "1001"},
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_fd_detail_user_scoping(api_client, seeded, test_user, django_user_model):
    portfolio = ensure_default_portfolio(test_user)
    bank = create_test_bank_account(test_user, portfolio=portfolio)
    fd = _create_fd(test_user, portfolio.id, bank)
    other = django_user_model.objects.create_user(
        username="otherfd", email="otherfd@example.com", password="pass"
    )
    api_client.force_authenticate(user=other)
    response = api_client.get(f"/api/v1/fixed-deposits/{fd.id}/detail")
    assert response.status_code == 404


@pytest.mark.django_db
def test_interest_payment_delete_still_blocked(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = create_test_bank_account(test_user, portfolio=portfolio)
    fd = _create_fd(test_user, portfolio.id, bank)
    payment = create_fixed_deposit_interest_payment(
        test_user,
        fd.id,
        payment_date=date(2024, 4, 1),
        gross_interest=Decimal("1000"),
        tax_withheld=Decimal("0"),
    ).payment

    response = api_client.delete(
        f"/api/v1/fixed-deposit-interest-payments/{payment.id}"
    )
    assert response.status_code == 405
