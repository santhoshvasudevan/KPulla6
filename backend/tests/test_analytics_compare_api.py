from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from market_data.models import AssetType, BenchmarkIndexConfig, HistoricalPrice
from portfolios.models import Portfolio
from portfolios.seed import ensure_default_portfolio

FIXED_TODAY = date(2026, 3, 15)


@pytest.fixture
def today_patch(monkeypatch):
    monkeypatch.setattr("portfolios.dates.current_date", lambda: FIXED_TODAY)
    return FIXED_TODAY


def _compare_url(**params: str) -> str:
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    return f"/api/v1/analytics/compare?{qs}"


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


def _buy_msft(api_client, **kwargs):
    payload = {
        "asset_symbol": "MSFT",
        "date": "2026-01-01",
        "type": "BUY",
        "quantity": "5",
        "price_per_share": "200",
        "currency": "EUR",
        "fees": "0",
    }
    payload.update(kwargs)
    return api_client.post("/api/v1/transactions", payload, format="json")


def _price(symbol: str, d: str, close: str, *, currency: str = "EUR", asset_type=AssetType.STOCK):
    HistoricalPrice.objects.create(
        asset_symbol=symbol,
        date=date.fromisoformat(d),
        close_price=Decimal(close),
        currency=currency,
        source="test",
        asset_type=asset_type,
    )


def _index_price(symbol: str, d: str, close: str, *, currency: str = "USD"):
    _price(symbol, d, close, currency=currency, asset_type=AssetType.INDEX)


def _seed_two_stock_overlap(api_client):
    _buy(api_client, asset_symbol="AAPL", date="2026-01-01")
    _buy_msft(api_client, date="2026-01-01")
    _price("AAPL", "2026-01-01", "100")
    _price("AAPL", "2026-01-02", "110")
    _price("AAPL", "2026-01-03", "115")
    _price("AAPL", "2026-03-15", "120")
    _price("MSFT", "2026-01-01", "200")
    _price("MSFT", "2026-01-02", "198")
    _price("MSFT", "2026-01-03", "210")
    _price("MSFT", "2026-03-15", "220")


def _mf_payload(**overrides):
    base = {
        "asset_type": "MUTUAL_FUND",
        "scheme_code": "120503",
        "scheme_name": "Test Direct Growth Fund",
        "folio_number": "FOLIO-12345",
        "type": "BUY",
        "investment_date": "2026-03-01",
        "nav_date": "2026-03-01",
        "nav": "42.500000",
        "units_allotted": "100.00000000",
        "paid_value": "4255.00",
        "market_value": "4250.00",
        "fund_house": "Test AMC",
    }
    base.update(overrides)
    return base


def _mf_buy(api_client, **kwargs):
    return api_client.post(
        "/api/v1/transactions",
        _mf_payload(type="BUY", **kwargs),
        format="json",
    )


def _mf_nav(scheme: str, d: str, close: str):
    HistoricalPrice.objects.create(
        asset_symbol=scheme,
        date=date.fromisoformat(d),
        close_price=Decimal(close),
        currency="INR",
        source="test",
        asset_type=AssetType.MUTUAL_FUND,
    )


# --- A. Missing subjects ---


@pytest.mark.django_db
def test_compare_missing_subjects_400(api_client, seeded, today_patch):
    r = api_client.get("/api/v1/analytics/compare?range=ALL")
    assert r.status_code == 400
    assert "subjects" in r.json()["detail"].lower()


# --- B. Invalid subject format ---


@pytest.mark.django_db
def test_compare_invalid_subject_format_400(api_client, seeded, today_patch):
    r = api_client.get(_compare_url(subjects="AAPL,MSFT", range="ALL"))
    assert r.status_code == 400
    assert "format" in r.json()["detail"].lower()


# --- C. Wrong subject count ---


@pytest.mark.django_db
def test_compare_one_subject_400(api_client, seeded, today_patch):
    r = api_client.get(_compare_url(subjects="asset:AAPL", range="ALL"))
    assert r.status_code == 400
    assert "two" in r.json()["detail"].lower()


@pytest.mark.django_db
def test_compare_three_subjects_400(api_client, seeded, today_patch):
    r = api_client.get(
        _compare_url(subjects="asset:AAPL,asset:MSFT,asset:GOOG", range="ALL")
    )
    assert r.status_code == 400


@pytest.mark.django_db
def test_compare_unsupported_subject_type_400(api_client, seeded, today_patch):
    r = api_client.get(
        _compare_url(subjects="portfolio:1,asset:AAPL", range="ALL")
    )
    assert r.status_code == 400
    assert "unsupported" in r.json()["detail"].lower()


# --- D. Two stocks with overlapping dates ---


@pytest.mark.django_db
def test_compare_normalized_series_and_common_dates(api_client, seeded, today_patch):
    _seed_two_stock_overlap(api_client)
    r = api_client.get(
        _compare_url(subjects="asset:AAPL,asset:MSFT", range="ALL", portfolio_scope="all")
    )
    assert r.status_code == 200
    data = r.json()
    assert data["common_point_count"] >= 2
    assert data["common_start_date"] is not None
    assert data["common_end_date"] is not None
    assert len(data["normalized_series"]) >= 2

    first = data["normalized_series"][0]
    assert first["date"] == data["common_start_date"]
    for sid in ("asset:AAPL", "asset:MSFT"):
        assert sid in first["values"]
        assert first["values"][sid] == pytest.approx(0.0)

    second = data["normalized_series"][1]
    assert second["date"] != first["date"]
    assert isinstance(second["values"]["asset:AAPL"], float)
    assert isinstance(second["values"]["asset:MSFT"], float)


# --- E. Metrics over aligned window ---


METRIC_SHEET_RETURN_KEYS = {
    "cumulative_return",
    "cagr",
    "xirr",
    "xirr_scope",
    "twror",
}
METRIC_SHEET_RISK_KEYS = {
    "volatility_annualized",
    "downside_deviation",
    "sharpe_ratio",
    "sortino_ratio",
}
METRIC_SHEET_DRAWDOWN_KEYS = {
    "max_drawdown",
    "longest_drawdown_days",
    "calmar_ratio",
}
METRIC_SHEET_PERIOD_KEYS = {
    "best_day",
    "worst_day",
    "win_rate",
    "average_daily_return",
}


def _assert_metric_sheet_metrics_shape(metrics: dict) -> None:
    assert set(metrics["return"].keys()) == METRIC_SHEET_RETURN_KEYS
    assert set(metrics["risk"].keys()) == METRIC_SHEET_RISK_KEYS
    assert set(metrics["drawdown"].keys()) == METRIC_SHEET_DRAWDOWN_KEYS
    assert set(metrics["periods"].keys()) == METRIC_SHEET_PERIOD_KEYS


@pytest.mark.django_db
def test_compare_success_includes_common_window_warning_and_xirr_scope(
    api_client, seeded, today_patch
):
    _seed_two_stock_overlap(api_client)
    data = api_client.get(
        _compare_url(subjects="asset:AAPL,asset:MSFT", range="ALL", portfolio_scope="all")
    ).json()
    assert any(
        "Compare API metrics are computed over common overlapping dates only." in w
        for w in data["warnings"]
    )
    for subj in data["subjects"]:
        assert subj["metrics"]["return"]["xirr_scope"] == "full_scope"
        _assert_metric_sheet_metrics_shape(subj["metrics"])


@pytest.mark.django_db
def test_compare_metrics_use_aligned_window_not_independent_histories(
    api_client, seeded, today_patch
):
    _buy(api_client, asset_symbol="AAPL", date="2026-01-01")
    _buy_msft(api_client, date="2026-02-01")
    _price("AAPL", "2026-01-01", "100")
    _price("AAPL", "2026-01-02", "120")
    _price("AAPL", "2026-03-15", "120")
    _price("MSFT", "2026-02-01", "200")
    _price("MSFT", "2026-02-02", "220")
    _price("MSFT", "2026-03-15", "220")

    solo_aapl = api_client.get(
        "/api/v1/analytics/assets/AAPL/performance-metrics?range=ALL"
    ).json()
    compare = api_client.get(
        _compare_url(subjects="asset:AAPL,asset:MSFT", range="ALL")
    ).json()

    aapl_subject = next(s for s in compare["subjects"] if s["asset_symbol"] == "AAPL")
    solo_cum = solo_aapl["metrics"]["return"]["cumulative_return"]
    compare_cum = aapl_subject["metrics"]["return"]["cumulative_return"]
    assert solo_cum is not None
    assert compare_cum is not None
    # MSFT buy day often yields None daily return; first common aligned date is day after.
    assert compare["common_start_date"] == "2026-02-02"
    assert compare["range"]["start"] == compare["common_start_date"]
    assert solo_aapl["range"]["start"] < compare["range"]["start"]
    solo_twror = solo_aapl["metrics"]["return"]["twror"]
    compare_twror = aapl_subject["metrics"]["return"]["twror"]
    if solo_twror is not None and compare_twror is not None:
        assert compare_twror != pytest.approx(solo_twror, rel=1e-6)


# --- F. Missing overlap ---


@pytest.mark.django_db
def test_compare_insufficient_overlap_warning_and_null_metrics(
    api_client, seeded, today_patch
):
    _buy(api_client, asset_symbol="AAPL", date="2026-01-01", quantity="10")
    api_client.post(
        "/api/v1/transactions",
        {
            "asset_symbol": "AAPL",
            "date": "2026-01-05",
            "type": "SELL",
            "quantity": "10",
            "price_per_share": "110",
            "currency": "EUR",
            "fees": "0",
        },
        format="json",
    )
    _buy_msft(api_client, date="2026-03-01")
    _price("AAPL", "2026-01-01", "100")
    _price("AAPL", "2026-01-05", "110")
    _price("MSFT", "2026-03-01", "200")
    _price("MSFT", "2026-03-02", "210")

    data = api_client.get(
        _compare_url(subjects="asset:AAPL,asset:MSFT", range="ALL")
    ).json()
    assert data["common_point_count"] < 2
    assert any("Insufficient common overlapping" in w for w in data["warnings"])
    for subj in data["subjects"]:
        assert subj["metrics"]["return"]["cumulative_return"] is None
        assert subj["periodic_returns"] == {"monthly": [], "yearly": []}
        assert subj["drawdown_periods"] == {"worst": []}
        assert subj["drawdown_series"] == []


@pytest.mark.django_db
def test_compare_subjects_include_periodic_returns_and_drawdown_periods(
    api_client, seeded, today_patch
):
    _seed_two_stock_overlap(api_client)
    data = api_client.get(
        _compare_url(subjects="asset:AAPL,asset:MSFT", range="ALL", portfolio_scope="all")
    ).json()
    assert len(data["subjects"]) == 2
    for subj in data["subjects"]:
        assert "periodic_returns" in subj
        assert "drawdown_periods" in subj
        assert isinstance(subj["periodic_returns"]["monthly"], list)
        assert isinstance(subj["periodic_returns"]["yearly"], list)
        assert isinstance(subj["drawdown_periods"]["worst"], list)
        assert "drawdown_series" in subj
        assert isinstance(subj["drawdown_series"], list)
        for pt in subj["drawdown_series"]:
            assert pt["drawdown"] <= 0
        for ep in subj["drawdown_periods"]["worst"]:
            assert "rank" in ep


# --- G. Benchmark metrics ---


@pytest.mark.django_db
def test_compare_benchmark_metrics_per_subject(api_client, seeded, today_patch):
    BenchmarkIndexConfig.objects.get_or_create(
        symbol="^GSPC",
        defaults={"display_name": "S&P 500", "enabled": True},
    )
    _seed_two_stock_overlap(api_client)
    _index_price("^GSPC", "2026-01-01", "1000")
    _index_price("^GSPC", "2026-01-02", "1010")
    _index_price("^GSPC", "2026-01-03", "1005")
    _index_price("^GSPC", "2026-03-15", "1020")

    data = api_client.get(
        _compare_url(
            subjects="asset:AAPL,asset:MSFT",
            range="ALL",
            benchmark="^GSPC",
        )
    ).json()
    for subj in data["subjects"]:
        assert subj["benchmark"] is not None
        assert subj["benchmark"]["symbol"] == "^GSPC"
        assert subj["benchmark"]["paired_count"] >= 2
        assert subj["benchmark"]["metrics"]["beta"] is not None


# --- H. Missing benchmark prices ---


@pytest.mark.django_db
def test_compare_missing_benchmark_prices_null_metrics_and_warning(
    api_client, seeded, today_patch
):
    BenchmarkIndexConfig.objects.get_or_create(
        symbol="^GSPC",
        defaults={"display_name": "S&P 500", "enabled": True},
    )
    _seed_two_stock_overlap(api_client)
    data = api_client.get(
        _compare_url(
            subjects="asset:AAPL,asset:MSFT",
            range="ALL",
            benchmark="^GSPC",
        )
    ).json()
    for subj in data["subjects"]:
        assert subj["benchmark"]["metrics"] is None
        assert subj["benchmark"]["paired_count"] == 0
        assert any("Benchmark prices" in w for w in subj["warnings"])


# --- I. Split warning propagation ---


@pytest.mark.django_db
def test_compare_split_warning_on_one_subject(api_client, seeded, today_patch):
    api_client.post(
        "/api/v1/transactions",
        {
            "asset_symbol": "RAW",
            "date": "2026-01-01",
            "type": "BUY",
            "quantity": "1",
            "price_per_share": "100",
            "currency": "EUR",
            "fees": "0",
        },
        format="json",
    )
    api_client.post(
        "/api/v1/transactions",
        {
            "asset_symbol": "RAW",
            "date": "2026-01-10",
            "type": "STOCK_SPLIT",
            "split_from": "1",
            "split_to": "10",
            "currency": "EUR",
        },
        format="json",
    )
    _buy_msft(api_client, date="2026-01-01")
    _price("RAW", "2026-01-01", "100")
    _price("RAW", "2026-01-10", "10")
    _price("RAW", "2026-03-15", "10")
    _price("MSFT", "2026-01-01", "200")
    _price("MSFT", "2026-01-02", "200")
    _price("MSFT", "2026-03-15", "200")

    data = api_client.get(
        _compare_url(subjects="asset:RAW,asset:MSFT", range="ALL")
    ).json()
    raw_subj = next(s for s in data["subjects"] if s["asset_symbol"] == "RAW")
    assert any("split-adjusted" in w.lower() for w in raw_subj["warnings"])


# --- J. Scoping ---


@pytest.mark.django_db
def test_compare_portfolio_id_scoping(api_client, seeded, today_patch):
    p1 = ensure_default_portfolio()
    p2 = Portfolio.objects.create(name="Scoped", base_currency="EUR", is_active=True)
    _buy(api_client, portfolio_id=p1.id, asset_symbol="AAPL", date="2026-01-01")
    _buy(api_client, portfolio_id=p2.id, asset_symbol="AAPL", date="2026-01-01")
    _buy_msft(api_client, portfolio_id=p2.id, date="2026-01-01")
    for sym in ("AAPL", "MSFT"):
        _price(sym, "2026-01-01", "100")
        _price(sym, "2026-01-02", "110")
        _price(sym, "2026-03-15", "120")

    missing = api_client.get(
        _compare_url(
            subjects="asset:AAPL,asset:MSFT",
            range="ALL",
            portfolio_id=str(p1.id),
        )
    )
    assert missing.status_code == 404

    scoped = api_client.get(
        _compare_url(
            subjects="asset:AAPL,asset:MSFT",
            range="ALL",
            portfolio_id=str(p2.id),
        )
    )
    assert scoped.status_code == 200


# --- K. Mutual fund ---


@pytest.mark.django_db
def test_compare_mf_vs_stock(api_client, seeded, today_patch):
    _mf_buy(api_client, investment_date="2026-03-01", nav_date="2026-03-01")
    _buy_msft(api_client, date="2026-03-01")
    for day in range(1, 16):
        _mf_nav("120503", f"2026-03-{day:02d}", str(42.50 + day * 0.1))
    _price("MSFT", "2026-03-01", "200")
    _price("MSFT", "2026-03-02", "210")
    _price("MSFT", "2026-03-15", "220")

    r = api_client.get(
        _compare_url(
            subjects="asset:120503,asset:MSFT",
            range="ALL",
        )
    )
    assert r.status_code == 200
    data = r.json()
    assert data["common_point_count"] >= 2
    mf_subj = next(s for s in data["subjects"] if s["asset_symbol"] == "120503")
    assert mf_subj["folio_number"] == "FOLIO-12345"


@pytest.mark.django_db
def test_compare_unknown_asset_404(api_client, seeded, today_patch):
    _buy(api_client)
    _price("AAPL", "2026-01-01", "100")
    r = api_client.get(
        _compare_url(subjects="asset:AAPL,asset:NOPE", range="ALL")
    )
    assert r.status_code == 404


# --- L. No external calls ---


@pytest.mark.django_db
@patch("yfinance.Ticker")
def test_compare_no_yfinance_on_read(mock_ticker, api_client, seeded, today_patch):
    _seed_two_stock_overlap(api_client)
    r = api_client.get(
        _compare_url(subjects="asset:AAPL,asset:MSFT", range="ALL")
    )
    assert r.status_code == 200
    mock_ticker.assert_not_called()
