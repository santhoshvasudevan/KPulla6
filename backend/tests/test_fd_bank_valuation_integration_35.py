"""#39 — Combined FD + bank-cash valuation consistency across summary/holdings/history.

Uses real investment transactions to establish distinct portfolio valuation currencies
(INR vs EUR), synthetic broker-cash ledger balances, FDs, and opted-in bank cash.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from cash.models import CashEntryType, CashLedgerEntry
from debt.bank_ledger_services import create_manual_cash_movement
from debt.portfolio_value import FD_BANK_FX_VALUE_HISTORY_WARNING
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


def _buy(portfolio, symbol, *, amount, currency, as_of=TODAY):
    """Create a BUY that establishes portfolio valuation currency via transaction currency."""
    Transaction.objects.create(
        portfolio=portfolio,
        date=as_of - timedelta(days=40),
        type="BUY",
        asset_symbol=symbol,
        quantity=Decimal("1"),
        price_per_share=Decimal(amount),
        currency=currency,
        fees=Decimal("0"),
    )
    for day in (as_of - timedelta(days=40), as_of):
        HistoricalPrice.objects.update_or_create(
            asset_symbol=symbol,
            date=day,
            defaults={
                "close_price": Decimal(amount),
                "currency": currency,
                "asset_type": "STOCK",
            },
        )


def _broker_cash(portfolio, *, amount, currency, day=None):
    CashLedgerEntry.objects.create(
        portfolio=portfolio,
        date=day or (TODAY - timedelta(days=30)),
        currency=currency,
        entry_type=CashEntryType.CASH_DEPOSIT,
        amount=Decimal(amount),
    )


def _perf_body(client, **params):
    query = {"metric": "value", "display_currency": "EUR", **params}
    response = client.get("/api/v1/portfolio/performance", query)
    assert response.status_code == 200, response.json()
    body = response.json()
    if isinstance(body, dict) and "points" in body:
        return body
    return {"points": body, "warnings": []}


@pytest.mark.django_db
def test_combined_components_reconcile_before_headline_history_parity(
    api_client, seeded, test_user, monkeypatch
):
    monkeypatch.setattr("portfolios.dates.current_date", lambda: TODAY)
    # Distinct valuation currencies come from investment transaction currencies,
    # not portfolio label alone.
    p_inr = _portfolio(test_user, "INR Core")
    p_eur = _portfolio(test_user, "EUR Side", base="EUR")
    Portfolio.objects.filter(user=test_user).exclude(pk__in=[p_inr.id, p_eur.id]).update(
        is_active=False
    )

    _buy(p_inr, "RELIANCE", amount="100", currency="INR")
    _buy(p_eur, "SAP", amount="200", currency="EUR")
    _broker_cash(p_inr, amount="10000", currency="INR")
    _broker_cash(p_eur, amount="50", currency="EUR")

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

    shared = create_bank_account(
        test_user,
        name="Shared",
        institution_name="HDFC",
        account_number="shared-x",
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
        test_user,
        portfolio=p_inr,
        bank=shared,
        deposit_account_number="S1",
        principal_amount=Decimal("10000"),
        investment_date=TODAY - timedelta(days=40),
        maturity_date=TODAY + timedelta(days=200),
    )
    create_legacy_fixed_deposit_with_opening(
        test_user,
        portfolio=p_eur,
        bank=shared,
        deposit_account_number="S2",
        principal_amount=Decimal("5000"),
        investment_date=TODAY - timedelta(days=40),
        maturity_date=TODAY + timedelta(days=200),
    )
    update_bank_account(test_user, shared.id, include_in_portfolio_value=True)

    _fx(date(2026, 11, 20), "0.01")  # Friday before Sunday

    # --- Single INR portfolio (shared bank excluded; shared FD S1 included) ---
    # Components in INR before FX:
    #   stock 100 + broker 10000 + FD 160000 + bank remaining 50000 = 220100
    # EUR @ 0.01 → 2201
    summary = api_client.get(
        "/api/v1/portfolio/summary",
        {"portfolio_id": p_inr.id, "include_timeseries": "true", "display_currency": "EUR"},
    ).json()
    holdings = api_client.get(
        "/api/v1/portfolio/holdings",
        {"portfolio_id": p_inr.id, "display_currency": "EUR"},
    ).json()

    assert summary["base_currency"] == "INR"
    assert summary["display_currency"] == "EUR"
    assert summary["fx_status"] in {"ok", "filled"}

    fd_rows = [h for h in holdings["holdings"] if h.get("asset_type") == "FIXED_DEPOSIT"]
    bank_rows = [h for h in holdings["holdings"] if h.get("asset_type") == "BANK_CASH"]
    assert sum(h["current_value"] for h in fd_rows) == pytest.approx(1600.0, abs=0.05)
    assert sum(h["current_value"] for h in bank_rows) == pytest.approx(500.0, abs=0.05)
    assert all(h.get("bank_account_name") != "Shared" for h in bank_rows)
    assert not any(h.get("account_number") == "excl-1" for h in bank_rows)

    debt = next(b for b in summary["allocation_buckets"]["buckets"] if b["label"] == "Debt")
    cash = next(b for b in summary["allocation_buckets"]["buckets"] if "Cash" in b["label"])
    other = next(b for b in summary["allocation_buckets"]["buckets"] if b["label"] == "Other")
    equity = next(b for b in summary["allocation_buckets"]["buckets"] if b["label"] == "Equity")
    assert equity["value"] == pytest.approx(1.0, abs=0.05)
    assert debt["value"] == pytest.approx(1600.0, abs=0.05)
    # Bank cash lands in Cash; broker cash remains in Other under legacy allocation.
    assert cash["value"] == pytest.approx(500.0, abs=0.05)
    assert other["value"] == pytest.approx(100.0, abs=0.05)
    assert summary["current_value"] == pytest.approx(2201.0, abs=0.05)
    assert summary["cash_summary"]["total_display_value"] == pytest.approx(100.0, abs=0.05)

    latest = summary["timeseries"][-1]
    assert latest["date"] == TODAY.isoformat()
    assert latest["portfolio_value"] == pytest.approx(summary["current_value"], abs=0.05)

    # ALL history spans pre-FX days; assert same-date latest parity, not warning absence.
    hist = _perf_body(api_client, portfolio_id=p_inr.id, range="ALL")
    hist_latest = hist["points"][-1]
    assert hist_latest["date"] == TODAY.isoformat()
    assert hist_latest["value"] == pytest.approx(summary["current_value"], abs=0.05)

    # Recent window with complete eligible FX must omit the FD/bank history warning.
    FXRate.objects.update_or_create(
        from_currency="INR",
        to_currency="EUR",
        date=date(2026, 11, 15),
        defaults={"rate": Decimal("0.01")},
    )
    recent = _perf_body(api_client, portfolio_id=p_inr.id, range="7D")
    assert recent["points"][-1]["value"] == pytest.approx(summary["current_value"], abs=0.05)
    assert FD_BANK_FX_VALUE_HISTORY_WARNING not in recent.get("warnings", [])

    native = api_client.get(
        "/api/v1/portfolio/summary",
        {"portfolio_id": p_inr.id, "include_timeseries": "false", "display_currency": "INR"},
    ).json()
    assert native["current_value"] == pytest.approx(220100.0, abs=0.05)
    assert native["fx_status"] in {"ok", "filled"}

    # --- Single EUR portfolio: EUR stock + EUR broker + INR shared FD ---
    # EUR native: stock 200 + broker 50 = 250; FD S2 5000 INR → 50 EUR; total 300
    eur_summary = api_client.get(
        "/api/v1/portfolio/summary",
        {"portfolio_id": p_eur.id, "include_timeseries": "true", "display_currency": "EUR"},
    ).json()
    assert eur_summary["base_currency"] == "EUR"
    assert eur_summary["current_value"] == pytest.approx(300.0, abs=0.05)
    eur_latest = eur_summary["timeseries"][-1]
    assert eur_latest["date"] == TODAY.isoformat()
    assert eur_latest["portfolio_value"] == pytest.approx(300.0, abs=0.05)

    # --- All Portfolios ---
    # Children (no bank): p_inr stock+broker+FD = 100+10000+160000 = 170100 → 1701 EUR
    #                    p_eur stock+broker+FD = 200+50+50 = 300 EUR
    # Bank once: included remaining 50000 + shared remaining 15000 = 65000 → 650 EUR
    # Total = 1701 + 300 + 650 = 2651
    all_summary = api_client.get(
        "/api/v1/portfolio/summary",
        {
            "portfolio_scope": "all",
            "include_timeseries": "true",
            "display_currency": "EUR",
        },
    ).json()
    assert all_summary["current_value"] == pytest.approx(2651.0, abs=0.05)
    all_latest = all_summary["timeseries"][-1]
    assert all_latest["date"] == TODAY.isoformat()
    assert all_latest["portfolio_value"] == pytest.approx(all_summary["current_value"], abs=0.05)

    all_hist = _perf_body(api_client, portfolio_scope="all", range="ALL")
    assert all_hist["points"][-1]["date"] == TODAY.isoformat()
    assert all_hist["points"][-1]["value"] == pytest.approx(2651.0, abs=0.05)

    # Genuine unavailable: wipe FX. Preserve investment compatibility fallback
    # (unconverted investment amount kept) while FD/bank omit missing conversions.
    FXRate.objects.all().delete()
    missing = api_client.get(
        "/api/v1/portfolio/summary",
        {"portfolio_id": p_inr.id, "include_timeseries": "false", "display_currency": "EUR"},
    ).json()
    assert missing["fx_status"] == "fx_unavailable"
    # Investment 100 INR kept via compatibility fallback; broker cash INR→EUR fails → 0;
    # FD/bank omitted when FX missing → contribute 0.
    assert missing["current_value"] == pytest.approx(100.0, abs=0.05)
    assert any("FX unavailable" in w for w in missing["warnings"])
    assert any("bank" in w.lower() or "fixed deposit" in w.lower() or "FX" in w
               for w in missing["warnings"])

    missing_hist = _perf_body(api_client, portfolio_id=p_inr.id, range="7D")
    assert FD_BANK_FX_VALUE_HISTORY_WARNING in missing_hist.get("warnings", [])
