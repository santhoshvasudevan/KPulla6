"""FD-ACC-9: End-to-end fixed deposit accounting scenario audits."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from debt.bank_ledger_services import seed_opening_balance
from debt.cash_ledger_flows import BankCashFlowKind, classify_bank_cash_movement
from debt.models import (
    CashMovement,
    CashMovementType,
    FixedDeposit,
    FixedDepositStatus,
)
from debt.services import create_bank_account, create_fixed_deposit, update_bank_account
from portfolios.models import Portfolio
from portfolios.scope import ResolvedPortfolioScope
from portfolios.seed import ensure_default_portfolio
from portfolios.xirr_service import compute_scope_xirr_detail
from tests.debt_test_helpers import fund_bank_account


def _bank(user, **overrides):
    payload = dict(
        name="Savings",
        institution_name="HDFC",
        account_number="e2e-111",
        currency="INR",
    )
    payload.update(overrides)
    return create_bank_account(user, **payload)


def _enable_inclusion(user, bank):
    return update_bank_account(user, bank.id, include_in_portfolio_value=True)


def _summary(api_client, **query):
    params = "include_timeseries=false&display_currency=INR"
    for key, val in query.items():
        params += f"&{key}={val}"
    return api_client.get(f"/api/v1/portfolio/summary?{params}").json()


def _perf_points(api_client, metric="value", **query):
    params = f"metric={metric}&range=ALL&display_currency=INR"
    for key, val in query.items():
        params += f"&{key}={val}"
    payload = api_client.get(f"/api/v1/portfolio/performance?{params}").json()
    points = payload["points"] if isinstance(payload, dict) else payload
    return {p["date"]: p.get("value") for p in points}


def _metrics(api_client, **query):
    params = "range=ALL&display_currency=INR"
    for key, val in query.items():
        params += f"&{key}={val}"
    return api_client.get(f"/api/v1/analytics/performance-metrics?{params}").json()


@pytest.mark.django_db
def test_scenario_1_included_bank_cash_full_lifecycle(api_client, seeded, test_user):
    """Included bank cash: seed → FD open → interest → mark matured → settle."""
    portfolio = ensure_default_portfolio(test_user)
    bank = create_bank_account(
        test_user,
        name="E2E Savings",
        institution_name="HDFC",
        account_number="e2e-seed",
        currency="INR",
        opening_balance=Decimal("300000"),
    )
    seed_opening_balance(test_user, bank.id, movement_date=date(2024, 1, 1))
    bank.refresh_from_db()
    assert bank.current_balance == Decimal("300000")
    _enable_inclusion(test_user, bank)

    total_before = _summary(api_client)["current_value"]
    assert total_before == 300000.0

    fd_resp = api_client.post(
        "/api/v1/fixed-deposits",
        {
            "portfolio_id": portfolio.id,
            "bank_account_id": bank.id,
            "institution_name": "HDFC",
            "deposit_account_number": "FD-E2E-1",
            "principal_amount": 100000,
            "currency": "INR",
            "interest_rate_percent": 7,
            "interest_payout_frequency": "QUARTERLY",
            "investment_date": "2024-01-01",
            "maturity_date": "2026-01-01",
        },
        format="json",
    )
    assert fd_resp.status_code == 201
    fd_id = fd_resp.json()["id"]
    bank.refresh_from_db()
    assert bank.current_balance == Decimal("200000")

    after_open = _summary(api_client)
    assert after_open["current_value"] == pytest.approx(300000.0, rel=0.001)
    buckets = {b["label"]: b["value"] for b in after_open["allocation_buckets"]["buckets"]}
    assert buckets["Debt"] == 100000.0
    assert buckets["Cash / Bank Cash"] == 200000.0

    opening_mv = CashMovement.objects.get(
        linked_fixed_deposit_id=fd_id, movement_type=CashMovementType.FD_OPENING
    )
    assert classify_bank_cash_movement(opening_mv, bank_included=True) == BankCashFlowKind.INTERNAL

    holdings = api_client.get("/api/v1/portfolio/holdings?display_currency=INR").json()["holdings"]
    fd_rows = [h for h in holdings if h.get("asset_type") == "FIXED_DEPOSIT"]
    bank_rows = [h for h in holdings if h.get("asset_type") == "BANK_CASH"]
    assert len(fd_rows) == 1
    assert fd_rows[0]["principal_amount"] == 100000.0
    assert len(bank_rows) == 1
    assert bank_rows[0]["current_value"] == 200000.0

    interest = api_client.post(
        f"/api/v1/fixed-deposits/{fd_id}/interest-payments",
        {"payment_date": "2025-03-01", "gross_interest": 5000, "tax_withheld": 500},
        format="json",
    )
    assert interest.status_code == 201
    bank.refresh_from_db()
    assert bank.current_balance == Decimal("204500")

    after_interest = _summary(api_client)
    assert after_interest["current_value"] == pytest.approx(304500.0, rel=0.001)
    assert after_interest["allocation_buckets"]["buckets"][-1]["label"] != "Debt" or buckets["Debt"] == 100000.0

    mark = api_client.post(f"/api/v1/fixed-deposits/{fd_id}/mark-matured", {}, format="json")
    assert mark.status_code == 200
    bank.refresh_from_db()
    assert bank.current_balance == Decimal("204500")
    matured_summary = _summary(api_client)
    assert matured_summary["current_value"] == pytest.approx(304500.0, rel=0.001)

    settle = api_client.post(
        f"/api/v1/fixed-deposits/{fd_id}/settle",
        {
            "settlement_type": "MATURITY",
            "settlement_date": "2026-01-01",
            "gross_interest": 5000,
            "tax_withheld": 500,
        },
        format="json",
    )
    assert settle.status_code == 201
    bank.refresh_from_db()
    assert bank.current_balance == Decimal("309000")

    after_settle = _summary(api_client)
    # Principal flat (300k); net final interest +4500 on top of post-periodic-interest total.
    assert after_settle["current_value"] == pytest.approx(309000.0, rel=0.001)
    assert after_settle.get("has_fixed_deposits") is not True

    perf_value = _perf_points(api_client)
    assert perf_value.get("2025-12-31") == pytest.approx(304500.0, rel=0.01)
    assert perf_value.get("2026-01-01") == pytest.approx(309000.0, rel=0.01)

    scope = ResolvedPortfolioScope(kind="all_active", portfolio_ids=[portfolio.id])
    xirr = compute_scope_xirr_detail(scope, display_currency="INR", user=test_user)
    assert xirr.value is not None

    twror = _perf_points(api_client, metric="twror")
    open_day = twror.get("2024-01-01")
    if open_day is not None:
        assert abs(open_day) < 0.05

    metrics = _metrics(api_client)
    assert metrics.get("cumulative_return") is not None or metrics.get("metrics")


@pytest.mark.django_db
def test_scenario_2_renewal_direct_and_partial_payout(api_client, seeded, test_user):
    """Direct rollover and partial cash payout without double-counting."""
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fund_bank_account(test_user, bank, "200000")
    fd = create_fixed_deposit(
        test_user,
        portfolio_id=portfolio.id,
        bank_account_id=bank.id,
        institution_name="HDFC",
        deposit_account_number="FD-REN-OLD",
        principal_amount=Decimal("100000"),
        currency="INR",
        interest_rate_percent=Decimal("7"),
        interest_payout_frequency="QUARTERLY",
        investment_date=date(2024, 1, 1),
        maturity_date=date(2026, 1, 1),
    )

    renew_full = api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/renew",
        {
            "renewal_date": "2026-01-01",
            "new_deposit_account_number": "FD-REN-NEW",
            "new_principal_amount": 100000,
            "new_interest_rate_percent": 7.5,
            "new_interest_payout_frequency": "QUARTERLY",
            "new_investment_date": "2026-01-01",
            "new_maturity_date": "2028-01-01",
        },
        format="json",
    )
    assert renew_full.status_code == 201
    body = renew_full.json()
    assert body["old_fixed_deposit"]["status"] == "MATURED_SETTLED"
    assert body["new_fixed_deposit"]["status"] == "ACTIVE"
    assert body["cash_movement_ids"] == []

    new_fd_id = body["new_fixed_deposit"]["id"]
    assert not CashMovement.objects.filter(
        linked_fixed_deposit_id=new_fd_id, movement_type=CashMovementType.FD_OPENING
    ).exists()

    perf = _perf_points(api_client)
    assert perf.get("2025-12-31") == pytest.approx(100000.0, rel=1e-6)
    assert perf.get("2026-01-01") == pytest.approx(100000.0, rel=1e-6)

    summary = _summary(api_client)
    assert summary["current_value"] == 100000.0

    bank2 = _bank(test_user, account_number="e2e-ren-2")
    fund_bank_account(test_user, bank2, "200000")
    fd2 = create_fixed_deposit(
        test_user,
        portfolio_id=portfolio.id,
        bank_account_id=bank2.id,
        institution_name="HDFC",
        deposit_account_number="FD-PARTIAL",
        principal_amount=Decimal("100000"),
        currency="INR",
        interest_rate_percent=Decimal("7"),
        interest_payout_frequency="QUARTERLY",
        investment_date=date(2024, 1, 1),
        maturity_date=date(2026, 1, 1),
    )
    bank2.refresh_from_db()
    balance_before = bank2.current_balance

    partial = api_client.post(
        f"/api/v1/fixed-deposits/{fd2.id}/renew",
        {
            "renewal_date": "2026-01-01",
            "new_deposit_account_number": "FD-PARTIAL-NEW",
            "new_principal_amount": 90000,
            "new_interest_rate_percent": 7.5,
            "new_interest_payout_frequency": "QUARTERLY",
            "new_investment_date": "2026-01-01",
            "new_maturity_date": "2028-01-01",
            "cash_payout_amount": 10000,
        },
        format="json",
    )
    assert partial.status_code == 201
    payout_body = partial.json()
    assert payout_body["cash_payout_amount"] == 10000.0
    assert len(payout_body["cash_movement_ids"]) == 1
    bank2.refresh_from_db()
    assert bank2.current_balance == balance_before + Decimal("10000")

    after_partial = _summary(api_client)
    assert after_partial["current_value"] == pytest.approx(190000.0, rel=0.01)


@pytest.mark.django_db
def test_scenario_3_excluded_bank_cash_conservative_behavior(api_client, seeded, test_user):
    """Bank cash excluded: FD open steps PV up; settle steps PV down."""
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fund_bank_account(test_user, bank, "200000")

    before = _summary(api_client)["current_value"]
    assert before == 0.0

    fd_resp = api_client.post(
        "/api/v1/fixed-deposits",
        {
            "portfolio_id": portfolio.id,
            "bank_account_id": bank.id,
            "institution_name": "HDFC",
            "deposit_account_number": "FD-EXCL",
            "principal_amount": 100000,
            "currency": "INR",
            "interest_rate_percent": 7,
            "interest_payout_frequency": "QUARTERLY",
            "investment_date": "2024-01-01",
            "maturity_date": "2026-01-01",
        },
        format="json",
    )
    assert fd_resp.status_code == 201
    fd_id = fd_resp.json()["id"]

    after_open = _summary(api_client)["current_value"]
    assert after_open == 100000.0

    opening_mv = CashMovement.objects.get(
        linked_fixed_deposit_id=fd_id, movement_type=CashMovementType.FD_OPENING
    )
    # Excluded bank: movement ignored in return flow maps (not external contribution).
    assert classify_bank_cash_movement(opening_mv, bank_included=False) == BankCashFlowKind.IGNORED

    api_client.post(
        f"/api/v1/fixed-deposits/{fd_id}/interest-payments",
        {"payment_date": "2025-03-01", "gross_interest": 1000, "tax_withheld": 100},
        format="json",
    )
    after_interest = _summary(api_client)["current_value"]
    assert after_interest == 100000.0

    api_client.post(
        f"/api/v1/fixed-deposits/{fd_id}/settle",
        {
            "settlement_type": "MATURITY",
            "settlement_date": "2026-01-01",
            "gross_interest": 0,
            "tax_withheld": 0,
        },
        format="json",
    )
    after_settle = _summary(api_client)["current_value"]
    assert after_settle == 0.0

    perf = _perf_points(api_client)
    assert perf.get("2025-12-31") == pytest.approx(100000.0, rel=1e-6)
    assert perf.get("2026-01-01") in (None, 0.0)


@pytest.mark.django_db
def test_scenario_4_unseeded_manual_balance(api_client, seeded, test_user):
    """Manual/reference balance excluded from portfolio value; FD create needs ledger."""
    portfolio = ensure_default_portfolio(test_user)
    bank = create_bank_account(
        test_user,
        name="Manual Ref",
        institution_name="HDFC",
        account_number="e2e-manual",
        currency="INR",
        opening_balance=Decimal("250000"),
        current_balance=Decimal("250000"),
    )
    _enable_inclusion(test_user, bank)

    summary = _summary(api_client)
    assert summary["current_value"] == 0.0

    fd_fail = api_client.post(
        "/api/v1/fixed-deposits",
        {
            "portfolio_id": portfolio.id,
            "bank_account_id": bank.id,
            "institution_name": "HDFC",
            "deposit_account_number": "FD-NO-LEDGER",
            "principal_amount": 100000,
            "currency": "INR",
            "interest_rate_percent": 7,
            "interest_payout_frequency": "QUARTERLY",
            "investment_date": "2024-01-01",
            "maturity_date": "2026-01-01",
        },
        format="json",
    )
    assert fd_fail.status_code == 400
    assert fd_fail.json()["available"] == 0.0
    assert "seed" in fd_fail.json()["hint"].lower()
    assert FixedDeposit.objects.filter(user=test_user).count() == 0


@pytest.mark.django_db
def test_scenario_5_portfolio_scope_attribution(api_client, seeded, test_user):
    """All-scope counts bank once; single-portfolio uses conservative FD-ACC-7 rules."""
    p1 = ensure_default_portfolio(test_user)
    p2 = Portfolio.objects.create(
        user=test_user, name="Second E2E", base_currency="INR", is_active=True
    )

    exclusive_bank = _bank(test_user, account_number="e2e-exclusive")
    fund_bank_account(test_user, exclusive_bank, "55000")
    _enable_inclusion(test_user, exclusive_bank)
    create_fixed_deposit(
        test_user,
        portfolio_id=p1.id,
        bank_account_id=exclusive_bank.id,
        institution_name="HDFC",
        deposit_account_number="FD-EXCL-P1",
        principal_amount=Decimal("5000"),
        currency="INR",
        interest_rate_percent=Decimal("7"),
        interest_payout_frequency="QUARTERLY",
        investment_date=date(2024, 1, 1),
        maturity_date=date(2026, 1, 1),
    )
    exclusive_summary = _summary(api_client, portfolio_id=p1.id)
    assert exclusive_summary["current_value"] == pytest.approx(55000.0, rel=0.001)

    bank = _bank(test_user, account_number="e2e-scope")
    fund_bank_account(test_user, bank, "80000")
    _enable_inclusion(test_user, bank)

    create_fixed_deposit(
        test_user,
        portfolio_id=p1.id,
        bank_account_id=bank.id,
        institution_name="HDFC",
        deposit_account_number="FD-P1",
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
        deposit_account_number="FD-P2",
        principal_amount=Decimal("20000"),
        currency="INR",
        interest_rate_percent=Decimal("7"),
        interest_payout_frequency="QUARTERLY",
        investment_date=date(2024, 1, 1),
        maturity_date=date(2026, 1, 1),
    )

    all_summary = _summary(api_client, portfolio_scope="all")
    p1_summary = _summary(api_client, portfolio_id=p1.id)
    p2_summary = _summary(api_client, portfolio_id=p2.id)

    # All scope: shared bank cash once + all FD principals + exclusive bank.
    assert all_summary["current_value"] == pytest.approx(135000.0, rel=0.001)
    # Multi-portfolio shared bank: FD principal only per portfolio (conservative).
    assert p1_summary["current_value"] == pytest.approx(65000.0, rel=0.001)
    assert p2_summary["current_value"] == 20000.0

    all_perf = max(_perf_points(api_client, portfolio_scope="all").values())
    assert all_perf == pytest.approx(135000.0, rel=0.001)
