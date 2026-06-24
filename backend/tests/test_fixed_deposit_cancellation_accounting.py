"""FD-ACC-10A: cancel ledger-backed FD restores bank cash and portfolio value."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from debt.bank_ledger_services import compute_bank_account_balance
from debt.models import (
    BankAccount,
    CashMovement,
    CashMovementDirection,
    CashMovementType,
    FixedDepositStatus,
)
from debt.services import (
    create_bank_account,
    create_fixed_deposit,
    deactivate_fixed_deposit,
    update_bank_account,
)
from portfolios.models import Portfolio
from portfolios.seed import ensure_default_portfolio
from tests.debt_test_helpers import create_test_bank_account, fund_bank_account


def _bank(user, name="Savings", account_number="111", portfolio=None):
    return create_test_bank_account(
        user, portfolio=portfolio, name=name, account_number=account_number
    )



def _create_fd(user, portfolio_id, bank_id, principal="100000", *, fund=True, **kw):
    bank = BankAccount.objects.get(pk=bank_id)
    if fund:
        fund_bank_account(
            user,
            bank,
            Decimal(principal) + Decimal("50000"),
            movement_date=kw.get("fund_date", date(2024, 1, 1)),
        )
        bank.refresh_from_db()
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
        status=kw.get("status", "ACTIVE"),
        skip_opening_debit=kw.get("skip_opening_debit", False),
    )


def _enable_bank(user, bank):
    return update_bank_account(user, bank.id, include_in_portfolio_value=True)


def _summary_value(api_client, **query):
    params = "include_timeseries=false&display_currency=INR"
    for key, val in query.items():
        params += f"&{key}={val}"
    return api_client.get(f"/api/v1/portfolio/summary?{params}").json()


def _perf_map(api_client, **query):
    params = "metric=value&range=ALL&display_currency=INR"
    for key, val in query.items():
        params += f"&{key}={val}"
    payload = api_client.get(f"/api/v1/portfolio/performance?{params}").json()
    points = payload["points"] if isinstance(payload, dict) else payload
    return {p["date"]: p["value"] for p in points}


@pytest.mark.django_db
def test_fd_create_debits_bank_and_includes_principal(api_client, seeded, test_user):
    portfolio_a = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    _enable_bank(test_user, bank)
    initial_bank = Decimal("150000")
    fund_bank_account(test_user, bank, initial_bank)

    fd_resp = api_client.post(
        "/api/v1/fixed-deposits",
        {
            "portfolio_id": portfolio_a.id,
            "bank_account_id": bank.id,
            "institution_name": "HDFC",
            "deposit_account_number": "FD-WRONG",
            "principal_amount": "100000",
            "currency": "INR",
            "interest_rate_percent": "7",
            "interest_payout_frequency": "QUARTERLY",
            "investment_date": "2024-01-01",
            "maturity_date": "2026-01-01",
        },
        format="json",
    )
    assert fd_resp.status_code == 201
    fd_id = fd_resp.json()["id"]
    assert fd_resp.json()["has_opening_cash_movement"] is True

    bank.refresh_from_db()
    assert bank.current_balance == pytest.approx(float(initial_bank - Decimal("100000")))

    opening = CashMovement.objects.get(
        linked_fixed_deposit_id=fd_id, movement_type=CashMovementType.FD_OPENING
    )
    assert opening.direction == CashMovementDirection.DEBIT
    assert opening.amount == Decimal("100000")

    summary = _summary_value(api_client, portfolio_id=portfolio_a.id)
    assert summary["current_value"] == pytest.approx(150000.0)
    all_summary = _summary_value(api_client, portfolio_scope="all")
    assert all_summary["current_value"] == pytest.approx(150000.0)


@pytest.mark.django_db
def test_deactivate_ledger_fd_blocked_and_leaves_bank_reduced(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    _enable_bank(test_user, bank)
    fd = _create_fd(test_user, portfolio.id, bank.id)
    bank.refresh_from_db()
    bank_before = bank.current_balance

    response = api_client.delete(f"/api/v1/fixed-deposits/{fd.id}")
    assert response.status_code == 409
    assert "Cancel FD" in response.json()["detail"]

    bank.refresh_from_db()
    assert bank.current_balance == bank_before
    assert _summary_value(api_client)["current_value"] == pytest.approx(150000.0)


@pytest.mark.django_db
def test_cancel_ledger_fd_restores_bank_cash(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    _enable_bank(test_user, bank)
    fd = _create_fd(test_user, portfolio.id, bank.id)
    bank.refresh_from_db()
    bank_after_open = bank.current_balance

    response = api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/cancel",
        {"cancellation_date": "2024-06-15"},
        format="json",
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == FixedDepositStatus.CANCELLED
    assert body["is_active"] is False
    assert body["has_opening_cash_movement"] is False

    bank.refresh_from_db()
    assert float(bank.current_balance) == pytest.approx(float(bank_after_open + Decimal("100000")))

    reversal = CashMovement.objects.get(
        linked_fixed_deposit_id=fd.id,
        movement_type=CashMovementType.FD_OPENING_REVERSAL,
    )
    assert reversal.direction == CashMovementDirection.CREDIT
    assert reversal.amount == Decimal("100000")
    assert reversal.is_reversal is True
    assert reversal.reverses.movement_type == CashMovementType.FD_OPENING


@pytest.mark.django_db
def test_cancelled_fd_excluded_from_summary_and_holdings(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank.id)

    api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/cancel",
        {"cancellation_date": "2024-06-15"},
        format="json",
    )

    summary = _summary_value(api_client)["current_value"]
    assert summary == 0.0

    holdings = api_client.get("/api/v1/portfolio/holdings?display_currency=INR").json()["holdings"]
    assert not [h for h in holdings if h.get("asset_type") == "FIXED_DEPOSIT"]


@pytest.mark.django_db
def test_cancelled_fd_excluded_from_fd_list(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank.id)

    api_client.post(f"/api/v1/fixed-deposits/{fd.id}/cancel", {}, format="json")

    listed = api_client.get("/api/v1/fixed-deposits").json()
    assert listed == []


@pytest.mark.django_db
def test_cancelled_fd_value_history_excludes_principal(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    _enable_bank(test_user, bank)
    fd = _create_fd(test_user, portfolio.id, bank.id, investment_date=date(2024, 1, 1))

    api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/cancel",
        {"cancellation_date": "2024-06-15"},
        format="json",
    )

    values = _perf_map(api_client)
    assert values.get("2024-01-02") == pytest.approx(50000.0)
    assert values.get("2024-06-14") == pytest.approx(50000.0)
    assert values.get("2024-06-15") == pytest.approx(150000.0)


@pytest.mark.django_db
def test_all_scope_value_stable_after_cancel(api_client, seeded, test_user):
    portfolio_a = ensure_default_portfolio(test_user)
    portfolio_b = Portfolio.objects.create(
        user=test_user, name="Portfolio B", base_currency="INR", is_active=True
    )
    bank = _bank(test_user)
    _enable_bank(test_user, bank)
    fund_bank_account(test_user, bank, Decimal("200000"))

    baseline = _summary_value(api_client, portfolio_scope="all")["current_value"]

    fd = _create_fd(test_user, portfolio_a.id, bank.id, fund=False)
    after_create = _summary_value(api_client, portfolio_scope="all")["current_value"]
    assert after_create == pytest.approx(baseline)

    api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/cancel",
        {"cancellation_date": "2024-06-15"},
        format="json",
    )
    after_cancel = _summary_value(api_client, portfolio_scope="all")["current_value"]
    assert after_cancel == pytest.approx(baseline)


@pytest.mark.django_db
def test_legacy_fd_without_opening_can_still_deactivate(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank.id, skip_opening_debit=True)

    response = api_client.delete(f"/api/v1/fixed-deposits/{fd.id}")
    assert response.status_code == 200
    assert response.json()["is_active"] is False
    assert CashMovement.objects.filter(linked_fixed_deposit_id=fd.id).count() == 0


@pytest.mark.django_db
def test_cannot_cancel_fd_with_interest_payment(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank.id)

    pay_resp = api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/interest-payments",
        {
            "payment_date": "2024-06-01",
            "gross_interest": "1000",
            "tax_withheld": "100",
        },
        format="json",
    )
    assert pay_resp.status_code == 201

    response = api_client.post(f"/api/v1/fixed-deposits/{fd.id}/cancel", {}, format="json")
    assert response.status_code == 400
    assert "interest" in response.json()["detail"].lower()


@pytest.mark.django_db
def test_cannot_cancel_settled_fd(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank.id)

    settle_resp = api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/settle",
        {
            "settlement_type": "CLOSURE",
            "settlement_date": "2024-06-01",
            "gross_interest": 0,
            "tax_withheld": 0,
        },
        format="json",
    )
    assert settle_resp.status_code == 201

    response = api_client.post(f"/api/v1/fixed-deposits/{fd.id}/cancel", {}, format="json")
    assert response.status_code == 400


@pytest.mark.django_db
def test_cannot_cancel_renewed_fd(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank.id)

    renew_resp = api_client.post(
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
    assert renew_resp.status_code == 201

    response = api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/cancel",
        {},
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_duplicate_cancel_rejected(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank.id)

    first = api_client.post(f"/api/v1/fixed-deposits/{fd.id}/cancel", {}, format="json")
    assert first.status_code == 200

    second = api_client.post(f"/api/v1/fixed-deposits/{fd.id}/cancel", {}, format="json")
    assert second.status_code == 404


@pytest.mark.django_db
def test_cancel_user_scoped(api_client, seeded, test_user, django_user_model):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank.id)

    other = django_user_model.objects.create_user(
        username="other", email="other@example.com", password="pass"
    )
    api_client.force_authenticate(user=other)
    response = api_client.post(f"/api/v1/fixed-deposits/{fd.id}/cancel", {}, format="json")
    assert response.status_code == 404


@pytest.mark.django_db
def test_classify_fd_opening_reversal_as_internal(seeded, test_user):
    from debt.cash_ledger_flows import BankCashFlowKind, classify_bank_cash_movement

    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    _enable_bank(test_user, bank)
    fd = _create_fd(test_user, portfolio.id, bank.id)

    from debt.cancellation_services import cancel_fixed_deposit

    cancel_fixed_deposit(test_user, fd.id, cancellation_date=date(2024, 6, 15))

    reversal = CashMovement.objects.get(
        linked_fixed_deposit_id=fd.id,
        movement_type=CashMovementType.FD_OPENING_REVERSAL,
    )
    assert (
        classify_bank_cash_movement(reversal, bank_included=True)
        == BankCashFlowKind.INTERNAL
    )


@pytest.mark.django_db
def test_cancel_restores_ledger_balance_as_of(seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fund_bank_account(test_user, bank, Decimal("150000"))
    fd = _create_fd(test_user, portfolio.id, bank.id, fund=False)

    assert compute_bank_account_balance(bank) == Decimal("50000")

    from debt.cancellation_services import cancel_fixed_deposit

    cancel_fixed_deposit(test_user, fd.id, cancellation_date=date(2024, 6, 15))

    assert compute_bank_account_balance(bank) == Decimal("150000")
    assert compute_bank_account_balance(bank, as_of_date=date(2024, 6, 14)) == Decimal("50000")
