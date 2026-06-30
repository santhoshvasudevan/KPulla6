"""FD-PERF-2: portfolio-attributed FD payout income for performance metrics."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from debt.fd_attributed_income import (
    build_fd_attributed_income_by_date,
    build_fd_attributed_xirr_flows,
    list_fd_attributed_income_events,
)
from debt.interest_payment_services import create_fixed_deposit_interest_payment
from debt.models import FixedDeposit
from debt.reversal_services import reverse_fixed_deposit_interest_payment
from debt.services import create_bank_account, create_fixed_deposit, update_bank_account
from portfolios.models import Portfolio
from portfolios.scope import ResolvedPortfolioScope
from portfolios.seed import ensure_default_portfolio
from portfolios.xirr_service import compute_scope_xirr_detail
from tests.debt_test_helpers import create_test_bank_account, fund_bank_account


def _bank(user, portfolio=None, **overrides):
    return create_test_bank_account(user, portfolio=portfolio, **overrides)


def _enable(user, bank):
    return update_bank_account(user, bank.id, include_in_portfolio_value=True)


def _scope(portfolio_id):
    return ResolvedPortfolioScope(kind="single", portfolio_ids=[portfolio_id])


def _create_fd(user, portfolio_id, bank, **kw):
    fund_bank_account(user, bank, Decimal("200000"))
    return create_fixed_deposit(
        user,
        portfolio_id=portfolio_id,
        bank_account_id=bank.id,
        institution_name="HDFC",
        deposit_account_number=kw.get("deposit_account_number", "FD-ATTR"),
        principal_amount=Decimal(kw.get("principal", "100000")),
        currency="INR",
        interest_rate_percent=Decimal("7"),
        interest_payout_frequency=kw.get("interest_payout_frequency", "QUARTERLY"),
        investment_date=kw.get("investment_date", date(2024, 1, 1)),
        maturity_date=kw.get("maturity_date", date(2026, 1, 1)),
    )


def _perf_map(api_client, metric, **query):
    params = f"metric={metric}&range=ALL&display_currency=INR"
    for key, val in query.items():
        params += f"&{key}={val}"
    payload = api_client.get(f"/api/v1/portfolio/performance?{params}").json()
    points = payload["points"] if isinstance(payload, dict) else payload
    return {p["date"]: p["value"] for p in points}


@pytest.mark.django_db
def test_attributed_income_event_excluded_bank(seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)
    create_fixed_deposit_interest_payment(
        test_user,
        fd.id,
        payment_date=date(2025, 6, 30),
        gross_interest=Decimal("2000"),
        tax_withheld=Decimal("200"),
    )
    events = list_fd_attributed_income_events(test_user, _scope(portfolio.id))
    assert len(events) == 1
    event = events[0]
    assert event.portfolio_id == portfolio.id
    assert event.net_interest == Decimal("1800")
    assert event.bank_included_in_portfolio_scope is False
    assert event.should_count_as_attributed_income is True


@pytest.mark.django_db
def test_attributed_income_skipped_when_bank_included(seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    _enable(test_user, bank)
    fd = _create_fd(test_user, portfolio.id, bank)
    create_fixed_deposit_interest_payment(
        test_user,
        fd.id,
        payment_date=date(2025, 6, 30),
        gross_interest=Decimal("2000"),
        tax_withheld=Decimal("200"),
    )
    events = list_fd_attributed_income_events(test_user, _scope(portfolio.id))
    assert len(events) == 1
    assert events[0].should_count_as_attributed_income is False


@pytest.mark.django_db
def test_attributed_income_portfolio_isolation(seeded, test_user):
    p_a = ensure_default_portfolio(test_user)
    p_b = Portfolio.objects.create(
        user=test_user, name="Other", base_currency="INR", is_active=True
    )
    bank = create_bank_account(
        test_user,
        name="External",
        institution_name="HDFC",
        account_number="ext-bank",
        currency="INR",
        portfolio_id=p_b.id,
    )
    fund_bank_account(test_user, bank, "200000")
    fd = _create_fd(test_user, p_a.id, bank, deposit_account_number="FD-A")
    create_fixed_deposit_interest_payment(
        test_user,
        fd.id,
        payment_date=date(2025, 6, 30),
        gross_interest=Decimal("2000"),
        tax_withheld=Decimal("200"),
    )
    events_a = list_fd_attributed_income_events(test_user, _scope(p_a.id))
    events_b = list_fd_attributed_income_events(test_user, _scope(p_b.id))
    assert len(events_a) == 1
    assert events_a[0].portfolio_id == p_a.id
    assert len(events_b) == 0


@pytest.mark.django_db
def test_reversed_payment_excluded(seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)
    payment = create_fixed_deposit_interest_payment(
        test_user,
        fd.id,
        payment_date=date(2025, 6, 30),
        gross_interest=Decimal("2000"),
        tax_withheld=Decimal("200"),
    )
    reverse_fixed_deposit_interest_payment(
        test_user, payment.payment.id, reversal_date=date(2025, 7, 1), reason="Error"
    )
    by_date, _, _ = build_fd_attributed_income_by_date(
        test_user, _scope(portfolio.id), calculation_currency="INR"
    )
    assert by_date == {}


@pytest.mark.django_db
def test_xirr_flows_excluded_bank_only(seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)
    create_fixed_deposit_interest_payment(
        test_user,
        fd.id,
        payment_date=date(2025, 6, 30),
        gross_interest=Decimal("2000"),
        tax_withheld=Decimal("200"),
    )
    flows, fx_missing = build_fd_attributed_xirr_flows(
        test_user, _scope(portfolio.id), calculation_currency="INR"
    )
    assert fx_missing is False
    assert flows[date(2025, 6, 30)] == Decimal("1800")


@pytest.mark.django_db
def test_xirr_flows_empty_when_bank_included(seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    _enable(test_user, bank)
    fd = _create_fd(test_user, portfolio.id, bank)
    create_fixed_deposit_interest_payment(
        test_user,
        fd.id,
        payment_date=date(2025, 6, 30),
        gross_interest=Decimal("2000"),
        tax_withheld=Decimal("200"),
    )
    flows, _ = build_fd_attributed_xirr_flows(
        test_user, _scope(portfolio.id), calculation_currency="INR"
    )
    assert flows == {}


@pytest.mark.django_db
def test_excluded_bank_twror_positive_on_payment_date(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)
    before = _perf_map(api_client, "twror")
    create_fixed_deposit_interest_payment(
        test_user,
        fd.id,
        payment_date=date(2025, 6, 30),
        gross_interest=Decimal("2000"),
        tax_withheld=Decimal("200"),
    )
    after = _perf_map(api_client, "twror")
    assert after.get("2025-06-29") in (None, 0.0) or after.get("2025-06-29", 0) == before.get(
        "2025-06-29", 0
    )
    payment_twror = after.get("2025-06-30")
    assert payment_twror is not None
    assert payment_twror > 0.3


@pytest.mark.django_db
def test_excluded_bank_cumulative_return_increases_not_value(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)
    value_before = _perf_map(api_client, "value")
    create_fixed_deposit_interest_payment(
        test_user,
        fd.id,
        payment_date=date(2025, 6, 30),
        gross_interest=Decimal("2000"),
        tax_withheld=Decimal("200"),
    )
    value_after = _perf_map(api_client, "value")
    twror_after = _perf_map(api_client, "twror").get("2025-06-30")
    assert value_after == value_before
    assert twror_after is not None
    assert twror_after > 0.3


@pytest.mark.django_db
def test_included_bank_no_double_count_twror(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    _enable(test_user, bank)
    fd = _create_fd(test_user, portfolio.id, bank)
    create_fixed_deposit_interest_payment(
        test_user,
        fd.id,
        payment_date=date(2025, 6, 30),
        gross_interest=Decimal("2000"),
        tax_withheld=Decimal("200"),
    )
    twror = _perf_map(api_client, "twror").get("2025-06-30")
    assert twror is not None
    # TWROR is cumulative return in percentage points; ~0.9% single-count vs ~1.8% double
    assert 0.3 < twror < 1.5


@pytest.mark.django_db
def test_compounded_fd_no_attributed_income_without_payment(seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(
        test_user,
        portfolio.id,
        bank,
        interest_payout_frequency="COMPOUNDED",
        deposit_account_number="FD-COMP",
    )
    by_date, _, _ = build_fd_attributed_income_by_date(
        test_user, _scope(portfolio.id), calculation_currency="INR"
    )
    assert by_date == {}
    assert FixedDeposit.objects.get(pk=fd.id).interest_payout_frequency == "COMPOUNDED"


@pytest.mark.django_db
def test_all_scope_attributed_income_once(seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)
    create_fixed_deposit_interest_payment(
        test_user,
        fd.id,
        payment_date=date(2025, 6, 30),
        gross_interest=Decimal("2000"),
        tax_withheld=Decimal("200"),
    )
    scope = ResolvedPortfolioScope(kind="all_active", portfolio_ids=[portfolio.id])
    by_date, _, _ = build_fd_attributed_income_by_date(
        test_user, scope, calculation_currency="INR"
    )
    assert by_date[date(2025, 6, 30)] == Decimal("1800")


@pytest.mark.django_db
def test_xirr_detail_includes_attributed_flow_when_bank_excluded(seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)
    create_fixed_deposit_interest_payment(
        test_user,
        fd.id,
        payment_date=date(2025, 6, 30),
        gross_interest=Decimal("2000"),
        tax_withheld=Decimal("200"),
    )
    scope = _scope(portfolio.id)
    flows, _ = build_fd_attributed_xirr_flows(
        test_user, scope, calculation_currency="INR"
    )
    assert flows.get(date(2025, 6, 30)) == Decimal("1800")
    result = compute_scope_xirr_detail(scope, display_currency="INR", user=test_user)
    assert result.warnings is not None
