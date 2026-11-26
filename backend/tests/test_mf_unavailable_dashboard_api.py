"""Unavailable MF valuations remain readable across portfolio scopes and currencies."""
from datetime import date
from types import SimpleNamespace

import pytest

from portfolios.performance_service import _align_terminal_value_with_summary
from portfolios.scope import ResolvedPortfolioScope
from portfolios.seed import ensure_default_portfolio
from portfolios.xirr_service import compute_scope_xirr_detail
from tests.conftest import cached_mf_nav
from tests.test_mf_provisional_valuation_scopes_api import (
    SCHEME, _fx, cached, ledger_and_cache_state, mf_txn, provisional,
)


@pytest.mark.django_db
@pytest.mark.parametrize("cash_aware", [False, True])
@pytest.mark.parametrize("scope_kind", ["single", "all_active"])
@pytest.mark.parametrize("currency", ["INR", "EUR"])
@pytest.mark.parametrize("missing_kind", ["conflict", "missing"])
def test_unavailable_nav_keeps_summary_history_and_xirr_readable(
    api_client, legacy_seeded, test_user, monkeypatch,
    cash_aware, scope_kind, currency, missing_kind,
):
    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2026, 3, 20))
    portfolio = ensure_default_portfolio(test_user)
    portfolio.cash_aware_enabled = cash_aware
    portfolio.save(update_fields=["cash_aware_enabled"])
    if missing_kind == "conflict":
        cached(portfolio, "2026-03-10", "100", "40")
        provisional(portfolio, "2026-03-12", "10", "42.5")
        provisional(portfolio, "2026-03-12", "10", "43")
    else:
        mf_txn(portfolio, "2026-03-10", "100", "40")
    for day in range(1, 21):
        _fx(f"2026-03-{day:02d}", "0.012")
    before = ledger_and_cache_state()
    scope = ResolvedPortfolioScope(kind=scope_kind, portfolio_ids=[portfolio.id])
    params = {"display_currency": currency}
    params.update({"portfolio_scope": "all"} if scope_kind == "all_active"
                  else {"portfolio_id": portfolio.id})

    summary = api_client.get("/api/v1/portfolio/summary", params)
    assert summary.status_code == 200
    data = summary.json()
    assert data["current_value"] is None
    assert data["unrealized_pl"] is None
    assert data["xirr"] is None
    assert data["fx_status"] != "fx_unavailable"
    assert any("NAV" in warning for warning in data["warnings"])
    assert not any("FX rates are missing" in warning for warning in data["warnings"])
    assert data["timeseries"][-1]["portfolio_value"] is None

    result = compute_scope_xirr_detail(scope, display_currency=currency, user=test_user)
    assert result.value is None
    assert any("valuation" in warning for warning in result.warnings)
    assert not any("FX rates are missing" in warning for warning in result.warnings)

    response = api_client.get("/api/v1/portfolio/performance", {
        **params, "range": "ALL", "metric": "value",
    })
    assert response.status_code == 200
    payload = response.json()
    points = payload if isinstance(payload, list) else payload["points"]
    assert points[-1]["value"] is None
    assert ledger_and_cache_state() == before

    cached_mf_nav(SCHEME, "2026-03-19", "45")
    recovered = api_client.get("/api/v1/portfolio/summary", params).json()
    units = 120 if missing_kind == "conflict" else 100
    expected = units * 45 * (0.012 if currency == "EUR" else 1)
    assert recovered["current_value"] == pytest.approx(expected)
    recovered_xirr = compute_scope_xirr_detail(scope, display_currency=currency, user=test_user)
    assert not any("valuation" in warning for warning in recovered_xirr.warnings)


def test_terminal_alignment_preserves_unavailable_summary(monkeypatch):
    monkeypatch.setattr(
        "portfolios.performance_service.build_portfolio_summary",
        lambda **kwargs: SimpleNamespace(current_value=None, fx_status="ok"),
    )
    points = [{"date": "2026-03-19", "portfolio_value": 4000},
              {"date": "2026-03-20", "portfolio_value": 4000}]
    _align_terminal_value_with_summary(
        points, scope=ResolvedPortfolioScope(kind="single", portfolio_ids=[1]),
        disp_ccy="INR", today=date(2026, 3, 20), user=object(),
    )
    assert points[0]["portfolio_value"] == 4000
    assert points[-1]["portfolio_value"] is None
