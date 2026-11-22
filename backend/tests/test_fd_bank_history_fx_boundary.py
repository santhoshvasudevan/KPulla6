"""#38 — Eligible FX before the first emitted history date must remain usable."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from debt.bank_ledger_services import create_manual_cash_movement
from debt.portfolio_value import FD_BANK_FX_VALUE_HISTORY_WARNING
from debt.services import update_bank_account
from fx.models import FXRate
from portfolios.models import Portfolio
from tests.debt_test_helpers import (
    create_legacy_fixed_deposit_with_opening,
    create_test_bank_account,
)


def _sunday() -> date:
    return date(2026, 11, 22)


def _fx(day: date, rate="0.01", *, frm="INR", to="EUR") -> None:
    FXRate.objects.update_or_create(
        from_currency=frm,
        to_currency=to,
        date=day,
        defaults={"rate": Decimal(rate)},
    )


def _perf_body(client, **params):
    query = {"metric": "value", "display_currency": "EUR", **params}
    response = client.get("/api/v1/portfolio/performance", query)
    assert response.status_code == 200, response.json()
    body = response.json()
    if isinstance(body, dict) and "points" in body:
        return body
    return {"points": body, "warnings": []}


def _perf(client, **params):
    return _perf_body(client, **params)["points"]


def _point_map(points):
    out = {}
    for p in points:
        if isinstance(p, dict):
            out[p["date"]] = p.get("value")
        else:
            out[p.date] = p.value
    return out


@pytest.mark.django_db
def test_fd_history_uses_fx_before_bounded_range_start(
    api_client, seeded, test_user, monkeypatch
):
    today = _sunday()
    monkeypatch.setattr("portfolios.dates.current_date", lambda: today)
    portfolio = Portfolio.objects.create(
        user=test_user, name="FD Hist", base_currency="INR", is_active=True,
        cash_aware_enabled=False,
    )
    Portfolio.objects.filter(user=test_user).exclude(pk=portfolio.id).update(is_active=False)
    bank = create_test_bank_account(user=test_user, portfolio=portfolio, currency="INR")
    create_manual_cash_movement(
        test_user,
        bank_account_id=bank.id,
        movement_type="MANUAL_DEPOSIT",
        amount=Decimal("150000"),
        movement_date=today - timedelta(days=40),
        portfolio_id=portfolio.id,
    )
    create_legacy_fixed_deposit_with_opening(
        test_user,
        portfolio=portfolio,
        bank=bank,
        principal_amount=Decimal("100000"),
        investment_date=today - timedelta(days=30),
        maturity_date=today + timedelta(days=300),
    )
    # FX only on the Friday before a Monday range start (within 7-day lookback).
    range_start = date(2026, 11, 16)  # Monday
    _fx(date(2026, 11, 13), "0.01")  # Friday before range

    all_body = _perf_body(api_client, portfolio_id=portfolio.id, range="ALL")
    bounded_body = _perf_body(api_client, portfolio_id=portfolio.id, range="7D")
    all_points = _point_map(all_body["points"])
    bounded = _point_map(bounded_body["points"])
    assert range_start.isoformat() in bounded
    assert bounded[range_start.isoformat()] == pytest.approx(1000.0, abs=0.01)
    assert all_points[range_start.isoformat()] == pytest.approx(
        bounded[range_start.isoformat()], abs=0.01
    )
    # Non-terminal overlapping day must also agree (not only chart end).
    mid = date(2026, 11, 18).isoformat()
    assert bounded[mid] == pytest.approx(all_points[mid], abs=0.01)
    assert bounded[mid] == pytest.approx(1000.0, abs=0.01)
    # Complete 7D coverage: rate on range opening keeps every day within lookback.
    FXRate.objects.all().delete()
    _fx(date(2026, 11, 15), "0.01")
    covered = _perf_body(api_client, portfolio_id=portfolio.id, range="7D")
    covered_points = _point_map(covered["points"])
    assert covered_points[range_start.isoformat()] == pytest.approx(1000.0, abs=0.01)
    assert covered_points[today.isoformat()] == pytest.approx(1000.0, abs=0.01)
    assert FD_BANK_FX_VALUE_HISTORY_WARNING not in covered.get("warnings", [])


@pytest.mark.django_db
def test_bank_cash_history_opening_lookback_and_boundaries(
    api_client, seeded, test_user, monkeypatch
):
    today = _sunday()
    monkeypatch.setattr("portfolios.dates.current_date", lambda: today)
    portfolio = Portfolio.objects.create(
        user=test_user, name="Bank Hist", base_currency="INR", is_active=True,
        cash_aware_enabled=False,
    )
    Portfolio.objects.filter(user=test_user).exclude(pk=portfolio.id).update(is_active=False)
    bank = create_test_bank_account(user=test_user, portfolio=portfolio, currency="INR")
    create_manual_cash_movement(
        test_user,
        bank_account_id=bank.id,
        movement_type="MANUAL_DEPOSIT",
        amount=Decimal("50000"),
        movement_date=today - timedelta(days=20),
        portfolio_id=portfolio.id,
    )
    update_bank_account(test_user, bank.id, include_in_portfolio_value=True)

    range_start = date(2026, 11, 16)
    opening = range_start.isoformat()

    # Opening-day lookback: Friday before Monday remains usable for that day.
    _fx(date(2026, 11, 13), "0.01")
    opening_body = _perf_body(api_client, portfolio_id=portfolio.id, range="7D")
    opening_points = _point_map(opening_body["points"])
    assert opening_points[opening] == pytest.approx(500.0, abs=0.01)

    # Complete 7D coverage — no FD/bank FX history warning.
    FXRate.objects.all().delete()
    _fx(date(2026, 11, 15), "0.01")
    covered_body = _perf_body(api_client, portfolio_id=portfolio.id, range="7D")
    covered_points = _point_map(covered_body["points"])
    assert covered_points[opening] == pytest.approx(500.0, abs=0.01)
    assert covered_points[today.isoformat()] == pytest.approx(500.0, abs=0.01)
    assert FD_BANK_FX_VALUE_HISTORY_WARNING not in covered_body.get("warnings", [])

    FXRate.objects.all().delete()
    _fx(range_start - timedelta(days=8), "0.01")
    stale_body = _perf_body(api_client, portfolio_id=portfolio.id, range="7D")
    stale = _point_map(stale_body["points"])
    # Stale FX (>7d before opening): monetary opening must not use that rate.
    opening_stale = stale.get(opening)
    assert opening_stale is None or opening_stale == pytest.approx(0.0, abs=0.01)
    assert FD_BANK_FX_VALUE_HISTORY_WARNING in stale_body.get("warnings", [])

    FXRate.objects.all().delete()
    _fx(range_start + timedelta(days=1), "0.01")  # future relative to opening day
    # Opening day must not use a later observation.
    future_body = _perf_body(api_client, portfolio_id=portfolio.id, range="7D")
    future_only = _point_map(future_body["points"])
    opening_val = future_only.get(opening)
    assert opening_val is None or opening_val == pytest.approx(0.0, abs=0.01)
    assert FD_BANK_FX_VALUE_HISTORY_WARNING in future_body.get("warnings", [])


@pytest.mark.django_db
def test_mixed_history_native_equals_display_and_all_scope(
    api_client, seeded, test_user, monkeypatch
):
    today = _sunday()
    monkeypatch.setattr("portfolios.dates.current_date", lambda: today)
    portfolio = Portfolio.objects.create(
        user=test_user, name="Mixed Hist", base_currency="INR", is_active=True,
        cash_aware_enabled=False,
    )
    Portfolio.objects.filter(user=test_user).exclude(pk=portfolio.id).update(is_active=False)
    bank = create_test_bank_account(user=test_user, portfolio=portfolio, currency="INR")
    create_manual_cash_movement(
        test_user,
        bank_account_id=bank.id,
        movement_type="MANUAL_DEPOSIT",
        amount=Decimal("150000"),
        movement_date=today - timedelta(days=40),
        portfolio_id=portfolio.id,
    )
    create_legacy_fixed_deposit_with_opening(
        test_user,
        portfolio=portfolio,
        bank=bank,
        principal_amount=Decimal("100000"),
        investment_date=today - timedelta(days=30),
        maturity_date=today + timedelta(days=300),
    )
    update_bank_account(test_user, bank.id, include_in_portfolio_value=True)
    # Remaining bank after FD opening: 50,000; FD: 100,000 → 150,000 INR
    native = _point_map(
        _perf(
            api_client,
            portfolio_id=portfolio.id,
            range="7D",
            display_currency="INR",
        )
    )
    assert native[date(2026, 11, 16).isoformat()] == pytest.approx(150000.0, abs=0.01)

    _fx(date(2026, 11, 13), "0.01")
    single = _point_map(_perf(api_client, portfolio_id=portfolio.id, range="7D"))
    all_scope = _point_map(
        _perf(api_client, portfolio_scope="all", range="7D")
    )
    assert single[date(2026, 11, 16).isoformat()] == pytest.approx(1500.0, abs=0.01)
    assert all_scope[date(2026, 11, 16).isoformat()] == pytest.approx(1500.0, abs=0.01)
