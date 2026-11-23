"""#41 — Current vs History fixed deposit lifecycle list views."""

from datetime import date
from decimal import Decimal

import pytest

from debt.models import FixedDeposit, FixedDepositStatus
from debt.services import create_fixed_deposit
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
    fund_bank_account(user, bank, "500000")
    return create_fixed_deposit(user, **_fd_payload(portfolio_id, bank.id, **overrides))


def _renew_payload(**overrides):
    payload = dict(
        renewal_date=date(2026, 1, 1),
        new_deposit_account_number="FD-002",
        new_principal_amount=Decimal("100000"),
        new_interest_rate_percent=Decimal("7.5"),
        new_interest_payout_frequency="QUARTERLY",
        new_investment_date=date(2026, 1, 1),
        new_maturity_date=date(2028, 1, 1),
    )
    payload.update(overrides)
    return payload


@pytest.mark.django_db
def test_list_without_lifecycle_view_returns_all_active(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)
    renew = api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/renew",
        _renew_payload(),
        format="json",
    )
    assert renew.status_code == 201
    new_id = renew.json()["new_fixed_deposit"]["id"]

    response = api_client.get("/api/v1/fixed-deposits")
    assert response.status_code == 200
    ids = {row["id"] for row in response.json()}
    assert fd.id in ids
    assert new_id in ids


@pytest.mark.django_db
def test_current_view_excludes_renewed_predecessor(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)
    renew = api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/renew",
        _renew_payload(),
        format="json",
    )
    assert renew.status_code == 201
    new_id = renew.json()["new_fixed_deposit"]["id"]

    response = api_client.get("/api/v1/fixed-deposits?lifecycle_view=current")
    assert response.status_code == 200
    rows = response.json()
    ids = {row["id"] for row in rows}
    assert new_id in ids
    assert fd.id not in ids
    successor = next(row for row in rows if row["id"] == new_id)
    assert successor["lifecycle_view"] == "current"
    assert successor["status"] == "ACTIVE"
    assert successor["renewal_of_id"] == fd.id

    # Predecessor stays is_active — History is not implemented by clearing the flag.
    fd.refresh_from_db()
    assert fd.is_active is True
    assert fd.status == FixedDepositStatus.MATURED_SETTLED


@pytest.mark.django_db
def test_history_view_shows_renewed_predecessor_with_links(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)
    renew = api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/renew",
        _renew_payload(new_deposit_account_number="FD-001"),  # reused deposit number
        format="json",
    )
    assert renew.status_code == 201
    new_id = renew.json()["new_fixed_deposit"]["id"]

    response = api_client.get("/api/v1/fixed-deposits?lifecycle_view=history")
    assert response.status_code == 200
    rows = response.json()
    ids = {row["id"] for row in rows}
    assert fd.id in ids
    assert new_id not in ids
    predecessor = next(row for row in rows if row["id"] == fd.id)
    assert predecessor["lifecycle_view"] == "history"
    assert predecessor["is_renewed"] is True
    assert predecessor["has_renewal"] is True
    assert predecessor["next_term_id"] == new_id
    assert predecessor["deposit_account_number"] == "FD-001"

    new_fd = FixedDeposit.objects.get(id=new_id)
    assert new_fd.deposit_account_number == "FD-001"
    assert new_fd.renewal_of_id == fd.id


@pytest.mark.django_db
def test_matured_awaiting_settlement_stays_in_current(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(
        test_user, portfolio.id, bank, status=FixedDepositStatus.MATURED
    )

    current = api_client.get("/api/v1/fixed-deposits?lifecycle_view=current")
    assert current.status_code == 200
    assert fd.id in {row["id"] for row in current.json()}

    history = api_client.get("/api/v1/fixed-deposits?lifecycle_view=history")
    assert history.status_code == 200
    assert fd.id not in {row["id"] for row in history.json()}


@pytest.mark.django_db
def test_settled_without_renewal_appears_in_history(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)
    settle = api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/settle",
        {
            "settlement_type": "MATURITY",
            "settlement_date": "2026-01-01",
            "gross_interest": 5000,
            "tax_withheld": 500,
        },
        format="json",
    )
    assert settle.status_code == 201

    current = api_client.get("/api/v1/fixed-deposits?lifecycle_view=current")
    assert fd.id not in {row["id"] for row in current.json()}

    history = api_client.get("/api/v1/fixed-deposits?lifecycle_view=history")
    row = next(r for r in history.json() if r["id"] == fd.id)
    assert row["lifecycle_view"] == "history"
    assert row["is_renewed"] is False
    assert row["next_term_id"] is None


@pytest.mark.django_db
def test_multi_term_chain_and_cancelled_excluded(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    t1 = _create_fd(test_user, portfolio.id, bank, deposit_account_number="CHAIN")
    r1 = api_client.post(
        f"/api/v1/fixed-deposits/{t1.id}/renew",
        _renew_payload(
            new_deposit_account_number="CHAIN",
            new_maturity_date=date(2030, 1, 1),
        ),
        format="json",
    )
    assert r1.status_code == 201
    t2_id = r1.json()["new_fixed_deposit"]["id"]
    r2 = api_client.post(
        f"/api/v1/fixed-deposits/{t2_id}/renew",
        _renew_payload(
            renewal_date=date(2028, 1, 1),
            new_deposit_account_number="CHAIN",
            new_investment_date=date(2028, 1, 1),
            new_maturity_date=date(2030, 1, 1),
        ),
        format="json",
    )
    assert r2.status_code == 201
    t3_id = r2.json()["new_fixed_deposit"]["id"]

    cancelled = _create_fd(
        test_user, portfolio.id, bank, deposit_account_number="CANCEL-ME"
    )
    cancel = api_client.post(
        f"/api/v1/fixed-deposits/{cancelled.id}/cancel",
        {},
        format="json",
    )
    assert cancel.status_code in (200, 201)

    current_ids = {
        row["id"]
        for row in api_client.get("/api/v1/fixed-deposits?lifecycle_view=current").json()
    }
    history_rows = api_client.get("/api/v1/fixed-deposits?lifecycle_view=history").json()
    history_ids = {row["id"] for row in history_rows}

    assert current_ids == {t3_id}
    assert t1.id in history_ids
    assert t2_id in history_ids
    assert cancelled.id not in current_ids
    assert cancelled.id not in history_ids

    t1_row = next(r for r in history_rows if r["id"] == t1.id)
    t2_row = next(r for r in history_rows if r["id"] == t2_id)
    assert t1_row["next_term_id"] == t2_id
    assert t2_row["renewal_of_id"] == t1.id
    assert t2_row["next_term_id"] == t3_id


@pytest.mark.django_db
def test_invalid_lifecycle_view_rejected(api_client, seeded, test_user):
    response = api_client.get("/api/v1/fixed-deposits?lifecycle_view=bogus")
    assert response.status_code == 400


@pytest.mark.django_db
def test_lifecycle_view_respects_portfolio_scope(api_client, seeded, test_user):
    p1 = ensure_default_portfolio(test_user)
    from portfolios.models import Portfolio

    p2 = Portfolio.objects.create(user=test_user, name="Other", base_currency="INR")
    bank1 = _bank(test_user, portfolio=p1)
    bank2 = _bank(test_user, portfolio=p2, name="Other bank", account_number="99")
    fd1 = _create_fd(test_user, p1.id, bank1, deposit_account_number="P1")
    fd2 = _create_fd(test_user, p2.id, bank2, deposit_account_number="P2")
    api_client.post(
        f"/api/v1/fixed-deposits/{fd1.id}/renew",
        _renew_payload(new_deposit_account_number="P1-NEW"),
        format="json",
    )

    scoped = api_client.get(
        f"/api/v1/fixed-deposits?lifecycle_view=history&portfolio_id={p1.id}"
    )
    assert scoped.status_code == 200
    ids = {row["id"] for row in scoped.json()}
    assert fd1.id in ids
    assert fd2.id not in ids
