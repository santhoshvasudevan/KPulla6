"""Native FD/bank-only reporting must not invent FX needs for zero investment legs."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest

from debt.bank_ledger_services import create_manual_cash_movement
from debt.services import update_bank_account
from tests.debt_test_helpers import create_test_bank_account
from tests.test_fd_valuation_fx_consistency import _fd, _inr_portfolio, _sunday


@pytest.mark.django_db
def test_native_fd_only_does_not_require_unrelated_fx(api_client, seeded, test_user, monkeypatch):
    today = _sunday()
    monkeypatch.setattr("portfolios.dates.current_date", lambda: today)
    portfolio = _inr_portfolio(test_user)
    _fd(test_user, portfolio, investment_date=today - timedelta(days=60))
    # No investment cash flows or foreign components: INR principal in INR needs no FX.
    response = api_client.get("/api/v1/portfolio/summary", {
        "portfolio_id": portfolio.id, "display_currency": "INR", "include_timeseries": "false",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["current_value"] == pytest.approx(100000)
    assert data["allocation_buckets"]["fx_status"] == "ok"
    assert data["fx_status"] != "fx_unavailable", data
    assert data["fx_status"] == "ok"


@pytest.mark.django_db
def test_native_bank_cash_only_does_not_require_unrelated_fx(
    api_client, seeded, test_user, monkeypatch
):
    today = _sunday()
    monkeypatch.setattr("portfolios.dates.current_date", lambda: today)
    portfolio = _inr_portfolio(test_user)
    bank = create_test_bank_account(user=test_user, portfolio=portfolio, currency="INR")
    create_manual_cash_movement(
        test_user,
        bank_account_id=bank.id,
        movement_type="MANUAL_DEPOSIT",
        amount=Decimal("75000"),
        movement_date=today - timedelta(days=10),
        portfolio_id=portfolio.id,
    )
    update_bank_account(test_user, bank.id, include_in_portfolio_value=True)

    data = api_client.get("/api/v1/portfolio/summary", {
        "portfolio_id": portfolio.id, "display_currency": "INR", "include_timeseries": "false",
    }).json()
    assert data["current_value"] == pytest.approx(75000)
    assert data["allocation_buckets"]["fx_status"] == "ok"
    assert data["fx_status"] == "ok"
