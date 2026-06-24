from datetime import date
from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import call_command

from debt.bank_account_portfolio import (
    InferenceOutcome,
    find_bank_account_inference_reports,
)
from debt.models import BankAccount, FixedDeposit
from debt.services import create_bank_account, create_fixed_deposit
from portfolios.models import Portfolio
from portfolios.seed import ensure_default_portfolio
from tests.debt_test_helpers import create_legacy_fixed_deposit, fund_bank_account


def _create_bank(user, **overrides):
    payload = dict(
        name="Savings",
        institution_name="HDFC",
        account_number="ACC-1",
        currency="INR",
    )
    payload.update(overrides)
    return create_bank_account(user, **payload)


def _legacy_fd(user, portfolio, bank, **overrides):
    return create_legacy_fixed_deposit(user, portfolio=portfolio, bank=bank, **overrides)


@pytest.mark.django_db
def test_inference_unambiguous_from_fixed_deposit(seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _create_bank(test_user)
    _legacy_fd(test_user, portfolio, bank)

    report = find_bank_account_inference_reports(bank_account_id=bank.id)[0]
    assert report.outcome == InferenceOutcome.INFERRED
    assert report.inferred_portfolio_id == portfolio.id


@pytest.mark.django_db
def test_inference_ambiguous_multiple_portfolios(seeded, test_user):
    p1 = ensure_default_portfolio(test_user)
    p2 = Portfolio.objects.create(
        user=test_user, name="Second", base_currency="INR", is_active=True
    )
    bank = _create_bank(test_user)
    _legacy_fd(test_user, p1, bank)
    _legacy_fd(
        test_user,
        p2,
        bank,
        deposit_account_number="FD-2",
        investment_date=date(2024, 7, 1),
        maturity_date=date(2025, 7, 1),
    )

    report = find_bank_account_inference_reports(bank_account_id=bank.id)[0]
    assert report.outcome == InferenceOutcome.AMBIGUOUS
    assert report.inferred_portfolio_id is None


@pytest.mark.django_db
def test_inference_unassigned_no_signals(seeded, test_user):
    bank = _create_bank(test_user)
    report = find_bank_account_inference_reports(bank_account_id=bank.id)[0]
    assert report.outcome == InferenceOutcome.UNASSIGNED


@pytest.mark.django_db
def test_inference_unchanged_when_portfolio_already_set(seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = create_bank_account(
        test_user,
        name="Assigned",
        institution_name="SBI",
        account_number="X1",
        currency="INR",
        portfolio_id=portfolio.id,
    )
    report = find_bank_account_inference_reports(bank_account_id=bank.id)[0]
    assert report.outcome == InferenceOutcome.UNCHANGED


@pytest.mark.django_db
def test_command_dry_run_does_not_mutate(seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _create_bank(test_user)
    _legacy_fd(test_user, portfolio, bank)

    out = StringIO()
    call_command("infer_bank_account_portfolios", stdout=out)
    bank.refresh_from_db()
    assert bank.portfolio_id is None
    assert "Dry-run only" in out.getvalue()


@pytest.mark.django_db
def test_command_apply_assigns_unambiguous(seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _create_bank(test_user)
    _legacy_fd(test_user, portfolio, bank)

    call_command("infer_bank_account_portfolios", "--apply")
    bank.refresh_from_db()
    assert bank.portfolio_id == portfolio.id


@pytest.mark.django_db
def test_command_apply_skips_ambiguous(seeded, test_user):
    p1 = ensure_default_portfolio(test_user)
    p2 = Portfolio.objects.create(
        user=test_user, name="Second", base_currency="INR", is_active=True
    )
    bank = _create_bank(test_user)
    _legacy_fd(test_user, p1, bank)
    _legacy_fd(
        test_user,
        p2,
        bank,
        deposit_account_number="FD-2",
        investment_date=date(2024, 7, 1),
        maturity_date=date(2025, 7, 1),
    )

    call_command("infer_bank_account_portfolios", "--apply")
    bank.refresh_from_db()
    assert bank.portfolio_id is None


@pytest.mark.django_db
def test_command_bank_account_id_filter(seeded, test_user):
    bank_a = _create_bank(test_user, account_number="A")
    bank_b = _create_bank(test_user, name="Other", account_number="B")
    out = StringIO()
    call_command(
        "infer_bank_account_portfolios",
        f"--bank-account-id={bank_a.id}",
        stdout=out,
    )
    assert f"Bank account {bank_a.id}" in out.getvalue()
    assert f"Bank account {bank_b.id}" not in out.getvalue()
