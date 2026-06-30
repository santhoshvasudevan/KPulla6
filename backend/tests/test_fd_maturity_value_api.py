"""FD maturity value estimate and persistence API tests."""

from datetime import date
from decimal import Decimal

import pytest

from debt.models import FixedDeposit, MaturityValueSource
from debt.services import create_bank_account, create_fixed_deposit, update_fixed_deposit
from finance.fixed_deposits import ANNUAL_COMPOUND_ACTUAL_365, estimate_maturity_value
from portfolios.seed import ensure_default_portfolio
from tests.debt_test_helpers import create_test_bank_account, fund_bank_account


def _fd_payload(portfolio_id, bank_account_id, **overrides):
    payload = dict(
        bank_account_id=bank_account_id,
        institution_name="HDFC",
        deposit_account_number="FD-MAT-1",
        principal_amount=Decimal("100000"),
        currency="INR",
        interest_rate_percent=Decimal("7.0"),
        interest_payout_frequency="COMPOUNDED",
        investment_date=date(2024, 1, 1),
        maturity_date=date(2025, 1, 1),
    )
    payload.update(overrides)
    if portfolio_id is not None:
        payload["portfolio_id"] = portfolio_id
    return payload


@pytest.mark.django_db
def test_maturity_estimate_one_year_compounded():
    from types import SimpleNamespace

    fd = SimpleNamespace(
        principal_amount=Decimal("100000"),
        interest_rate_percent=Decimal("7"),
        interest_payout_frequency="COMPOUNDED",
        investment_date=date(2024, 1, 1),
        maturity_date=date(2025, 1, 1),
        status="ACTIVE",
        is_active=True,
    )
    result = estimate_maturity_value(fd)
    assert result.method == ANNUAL_COMPOUND_ACTUAL_365
    assert result.value is not None
    assert result.value > Decimal("100000")
    assert result.interest == result.value - Decimal("100000")


@pytest.mark.django_db
def test_maturity_estimate_non_whole_term_compounded():
    from types import SimpleNamespace

    fd = SimpleNamespace(
        principal_amount=Decimal("100000"),
        interest_rate_percent=Decimal("7"),
        interest_payout_frequency="COMPOUNDED",
        investment_date=date(2024, 1, 1),
        maturity_date=date(2026, 10, 1),
        status="ACTIVE",
        is_active=True,
    )
    result = estimate_maturity_value(fd)
    assert result.method == ANNUAL_COMPOUND_ACTUAL_365
    assert result.value is not None
    assert result.value > Decimal("100000")


@pytest.mark.django_db
def test_maturity_estimate_preview_api(api_client, seeded, test_user):
    response = api_client.get(
        "/api/v1/fixed-deposits/maturity-estimate",
        {
            "principal_amount": "100000",
            "interest_rate_percent": "7",
            "interest_payout_frequency": "COMPOUNDED",
            "investment_date": "2024-01-01",
            "maturity_date": "2025-01-01",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["estimated_maturity_value"] > 100000
    assert body["estimated_interest"] > 0
    assert body["maturity_estimate_method"] == ANNUAL_COMPOUND_ACTUAL_365
    assert "Actual/365" in body["maturity_estimate_method_label"]


@pytest.mark.django_db
def test_create_fd_auto_maturity_estimate(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = create_test_bank_account(test_user)
    fund_bank_account(test_user, bank, "200000")
    response = api_client.post(
        "/api/v1/fixed-deposits",
        _fd_payload(portfolio.id, bank.id, deposit_account_number="FD-AUTO-MAT"),
        format="json",
    )
    assert response.status_code == 201
    body = response.json()
    assert body["maturity_value_source"] == MaturityValueSource.AUTO_ESTIMATE
    assert body["estimated_maturity_value"] is not None
    assert body["expected_maturity_value"] == body["estimated_maturity_value"]
    assert body["expected_interest"] > 0


@pytest.mark.django_db
def test_create_fd_user_confirmed_maturity_value(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = create_test_bank_account(test_user, account_number="MAT-OVERRIDE")
    fund_bank_account(test_user, bank, "200000")
    response = api_client.post(
        "/api/v1/fixed-deposits",
        _fd_payload(
            portfolio.id,
            bank.id,
            deposit_account_number="FD-USER-MAT",
            expected_maturity_value=Decimal("112500"),
            maturity_value_note="Per bank statement",
        ),
        format="json",
    )
    assert response.status_code == 201
    body = response.json()
    assert body["maturity_value_source"] == MaturityValueSource.USER_CONFIRMED
    assert body["expected_maturity_value"] == 112500.0
    assert body["estimated_maturity_value"] is not None
    assert body["estimated_maturity_value"] != 112500.0
    assert body["maturity_value_note"] == "Per bank statement"


@pytest.mark.django_db
def test_update_fd_auto_recalculates_expected(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = create_test_bank_account(test_user, account_number="MAT-UPD-AUTO")
    fund_bank_account(test_user, bank, "200000")
    fd = create_fixed_deposit(
        test_user,
        **_fd_payload(portfolio.id, bank.id, deposit_account_number="FD-UPD-1"),
    )
    original_expected = fd.expected_maturity_value
    response = api_client.put(
        f"/api/v1/fixed-deposits/{fd.id}",
        {"interest_rate_percent": "8.5"},
        format="json",
    )
    assert response.status_code == 200
    body = response.json()
    assert body["maturity_value_source"] == MaturityValueSource.AUTO_ESTIMATE
    assert body["expected_maturity_value"] > float(original_expected)


@pytest.mark.django_db
def test_update_fd_user_confirmed_keeps_expected(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = create_test_bank_account(test_user, account_number="MAT-UPD-USER")
    fund_bank_account(test_user, bank, "200000")
    fd = create_fixed_deposit(
        test_user,
        **_fd_payload(
            portfolio.id,
            bank.id,
            deposit_account_number="FD-UPD-2",
            expected_maturity_value=Decimal("115000"),
        ),
    )
    response = api_client.put(
        f"/api/v1/fixed-deposits/{fd.id}",
        {"interest_rate_percent": "9.0"},
        format="json",
    )
    assert response.status_code == 200
    body = response.json()
    assert body["maturity_value_source"] == MaturityValueSource.USER_CONFIRMED
    assert body["expected_maturity_value"] == 115000.0
    assert body["estimated_maturity_value"] != 115000.0


@pytest.mark.django_db
def test_update_fd_clear_override_returns_to_auto(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = create_test_bank_account(test_user, account_number="MAT-CLR")
    fund_bank_account(test_user, bank, "200000")
    fd = create_fixed_deposit(
        test_user,
        **_fd_payload(
            portfolio.id,
            bank.id,
            deposit_account_number="FD-CLR-1",
            expected_maturity_value=Decimal("115000"),
        ),
    )
    response = api_client.put(
        f"/api/v1/fixed-deposits/{fd.id}",
        {"use_auto_maturity_estimate": True},
        format="json",
    )
    assert response.status_code == 200
    body = response.json()
    assert body["maturity_value_source"] == MaturityValueSource.AUTO_ESTIMATE
    assert body["expected_maturity_value"] == body["estimated_maturity_value"]
