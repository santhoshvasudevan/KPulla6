"""All-scope value history must not drop to cancelled-FD or cash-only artifacts."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from cash.models import CashEntryType, CashLedgerEntry
from debt.models import CashMovementType, FixedDepositStatus
from debt.repair_services import repair_deactivated_fd_opening_by_id
from debt.services import create_bank_account, create_fixed_deposit, update_bank_account
from market_data.models import AssetType, HistoricalPrice
from portfolios.models import Portfolio
from portfolios.seed import ensure_default_portfolio
from tests.debt_test_helpers import fund_bank_account


FIXED_TODAY = date(2026, 6, 24)
FD_PRINCIPAL = Decimal("1109389")
STOCK_VALUE = 500_000.0


@pytest.fixture
def today_patch(monkeypatch):
    monkeypatch.setattr("portfolios.dates.current_date", lambda: FIXED_TODAY)
    return FIXED_TODAY


def _buy(api_client, portfolio_id, **kwargs):
    payload = {
        "portfolio_id": portfolio_id,
        "asset_symbol": kwargs.get("asset_symbol", "STKA"),
        "date": kwargs.get("date", "2024-01-15"),
        "type": "BUY",
        "quantity": kwargs.get("quantity", "100"),
        "price_per_share": kwargs.get("price_per_share", "5000"),
        "currency": kwargs.get("currency", "INR"),
        "fees": "0",
    }
    payload.update(kwargs)
    resp = api_client.post("/api/v1/transactions", payload, format="json")
    assert resp.status_code == 201, resp.content
    return resp


def _price(symbol: str, d: str, close: str, *, currency: str = "INR"):
    HistoricalPrice.objects.create(
        asset_symbol=symbol,
        date=date.fromisoformat(d),
        close_price=Decimal(close),
        currency=currency,
        source="test",
        asset_type=AssetType.STOCK,
    )


def _perf_values(api_client, **query):
    params = "metric=value&range=ALL&display_currency=INR"
    for key, val in query.items():
        params += f"&{key}={val}"
    payload = api_client.get(f"/api/v1/portfolio/performance?{params}").json()
    points = payload["points"] if isinstance(payload, dict) else payload
    return {p["date"]: p["value"] for p in points}


def _cash_deposit(portfolio, *, amount: str, day: str = "2023-09-24"):
    CashLedgerEntry.objects.create(
        portfolio=portfolio,
        date=date.fromisoformat(day),
        currency="INR",
        entry_type=CashEntryType.CASH_DEPOSIT,
        amount=Decimal(amount),
    )


def _bank(user, account_number: str):
    return create_bank_account(
        user,
        name="Savings",
        institution_name="HDFC",
        account_number=account_number,
        currency="INR",
    )


def _create_fd(user, portfolio_id, bank, **overrides):
    investment_date = overrides.pop("investment_date", date(2023, 9, 25))
    principal = overrides.pop("principal_amount", FD_PRINCIPAL)
    fund_bank_account(
        user,
        bank,
        principal + Decimal("50000"),
        movement_date=investment_date - timedelta(days=1),
    )
    payload = dict(
        portfolio_id=portfolio_id,
        bank_account_id=bank.id,
        institution_name="HDFC",
        deposit_account_number=overrides.pop("deposit_account_number", "FD-ALL-SCOPE"),
        principal_amount=principal,
        currency="INR",
        interest_rate_percent=Decimal("7"),
        interest_payout_frequency="QUARTERLY",
        investment_date=investment_date,
        maturity_date=overrides.pop("maturity_date", date(2026, 9, 25)),
    )
    payload.update(overrides)
    return create_fixed_deposit(user, **payload)


def _deactivate_pre_10a(fd):
    fd.is_active = False
    fd.save(update_fields=["is_active", "updated_at"])
    return fd


@pytest.mark.django_db
def test_cancelled_repaired_fd_excluded_from_all_scope_value_history(
    api_client, legacy_seeded, test_user, today_patch
):
    """Scenario A: repaired cancelled FD must not appear in all-scope value history."""
    p_stock = Portfolio.objects.create(
        user=test_user, name="Stocks", base_currency="INR", is_active=True
    )
    p_fd = Portfolio.objects.create(
        user=test_user, name="FD Portfolio", base_currency="INR", is_active=True
    )
    p_cash = Portfolio.objects.create(
        user=test_user, name="IndianInvestments", base_currency="INR", is_active=True
    )

    _buy(api_client, p_stock.id, asset_symbol="STKA")
    _price("STKA", "2024-01-15", "5000")
    _price("STKA", FIXED_TODAY.isoformat(), "5000")

    bank = _bank(test_user, "50300861349345")
    update_bank_account(test_user, bank.id, include_in_portfolio_value=True)
    fd = _create_fd(test_user, p_fd.id, bank)
    _deactivate_pre_10a(fd)
    repair_deactivated_fd_opening_by_id(fd.id)

    fd.refresh_from_db()
    assert fd.status == FixedDepositStatus.CANCELLED
    assert fd.is_active is False
    assert fd.cash_movements.filter(
        movement_type=CashMovementType.FD_OPENING_REVERSAL
    ).exists()

    _cash_deposit(p_cash, amount=str(int(FD_PRINCIPAL)))

    all_values = _perf_values(api_client, portfolio_scope="all")
    fd_portfolio_values = _perf_values(api_client, portfolio_id=p_fd.id)
    stock_values = _perf_values(api_client, portfolio_id=p_stock.id)

    assert not any(
        v is not None and abs(v - float(FD_PRINCIPAL)) < 1
        for v in all_values.values()
    ), "all-scope must not show cancelled FD principal as portfolio value"

    recent_all = [v for d, v in all_values.items() if d >= "2026-06-01" and v is not None]
    assert recent_all, "all-scope should have recent value points"
    assert max(recent_all) >= STOCK_VALUE, (
        "all-scope recent value should include stock holdings, not cash-only drop"
    )

    if fd_portfolio_values:
        assert max(v for v in fd_portfolio_values.values() if v is not None) < float(
            FD_PRINCIPAL
        ) or not any(
            abs(v - float(FD_PRINCIPAL)) < 1
            for v in fd_portfolio_values.values()
            if v is not None
        )

    stock_recent = [
        v for d, v in stock_values.items() if d >= "2026-06-01" and v is not None
    ]
    assert stock_recent and max(stock_recent) >= STOCK_VALUE


@pytest.mark.django_db
def test_all_scope_merge_does_not_drop_to_cash_only_when_child_fx_missing(
    api_client, legacy_seeded, test_user, today_patch
):
    """Scenario B: one child's FX-missing None must not collapse all-scope to broker cash."""
    p_inr = Portfolio.objects.create(
        user=test_user, name="INR Stocks", base_currency="INR", is_active=True
    )
    p_eur = Portfolio.objects.create(
        user=test_user, name="EUR Stocks", base_currency="EUR", is_active=True
    )
    p_cash = Portfolio.objects.create(
        user=test_user, name="Cash Holder", base_currency="INR", is_active=True
    )

    _buy(api_client, p_inr.id, asset_symbol="INFB", price_per_share="1000", quantity="500")
    _price("INFB", "2024-06-01", "1000")
    _price("INFB", FIXED_TODAY.isoformat(), "1000")

    _buy(
        api_client,
        p_eur.id,
        asset_symbol="SAPE",
        currency="EUR",
        price_per_share="100",
        quantity="10",
        date="2024-06-01",
    )
    _price("SAPE", "2024-06-01", "100", currency="USD")
    _price("SAPE", FIXED_TODAY.isoformat(), "100", currency="USD")

    _cash_deposit(p_cash, amount="200000", day="2024-06-01")

    all_values = _perf_values(api_client, portfolio_scope="all")
    recent = [
        (d, v) for d, v in all_values.items() if d >= "2026-06-01" and v is not None
    ]
    assert recent, "expected recent all-scope value points"
    for _day, val in recent:
        assert val >= 500_000.0, (
            "all-scope must not drop to broker-cash-only when another portfolio has FX gaps"
        )
        assert abs(val - 200_000.0) > 1, "all-scope must not equal cash-only portfolio value"


@pytest.mark.django_db
def test_active_fd_still_included_in_all_scope_value_history(
    api_client, legacy_seeded, test_user, today_patch
):
    """Scenario C: active FD principal must still appear in all-scope value history."""
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user, "active-fd-scope")
    fund_bank_account(test_user, bank, "500000")
    create_fixed_deposit(
        test_user,
        portfolio_id=portfolio.id,
        bank_account_id=bank.id,
        institution_name="HDFC",
        deposit_account_number="FD-ACTIVE",
        principal_amount=Decimal("75000"),
        currency="INR",
        interest_rate_percent=Decimal("7"),
        interest_payout_frequency="QUARTERLY",
        investment_date=date(2024, 1, 1),
        maturity_date=date(2026, 1, 1),
    )

    values = _perf_values(api_client, portfolio_scope="all")
    assert values.get("2024-01-01") == pytest.approx(75000.0, rel=1e-6)
    recent = [v for d, v in values.items() if d >= "2026-06-01" and v is not None]
    assert recent and max(recent) >= 75000.0
