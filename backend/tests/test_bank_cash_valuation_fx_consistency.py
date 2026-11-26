"""#37 — Opted-in bank cash: FX lookback, eligibility, once-only all-scope."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from debt.bank_ledger_services import create_manual_cash_movement
from debt.portfolio_value import (
    build_bank_cash_holding_rows,
    build_bank_cash_value_timeseries,
    calculate_bank_cash_for_scope,
)
from debt.services import create_bank_account, update_bank_account
from fx.models import FXRate
from market_data.models import HistoricalPrice
from portfolios.models import Portfolio
from portfolios.scope import ResolvedPortfolioScope
from tests.debt_test_helpers import (
    create_legacy_fixed_deposit_with_opening,
    create_test_bank_account,
    fund_bank_account,
)
from transactions.models import Transaction


def _sunday() -> date:
    return date(2026, 11, 22)


def _friday() -> date:
    return date(2026, 11, 20)


def _fx(day: date, rate="0.01", *, frm="INR", to="EUR") -> None:
    FXRate.objects.update_or_create(
        from_currency=frm,
        to_currency=to,
        date=day,
        defaults={"rate": Decimal(rate)},
    )


def _inr_portfolio(user, name="INR Bank Scope") -> Portfolio:
    return Portfolio.objects.create(
        user=user,
        name=name,
        base_currency="INR",
        is_active=True,
        cash_aware_enabled=False,
    )


def _enable(user, bank):
    return update_bank_account(user, bank.id, include_in_portfolio_value=True)


def _fund_for_portfolio(user, bank, portfolio, amount, *, movement_date):
    """Credit bank cash with a portfolio-tagged deposit so single-scope inclusion resolves."""
    create_manual_cash_movement(
        user,
        bank_account_id=bank.id,
        movement_type="MANUAL_DEPOSIT",
        amount=Decimal(str(amount)),
        movement_date=movement_date,
        portfolio_id=portfolio.id,
    )
    bank.refresh_from_db()
    return bank


def _stock(portfolio, *, amount="100", as_of: date) -> None:
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
    for day in (as_of - timedelta(days=30), as_of):
        HistoricalPrice.objects.update_or_create(
            asset_symbol="RELIANCE",
            date=day,
            defaults={"close_price": Decimal(amount), "currency": "INR", "asset_type": "STOCK"},
        )


@pytest.mark.django_db
def test_bank_cash_friday_fx_covers_sunday_and_avoids_double_conversion(
    api_client, seeded, test_user, monkeypatch
):
    """Demonstrate weekend omission before lookback fix; mixed case stays single-converted."""
    today = _sunday()
    monkeypatch.setattr("portfolios.dates.current_date", lambda: today)
    portfolio = _inr_portfolio(test_user)
    _stock(portfolio, amount="100", as_of=today)
    bank = create_test_bank_account(user=test_user, portfolio=portfolio, currency="INR")
    _fund_for_portfolio(
        test_user, bank, portfolio, "100000", movement_date=today - timedelta(days=10)
    )
    _enable(test_user, bank)
    _fx(_friday(), "0.01")

    data = api_client.get(
        "/api/v1/portfolio/summary",
        {
            "portfolio_id": portfolio.id,
            "include_timeseries": "true",
            "display_currency": "EUR",
        },
    ).json()
    # INR 100 stock + INR 100,000 bank @ 0.01 → EUR 1,001
    assert data["current_value"] == pytest.approx(1001.0, abs=0.01)
    assert not any("FX unavailable for bank account" in w for w in data.get("warnings", []))

    holdings = api_client.get(
        "/api/v1/portfolio/holdings",
        {"portfolio_id": portfolio.id, "display_currency": "EUR"},
    ).json()
    bank_rows = [h for h in holdings["holdings"] if h.get("asset_type") == "BANK_CASH"]
    assert len(bank_rows) == 1
    assert bank_rows[0]["current_value"] == pytest.approx(1000.0, abs=0.01)
    cash_bucket = next(
        b for b in data["allocation_buckets"]["buckets"] if "Cash" in b["label"]
    )
    assert cash_bucket["value"] == pytest.approx(1000.0, abs=0.01)

    latest = data["timeseries"][-1]
    assert latest["date"] == today.isoformat()
    assert latest["portfolio_value"] == pytest.approx(1001.0, abs=0.01)

    native = api_client.get(
        "/api/v1/portfolio/summary",
        {
            "portfolio_id": portfolio.id,
            "include_timeseries": "false",
            "display_currency": "INR",
        },
    ).json()
    assert native["current_value"] == pytest.approx(100100.0, abs=0.01)


@pytest.mark.django_db
def test_bank_cash_fx_seven_day_boundaries(api_client, seeded, test_user, monkeypatch):
    today = _sunday()
    monkeypatch.setattr("portfolios.dates.current_date", lambda: today)
    portfolio = _inr_portfolio(test_user)
    bank = create_test_bank_account(user=test_user, portfolio=portfolio, currency="INR")
    _fund_for_portfolio(
        test_user, bank, portfolio, "50000", movement_date=today - timedelta(days=5)
    )
    _enable(test_user, bank)

    _fx(today - timedelta(days=7), "0.01")
    ok = api_client.get(
        "/api/v1/portfolio/summary",
        {"portfolio_id": portfolio.id, "include_timeseries": "false", "display_currency": "EUR"},
    ).json()
    assert ok["current_value"] == pytest.approx(500.0, abs=0.01)

    FXRate.objects.all().delete()
    _fx(today - timedelta(days=8), "0.01")
    stale = api_client.get(
        "/api/v1/portfolio/summary",
        {"portfolio_id": portfolio.id, "include_timeseries": "false", "display_currency": "EUR"},
    ).json()
    assert stale["current_value"] == pytest.approx(0.0, abs=0.01)
    assert any("FX unavailable for bank account" in w for w in stale.get("warnings", []))

    FXRate.objects.all().delete()
    _fx(today + timedelta(days=1), "0.01")
    future = api_client.get(
        "/api/v1/portfolio/summary",
        {"portfolio_id": portfolio.id, "include_timeseries": "false", "display_currency": "EUR"},
    ).json()
    assert future["current_value"] == pytest.approx(0.0, abs=0.01)

    FXRate.objects.all().delete()
    _fx(_friday(), "100", frm="EUR", to="INR")
    inverse = api_client.get(
        "/api/v1/portfolio/summary",
        {"portfolio_id": portfolio.id, "include_timeseries": "false", "display_currency": "EUR"},
    ).json()
    assert inverse["current_value"] == pytest.approx(500.0, abs=0.01)


@pytest.mark.django_db
def test_bank_cash_eligibility_and_once_only_all_scope(
    api_client, seeded, test_user, monkeypatch
):
    today = _sunday()
    monkeypatch.setattr("portfolios.dates.current_date", lambda: today)
    p1 = _inr_portfolio(test_user, name="P1")
    p2 = _inr_portfolio(test_user, name="P2")
    Portfolio.objects.filter(user=test_user).exclude(pk__in=[p1.id, p2.id]).update(
        is_active=False
    )

    excluded = create_test_bank_account(
        user=test_user, portfolio=p1, currency="INR", account_number="excl"
    )
    fund_bank_account(test_user, excluded, "90000", movement_date=today - timedelta(days=3))
    # Not opted in.

    shared = create_bank_account(
        test_user,
        name="Shared",
        institution_name="HDFC",
        account_number="shared-1",
        currency="INR",
    )
    fund_bank_account(test_user, shared, "40000", movement_date=today - timedelta(days=90))
    create_legacy_fixed_deposit_with_opening(
        test_user,
        portfolio=p1,
        bank=shared,
        deposit_account_number="A",
        principal_amount=Decimal("10000"),
        investment_date=today - timedelta(days=60),
        maturity_date=today + timedelta(days=300),
    )
    create_legacy_fixed_deposit_with_opening(
        test_user,
        portfolio=p2,
        bank=shared,
        deposit_account_number="B",
        principal_amount=Decimal("5000"),
        investment_date=today - timedelta(days=60),
        maturity_date=today + timedelta(days=300),
    )
    _enable(test_user, shared)
    _fx(today, "0.01")

    # Ambiguous shared bank is excluded from single-portfolio scopes.
    p1_data = api_client.get(
        "/api/v1/portfolio/summary",
        {"portfolio_id": p1.id, "include_timeseries": "false", "display_currency": "EUR"},
    ).json()
    assert p1_data["current_value"] == pytest.approx(100.0, abs=0.01)  # FD only

    all_data = api_client.get(
        "/api/v1/portfolio/summary",
        {"portfolio_scope": "all", "include_timeseries": "false", "display_currency": "EUR"},
    ).json()
    # FDs 15,000 + shared bank once (~25,000 remaining after openings) = 40,000 INR → 400 EUR
    # Opening debits: 10k + 5k from 40k funded = 25k bank + 15k FD = 40k
    assert all_data["current_value"] == pytest.approx(400.0, abs=0.01)

    # Excluded bank never appears.
    holdings = api_client.get(
        "/api/v1/portfolio/holdings",
        {"portfolio_scope": "all", "display_currency": "EUR"},
    ).json()
    bank_names = {
        h.get("bank_account_name") or h.get("asset_symbol")
        for h in holdings["holdings"]
        if h.get("asset_type") == "BANK_CASH"
    }
    assert "Shared" in bank_names or any("Shared" in (n or "") for n in bank_names)
    assert not any("excl" in (n or "").lower() for n in bank_names)


@pytest.mark.django_db
def test_bank_cash_projections_share_fx_but_use_distinct_balance_dates(test_user):
    as_of = _sunday()
    portfolio = _inr_portfolio(test_user)
    bank = create_test_bank_account(user=test_user, portfolio=portfolio, currency="INR")
    _fund_for_portfolio(test_user, bank, portfolio, "10000", movement_date=as_of)
    _fund_for_portfolio(
        test_user, bank, portfolio, "5000", movement_date=as_of + timedelta(days=1)
    )
    _enable(test_user, bank)
    scope = ResolvedPortfolioScope(kind="single", portfolio_ids=[portfolio.id])

    def projections():
        current = calculate_bank_cash_for_scope(
            test_user, scope, display_currency=" eur ", as_of_date=as_of
        )
        (holding,) = build_bank_cash_holding_rows(
            test_user, scope, display_currency=" eur ", as_of_date=as_of
        )
        (day,) = build_bank_cash_value_timeseries(
            test_user, scope, display_currency=" eur ", start_date=as_of, end_date=as_of
        )
        return current, holding, day

    _fx(as_of - timedelta(days=8))
    current, holding, day = projections()
    assert current.current_value == holding["current_value"] == day["bank_cash_value"] == 0
    assert current.any_fx_missing
    assert holding["fx_status"] == day["fx_status"] == "fx_unavailable"

    _fx(as_of - timedelta(days=7))
    current, holding, day = projections()
    assert current.current_value == holding["current_value"] == 150
    assert day["bank_cash_value"] == 100
    assert not current.any_fx_missing
    assert holding["display_currency"] == "EUR"
    assert holding["fx_status"] == day["fx_status"] == "ok"
