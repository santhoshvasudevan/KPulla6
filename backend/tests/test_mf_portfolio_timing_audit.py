"""Characterize existing portfolio timing behavior; a correction needs separate approval."""
from datetime import date

import pytest

from tests.test_mf_nav_performance_contract import nav
from tests.test_analytics_asset_metrics_api import _mf_payload
from portfolios.models import Portfolio


@pytest.mark.django_db
@pytest.mark.parametrize("cash_aware", [False, True])
@pytest.mark.parametrize("kind,payment_first", [("BUY", True), ("BUY", False), ("SELL", True), ("SELL", False)])
def test_delayed_subscription_existing_portfolio_timing(api_client, legacy_seeded, test_user, monkeypatch, cash_aware, kind, payment_first):
    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2026, 3, 5))
    p = Portfolio.objects.create(user=test_user, name="Timing audit", base_currency="INR", cash_aware_enabled=cash_aware)
    if cash_aware:
        response = api_client.post("/api/v1/cash/deposits", {
            "portfolio_id": p.id, "date": "2026-03-01", "currency": "INR", "amount": "2000"}, format="json")
        assert response.status_code == 201, response.json()
    dates = ("2026-03-03", "2026-03-04") if payment_first else ("2026-03-04", "2026-03-03")
    for payment, allotment, units, paid, action in [("2026-03-01", "2026-03-01", "100", "1000", "BUY"),
                                            (*dates, "50", "500", kind)]:
        response = api_client.post("/api/v1/transactions", _mf_payload(
            portfolio_id=p.id, investment_date=payment, nav_date=allotment,
            type=action, nav="10", units_allotted=units, paid_value=paid, market_value=paid), format="json")
        assert response.status_code == 201, response.json()
    for day in range(1, 6):
        nav(f"2026-03-{day:02d}", "10")
    response = api_client.get("/api/v1/portfolio/performance", {
        "portfolio_id": p.id, "metric": "twror", "range": "ALL", "display_currency": "INR"})
    assert response.status_code == 200
    data = response.json()
    settled_return = -25.0 if not cash_aware and payment_first else 0.0
    assert data[-1]["value"] == pytest.approx(settled_return)
