"""Fund performance must be NAV-only; personal and portfolio returns are separate."""
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest

from market_data.models import AssetType, HistoricalPrice
from tests.test_analytics_asset_metrics_api import _mf_payload


def nav(day, value, scheme="120503"):
    HistoricalPrice.objects.create(asset_symbol=scheme, asset_type=AssetType.MUTUAL_FUND,
        date=date.fromisoformat(day), close_price=Decimal(value), currency="INR")


def metrics(client, scheme="120503", **params):
    query = {"range": "ALL", "display_currency": "EUR", **params}
    response = client.get(f"/api/v1/analytics/assets/{scheme}/performance-metrics", query)
    assert response.status_code == 200, response.json()
    return response.json()


@pytest.mark.django_db
def test_mf_heatmap_is_nav_only_despite_delayed_buy(api_client, legacy_seeded, monkeypatch):
    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2024, 3, 31))
    assert api_client.post("/api/v1/transactions", _mf_payload(
        investment_date="2024-02-27", nav_date="2024-02-29"), format="json").status_code == 201
    assert api_client.post("/api/v1/transactions", _mf_payload(
        investment_date="2024-03-25", nav_date="2024-03-26"), format="json").status_code == 201
    # Pinned public NAV endpoints, with eligible intervening observations.
    d = date(2024, 2, 29)
    while d < date(2024, 3, 31):
        nav(d.isoformat(), "481.392")
        d += timedelta(days=1)
    nav("2024-03-31", "484.131")
    result = metrics(api_client)
    assert result["performance_basis"] == "nav"
    assert result["currency"] == "INR"
    march = next(r for r in result["periodic_returns"]["monthly"] if r["period"] == "2024-03")
    assert march["return"] == pytest.approx(0.005689749725795194)
    assert result["metrics"]["return"]["xirr"] is None
    assert "personal_metrics" in result
    assert metrics(api_client, display_currency="INR")["metrics"] == result["metrics"]


@pytest.mark.django_db
def test_fund_history_precedes_purchase_and_allows_multiple_folios(api_client, legacy_seeded, monkeypatch):
    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2026, 3, 20))
    for folio in ("F1", "F2"):
        assert api_client.post("/api/v1/transactions", _mf_payload(folio_number=folio), format="json").status_code == 201
    for day, value in [("2026-03-01", "100"), ("2026-03-05", "100"),
                       ("2026-03-10", "100"), ("2026-03-15", "100"), ("2026-03-20", "100")]:
        nav(day, value)
    result = metrics(api_client)
    assert result["range"]["start"] == "2026-03-01"
    assert result["metrics"]["return"]["cumulative_return"] == 0
    assert metrics(api_client, folio_number="F1")["metrics"] == result["metrics"]


@pytest.mark.django_db
def test_nav_returns_do_not_change_after_trade_edits(api_client, legacy_seeded, monkeypatch):
    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2026, 3, 20))
    created = api_client.post("/api/v1/transactions", _mf_payload(), format="json").json()
    for day, value in [("2026-03-01", "100"), ("2026-03-05", "101"),
                       ("2026-03-10", "102"), ("2026-03-15", "103"), ("2026-03-20", "104")]:
        nav(day, value)
    original = metrics(api_client)
    response = api_client.put(f"/api/v1/transactions/{created['id']}", _mf_payload(
        investment_date="2026-02-01", nav_date="2026-02-03", units_allotted="200",
        paid_value="8505", market_value="8500"), format="json")
    assert response.status_code == 200
    changed = metrics(api_client)
    for block in ("metrics", "periodic_returns", "drawdown_periods", "drawdown_series", "coverage"):
        assert changed[block] == original[block]


@pytest.mark.django_db
def test_bounded_range_has_predecessor_and_no_invented_holiday_returns(api_client, legacy_seeded, monkeypatch):
    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2026, 3, 20))
    api_client.post("/api/v1/transactions", _mf_payload(), format="json")
    nav("2026-03-12", "100")
    nav("2026-03-13", "110")
    nav("2026-03-16", "121")
    nav("2026-03-20", "121")
    data = metrics(api_client, range="7D")
    assert data["metrics"]["return"]["cumulative_return"] == pytest.approx(.21)
    assert data["metrics"]["return"]["twror"] == pytest.approx(.21)
    assert data["range"]["start"] == "2026-03-13"
    assert data["coverage"]["partial_months"] == ["2026-03"]


@pytest.mark.django_db
def test_unexplained_gap_is_not_zero_or_compounded(api_client, legacy_seeded, monkeypatch):
    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2026, 3, 20))
    api_client.post("/api/v1/transactions", _mf_payload(), format="json")
    nav("2026-03-01", "100")
    nav("2026-03-20", "200")
    data = metrics(api_client)
    assert data["metrics"]["return"]["cumulative_return"] is None
    assert data["periodic_returns"]["monthly"] == []
    assert data["coverage"]["incomplete"] is True
    assert data["drawdown_series"] == []


@pytest.mark.django_db
def test_mf_compare_uses_same_series_and_never_calls_provider(api_client, legacy_seeded, monkeypatch):
    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2026, 3, 20))
    for scheme in ("120503", "120504"):
        api_client.post("/api/v1/transactions", _mf_payload(scheme_code=scheme), format="json")
        for day, value in [("2026-03-01", "100"), ("2026-03-05", "101"),
                           ("2026-03-10", "102"), ("2026-03-15", "103"), ("2026-03-20", "104")]:
            nav(day, value, scheme)
    with patch("market_data.providers.mutual_fund_nav_provider.http_get_json", side_effect=AssertionError("no providers on reads")):
        direct = metrics(api_client)
        response = api_client.get("/api/v1/analytics/compare", {
            "subjects": "asset:120503,asset:120504", "range": "ALL", "display_currency": "EUR"})
    assert response.status_code == 200
    data = response.json()
    assert data["currency"] == "INR"
    assert data["subjects"][0]["metrics"] == direct["metrics"]
    assert data["subjects"][0]["periodic_returns"] == direct["periodic_returns"]


@pytest.mark.django_db
def test_native_fund_metrics_require_compatible_benchmark(api_client, legacy_seeded, monkeypatch):
    from market_data.models import BenchmarkIndexConfig
    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2026, 3, 20))
    api_client.post("/api/v1/transactions", _mf_payload(), format="json")
    nav("2026-03-18", "100")
    nav("2026-03-19", "101")
    nav("2026-03-20", "102")
    BenchmarkIndexConfig.objects.create(symbol="USD_TEST", display_name="USD test", currency="USD")
    data = metrics(api_client, benchmark="USD_TEST")
    assert data.get("benchmark") is None
    assert any("INR benchmark" in w for w in data["warnings"])


@pytest.mark.django_db
def test_analytics_get_does_not_write_and_preserves_asset_access(api_client, legacy_seeded, monkeypatch):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext
    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2026, 3, 20))
    api_client.post("/api/v1/transactions", _mf_payload(), format="json")
    nav("2026-03-19", "100")
    nav("2026-03-20", "101")
    with CaptureQueriesContext(connection) as queries:
        metrics(api_client)
    assert not any(q["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for q in queries)
    assert api_client.get("/api/v1/analytics/assets/999999/performance-metrics").status_code == 404


@pytest.mark.django_db
def test_personal_xirr_uses_native_inr_settlement_flows(api_client, legacy_seeded, monkeypatch):
    """958-day oracle: −₹10,000 on 2024-01-01 → ₹11,808.953 on 2026-08-16 ≈ 6.54%.

    Independent two-flow annualization confirms ~6.54%. The legacy ~491.67% result
    mixed EUR-converted principal with an INR terminal value and must not return.
    """
    from fx.services import upsert_fx_rate

    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2026, 8, 16))
    api_client.post("/api/v1/transactions", _mf_payload(
        investment_date="2024-01-01", nav_date="2024-01-01", nav="100",
        units_allotted="100", paid_value="10000", market_value="10000"), format="json")
    nav("2026-08-16", "118.089530")
    # Irrelevant FX must not change the native-INR personal return.
    upsert_fx_rate(from_currency="INR", to_currency="EUR", row_date=date(2024, 1, 1), rate=Decimal("0.01111111"))
    data = metrics(api_client)
    personal = data["personal_metrics"]
    assert personal["xirr"] == pytest.approx(0.0654, abs=5e-4)
    assert personal["status"] == "calculated"
    assert personal["basis"] == "native_inr"
    assert personal["xirr_scope"] == "full_scope"
    assert personal["warnings"] == []
    assert data["metrics"]["return"]["xirr"] is None


@pytest.mark.django_db
def test_compare_recalculates_returns_on_common_nav_intervals(api_client, legacy_seeded, monkeypatch):
    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2026, 3, 5))
    for scheme in ("120503", "120504"):
        api_client.post("/api/v1/transactions", _mf_payload(scheme_code=scheme), format="json")
        for day, value in [(1,"100"),(2,"100"),(3,"110"),(4,"121"),(5,"133.1")]:
            if scheme == "120504" and day == 3:
                continue
            nav(f"2026-03-{day:02d}", value, scheme)
    data = api_client.get("/api/v1/analytics/compare", {
        "subjects":"asset:120503,asset:120504", "range":"ALL"}).json()
    for subject in data["subjects"]:
        assert subject["metrics"]["return"]["cumulative_return"] == pytest.approx(.331)
    for value in data["normalized_series"][-1]["values"].values():
        assert value == pytest.approx(.331)


@pytest.mark.django_db
def test_benchmark_intervals_and_opening_returns_match_asset_and_compare(api_client, legacy_seeded, monkeypatch):
    from market_data.models import BenchmarkIndexConfig
    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2026, 3, 5))
    BenchmarkIndexConfig.objects.create(symbol="INR_TEST", display_name="INR test", currency="INR")
    for scheme in ("120503", "120504"):
        api_client.post("/api/v1/transactions", _mf_payload(scheme_code=scheme), format="json")
        for day, value in [(1,"100"),(2,"101"),(3,"103"),(4,"102"),(5,"104")]:
            nav(f"2026-03-{day:02d}", value, scheme)
    for day, value in [(1,"100"),(2,"101"),(3,"103"),(4,"102"),(5,"104")]:
        HistoricalPrice.objects.create(asset_symbol="INR_TEST",asset_type=AssetType.INDEX,
            date=date(2026,3,day),close_price=Decimal(value),currency="INR")
    direct = metrics(api_client, benchmark="INR_TEST")
    compared = api_client.get("/api/v1/analytics/compare", {
        "subjects":"asset:120503,asset:120504", "range":"ALL", "benchmark":"INR_TEST"}).json()
    assert direct["benchmark"]["paired_count"] == 4
    assert compared["subjects"][0]["benchmark"] == direct["benchmark"]


@pytest.mark.django_db
def test_compare_keeps_shared_predecessor_before_trimming(api_client, legacy_seeded, monkeypatch):
    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2026, 3, 20))
    for scheme in ("120503", "120504"):
        api_client.post("/api/v1/transactions", _mf_payload(scheme_code=scheme), format="json")
        for day in (11,13,16,20):
            nav(f"2026-03-{day:02d}", "100", scheme)
    nav("2026-03-12", "100", "120503")
    data = api_client.get("/api/v1/analytics/compare", {
        "subjects":"asset:120503,asset:120504", "range":"7D"}).json()
    for subject in data["subjects"]:
        assert subject["metrics"]["return"]["cumulative_return"] == 0
        assert subject["coverage"]["incomplete"] is False


@pytest.mark.django_db
def test_mixed_compare_preserves_fund_metrics_without_stock_overlap(api_client, legacy_seeded, monkeypatch):
    from tests.test_analytics_asset_metrics_api import _buy, _price
    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2026, 3, 20))
    api_client.post("/api/v1/transactions", _mf_payload(), format="json")
    _buy(api_client, date="2026-03-20")
    _price("AAPL", "2026-03-20", "100")
    nav("2026-03-18", "100")
    nav("2026-03-19", "101")
    nav("2026-03-20", "102")
    direct = metrics(api_client)
    data = api_client.get("/api/v1/analytics/compare", {
        "subjects":"asset:120503,asset:AAPL", "range":"ALL"}).json()
    assert data["comparison_compatible"] is False
    assert data["normalized_series"] == []
    assert data["subjects"][0]["metrics"] == direct["metrics"]


@pytest.mark.django_db
def test_benchmark_gap_remains_explicit_when_valid_pairs_survive(api_client, legacy_seeded, monkeypatch):
    from market_data.models import BenchmarkIndexConfig
    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2026, 3, 16))
    api_client.post("/api/v1/transactions", _mf_payload(), format="json")
    BenchmarkIndexConfig.objects.create(symbol="GAP_TEST",display_name="Gap test",currency="INR")
    for day in range(1,17):
        nav(f"2026-03-{day:02d}", str(100+day))
    for day in (1,2,15,16):
        HistoricalPrice.objects.create(asset_symbol="GAP_TEST",asset_type=AssetType.INDEX,
            date=date(2026,3,day),close_price=Decimal(100+day),currency="INR")
    data = metrics(api_client, benchmark="GAP_TEST")
    assert data["benchmark"]["paired_count"] == 2
    assert data["benchmark"]["coverage"]["partial"] is True
    assert any("Benchmark coverage is incomplete" in w for w in data["warnings"])


@pytest.mark.django_db
def test_fund_scope_independence_does_not_expand_other_user_access(api_client, legacy_seeded, test_user, monkeypatch):
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from portfolios.models import Portfolio
    from portfolios.seed import ensure_default_portfolio
    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2026, 3, 20))
    original = ensure_default_portfolio(test_user)
    second = Portfolio.objects.create(user=test_user,name="Other scope",base_currency="INR",cash_aware_enabled=False)
    for p in (original,second):
        assert api_client.post("/api/v1/transactions", _mf_payload(portfolio_id=p.id), format="json").status_code == 201
    nav("2026-03-19","100")
    nav("2026-03-20","101")
    assert metrics(api_client,portfolio_id=original.id)["metrics"] == metrics(api_client,portfolio_id=second.id)["metrics"]
    other = get_user_model().objects.create_user(username="other-fund-user")
    other_client = APIClient()
    other_client.force_authenticate(other)
    assert other_client.get("/api/v1/analytics/assets/120503/performance-metrics").status_code == 404
