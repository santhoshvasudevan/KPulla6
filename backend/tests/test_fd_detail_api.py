from datetime import date
from decimal import Decimal

import pytest

from debt.interest_payment_services import create_fixed_deposit_interest_payment
from debt.models import CashMovement, CashMovementType, FixedDepositStatus
from debt.services import create_fixed_deposit
from fx.services import upsert_fx_rate
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
    other_payment = create_fixed_deposit_interest_payment(
        test_user,
        fd.id,
        payment_date=payment.payment_date,
        gross_interest=Decimal("250"),
    ).payment
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
    other_payment.refresh_from_db()
    assert other_payment.payment_date == date(2024, 4, 1)
    assert other_payment.net_interest == Decimal("250")
    other_payment.cash_movement.refresh_from_db()
    assert other_payment.cash_movement.amount == Decimal("250")
    assert other_payment.cash_movement.movement_date == date(2024, 4, 1)


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


@pytest.mark.django_db
def test_partial_rollover_detail_includes_maturity_interest_once(api_client, seeded, test_user):
    """#43 review: predecessor detail must show renewal interest paid + reinvested."""
    portfolio = ensure_default_portfolio(test_user)
    bank = create_test_bank_account(test_user, portfolio=portfolio)
    fd = _create_fd(test_user, portfolio.id, bank, principal_amount=Decimal("100000"))
    bank.refresh_from_db()
    balance_before = bank.current_balance

    renew = api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/renew",
        {
            "renewal_date": "2026-01-01",
            "new_deposit_account_number": "FD-DETAIL-NEW",
            "new_principal_amount": "102000",
            "new_interest_rate_percent": "7.5",
            "new_interest_payout_frequency": "QUARTERLY",
            "new_investment_date": "2026-01-01",
            "new_maturity_date": "2028-01-01",
            "gross_interest": "5000",
            "tax_withheld": "500",
            "cash_payout_amount": "2500",
        },
        format="json",
    )
    assert renew.status_code == 201
    renew_body = renew.json()
    new_id = renew_body["new_fixed_deposit"]["id"]
    assert renew_body["net_interest"] == 4500.0
    assert renew_body["interest_cash_amount"] == 2500.0
    assert renew_body["reinvested_interest_amount"] == 2000.0
    assert len(renew_body["cash_movement_ids"]) == 1

    bank.refresh_from_db()
    assert bank.current_balance == balance_before + Decimal("2500")
    assert (
        CashMovement.objects.filter(
            linked_fixed_deposit_id=fd.id,
            movement_type=CashMovementType.FD_MATURITY_INTEREST,
            amount=Decimal("2500"),
        ).count()
        == 1
    )

    predecessor = api_client.get(f"/api/v1/fixed-deposits/{fd.id}/detail").json()
    totals = predecessor["term_totals"]
    assert totals["actual_gross_interest"] == 5000.0
    assert totals["tax_withheld"] == 500.0
    assert totals["actual_net_interest"] == 4500.0
    assert totals["interest_cash_amount"] == 2500.0
    assert totals["reinvested_interest_amount"] == 2000.0

    fy = api_client.get(
        f"/api/v1/fixed-deposits/{fd.id}/detail?financial_year=2025-26"
    ).json()["financial_year_summary"]
    assert fy["actual_gross_interest_fy"] == 5000.0
    assert fy["tax_withheld_fy"] == 500.0
    assert fy["actual_net_interest_fy"] == 4500.0
    assert fy["interest_cash_amount_fy"] == 2500.0
    assert fy["reinvested_interest_amount_fy"] == 2000.0

    report = api_client.get("/api/v1/reports/fixed-deposit-interest").json()
    renewal_rows = [r for r in report["rows"] if r["source_type"] == "RENEWAL"]
    assert len(renewal_rows) == 1
    assert renewal_rows[0]["fixed_deposit_id"] == fd.id
    assert renewal_rows[0]["net_interest"] == 4500.0
    assert renewal_rows[0]["interest_cash_amount"] == 2500.0
    assert renewal_rows[0]["reinvested_interest_amount"] == 2000.0
    assert not any(r["fixed_deposit_id"] == new_id for r in report["rows"])

    upsert_fx_rate(
        from_currency="INR", to_currency="EUR", row_date=date(2026, 1, 1), rate=Decimal("0.01")
    )
    converted = api_client.get("/api/v1/reports/fixed-deposit-interest?display_currency=EUR")
    assert converted.status_code == 200
    converted_report = converted.json()
    assert len(converted_report["rows"]) == 1
    converted_row = converted_report["rows"][0]
    assert converted_report["totals"]["net_interest"] == 45.0
    assert converted_row["display_currency"] == "EUR"
    assert converted_row["currency"] == "INR"
    assert converted_row["interest_cash_amount"] == 2500.0
    assert converted_row["reinvested_interest_amount"] == 2000.0

    successor = api_client.get(f"/api/v1/fixed-deposits/{new_id}/detail").json()
    assert successor["term_totals"]["actual_gross_interest"] == 0.0
    assert successor["term_totals"]["actual_net_interest"] == 0.0
    assert successor["term_totals"]["interest_cash_amount"] in (0.0, None)
    assert successor["term_totals"]["reinvested_interest_amount"] in (0.0, None)
