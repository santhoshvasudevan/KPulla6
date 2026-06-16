"""FD-ACC-8B: FD principal and included bank cash in portfolio value history."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from debt.bank_ledger_services import create_manual_cash_movement
from debt.models import FixedDeposit, FixedDepositStatus
from debt.services import create_bank_account, create_fixed_deposit, update_bank_account
from portfolios.models import Portfolio
from portfolios.seed import ensure_default_portfolio
from tests.debt_test_helpers import fund_bank_account


def _bank(user, **overrides):
    payload = dict(
        name="Savings",
        institution_name="HDFC",
        account_number="111",
        currency="INR",
    )
    payload.update(overrides)
    return create_bank_account(user, **payload)


def _create_fd(user, portfolio_id, bank_id, principal="100000", status="ACTIVE", **kw):
    from debt.models import BankAccount

    bank = BankAccount.objects.get(pk=bank_id)
    fund_bank_account(user, bank, Decimal(principal) + Decimal("50000"))
    return create_fixed_deposit(
        user,
        portfolio_id=portfolio_id,
        bank_account_id=bank.id,
        institution_name="HDFC",
        deposit_account_number=kw.get("deposit_account_number", "FD-1"),
        principal_amount=Decimal(principal),
        currency="INR",
        interest_rate_percent=Decimal("7"),
        interest_payout_frequency="QUARTERLY",
        investment_date=kw.get("investment_date", date(2024, 1, 1)),
        maturity_date=kw.get("maturity_date", date(2026, 1, 1)),
        status=status,
    )


def _enable_bank_inclusion(user, bank):
    return update_bank_account(user, bank.id, include_in_portfolio_value=True)


def _perf_map(api_client, **query):
    params = "metric=value&range=ALL&display_currency=INR"
    for key, val in query.items():
        params += f"&{key}={val}"
    payload = api_client.get(f"/api/v1/portfolio/performance?{params}").json()
    points = payload["points"] if isinstance(payload, dict) else payload
    return {p["date"]: p["value"] for p in points}


def _summary_value(api_client, **query):
    params = "include_timeseries=false&display_currency=INR"
    for key, val in query.items():
        params += f"&{key}={val}"
    return api_client.get(f"/api/v1/portfolio/summary?{params}").json()["current_value"]


@pytest.mark.django_db
def test_fd_principal_appears_from_investment_date(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    _create_fd(test_user, portfolio.id, bank.id, investment_date=date(2024, 6, 15))
    values = _perf_map(api_client)
    assert values.get("2024-06-14") in (None, 0.0) or "2024-06-14" not in values
    assert values.get("2024-06-15") == pytest.approx(100000.0, rel=1e-6)


@pytest.mark.django_db
def test_fd_principal_absent_before_investment_date(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    _create_fd(test_user, portfolio.id, bank.id, investment_date=date(2025, 1, 10))
    values = _perf_map(api_client)
    for day, val in values.items():
        if day < "2025-01-10":
            assert val in (None, 0.0)


@pytest.mark.django_db
def test_active_and_matured_fd_contribute(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank.id)
    api_client.post(f"/api/v1/fixed-deposits/{fd.id}/mark-matured", {}, format="json")
    values = _perf_map(api_client)
    assert max(values.values()) == pytest.approx(100000.0, rel=1e-6)


@pytest.mark.django_db
def test_settled_fd_excluded_after_settlement_date(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank.id)
    api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/settle",
        {
            "settlement_type": "CLOSURE",
            "settlement_date": "2025-06-01",
            "gross_interest": 0,
            "tax_withheld": 0,
        },
        format="json",
    )
    values = _perf_map(api_client)
    assert values.get("2025-05-31") == pytest.approx(100000.0, rel=1e-6)
    assert values.get("2025-06-01") in (None, 0.0)


@pytest.mark.django_db
def test_renewal_does_not_double_count_on_renewal_date(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank.id)
    api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/renew",
        {
            "renewal_date": "2026-01-01",
            "new_deposit_account_number": "FD-002",
            "new_principal_amount": 120000,
            "new_interest_rate_percent": 7.5,
            "new_interest_payout_frequency": "QUARTERLY",
            "new_investment_date": "2026-01-01",
            "new_maturity_date": "2028-01-01",
        },
        format="json",
    )
    values = _perf_map(api_client)
    assert values.get("2025-12-31") == pytest.approx(100000.0, rel=1e-6)
    assert values.get("2026-01-01") == pytest.approx(120000.0, rel=1e-6)


@pytest.mark.django_db
def test_interest_payment_does_not_change_fd_principal_value(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank.id)
    before = _perf_map(api_client)
    api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/interest-payments",
        {
            "payment_date": "2025-03-01",
            "gross_interest": 5000,
            "tax_withheld": 500,
        },
        format="json",
    )
    after = _perf_map(api_client)
    assert after == before


@pytest.mark.django_db
def test_included_bank_cash_in_value_history(api_client, seeded, test_user):
    bank = _bank(test_user)
    fund_bank_account(test_user, bank, "55000")
    _enable_bank_inclusion(test_user, bank)
    values = _perf_map(api_client)
    assert max(values.values()) == pytest.approx(55000.0, rel=1e-6)


@pytest.mark.django_db
def test_bank_cash_excluded_by_default(api_client, seeded, test_user):
    bank = _bank(test_user)
    fund_bank_account(test_user, bank, "44000")
    values = _perf_map(api_client)
    assert not values or max(values.values()) in (None, 0.0)


@pytest.mark.django_db
def test_unseeded_manual_balance_not_in_value_history(api_client, seeded, test_user):
    bank = create_bank_account(
        test_user,
        name="Manual",
        institution_name="HDFC",
        account_number="manual",
        currency="INR",
        current_balance=Decimal("99000"),
    )
    _enable_bank_inclusion(test_user, bank)
    values = _perf_map(api_client)
    assert not values or max(values.values()) in (None, 0.0)


@pytest.mark.django_db
def test_fd_create_with_included_bank_cash_keeps_value_stable(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fund_bank_account(test_user, bank, "200000")
    _enable_bank_inclusion(test_user, bank)
    before = max(_perf_map(api_client).values())
    create_fixed_deposit(
        test_user,
        portfolio_id=portfolio.id,
        bank_account_id=bank.id,
        institution_name="HDFC",
        deposit_account_number="FD-STABLE",
        principal_amount=Decimal("100000"),
        currency="INR",
        interest_rate_percent=Decimal("7"),
        interest_payout_frequency="QUARTERLY",
        investment_date=date(2024, 1, 1),
        maturity_date=date(2026, 1, 1),
    )
    perf_after = max(_perf_map(api_client).values())
    assert perf_after == pytest.approx(before, rel=0.001)


@pytest.mark.django_db
def test_fd_settlement_with_included_bank_cash_keeps_value_stable(
    api_client, seeded, test_user
):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fund_bank_account(test_user, bank, "150000")
    fd = create_fixed_deposit(
        test_user,
        portfolio_id=portfolio.id,
        bank_account_id=bank.id,
        institution_name="HDFC",
        deposit_account_number="FD-SETTLE",
        principal_amount=Decimal("100000"),
        currency="INR",
        interest_rate_percent=Decimal("7"),
        interest_payout_frequency="QUARTERLY",
        investment_date=date(2024, 1, 1),
        maturity_date=date(2026, 1, 1),
    )
    _enable_bank_inclusion(test_user, bank)
    before = max(_perf_map(api_client).values())
    api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/settle",
        {
            "settlement_type": "MATURITY",
            "settlement_date": "2026-01-01",
            "gross_interest": 5000,
            "tax_withheld": 500,
        },
        format="json",
    )
    perf_after = max(_perf_map(api_client).values())
    assert perf_after == pytest.approx(before + 4500, rel=0.01)


@pytest.mark.django_db
def test_interest_payment_with_included_bank_cash_increases_value(
    api_client, seeded, test_user
):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fund_bank_account(test_user, bank, "200000")
    fd = create_fixed_deposit(
        test_user,
        portfolio_id=portfolio.id,
        bank_account_id=bank.id,
        institution_name="HDFC",
        deposit_account_number="FD-INT",
        principal_amount=Decimal("100000"),
        currency="INR",
        interest_rate_percent=Decimal("7"),
        interest_payout_frequency="QUARTERLY",
        investment_date=date(2024, 1, 1),
        maturity_date=date(2026, 1, 1),
    )
    _enable_bank_inclusion(test_user, bank)
    before = max(_perf_map(api_client).values())
    api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/interest-payments",
        {
            "payment_date": "2025-06-01",
            "gross_interest": 5000,
            "tax_withheld": 500,
        },
        format="json",
    )
    after_perf = max(_perf_map(api_client).values())
    assert after_perf == pytest.approx(before + 4500, rel=0.01)


@pytest.mark.django_db
def test_backdated_bank_movement_affects_historical_value(api_client, seeded, test_user):
    bank = _bank(test_user)
    fund_bank_account(test_user, bank, "10000", movement_date=date(2024, 3, 1))
    _enable_bank_inclusion(test_user, bank)
    create_manual_cash_movement(
        test_user,
        bank_account_id=bank.id,
        movement_type="MANUAL_DEPOSIT",
        amount=Decimal("5000"),
        movement_date=date(2024, 5, 1),
    )
    values = _perf_map(api_client)
    assert values.get("2024-04-30") == pytest.approx(10000.0, rel=1e-6)
    assert values.get("2024-05-01") == pytest.approx(15000.0, rel=1e-6)


@pytest.mark.django_db
def test_all_scope_includes_bank_account_once(api_client, seeded, test_user):
    bank = _bank(test_user)
    fund_bank_account(test_user, bank, "33000")
    _enable_bank_inclusion(test_user, bank)
    summary = _summary_value(api_client, portfolio_scope="all")
    perf = max(_perf_map(api_client, portfolio_scope="all").values())
    assert summary == pytest.approx(33000.0, rel=1e-6)
    assert perf == pytest.approx(33000.0, rel=1e-6)


@pytest.mark.django_db
def test_single_portfolio_scope_conservative_bank_attribution(
    api_client, seeded, test_user
):
    p1 = ensure_default_portfolio(test_user)
    p2 = Portfolio.objects.create(
        user=test_user, name="Second", base_currency="INR", is_active=True
    )
    bank = _bank(test_user)
    fund_bank_account(test_user, bank, "80000")
    create_fixed_deposit(
        test_user,
        portfolio_id=p1.id,
        bank_account_id=bank.id,
        institution_name="HDFC",
        deposit_account_number="A",
        principal_amount=Decimal("10000"),
        currency="INR",
        interest_rate_percent=Decimal("7"),
        interest_payout_frequency="QUARTERLY",
        investment_date=date(2024, 1, 1),
        maturity_date=date(2026, 1, 1),
    )
    create_fixed_deposit(
        test_user,
        portfolio_id=p2.id,
        bank_account_id=bank.id,
        institution_name="HDFC",
        deposit_account_number="B",
        principal_amount=Decimal("20000"),
        currency="INR",
        interest_rate_percent=Decimal("7"),
        interest_payout_frequency="QUARTERLY",
        investment_date=date(2024, 1, 1),
        maturity_date=date(2026, 1, 1),
    )
    _enable_bank_inclusion(test_user, bank)
    p1_perf = max(_perf_map(api_client, portfolio_id=p1.id).values())
    all_perf = max(_perf_map(api_client, portfolio_scope="all").values())
    assert p1_perf == pytest.approx(10000.0, rel=1e-6)
    assert all_perf == pytest.approx(80000.0, rel=0.01)


@pytest.mark.django_db
def test_other_user_fd_and_bank_cash_excluded(
    api_client, seeded, test_user, django_user_model
):
    other = django_user_model.objects.create_user(
        username="other-fd-perf", email="otherfd@example.com", password="pass"
    )
    other_portfolio = Portfolio.objects.create(
        user=other, name="Other", base_currency="INR", is_active=True
    )
    other_bank = _bank(other, account_number="OTHER")
    fund_bank_account(other, other_bank, "99999")
    _enable_bank_inclusion(other, other_bank)
    _create_fd(other, other_portfolio.id, other_bank.id, principal="50000")

    values = _perf_map(api_client)
    assert not values or max(values.values()) in (None, 0.0)


@pytest.mark.django_db
def test_performance_terminal_value_aligns_with_summary(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    _create_fd(test_user, portfolio.id, bank.id, principal="100000")
    summary = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false&display_currency=INR"
    ).json()
    perf = max(_perf_map(api_client).values())
    assert perf == pytest.approx(summary["current_value"], rel=1e-6)
