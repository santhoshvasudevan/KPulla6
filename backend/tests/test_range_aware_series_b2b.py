"""Phase B2B: range-aware portfolio value series parity and correctness."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from finance.performance_range import resolve_performance_range_start
from finance.twror import compute_twror_series
from fx.services import upsert_fx_rate
from market_data.models import AssetType, HistoricalPrice
from portfolios.models import Portfolio
from portfolios.performance_service import (
    build_all_scope_external_flows,
    build_portfolio_performance,
    performance_list_payload,
)
from portfolios.scope import resolve_portfolio_scope
from portfolios.summary_service import build_all_scope_portfolio_value_timeseries


def _mf_payload(**overrides):
    base = {
        "asset_type": "MUTUAL_FUND",
        "scheme_code": "120503",
        "scheme_name": "Test Direct Growth Fund",
        "folio_number": "FOLIO-12345",
        "type": "BUY",
        "investment_date": "2026-03-10",
        "nav_date": "2026-03-15",
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


def _price(symbol: str, d: str, close: str, *, currency: str = "EUR", asset_type=AssetType.STOCK):
    HistoricalPrice.objects.create(
        asset_symbol=symbol,
        date=date.fromisoformat(d),
        close_price=Decimal(close),
        currency=currency,
        source="test",
        asset_type=asset_type,
    )


def _mf_nav(scheme: str, d: str, close: str):
    _price(scheme, d, close, currency="INR", asset_type=AssetType.MUTUAL_FUND)


def _reference_value_series(
    scope,
    display_currency: str,
    range_code: str,
    today: date,
) -> list[dict]:
    """Full inception build + post-hoc slice (pre-B2B behavior)."""
    full = build_all_scope_portfolio_value_timeseries(
        scope, display_currency, emit_start_date=None
    )
    if not full:
        return []
    from portfolios.summary_service import fifo_eligible_queryset

    txns = list(fifo_eligible_queryset(scope.portfolio_ids))
    inception = min(t.date for t in txns)
    range_start = resolve_performance_range_start(range_code, today, inception)
    start_iso = range_start.isoformat()
    return [p for p in full if p["date"] >= start_iso]


def _reference_performance_points(
    scope,
    metric: str,
    range_code: str,
    display_currency: str,
    today: date,
) -> list[dict]:
    sliced = _reference_value_series(scope, display_currency, range_code, today)
    if metric == "value":
        return [
            {
                "date": p["date"],
                "value": p.get("portfolio_value"),
                "metric": "value",
                "currency": display_currency,
            }
            for p in sliced
        ]
    flows, flows_unknown = build_all_scope_external_flows(scope, display_currency)
    if metric == "cumulative_return":
        out = []
        for p in sliced:
            d = date.fromisoformat(p["date"])
            pv = p.get("portfolio_value")
            if pv is None:
                out.append({"date": p["date"], "value": None, "metric": metric})
                continue
            contrib = Decimal("0")
            withdraw = Decimal("0")
            for td, f in flows.items():
                if td > d:
                    continue
                if f >= 0:
                    contrib += f
                else:
                    withdraw += -f
            if contrib <= 0:
                out.append({"date": p["date"], "value": None, "metric": metric})
                continue
            val = float(((Decimal(str(pv)) + withdraw - contrib) / contrib) * 100)
            out.append({"date": p["date"], "value": val, "metric": metric})
        return out
    twror_pts = compute_twror_series(sliced, flows, flows_unknown_from=flows_unknown)
    return [
        {
            "date": p.date.isoformat(),
            "value": float(p.value) if p.value is not None else None,
            "metric": "twror",
        }
        for p in twror_pts
    ]


def _points_by_date(rows: list[dict]) -> dict[str, float | None]:
    return {r["date"]: r.get("value") for r in rows}


def _assert_points_match(actual: dict[str, float | None], expected: dict[str, float | None]) -> None:
    assert actual.keys() == expected.keys()
    for day in actual:
        av, ev = actual[day], expected[day]
        if av is None and ev is None:
            continue
        assert av == pytest.approx(ev, rel=1e-6, abs=1e-4)


@pytest.fixture
def pln_mf_scope(api_client, seeded, monkeypatch, test_user):
    """Mixed EUR PLN stock + INR MF all-scope (from performance gap tests)."""
    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2024, 4, 15))
    eur_portfolio = Portfolio.objects.create(user=test_user, 
        name="EUR PLN Stock", base_currency="EUR", is_active=True
    )
    inr_portfolio = Portfolio.objects.create(user=test_user, 
        name="INR MF Only", base_currency="INR", is_active=True
    )
    api_client.post(
        "/api/v1/transactions",
        {
            "portfolio_id": eur_portfolio.id,
            "asset_symbol": "PLNSTK",
            "date": "2024-04-01",
            "type": "BUY",
            "quantity": "10",
            "price_per_share": "100",
            "currency": "EUR",
            "fees": "0",
        },
        format="json",
    )
    _mf_buy(
        api_client,
        portfolio_id=inr_portfolio.id,
        folio_number="B2B-FOLIO",
        investment_date="2024-04-01",
        nav_date="2024-04-01",
        nav="50.00",
        units_allotted="100.00000000",
        paid_value="5000.00",
        market_value="5000.00",
    )
    _price("PLNSTK", "2024-04-01", "100", currency="PLN")
    _price("PLNSTK", "2024-04-15", "110", currency="PLN")
    _mf_nav("120503", "2024-04-01", "50.00")
    _mf_nav("120503", "2024-04-15", "55.00")
    for day in range(1, 16):
        d = date(2024, 4, day)
        upsert_fx_rate(
            from_currency="PLN",
            to_currency="EUR",
            row_date=d,
            rate=Decimal("0.23"),
        )
        upsert_fx_rate(
            from_currency="INR",
            to_currency="EUR",
            row_date=d,
            rate=Decimal("0.011"),
        )
    return resolve_portfolio_scope(test_user, portfolio_scope="all")


@pytest.mark.django_db
@pytest.mark.parametrize("metric", ["value", "cumulative_return", "twror"])
@pytest.mark.parametrize("range_code", ["30D", "1Y"])
def test_range_aware_parity_vs_full_build_slice(pln_mf_scope, metric, range_code):
    scope = pln_mf_scope
    today = date(2024, 4, 15)
    pts = performance_list_payload(
        build_portfolio_performance(
            scope=scope,
            metric=metric,  # type: ignore[arg-type]
            range_code=range_code,
            display_currency="EUR",
            today=today,
        ).points
    )
    ref = _reference_performance_points(scope, metric, range_code, "EUR", today)
    _assert_points_match(_points_by_date(pts), _points_by_date(ref))
    assert len(pts) == len(ref)
    assert len(pts) < 20 if range_code == "30D" else len(pts) < 400


@pytest.mark.django_db
def test_range_aware_opening_holdings_before_range_start(api_client, seeded, monkeypatch, test_user):
    """Asset bought before range_start still contributes to in-range value."""
    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2026, 3, 20))
    p = Portfolio.objects.create(user=test_user, name="Holdings", base_currency="EUR", is_active=True)
    api_client.post(
        "/api/v1/transactions",
        {
            "portfolio_id": p.id,
            "asset_symbol": "EARLY",
            "date": "2026-01-01",
            "type": "BUY",
            "quantity": "10",
            "price_per_share": "100",
            "currency": "EUR",
            "fees": "0",
        },
        format="json",
    )
    HistoricalPrice.objects.create(
        asset_symbol="EARLY",
        date=date(2026, 1, 1),
        close_price=Decimal("100"),
        currency="EUR",
        source="test",
        asset_type=AssetType.STOCK,
    )
    HistoricalPrice.objects.create(
        asset_symbol="EARLY",
        date=date(2026, 3, 20),
        close_price=Decimal("120"),
        currency="EUR",
        source="test",
        asset_type=AssetType.STOCK,
    )
    scope = resolve_portfolio_scope(test_user, portfolio_scope="all")
    pts = performance_list_payload(
        build_portfolio_performance(
            scope=scope,
            metric="value",
            range_code="30D",
            display_currency="EUR",
        ).points
    )
    last = [p for p in pts if p["date"] == "2026-03-20"][0]
    assert last["value"] == pytest.approx(1200.0)


@pytest.mark.django_db
def test_range_aware_mf_nav_forward_fill(api_client, seeded, monkeypatch, test_user):
    """NAV before range_start forward-fills until a newer NAV appears."""
    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2026, 3, 10))
    p = Portfolio.objects.create(user=test_user, name="MF Nav", base_currency="INR", is_active=True)
    _mf_buy(
        api_client,
        portfolio_id=p.id,
        folio_number="NAV-FOLIO",
        investment_date="2026-01-01",
        nav_date="2026-01-01",
        nav="50.00",
        units_allotted="10.00000000",
        paid_value="500.00",
        market_value="500.00",
    )
    _mf_nav("120503", "2026-01-01", "50.00")
    _mf_nav("120503", "2026-03-10", "60.00")
    upsert_fx_rate(
        from_currency="INR",
        to_currency="EUR",
        row_date=date(2026, 1, 1),
        rate=Decimal("0.01"),
    )
    upsert_fx_rate(
        from_currency="INR",
        to_currency="EUR",
        row_date=date(2026, 3, 10),
        rate=Decimal("0.01"),
    )
    scope = resolve_portfolio_scope(test_user, portfolio_scope="all")
    ref = _reference_value_series(scope, "EUR", "30D", date(2026, 3, 10))
    aware = build_all_scope_portfolio_value_timeseries(
        scope,
        "EUR",
        emit_start_date=resolve_performance_range_start(
            "30D", date(2026, 3, 10), date(2026, 1, 1)
        ),
    )
    assert {p["date"]: p["portfolio_value"] for p in aware} == {
        p["date"]: p["portfolio_value"] for p in ref
    }


@pytest.mark.django_db
def test_range_aware_fx_seven_day_lookback(api_client, seeded, monkeypatch, test_user):
    """FX rate within 7 days before range_start is used via fill semantics."""
    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2026, 3, 20))
    p = Portfolio.objects.create(user=test_user, name="FX Lookback", base_currency="EUR", is_active=True)
    api_client.post(
        "/api/v1/transactions",
        {
            "portfolio_id": p.id,
            "asset_symbol": "FXSTK",
            "date": "2026-01-01",
            "type": "BUY",
            "quantity": "10",
            "price_per_share": "100",
            "currency": "USD",
            "fees": "0",
        },
        format="json",
    )
    HistoricalPrice.objects.create(
        asset_symbol="FXSTK",
        date=date(2026, 1, 1),
        close_price=Decimal("100"),
        currency="USD",
        source="test",
        asset_type=AssetType.STOCK,
    )
    HistoricalPrice.objects.create(
        asset_symbol="FXSTK",
        date=date(2026, 3, 20),
        close_price=Decimal("100"),
        currency="USD",
        source="test",
        asset_type=AssetType.STOCK,
    )
    range_start = date(2026, 3, 15)
    upsert_fx_rate(
        from_currency="USD",
        to_currency="EUR",
        row_date=range_start - timedelta(days=3),
        rate=Decimal("0.90"),
    )
    scope = resolve_portfolio_scope(test_user, portfolio_scope="all")
    ref = _reference_value_series(scope, "EUR", "30D", date(2026, 3, 20))
    aware = build_all_scope_portfolio_value_timeseries(
        scope, "EUR", emit_start_date=range_start
    )
    ref_at_start = [p for p in ref if p["date"] == range_start.isoformat()][0]
    aware_at_start = [p for p in aware if p["date"] == range_start.isoformat()][0]
    assert aware_at_start["portfolio_value"] == pytest.approx(
        ref_at_start["portfolio_value"], rel=1e-6
    )
    assert aware_at_start["portfolio_value"] == pytest.approx(900.0, rel=1e-6)


@pytest.mark.django_db
def test_range_aware_stock_split(api_client, seeded, monkeypatch, test_user):
    """Split-adjusted quantity/value remains correct when split precedes range."""
    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2026, 3, 20))
    p = Portfolio.objects.create(user=test_user, name="Split", base_currency="EUR", is_active=True)
    api_client.post(
        "/api/v1/transactions",
        {
            "portfolio_id": p.id,
            "asset_symbol": "SPLT",
            "date": "2026-01-01",
            "type": "BUY",
            "quantity": "10",
            "price_per_share": "100",
            "currency": "EUR",
            "fees": "0",
        },
        format="json",
    )
    api_client.post(
        "/api/v1/transactions",
        {
            "portfolio_id": p.id,
            "asset_symbol": "SPLT",
            "date": "2026-02-01",
            "type": "STOCK_SPLIT",
            "quantity": "0",
            "price_per_share": "0",
            "currency": "EUR",
            "split_from": "1",
            "split_to": "2",
            "fees": "0",
        },
        format="json",
    )
    _price("SPLT", "2026-01-01", "100")
    _price("SPLT", "2026-02-01", "50")
    _price("SPLT", "2026-03-20", "55")
    scope = resolve_portfolio_scope(test_user, portfolio_scope="all")
    ref = _reference_performance_points(scope, "value", "30D", "EUR", date(2026, 3, 20))
    pts = performance_list_payload(
        build_portfolio_performance(
            scope=scope,
            metric="value",
            range_code="30D",
            display_currency="EUR",
        ).points
    )
    assert _points_by_date(pts) == _points_by_date(ref)


@pytest.mark.django_db
def test_range_aware_twror_first_point_null(pln_mf_scope):
    scope = pln_mf_scope
    pts = performance_list_payload(
        build_portfolio_performance(
            scope=scope,
            metric="twror",
            range_code="30D",
            display_currency="EUR",
            today=date(2024, 4, 15),
        ).points
    )
    assert pts[0]["value"] is None
    assert any(p["value"] is not None for p in pts[1:])


@pytest.mark.django_db
def test_range_aware_1y_uses_bulk_fx_not_n_plus_one(pln_mf_scope):
    from django.db import connection, reset_queries
    from django.test.utils import CaptureQueriesContext

    scope = pln_mf_scope
    reset_queries()
    with CaptureQueriesContext(connection) as ctx:
        build_portfolio_performance(
            scope=scope,
            metric="value",
            range_code="1Y",
            display_currency="EUR",
            today=date(2024, 4, 15),
        )
    fx_queries = sum(1 for q in ctx.captured_queries if '"fx_rates"' in q["sql"])
    assert len(ctx.captured_queries) < 200
    assert fx_queries <= 10
