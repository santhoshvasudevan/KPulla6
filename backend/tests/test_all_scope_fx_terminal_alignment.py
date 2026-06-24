"""All-scope performance terminal value must align with summary for same currency."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from cash.models import CashEntryType, CashLedgerEntry
from debt.models import CashMovementType, FixedDepositStatus
from debt.repair_services import repair_deactivated_fd_opening_by_id
from debt.services import create_bank_account, create_fixed_deposit, update_bank_account
from fx.services import upsert_fx_rate
from market_data.models import AssetType, HistoricalPrice
from portfolios.models import Portfolio
from portfolios.seed import ensure_default_portfolio
from tests.debt_test_helpers import fund_bank_account


FIXED_TODAY = date(2026, 6, 24)


@pytest.fixture
def today_patch(monkeypatch):
    monkeypatch.setattr("portfolios.dates.current_date", lambda: FIXED_TODAY)
    return FIXED_TODAY


def _buy(api_client, portfolio_id, **kwargs):
    payload = {
        "portfolio_id": portfolio_id,
        "asset_symbol": kwargs.get("asset_symbol", "ALN1"),
        "date": kwargs.get("date", "2024-06-01"),
        "type": "BUY",
        "quantity": kwargs.get("quantity", "10"),
        "price_per_share": kwargs.get("price_per_share", "100"),
        "currency": kwargs.get("currency", "EUR"),
        "fees": "0",
    }
    payload.update(kwargs)
    resp = api_client.post("/api/v1/transactions", payload, format="json")
    assert resp.status_code == 201, resp.content
    return resp


def _price(symbol: str, d: str, close: str, *, currency: str = "EUR"):
    HistoricalPrice.objects.create(
        asset_symbol=symbol,
        date=date.fromisoformat(d),
        close_price=Decimal(close),
        currency=currency,
        source="test",
        asset_type=AssetType.STOCK,
    )


def _summary_value(api_client, **query):
    params = "include_timeseries=false"
    for key, val in query.items():
        params += f"&{key}={val}"
    return api_client.get(f"/api/v1/portfolio/summary?{params}").json()


def _last_perf_value(api_client, **query):
    params = "metric=value&range=ALL"
    for key, val in query.items():
        params += f"&{key}={val}"
    points = api_client.get(f"/api/v1/portfolio/performance?{params}").json()
    valid = [p["value"] for p in points if p.get("value") is not None]
    assert valid, "expected at least one performance value point"
    return valid[-1]


def _seed_inverse_only_inr_eur_rates():
    """Mirror production: recent INR->EUR rows without direct EUR->INR rows."""
    for offset, rate in [(0, "0.0108"), (1, "0.0109"), (2, "0.0107"), (3, "0.0106")]:
        d = FIXED_TODAY - timedelta(days=offset)
        upsert_fx_rate(
            from_currency="INR",
            to_currency="EUR",
            row_date=d,
            rate=Decimal(rate),
        )


@pytest.mark.django_db
def test_all_scope_inr_terminal_performance_matches_summary(
    api_client, legacy_seeded, test_user, today_patch
):
    """Terminal INR value history must include EUR portfolio via inverse FX rows."""
    _seed_inverse_only_inr_eur_rates()

    eur_portfolio = Portfolio.objects.create(
        user=test_user, name="EUR Holdings", base_currency="EUR", is_active=True
    )
    inr_portfolio = Portfolio.objects.create(
        user=test_user, name="INR Holdings", base_currency="INR", is_active=True
    )

    _buy(api_client, eur_portfolio.id, asset_symbol="EURSTK", quantity="100", price_per_share="50")
    _buy(
        api_client,
        inr_portfolio.id,
        asset_symbol="INRSTK",
        currency="INR",
        quantity="200",
        price_per_share="1000",
    )
    _price("EURSTK", "2024-06-01", "50")
    _price("EURSTK", FIXED_TODAY.isoformat(), "60")
    _price("INRSTK", "2024-06-01", "1000", currency="INR")
    _price("INRSTK", FIXED_TODAY.isoformat(), "1000", currency="INR")

    summary = _summary_value(
        api_client, portfolio_scope="all", display_currency="INR"
    )["current_value"]
    last_perf = _last_perf_value(
        api_client, portfolio_scope="all", display_currency="INR"
    )

    assert summary == pytest.approx(last_perf, rel=1e-4, abs=1.0)
    assert summary > 500_000.0


@pytest.mark.django_db
def test_all_scope_eur_and_inr_both_align_with_summary(
    api_client, legacy_seeded, test_user, today_patch
):
    _seed_inverse_only_inr_eur_rates()

    eur_portfolio = Portfolio.objects.create(
        user=test_user, name="EUR Mix", base_currency="EUR", is_active=True
    )
    inr_portfolio = Portfolio.objects.create(
        user=test_user, name="INR Mix", base_currency="INR", is_active=True
    )

    _buy(api_client, eur_portfolio.id, asset_symbol="EMIX", quantity="20", price_per_share="80")
    _buy(
        api_client,
        inr_portfolio.id,
        asset_symbol="IMIX",
        currency="INR",
        quantity="50",
        price_per_share="2000",
    )
    _price("EMIX", "2024-06-01", "80")
    _price("EMIX", FIXED_TODAY.isoformat(), "85")
    _price("IMIX", "2024-06-01", "2000", currency="INR")
    _price("IMIX", FIXED_TODAY.isoformat(), "2000", currency="INR")

    for ccy in ("EUR", "INR"):
        summary = _summary_value(
            api_client, portfolio_scope="all", display_currency=ccy
        )["current_value"]
        last_perf = _last_perf_value(
            api_client, portfolio_scope="all", display_currency=ccy
        )
        assert summary == pytest.approx(last_perf, rel=1e-4, abs=1.0), ccy


@pytest.mark.django_db
def test_all_scope_inr_historical_fx_gap_does_not_substitute_cash_only(
    api_client, legacy_seeded, test_user, today_patch
):
    """Historical partial/null is allowed; terminal must still match summary."""
    eur_portfolio = Portfolio.objects.create(
        user=test_user, name="EUR Gap", base_currency="EUR", is_active=True
    )
    cash_portfolio = Portfolio.objects.create(
        user=test_user, name="INR Cash", base_currency="INR", is_active=True
    )

    _buy(api_client, eur_portfolio.id, asset_symbol="GAP1", quantity="10", price_per_share="100")
    _price("GAP1", "2024-06-01", "100")
    _price("GAP1", FIXED_TODAY.isoformat(), "100")

    CashLedgerEntry.objects.create(
        portfolio=cash_portfolio,
        date=date(2024, 6, 1),
        currency="INR",
        entry_type=CashEntryType.CASH_DEPOSIT,
        amount=Decimal("250000"),
    )

    # No FX on buy date; terminal rates only.
    upsert_fx_rate(
        from_currency="INR",
        to_currency="EUR",
        row_date=FIXED_TODAY,
        rate=Decimal("0.011"),
    )

    summary = _summary_value(
        api_client, portfolio_scope="all", display_currency="INR"
    )["current_value"]
    last_perf = _last_perf_value(
        api_client, portfolio_scope="all", display_currency="INR"
    )
    assert summary == pytest.approx(last_perf, rel=1e-4, abs=1.0)
    assert last_perf > 250_000.0


@pytest.mark.django_db
def test_cancelled_fd_still_excluded_from_all_scope_inr_terminal(
    api_client, seeded, test_user, today_patch
):
    principal = Decimal("1109389")
    p_stock = Portfolio.objects.create(
        user=test_user, name="Stocks", base_currency="INR", is_active=True
    )
    p_fd = Portfolio.objects.create(
        user=test_user, name="FD", base_currency="INR", is_active=True
    )

    _buy(
        api_client,
        p_stock.id,
        asset_symbol="REG",
        currency="INR",
        quantity="100",
        price_per_share="5000",
    )
    _price("REG", "2024-01-15", "5000", currency="INR")
    _price("REG", FIXED_TODAY.isoformat(), "5000", currency="INR")

    bank = create_bank_account(
        user=test_user,
        name="Savings",
        institution_name="HDFC",
        account_number="align-fd",
        currency="INR",
        portfolio_id=p_fd.id,
    )
    fund_bank_account(
        test_user,
        bank,
        principal + Decimal("50000"),
        movement_date=date(2023, 9, 24),
    )
    fd = create_fixed_deposit(
        test_user,
        portfolio_id=p_fd.id,
        bank_account_id=bank.id,
        institution_name="HDFC",
        deposit_account_number="FD-ALIGN",
        principal_amount=principal,
        currency="INR",
        interest_rate_percent=Decimal("7"),
        interest_payout_frequency="QUARTERLY",
        investment_date=date(2023, 9, 25),
        maturity_date=date(2026, 9, 25),
    )
    fd.is_active = False
    fd.save(update_fields=["is_active", "updated_at"])
    repair_deactivated_fd_opening_by_id(fd.id)
    fd.refresh_from_db()
    assert fd.status == FixedDepositStatus.CANCELLED

    perf = api_client.get(
        "/api/v1/portfolio/performance?portfolio_scope=all&metric=value&range=ALL&display_currency=INR"
    ).json()
    assert not any(
        p.get("value") is not None and abs(p["value"] - float(principal)) < 1
        for p in perf
    )
