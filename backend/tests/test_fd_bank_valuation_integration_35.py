"""#39 — Combined FD + bank-cash valuation consistency across summary/holdings/history."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from debt.bank_ledger_services import create_manual_cash_movement
from debt.services import create_bank_account, update_bank_account
from fx.models import FXRate
from market_data.models import HistoricalPrice
from portfolios.models import Portfolio
from tests.debt_test_helpers import (
    create_legacy_fixed_deposit_with_opening,
    create_test_bank_account,
)
from transactions.models import Transaction


TODAY = date(2026, 11, 22)  # Sunday


def _fx(day: date, rate="0.01", *, frm="INR", to="EUR") -> None:
    FXRate.objects.update_or_create(
        from_currency=frm, to_currency=to, date=day, defaults={"rate": Decimal(rate)}
    )


def _portfolio(user, name, base="INR") -> Portfolio:
    return Portfolio.objects.create(
        user=user, name=name, base_currency=base, is_active=True, cash_aware_enabled=False
    )


def _stock(portfolio, symbol, amount, as_of=TODAY):
    Transaction.objects.create(
        portfolio=portfolio,
        date=as_of - timedelta(days=40),
        type="BUY",
        asset_symbol=symbol,
        quantity=Decimal("1"),
        price_per_share=Decimal(amount),
        currency="INR",
        fees=Decimal("0"),
    )
    for day in (as_of - timedelta(days=40), as_of):
        HistoricalPrice.objects.update_or_create(
            asset_symbol=symbol,
            date=day,
            defaults={"close_price": Decimal(amount), "currency": "INR", "asset_type": "STOCK"},
        )


@pytest.mark.django_db
def test_combined_components_reconcile_before_headline_history_parity(
    api_client, seeded, test_user, monkeypatch
):
    monkeypatch.setattr("portfolios.dates.current_date", lambda: TODAY)
    p_inr = _portfolio(test_user, "INR Core")
    p_eur = _portfolio(test_user, "EUR Side", base="EUR")
    Portfolio.objects.filter(user=test_user).exclude(pk__in=[p_inr.id, p_eur.id]).update(
        is_active=False
    )

    _stock(p_inr, "RELIANCE", "100")
    bank_included = create_test_bank_account(
        user=test_user, portfolio=p_inr, currency="INR", account_number="inc-1"
    )
    create_manual_cash_movement(
        test_user,
        bank_account_id=bank_included.id,
        movement_type="MANUAL_DEPOSIT",
        amount=Decimal("200000"),
        movement_date=TODAY - timedelta(days=90),
        portfolio_id=p_inr.id,
    )
    create_legacy_fixed_deposit_with_opening(
        test_user,
        portfolio=p_inr,
        bank=bank_included,
        deposit_account_number="FD-A",
        principal_amount=Decimal("100000"),
        investment_date=TODAY - timedelta(days=60),
        maturity_date=TODAY + timedelta(days=300),
    )
    create_legacy_fixed_deposit_with_opening(
        test_user,
        portfolio=p_inr,
        bank=bank_included,
        deposit_account_number="FD-B",
        principal_amount=Decimal("50000"),
        investment_date=TODAY - timedelta(days=50),
        maturity_date=TODAY + timedelta(days=300),
    )
    update_bank_account(test_user, bank_included.id, include_in_portfolio_value=True)

    excluded = create_test_bank_account(
        user=test_user, portfolio=p_inr, currency="INR", account_number="excl-1"
    )
    create_manual_cash_movement(
        test_user,
        bank_account_id=excluded.id,
        movement_type="MANUAL_DEPOSIT",
        amount=Decimal("99999"),
        movement_date=TODAY - timedelta(days=20),
        portfolio_id=p_inr.id,
    )
    # leave include_in_portfolio_value=False

    # Shared ambiguous bank across portfolios — excluded from single scopes, once in all.
    shared = create_bank_account(
        test_user, name="Shared", institution_name="HDFC", account_number="shared-x",
        currency="INR",
    )
    create_manual_cash_movement(
        test_user,
        bank_account_id=shared.id,
        movement_type="MANUAL_DEPOSIT",
        amount=Decimal("30000"),
        movement_date=TODAY - timedelta(days=90),
    )
    create_legacy_fixed_deposit_with_opening(
        test_user, portfolio=p_inr, bank=shared, deposit_account_number="S1",
        principal_amount=Decimal("10000"),
        investment_date=TODAY - timedelta(days=40),
        maturity_date=TODAY + timedelta(days=200),
    )
    create_legacy_fixed_deposit_with_opening(
        test_user, portfolio=p_eur, bank=shared, deposit_account_number="S2",
        principal_amount=Decimal("5000"),
        investment_date=TODAY - timedelta(days=40),
        maturity_date=TODAY + timedelta(days=200),
    )
    update_bank_account(test_user, shared.id, include_in_portfolio_value=True)

    _fx(date(2026, 11, 20), "0.01")  # Friday before Sunday

    # Component oracle for p_inr single scope (shared bank excluded; shared FD on p_inr included):
    # stock 100 + FD-A 100000 + FD-B 50000 + FD-S1 10000 + bank_included remaining
    # openings from bank_included: 100000+50000; funded 200000 → remaining 50000
    # total INR = 100 + 160000 + 50000 = 210100 → EUR 2101
    summary = api_client.get(
        "/api/v1/portfolio/summary",
        {"portfolio_id": p_inr.id, "include_timeseries": "true", "display_currency": "EUR"},
    ).json()
    holdings = api_client.get(
        "/api/v1/portfolio/holdings",
        {"portfolio_id": p_inr.id, "display_currency": "EUR"},
    ).json()

    fd_rows = [h for h in holdings["holdings"] if h.get("asset_type") == "FIXED_DEPOSIT"]
    bank_rows = [h for h in holdings["holdings"] if h.get("asset_type") == "BANK_CASH"]
    assert sum(h["current_value"] for h in fd_rows) == pytest.approx(1600.0, abs=0.05)
    assert sum(h["current_value"] for h in bank_rows) == pytest.approx(500.0, abs=0.05)
    assert all(h.get("bank_account_name") != "Shared" for h in bank_rows)
    assert not any(h.get("account_number") == "excl-1" for h in bank_rows)

    debt = next(b for b in summary["allocation_buckets"]["buckets"] if b["label"] == "Debt")
    cash = next(b for b in summary["allocation_buckets"]["buckets"] if "Cash" in b["label"])
    assert debt["value"] == pytest.approx(1600.0, abs=0.05)
    assert cash["value"] == pytest.approx(500.0, abs=0.05)
    assert summary["current_value"] == pytest.approx(2101.0, abs=0.05)

    latest = summary["timeseries"][-1]
    assert latest["date"] == TODAY.isoformat()
    assert latest["portfolio_value"] == pytest.approx(summary["current_value"], abs=0.05)

    native = api_client.get(
        "/api/v1/portfolio/summary",
        {"portfolio_id": p_inr.id, "include_timeseries": "false", "display_currency": "INR"},
    ).json()
    assert native["current_value"] == pytest.approx(210100.0, abs=0.05)

    all_summary = api_client.get(
        "/api/v1/portfolio/summary",
        {"portfolio_scope": "all", "include_timeseries": "false", "display_currency": "EUR"},
    ).json()
    # p_inr 210100 + p_eur shared FD 5000 + shared bank once remaining 15000
    # = 210100 + 5000 + 15000 = 230100 → EUR 2301
    assert all_summary["current_value"] == pytest.approx(2301.0, abs=0.05)

    # Genuine unavailable: wipe FX → warnings, do not invent coverage.
    FXRate.objects.all().delete()
    missing = api_client.get(
        "/api/v1/portfolio/summary",
        {"portfolio_id": p_inr.id, "include_timeseries": "false", "display_currency": "EUR"},
    ).json()
    assert missing["current_value"] == pytest.approx(0.0, abs=0.05) or missing.get("fx_status") == "fx_unavailable"
    assert missing.get("warnings")
