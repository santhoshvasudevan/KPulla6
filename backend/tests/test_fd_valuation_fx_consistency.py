"""#36 — FD current valuation: FX lookback + single conversion boundary."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from fx.models import FXRate
from market_data.models import HistoricalPrice
from portfolios.models import Portfolio
from tests.debt_test_helpers import (
    create_test_bank_account,
    create_legacy_fixed_deposit_with_opening,
    fund_bank_account,
)
from transactions.models import Transaction


def _sunday() -> date:
    return date(2026, 11, 22)  # Sunday


def _friday() -> date:
    return date(2026, 11, 20)


def _inr_portfolio(user) -> Portfolio:
    return Portfolio.objects.create(
        user=user,
        name="INR Valuation",
        base_currency="INR",
        is_active=True,
        cash_aware_enabled=False,
    )


def _inr_investment(portfolio, *, amount="100", as_of: date) -> None:
    Transaction.objects.create(
        portfolio=portfolio,
        date=as_of - timedelta(days=30),
        type="BUY",
        asset_symbol="RELIANCE",
        quantity=Decimal("1"),
        price_per_share=Decimal(amount),
        currency="INR",
        fees=Decimal("0"),
    )
    HistoricalPrice.objects.update_or_create(
        asset_symbol="RELIANCE",
        date=as_of - timedelta(days=30),
        defaults={"close_price": Decimal(amount), "currency": "INR", "asset_type": "STOCK"},
    )
    HistoricalPrice.objects.update_or_create(
        asset_symbol="RELIANCE",
        date=as_of,
        defaults={"close_price": Decimal(amount), "currency": "INR", "asset_type": "STOCK"},
    )


def _fx(day: date, rate="0.01", *, frm="INR", to="EUR") -> None:
    FXRate.objects.update_or_create(
        from_currency=frm,
        to_currency=to,
        date=day,
        defaults={"rate": Decimal(rate)},
    )


def _fd(user, portfolio, *, principal="100000", investment_date: date):
    bank = create_test_bank_account(user, portfolio=portfolio, currency="INR")
    fund_bank_account(
        user, bank, Decimal(principal) + Decimal("50000"), movement_date=investment_date
    )
    return create_legacy_fixed_deposit_with_opening(
        user,
        portfolio=portfolio,
        bank=bank,
        principal_amount=Decimal(principal),
        currency="INR",
        investment_date=investment_date,
        maturity_date=investment_date + timedelta(days=365),
        status="ACTIVE",
    )


def _summary(client, **params):
    query = {
        "include_timeseries": "true",
        "display_currency": "EUR",
        "portfolio_id": params.pop("portfolio_id"),
        **params,
    }
    response = client.get("/api/v1/portfolio/summary", query)
    assert response.status_code == 200, response.json()
    return response.json()


def _holdings(client, portfolio_id, display_currency="EUR"):
    response = client.get(
        "/api/v1/portfolio/holdings",
        {"portfolio_id": portfolio_id, "display_currency": display_currency},
    )
    assert response.status_code == 200, response.json()
    return response.json()


@pytest.mark.django_db
def test_fd_same_day_fx_is_not_converted_twice(api_client, seeded, test_user, monkeypatch):
    """INR 100k FD + INR 100 stock @ 0.01 → EUR 1,001 (not EUR 11)."""
    today = _sunday()
    monkeypatch.setattr("portfolios.dates.current_date", lambda: today)
    portfolio = _inr_portfolio(test_user)
    _inr_investment(portfolio, amount="100", as_of=today)
    _fd(test_user, portfolio, investment_date=today - timedelta(days=60))
    _fx(today, "0.01")

    data = _summary(api_client, portfolio_id=portfolio.id)
    assert data["current_value"] == pytest.approx(1001.0, abs=0.01)
    assert data["display_currency"] == "EUR"

    holdings = _holdings(api_client, portfolio.id)
    fd_rows = [h for h in holdings["holdings"] if h.get("asset_type") == "FIXED_DEPOSIT"]
    assert len(fd_rows) == 1
    assert fd_rows[0]["current_value"] == pytest.approx(1000.0, abs=0.01)
    debt = next(
        b for b in data["allocation_buckets"]["buckets"] if b["label"] == "Debt"
    )
    assert debt["value"] == pytest.approx(1000.0, abs=0.01)

    native = _summary(api_client, portfolio_id=portfolio.id, display_currency="INR")
    assert native["current_value"] == pytest.approx(100100.0, abs=0.01)


@pytest.mark.django_db
def test_fd_friday_fx_covers_sunday_valuation(api_client, seeded, test_user, monkeypatch):
    """Eligible Friday FX must value Sunday FD wealth (not omit FD → ~EUR 1)."""
    today = _sunday()
    monkeypatch.setattr("portfolios.dates.current_date", lambda: today)
    portfolio = _inr_portfolio(test_user)
    _inr_investment(portfolio, amount="100", as_of=today)
    _fd(test_user, portfolio, investment_date=today - timedelta(days=60))
    _fx(_friday(), "0.01")

    data = _summary(api_client, portfolio_id=portfolio.id)
    assert data["current_value"] == pytest.approx(1001.0, abs=0.01)
    assert not any("FX unavailable for fixed deposit" in w for w in data.get("warnings", []))

    holdings = _holdings(api_client, portfolio.id)
    fd_rows = [h for h in holdings["holdings"] if h.get("asset_type") == "FIXED_DEPOSIT"]
    assert fd_rows[0]["current_value"] == pytest.approx(1000.0, abs=0.01)
    assert fd_rows[0]["fx_status"] != "fx_unavailable"
    debt = next(
        b for b in data["allocation_buckets"]["buckets"] if b["label"] == "Debt"
    )
    assert debt["value"] == pytest.approx(1000.0, abs=0.01)

    series = data["timeseries"]
    assert series, "expected value history"
    latest = series[-1]
    assert latest["date"] == today.isoformat()
    assert latest["portfolio_value"] == pytest.approx(1001.0, abs=0.01)


@pytest.mark.django_db
def test_fd_fx_seven_day_boundary_and_genuine_gaps(api_client, seeded, test_user, monkeypatch):
    today = _sunday()
    monkeypatch.setattr("portfolios.dates.current_date", lambda: today)
    portfolio = _inr_portfolio(test_user)
    _fd(test_user, portfolio, investment_date=today - timedelta(days=60))

    # Exactly seven calendar days earlier is eligible.
    _fx(today - timedelta(days=7), "0.01")
    ok = _summary(api_client, portfolio_id=portfolio.id)
    assert ok["current_value"] == pytest.approx(1000.0, abs=0.01)

    FXRate.objects.all().delete()
    # Eight days old is too stale.
    _fx(today - timedelta(days=8), "0.01")
    stale = _summary(api_client, portfolio_id=portfolio.id)
    assert stale["current_value"] == pytest.approx(0.0, abs=0.01)
    assert any("FX unavailable for fixed deposit" in w for w in stale.get("warnings", []))

    FXRate.objects.all().delete()
    # Future-only must not be used.
    _fx(today + timedelta(days=1), "0.01")
    future = _summary(api_client, portfolio_id=portfolio.id)
    assert future["current_value"] == pytest.approx(0.0, abs=0.01)
    assert any("FX unavailable for fixed deposit" in w for w in future.get("warnings", []))

    # Inverse-only prior-day rate.
    FXRate.objects.all().delete()
    _fx(_friday(), "100", frm="EUR", to="INR")  # inverse → 0.01
    inverse = _summary(api_client, portfolio_id=portfolio.id)
    assert inverse["current_value"] == pytest.approx(1000.0, abs=0.01)


@pytest.mark.django_db
def test_fd_only_control_and_all_scope_agree(api_client, seeded, test_user, monkeypatch):
    today = _sunday()
    monkeypatch.setattr("portfolios.dates.current_date", lambda: today)
    portfolio = _inr_portfolio(test_user)
    _fd(test_user, portfolio, investment_date=today - timedelta(days=60))
    _fx(today, "0.01")

    single = _summary(api_client, portfolio_id=portfolio.id)
    assert single["current_value"] == pytest.approx(1000.0, abs=0.01)
    holdings = _holdings(api_client, portfolio.id)
    fd_rows = [h for h in holdings["holdings"] if h.get("asset_type") == "FIXED_DEPOSIT"]
    assert fd_rows[0]["current_value"] == pytest.approx(1000.0, abs=0.01)

    # Deactivate other portfolios so All Portfolios is FD-only wealth.
    Portfolio.objects.filter(user=test_user).exclude(pk=portfolio.id).update(is_active=False)
    all_scope = api_client.get(
        "/api/v1/portfolio/summary",
        {"include_timeseries": "false", "display_currency": "EUR", "portfolio_scope": "all"},
    )
    assert all_scope.status_code == 200, all_scope.json()
    assert all_scope.json()["current_value"] == pytest.approx(1000.0, abs=0.01)
