"""Public API acceptance edges for pending MF purchase valuation (#33)."""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from fx.services import upsert_fx_rate
from market_data.models import AssetType, HistoricalPrice
from tests.test_cash_aware_transactions_api import _deposit, _mf_payload


def _buy(client, portfolio, *, payment="2026-03-12", recognition="2026-03-16"):
    response = client.post("/api/v1/transactions", _mf_payload(
        portfolio_id=portfolio.id, investment_date=payment, nav_date=recognition,
        paid_value="4250", market_value="4250", fees="0",
    ), format="json")
    assert response.status_code == 201, response.json()


def _nav(day, value="42.5"):
    HistoricalPrice.objects.create(
        asset_symbol="120503", asset_type=AssetType.MUTUAL_FUND,
        date=date.fromisoformat(day), close_price=Decimal(value), currency="INR",
    )


def _performance(client, portfolio, *, scope="single", currency="INR", period="ALL"):
    selector = {"portfolio_scope": "all"} if scope == "all" else {"portfolio_id": portfolio.id}
    response = client.get("/api/v1/portfolio/performance", {
        **selector, "display_currency": currency, "range": period, "metric": "value",
    })
    assert response.status_code == 200, response.json()
    data = response.json()
    points = data["points"] if isinstance(data, dict) else data
    return {p["date"]: p["value"] for p in points}, data.get("warnings", []) if isinstance(data, dict) else []


@pytest.mark.django_db
@pytest.mark.parametrize("scope", ["single", "all"])
def test_pending_before_bounded_range_is_included_without_becoming_cash(
    api_client, cash_aware_portfolio, monkeypatch, scope,
):
    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2026, 3, 20))
    portfolio = cash_aware_portfolio
    _deposit(portfolio, day="2026-03-10", amount="10000", currency="INR")
    _buy(api_client, portfolio)
    _nav("2026-03-16")
    _nav("2026-03-20")
    values, warnings = _performance(api_client, portfolio, scope=scope, period="7D")
    assert min(values) == "2026-03-13"
    assert values["2026-03-13"] == pytest.approx(10000)
    assert values["2026-03-15"] == pytest.approx(10000)
    assert values["2026-03-16"] == pytest.approx(10000)
    assert not warnings
    cash = api_client.get("/api/v1/cash/balances", {
        "portfolio_id": portfolio.id, "as_of_date": "2026-03-13",
    })
    assert cash.status_code == 200
    assert cash.json()["balances"] == [{"currency": "INR", "balance": 5750.0}]


@pytest.mark.django_db
def test_missing_nav_after_recognition_stays_unknown_not_pending_cash(
    api_client, cash_aware_portfolio, monkeypatch,
):
    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2026, 3, 17))
    portfolio = cash_aware_portfolio
    _deposit(portfolio, day="2026-03-10", amount="10000", currency="INR")
    _buy(api_client, portfolio)
    values, _ = _performance(api_client, portfolio)
    assert values["2026-03-13"] == pytest.approx(10000)
    assert values["2026-03-16"] is None
    assert values["2026-03-17"] is None
    cash = api_client.get("/api/v1/cash/balances", {"portfolio_id": portfolio.id})
    assert cash.json()["balances"] == [{"currency": "INR", "balance": 5750.0}]
    metrics = api_client.get("/api/v1/analytics/performance-metrics", {
        "portfolio_id": portfolio.id, "display_currency": "INR", "range": "ALL",
    })
    assert metrics.status_code == 200
    assert any("NAV" in warning for warning in metrics.json()["warnings"])


@pytest.mark.django_db
@pytest.mark.parametrize("metric", ["value", "cumulative_return", "twror"])
def test_all_portfolios_preserves_missing_nav_beside_valued_holdings(
    api_client, cash_aware_portfolio, test_user, monkeypatch, metric,
):
    from portfolios.models import Portfolio

    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2026, 3, 17))
    missing = cash_aware_portfolio
    missing.base_currency = "INR"
    missing.save(update_fields=["base_currency"])
    known = Portfolio.objects.create(
        user=test_user, name="Valued portfolio", base_currency="INR",
        cash_aware_enabled=True,
    )
    for portfolio in (missing, known):
        _deposit(portfolio, day="2026-03-10", amount="10000", currency="INR")
    _buy(api_client, missing)
    response = api_client.post("/api/v1/transactions", _mf_payload(
        portfolio_id=known.id, scheme_code="119062", investment_date="2026-03-12",
        nav_date="2026-03-16", paid_value="4250", market_value="4250", fees="0",
    ), format="json")
    assert response.status_code == 201, response.json()
    HistoricalPrice.objects.create(
        asset_symbol="119062", asset_type=AssetType.MUTUAL_FUND,
        date=date(2026, 3, 16), close_price=Decimal("42.5"), currency="INR",
    )
    response = api_client.get("/api/v1/portfolio/performance", {
        "portfolio_scope": "all", "display_currency": "INR",
        "range": "ALL", "metric": metric,
    })
    assert response.status_code == 200, response.json()
    data = response.json()
    points = data["points"] if isinstance(data, dict) else data
    values = {point["date"]: point["value"] for point in points}
    if metric == "value":
        assert values["2026-03-13"] == pytest.approx(20000)
    assert values["2026-03-16"] is None
    assert values["2026-03-17"] is None
    for selector in ({"portfolio_id": missing.id}, {"portfolio_scope": "all"}):
        summary = api_client.get("/api/v1/portfolio/summary", {
            **selector, "display_currency": "INR",
        })
        assert summary.status_code == 200
        assert all("_nav_missing" not in point for point in summary.json()["timeseries"])


@pytest.mark.django_db
def test_missing_display_fx_retains_known_child_value(
    api_client, legacy_seeded, test_user, monkeypatch,
):
    from portfolios.models import Portfolio
    from tests.test_cash_aware_transactions_api import _stock_payload

    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2026, 3, 17))
    euro = Portfolio.objects.get(user=test_user, is_default=True)
    known = Portfolio.objects.create(user=test_user, name="INR", base_currency="INR")
    response = api_client.post("/api/v1/transactions", _stock_payload(
        portfolio_id=euro.id, date="2026-03-10", quantity="1", fees="0",
    ), format="json")
    assert response.status_code == 201, response.json()
    HistoricalPrice.objects.create(
        asset_symbol="AAPL", asset_type=AssetType.STOCK, date=date(2026, 3, 10),
        close_price=Decimal("100"), currency="EUR",
    )
    _buy(api_client, known)
    _nav("2026-03-16")
    values, _ = _performance(api_client, known, scope="all", currency="INR")
    # EUR->INR is missing, but the established FX-only partial-value policy
    # retains the INR holding rather than treating it as missing NAV.
    assert values["2026-03-16"] == pytest.approx(4250)


@pytest.mark.django_db
@pytest.mark.parametrize("scope", ["single", "all"])
@pytest.mark.parametrize("fx_mode", ["direct", "filled", "missing"])
def test_pending_and_investments_convert_once_across_base_and_display_currency(
    api_client, cash_aware_portfolio, monkeypatch, scope, fx_mode,
):
    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2026, 3, 17))
    portfolio = cash_aware_portfolio  # EUR portfolio, INR fund/cash, USD display.
    assert portfolio.base_currency == "EUR"
    _deposit(portfolio, day="2026-03-10", amount="10000", currency="INR")
    _buy(api_client, portfolio)
    _nav("2026-03-16")
    _nav("2026-03-17")
    if fx_mode != "missing":
        days = range(8) if fx_mode == "direct" else range(1)
        for offset in days:
            day = date(2026, 3, 10) + timedelta(days=offset)
            for source, target, rate in (("INR", "EUR", "0.01"), ("EUR", "USD", "2"), ("INR", "USD", "0.02")):
                upsert_fx_rate(from_currency=source, to_currency=target, row_date=day, rate=Decimal(rate))
    values, warnings = _performance(api_client, portfolio, scope=scope, currency="USD")
    if fx_mode == "missing":
        assert warnings
        assert any("FX" in warning for warning in warnings)
        assert values["2026-03-16"] is None
    else:
        # INR 5750 cash + INR 4250 pending/units = USD 200, never another conversion.
        assert values["2026-03-13"] == pytest.approx(200)
        assert values["2026-03-16"] == pytest.approx(200)
        assert values["2026-03-17"] == pytest.approx(200)


@pytest.mark.django_db
def test_legacy_purchase_does_not_gain_cash_aware_pending_value(
    api_client, legacy_seeded, test_user, monkeypatch,
):
    from portfolios.models import Portfolio

    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2026, 3, 17))
    portfolio = Portfolio.objects.get(user=test_user, is_default=True)
    assert not portfolio.cash_aware_enabled
    _buy(api_client, portfolio)
    _nav("2026-03-16")
    values, _ = _performance(api_client, portfolio)
    assert all(day >= "2026-03-16" for day in values)
    assert values["2026-03-16"] == pytest.approx(4250)
