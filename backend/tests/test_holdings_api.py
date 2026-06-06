from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from cash.models import CashEntryType, CashLedgerEntry
from fx.services import upsert_fx_rate
from market_data.models import AssetType, HistoricalPrice
from portfolios.models import Portfolio
from portfolios.seed import ensure_default_portfolio
from transactions.models import Transaction, TransactionType


def _buy(api_client, **kwargs):
    payload = {
        "asset_symbol": "AAPL",
        "date": "2026-01-01",
        "type": "BUY",
        "quantity": "10",
        "price_per_share": "100",
        "currency": "EUR",
        "fees": "0",
    }
    payload.update(kwargs)
    return api_client.post("/api/v1/transactions", payload, format="json")


def _sell(api_client, **kwargs):
    payload = {
        "asset_symbol": "AAPL",
        "date": "2026-02-01",
        "type": "SELL",
        "quantity": "4",
        "price_per_share": "150",
        "currency": "EUR",
        "fees": "0",
    }
    payload.update(kwargs)
    return api_client.post("/api/v1/transactions", payload, format="json")


def _price(symbol: str, close: str, *, currency: str = "EUR", d: str = "2026-03-01"):
    HistoricalPrice.objects.create(
        asset_symbol=symbol,
        date=date.fromisoformat(d),
        close_price=Decimal(close),
        currency=currency,
        source="test",
        asset_type=AssetType.STOCK,
    )


@pytest.mark.django_db
def test_holdings_defaults_to_scope_all(api_client, legacy_seeded, test_user):
    default = ensure_default_portfolio(test_user)
    _buy(api_client, portfolio_id=default.id)
    r = api_client.get("/api/v1/portfolio/holdings")
    assert r.status_code == 200
    assert "holdings" in r.json()


@pytest.mark.django_db
def test_holdings_scope_all_includes_multiple_portfolios(api_client, legacy_seeded, test_user):
    p1 = ensure_default_portfolio(test_user)
    p2 = Portfolio.objects.create(user=test_user, name="P2", base_currency="EUR", is_active=True)
    _buy(api_client, asset_symbol="AAA", portfolio_id=p1.id)
    _buy(api_client, asset_symbol="BBB", portfolio_id=p2.id)
    r = api_client.get("/api/v1/portfolio/holdings?portfolio_scope=all")
    symbols = {h["asset_symbol"] for h in r.json()["holdings"]}
    assert symbols == {"AAA", "BBB"}


@pytest.mark.django_db
def test_holdings_portfolio_id_filter(api_client, legacy_seeded, test_user):
    p1 = ensure_default_portfolio(test_user)
    p2 = Portfolio.objects.create(user=test_user, name="Scoped", base_currency="EUR", is_active=True)
    _buy(api_client, asset_symbol="AAA", portfolio_id=p1.id)
    _buy(api_client, asset_symbol="BBB", portfolio_id=p2.id)
    r = api_client.get(f"/api/v1/portfolio/holdings?portfolio_id={p2.id}")
    symbols = {h["asset_symbol"] for h in r.json()["holdings"]}
    assert symbols == {"BBB"}


@pytest.mark.django_db
def test_holdings_rejects_scope_and_portfolio_id(api_client, legacy_seeded):
    r = api_client.get("/api/v1/portfolio/holdings?portfolio_scope=all&portfolio_id=1")
    assert r.status_code == 422


@pytest.mark.django_db
def test_holdings_unknown_portfolio_id_404(api_client, legacy_seeded):
    r = api_client.get("/api/v1/portfolio/holdings?portfolio_id=999999")
    assert r.status_code == 404


@pytest.mark.django_db
def test_holdings_inactive_portfolio_id_404(api_client, legacy_seeded, test_user):
    inactive = Portfolio.objects.create(user=test_user, name="Inactive", is_active=False)
    r = api_client.get(f"/api/v1/portfolio/holdings?portfolio_id={inactive.id}")
    assert r.status_code == 404


@pytest.mark.django_db
def test_buy_creates_holding_quantity_and_invested(api_client, legacy_seeded, test_user):
    default = ensure_default_portfolio(test_user)
    _buy(api_client, portfolio_id=default.id)
    _price("AAPL", "120")
    h = api_client.get("/api/v1/portfolio/holdings").json()["holdings"][0]
    assert h["quantity"] == 10.0
    assert h["invested_amount"] == 1000.0


@pytest.mark.django_db
def test_sell_reduces_quantity(api_client, legacy_seeded, test_user):
    default = ensure_default_portfolio(test_user)
    _buy(api_client, portfolio_id=default.id)
    _sell(api_client, portfolio_id=default.id)
    _price("AAPL", "120")
    h = api_client.get("/api/v1/portfolio/holdings").json()["holdings"][0]
    assert h["quantity"] == 6.0


@pytest.mark.django_db
def test_fifo_realized_pl_on_partial_sell(api_client, legacy_seeded, test_user):
    default = ensure_default_portfolio(test_user)
    _buy(api_client, portfolio_id=default.id)
    _sell(api_client, portfolio_id=default.id)
    _price("AAPL", "120")
    h = api_client.get("/api/v1/portfolio/holdings").json()["holdings"][0]
    assert h["realized_gain_loss"] == 200.0


@pytest.mark.django_db
def test_partial_sell_remaining_invested(api_client, legacy_seeded, test_user):
    default = ensure_default_portfolio(test_user)
    _buy(api_client, portfolio_id=default.id)
    _sell(api_client, portfolio_id=default.id)
    _price("AAPL", "120")
    h = api_client.get("/api/v1/portfolio/holdings").json()["holdings"][0]
    assert h["invested_amount"] == 600.0
    assert h["avg_cost_per_share"] == 100.0


@pytest.mark.django_db
def test_fully_sold_holding_status_closed(api_client, legacy_seeded, test_user):
    default = ensure_default_portfolio(test_user)
    _buy(api_client, portfolio_id=default.id)
    _sell(api_client, quantity="10", portfolio_id=default.id)
    _price("AAPL", "120")
    h = api_client.get("/api/v1/portfolio/holdings").json()["holdings"][0]
    assert h["quantity"] == 0.0
    assert h["holding_status"] == "closed"


@pytest.mark.django_db
def test_oversell_exposes_status_and_warning(api_client, legacy_seeded, test_user):
    default = ensure_default_portfolio(test_user)
    _buy(api_client, quantity="10", portfolio_id=default.id)
    _sell(api_client, quantity="15", portfolio_id=default.id)
    _price("AAPL", "120")
    h = api_client.get("/api/v1/portfolio/holdings").json()["holdings"][0]
    assert h["holding_status"] == "oversold"
    assert any("exceeded" in w.lower() for w in h["warnings"])


@pytest.mark.django_db
def test_stock_split_adjusts_metrics(api_client, legacy_seeded, test_user):
    default = ensure_default_portfolio(test_user)
    api_client.post(
        "/api/v1/transactions",
        {
            "asset_symbol": "AAPL",
            "date": "2023-12-01",
            "type": "BUY",
            "quantity": "1",
            "price_per_share": "200",
            "currency": "EUR",
        },
        format="json",
    )
    api_client.post(
        "/api/v1/transactions",
        {
            "asset_symbol": "AAPL",
            "date": "2024-01-01",
            "type": "STOCK_SPLIT",
            "split_from": "1",
            "split_to": "20",
            "currency": "EUR",
        },
        format="json",
    )
    _price("AAPL", "10")
    h = api_client.get("/api/v1/portfolio/holdings").json()["holdings"][0]
    assert h["quantity"] == 20.0
    assert h["invested_amount"] == 200.0


@pytest.mark.django_db
def test_different_symbols_independent(api_client, legacy_seeded, test_user):
    default = ensure_default_portfolio(test_user)
    _buy(api_client, asset_symbol="AAA", portfolio_id=default.id)
    _buy(api_client, asset_symbol="BBB", quantity="5", price_per_share="50", portfolio_id=default.id)
    _price("AAA", "100")
    _price("BBB", "60")
    holdings = {h["asset_symbol"]: h for h in api_client.get("/api/v1/portfolio/holdings").json()["holdings"]}
    assert holdings["AAA"]["quantity"] == 10.0
    assert holdings["BBB"]["quantity"] == 5.0


@pytest.mark.django_db
def test_latest_historical_price_used(api_client, legacy_seeded, test_user):
    default = ensure_default_portfolio(test_user)
    _buy(api_client, portfolio_id=default.id)
    HistoricalPrice.objects.create(
        asset_symbol="AAPL",
        date=date(2026, 1, 1),
        close_price=Decimal("100"),
        currency="EUR",
        source="test",
        asset_type=AssetType.STOCK,
    )
    HistoricalPrice.objects.create(
        asset_symbol="AAPL",
        date=date(2026, 2, 1),
        close_price=Decimal("175.5"),
        currency="EUR",
        source="test",
        asset_type=AssetType.STOCK,
    )
    h = api_client.get("/api/v1/portfolio/holdings").json()["holdings"][0]
    assert h["latest_price"] == 175.5
    assert h["price_status"] == "ok"


@pytest.mark.django_db
def test_missing_price_status(api_client, legacy_seeded, test_user):
    default = ensure_default_portfolio(test_user)
    _buy(api_client, portfolio_id=default.id)
    h = api_client.get("/api/v1/portfolio/holdings").json()["holdings"][0]
    assert h["latest_price"] is None
    assert h["price_status"] == "price_missing"


@pytest.mark.django_db
def test_no_external_price_fetch(api_client, legacy_seeded, test_user):
    default = ensure_default_portfolio(test_user)
    _buy(api_client, portfolio_id=default.id)
    with patch("portfolios.holdings_service.latest_historical_price") as mocked:
        mocked.return_value = None
        api_client.get("/api/v1/portfolio/holdings")
        mocked.assert_called()


@pytest.mark.django_db
def test_matching_display_currency_fx_ok(api_client, legacy_seeded, test_user):
    default = ensure_default_portfolio(test_user)
    _buy(api_client, portfolio_id=default.id)
    _price("AAPL", "120")
    data = api_client.get("/api/v1/portfolio/holdings?display_currency=EUR").json()
    assert data["fx_status"] == "ok"


@pytest.mark.django_db
def test_different_display_currency_fx_unavailable(api_client, legacy_seeded, test_user):
    default = ensure_default_portfolio(test_user)
    _buy(api_client, portfolio_id=default.id)
    _price("AAPL", "120")
    data = api_client.get("/api/v1/portfolio/holdings?display_currency=USD").json()
    assert data["fx_status"] == "fx_unavailable"


@pytest.mark.django_db
def test_xirr_returned_when_price_present(api_client, legacy_seeded, test_user):
    default = ensure_default_portfolio(test_user)
    _buy(api_client, date="2025-01-01", portfolio_id=default.id)
    _price("AAPL", "110", d="2026-03-01")
    h = api_client.get("/api/v1/portfolio/holdings").json()["holdings"][0]
    assert h["xirr"] is not None


@pytest.mark.django_db
def test_asset_detail_returns_metrics(api_client, legacy_seeded, test_user):
    default = ensure_default_portfolio(test_user)
    _buy(api_client, portfolio_id=default.id)
    _price("AAPL", "120")
    r = api_client.get("/api/v1/portfolio/assets/aapl")
    assert r.status_code == 200
    data = r.json()
    assert data["asset_symbol"] == "AAPL"
    assert data["cumulative_qty"] == 10.0


@pytest.mark.django_db
def test_asset_detail_case_insensitive(api_client, legacy_seeded, test_user):
    default = ensure_default_portfolio(test_user)
    _buy(api_client, portfolio_id=default.id)
    assert api_client.get("/api/v1/portfolio/assets/aapl").status_code == 200
    assert api_client.get("/api/v1/portfolio/assets/AAPL").status_code == 200


@pytest.mark.django_db
def test_asset_detail_transactions_ordered(api_client, legacy_seeded, test_user):
    default = ensure_default_portfolio(test_user)
    _buy(api_client, date="2026-01-01", portfolio_id=default.id)
    _sell(api_client, date="2026-02-01", portfolio_id=default.id)
    txns = api_client.get("/api/v1/portfolio/assets/AAPL").json()["transactions"]
    assert len(txns) == 2
    assert txns[0]["date"] <= txns[1]["date"]


@pytest.mark.django_db
def test_asset_detail_portfolio_scope(api_client, legacy_seeded, test_user):
    p1 = ensure_default_portfolio(test_user)
    p2 = Portfolio.objects.create(user=test_user, name="Other", base_currency="EUR", is_active=True)
    _buy(api_client, asset_symbol="ZZZ", portfolio_id=p2.id)
    r = api_client.get(f"/api/v1/portfolio/assets/ZZZ?portfolio_id={p1.id}")
    assert r.status_code == 404


@pytest.mark.django_db
def test_asset_detail_missing_asset_404(api_client, legacy_seeded):
    r = api_client.get("/api/v1/portfolio/assets/NONEXISTENT")
    assert r.status_code == 404


@pytest.mark.django_db
def test_asset_detail_price_status_missing(api_client, legacy_seeded, test_user):
    default = ensure_default_portfolio(test_user)
    _buy(api_client, portfolio_id=default.id)
    data = api_client.get("/api/v1/portfolio/assets/AAPL").json()
    assert data["price_status"] == "price_missing"


@pytest.mark.django_db
def test_asset_detail_oversell_warning(api_client, legacy_seeded, test_user):
    default = ensure_default_portfolio(test_user)
    _buy(api_client, quantity="10", portfolio_id=default.id)
    _sell(api_client, quantity="15", portfolio_id=default.id)
    data = api_client.get("/api/v1/portfolio/assets/AAPL").json()
    assert data["holding_status"] == "oversold"


def _fx(from_ccy: str, to_ccy: str, rate: str, d: str = "2026-03-01"):
    from fx.models import FXRate

    FXRate.objects.create(
        from_currency=from_ccy,
        to_currency=to_ccy,
        date=date.fromisoformat(d),
        rate=Decimal(rate),
        source="test",
    )


@pytest.mark.django_db
def test_holdings_converts_usd_price_to_eur_holding(api_client, legacy_seeded, test_user):
    default = ensure_default_portfolio(test_user)
    _buy(api_client, portfolio_id=default.id, currency="EUR")
    HistoricalPrice.objects.create(
        asset_symbol="AAPL",
        date=date(2026, 3, 1),
        close_price=Decimal("100"),
        currency="USD",
        source="test",
        asset_type=AssetType.STOCK,
    )
    _fx("USD", "EUR", "0.9")
    h = api_client.get("/api/v1/portfolio/holdings?display_currency=EUR").json()
    assert h["fx_status"] == "ok"
    row = h["holdings"][0]
    assert row["price_status"] == "ok"
    assert row["latest_price"] == 90.0
    assert row["current_value"] == 900.0


@pytest.mark.django_db
def test_holdings_fx_ok_when_display_matches_holding_despite_usd_price(api_client, legacy_seeded, test_user):
    default = ensure_default_portfolio(test_user)
    _buy(api_client, portfolio_id=default.id, currency="EUR")
    HistoricalPrice.objects.create(
        asset_symbol="AAPL",
        date=date(2026, 3, 1),
        close_price=Decimal("120"),
        currency="USD",
        source="test",
        asset_type=AssetType.STOCK,
    )
    _fx("USD", "EUR", "0.85")
    data = api_client.get("/api/v1/portfolio/holdings?display_currency=EUR").json()
    assert data["fx_status"] == "ok"
    assert data["holdings"][0]["fx_status"] == "ok"


@pytest.mark.django_db
def test_holdings_price_missing_without_fx_for_price_currency(api_client, legacy_seeded, test_user):
    default = ensure_default_portfolio(test_user)
    _buy(api_client, portfolio_id=default.id, currency="EUR")
    HistoricalPrice.objects.create(
        asset_symbol="AAPL",
        date=date(2026, 3, 1),
        close_price=Decimal("100"),
        currency="USD",
        source="test",
        asset_type=AssetType.STOCK,
    )
    h = api_client.get("/api/v1/portfolio/holdings").json()["holdings"][0]
    assert h["price_status"] == "price_missing"
    assert h["latest_price"] is None


@pytest.mark.django_db
def test_stock_split_sell_not_false_oversold(api_client, legacy_seeded, test_user):
    default = ensure_default_portfolio(test_user)
    api_client.post(
        "/api/v1/transactions",
        {
            "asset_symbol": "ANET",
            "date": "2022-11-11",
            "type": "BUY",
            "quantity": "10",
            "price_per_share": "100",
            "currency": "EUR",
        },
        format="json",
    )
    api_client.post(
        "/api/v1/transactions",
        {
            "asset_symbol": "ANET",
            "date": "2024-12-03",
            "type": "STOCK_SPLIT",
            "split_from": "1",
            "split_to": "4",
            "currency": "EUR",
        },
        format="json",
    )
    api_client.post(
        "/api/v1/transactions",
        {
            "asset_symbol": "ANET",
            "date": "2026-02-06",
            "type": "SELL",
            "quantity": "20",
            "price_per_share": "110",
            "currency": "EUR",
        },
        format="json",
    )
    _price("ANET", "120")
    h = api_client.get("/api/v1/portfolio/holdings").json()["holdings"][0]
    assert h["quantity"] == 20.0
    assert h["holding_status"] == "ok"
    assert h["holding_status"] != "oversold"


def _cash_deposit(portfolio, *, amount: str, currency: str = "EUR"):
    CashLedgerEntry.objects.create(
        portfolio=portfolio,
        date=date(2026, 6, 1),
        currency=currency,
        entry_type=CashEntryType.CASH_DEPOSIT,
        amount=Decimal(amount),
    )


@pytest.mark.django_db
def test_holdings_allocation_includes_cash_row(api_client, legacy_seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    portfolio.cash_aware_enabled = False
    portfolio.save(update_fields=["cash_aware_enabled"])
    _buy(api_client)
    _price("AAPL", "110")
    _cash_deposit(portfolio, amount="1200", currency="EUR")
    data = api_client.get("/api/v1/portfolio/holdings?display_currency=EUR").json()
    cash_rows = [r for r in data["allocation"] if r.get("asset_type") == "CASH"]
    assert len(cash_rows) == 1
    assert cash_rows[0]["asset_symbol"] == "Cash EUR"
    assert cash_rows[0]["primary_asset_class"] == "CASH"
    assert cash_rows[0]["current_value"] == 1200.0
    assert all(h.get("asset_type") != "CASH" for h in data["holdings"])


@pytest.mark.django_db
def test_holdings_allocation_cash_converted_to_display_currency(
    api_client, legacy_seeded, test_user
):
    portfolio = ensure_default_portfolio(test_user)
    _cash_deposit(portfolio, amount="80000", currency="INR")
    upsert_fx_rate(
        from_currency="INR",
        to_currency="EUR",
        row_date=date.today(),
        rate=Decimal("0.01"),
    )
    data = api_client.get("/api/v1/portfolio/holdings?display_currency=EUR").json()
    cash = next(r for r in data["allocation"] if r["asset_symbol"] == "Cash INR")
    assert cash["current_value"] == 800.0
    assert cash["currency"] == "EUR"


@pytest.mark.django_db
def test_holdings_allocation_missing_fx_excludes_cash_with_warning(
    api_client, legacy_seeded, test_user
):
    portfolio = ensure_default_portfolio(test_user)
    _cash_deposit(portfolio, amount="50000", currency="INR")
    data = api_client.get("/api/v1/portfolio/holdings?display_currency=EUR").json()
    assert not any(r.get("asset_type") == "CASH" for r in data["allocation"])
    assert any("cash balance" in w.lower() for w in data.get("warnings", []))
