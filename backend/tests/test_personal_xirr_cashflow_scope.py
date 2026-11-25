"""Personal XIRR cash-flow and scope regressions (#21).

Expectations use independently constructed date/amount series and pyxirr,
not merely another call into mutual_fund_holding_xirr.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest
import pyxirr
from tests.conftest import cached_mf_nav, historical_mf_transaction
from portfolios.seed import ensure_default_portfolio
from tests.test_mutual_fund_nav_sync import MockNavProvider

from market_data.models import AssetType, HistoricalPrice, MutualFundNavFetchState
from portfolios.models import Portfolio
from tests.test_analytics_asset_metrics_api import _mf_payload

MF_NAV_FETCH_FACTORY = "market_data.services.missing_nav_fetch.default_mutual_fund_nav_provider"


SCHEME = "120503"
FOLIO = "FOLIO-12345"


def _nav(day: str, value: str, scheme: str = SCHEME) -> None:
    HistoricalPrice.objects.create(
        asset_symbol=scheme,
        asset_type=AssetType.MUTUAL_FUND,
        date=date.fromisoformat(day),
        close_price=Decimal(value),
        currency="INR",
    )


def _oracle(flows: list[tuple[date, float]]) -> float | None:
    dates, amounts = zip(*flows)
    try:
        return pyxirr.xirr(list(dates), list(amounts))
    except Exception:
        return None


def _metrics(client, **params):
    query = {"range": "ALL", "display_currency": "EUR", **params}
    response = client.get(f"/api/v1/analytics/assets/{SCHEME}/performance-metrics", query)
    assert response.status_code == 200, response.json()
    return response.json()


def _holding_xirr(client, folio: str = FOLIO, **params):
    response = client.get("/api/v1/portfolio/holdings", {"display_currency": "EUR", **params})
    assert response.status_code == 200, response.json()
    rows = [
        h for h in response.json()["holdings"]
        if h.get("scheme_code") == SCHEME and h.get("folio_number") == folio
    ]
    assert len(rows) == 1, response.json()["holdings"]
    return rows[0]["xirr"]


def _detail_xirr(client, folio: str = FOLIO, **params):
    response = client.get(
        f"/api/v1/portfolio/assets/{SCHEME}",
        {"folio_number": folio, "display_currency": "EUR", **params},
    )
    assert response.status_code == 200, response.json()
    return response.json()["xirr"]


@pytest.mark.django_db
def test_personal_xirr_uses_investment_date_not_nav_date(api_client, legacy_seeded, monkeypatch):
    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2026, 8, 16))
    cached_mf_nav("120503", '2024-01-15', '100')
    assert api_client.post("/api/v1/transactions", _mf_payload(
        investment_date="2024-01-01", nav_date="2024-01-15", nav="100",
        units_allotted="100", paid_value="10000", market_value="10000",
        folio_number=FOLIO,
    ), format="json").status_code == 201
    _nav("2026-08-16", "118.089530")
    expected = _oracle([
        (date(2024, 1, 1), -10000.0),
        (date(2026, 8, 16), 11808.953),
    ])
    wrong_nav_date = _oracle([
        (date(2024, 1, 15), -10000.0),
        (date(2026, 8, 16), 11808.953),
    ])
    personal = _metrics(api_client, folio_number=FOLIO)["personal_metrics"]
    assert personal["xirr"] == pytest.approx(expected, abs=1e-9)
    assert personal["xirr"] != pytest.approx(wrong_nav_date, abs=1e-4)
    assert personal["xirr"] == pytest.approx(0.0654, abs=5e-4)
    years = (date(2026, 8, 16) - date(2024, 1, 1)).days / 365.0
    npv = -10000.0 + 11808.953 / ((1.0 + personal["xirr"]) ** years)
    assert abs(npv) < 1.0


@pytest.mark.django_db
def test_personal_xirr_buy_paid_value_does_not_double_count_fees(api_client, legacy_seeded, monkeypatch):
    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2025, 1, 1))
    cached_mf_nav("120503", '2024-01-01', '100')
    assert api_client.post("/api/v1/transactions", _mf_payload(
        investment_date="2024-01-01", nav_date="2024-01-01", nav="100",
        units_allotted="100", paid_value="10100", market_value="10000",
        fees="100", folio_number=FOLIO,
    ), format="json").status_code == 201
    _nav("2025-01-01", "110")
    expected = _oracle([
        (date(2024, 1, 1), -10100.0),  # paid_value already includes fees
        (date(2025, 1, 1), 11000.0),
    ])
    double_counted = _oracle([
        (date(2024, 1, 1), -10200.0),
        (date(2025, 1, 1), 11000.0),
    ])
    personal = _metrics(api_client, folio_number=FOLIO)["personal_metrics"]
    assert personal["xirr"] == pytest.approx(expected, abs=1e-9)
    assert personal["xirr"] != pytest.approx(double_counted, abs=1e-4)


@pytest.mark.django_db
def test_personal_xirr_sell_paid_value_zero_uses_units_nav_fees_fallback(
    api_client, legacy_seeded, monkeypatch
):
    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2025, 6, 1))
    cached_mf_nav("120503", '2024-01-01', '100')
    assert api_client.post("/api/v1/transactions", _mf_payload(
        investment_date="2024-01-01", nav_date="2024-01-01", nav="100",
        units_allotted="100", paid_value="10000", market_value="10000",
        folio_number=FOLIO,
    ), format="json").status_code == 201
    cached_mf_nav("120503", '2025-01-01', '120')
    sell = api_client.post("/api/v1/transactions", _mf_payload(
        type="SELL", investment_date="2025-01-01", nav_date="2025-01-01", nav="120",
        units_allotted="100", paid_value="0", market_value="12000",
        fees="50", folio_number=FOLIO,
    ), format="json")
    assert sell.status_code == 201, sell.json()
    expected = _oracle([
        (date(2024, 1, 1), -10000.0),
        (date(2025, 1, 1), 11950.0),  # 100*120 - 50
    ])
    personal = _metrics(api_client, folio_number=FOLIO)["personal_metrics"]
    assert personal["xirr"] == pytest.approx(expected, abs=1e-9)


@pytest.mark.django_db
def test_personal_xirr_sell_prefers_actual_cash_received(api_client, legacy_seeded, monkeypatch):
    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2025, 6, 1))
    cached_mf_nav("120503", '2024-01-01', '100')
    assert api_client.post("/api/v1/transactions", _mf_payload(
        investment_date="2024-01-01", nav_date="2024-01-01", nav="100",
        units_allotted="100", paid_value="10000", market_value="10000",
        folio_number=FOLIO,
    ), format="json").status_code == 201
    cached_mf_nav("120503", '2025-01-01', '120')
    sell = api_client.post("/api/v1/transactions", _mf_payload(
        type="SELL", investment_date="2025-01-01", nav_date="2025-01-01", nav="120",
        units_allotted="100", paid_value="12000", market_value="12000",
        actual_cash_received="11500", folio_number=FOLIO,
    ), format="json")
    assert sell.status_code == 201, sell.json()
    expected = _oracle([
        (date(2024, 1, 1), -10000.0),
        (date(2025, 1, 1), 11500.0),
    ])
    paid_value_path = _oracle([
        (date(2024, 1, 1), -10000.0),
        (date(2025, 1, 1), 12000.0),
    ])
    personal = _metrics(api_client, folio_number=FOLIO)["personal_metrics"]
    assert personal["status"] == "calculated"
    assert personal["xirr"] == pytest.approx(expected, abs=1e-9)
    assert personal["xirr"] != pytest.approx(paid_value_path, abs=1e-4)


@pytest.mark.django_db
def test_personal_xirr_partial_sale_and_same_day_flows(api_client, legacy_seeded, monkeypatch):
    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2025, 1, 1))
    cached_mf_nav("120503", '2024-01-01', '100')
    assert api_client.post("/api/v1/transactions", _mf_payload(
        investment_date="2024-01-01", nav_date="2024-01-01", nav="100",
        units_allotted="100", paid_value="10000", market_value="10000",
        folio_number=FOLIO,
    ), format="json").status_code == 201
    # Same-day second purchase.
    cached_mf_nav("120503", '2024-01-01', '100')
    assert api_client.post("/api/v1/transactions", _mf_payload(
        investment_date="2024-01-01", nav_date="2024-01-01", nav="100",
        units_allotted="50", paid_value="5000", market_value="5000",
        folio_number=FOLIO,
    ), format="json").status_code == 201
    cached_mf_nav("120503", '2024-07-01', '110')
    assert api_client.post("/api/v1/transactions", _mf_payload(
        type="SELL", investment_date="2024-07-01", nav_date="2024-07-01", nav="110",
        units_allotted="60", paid_value="6600", market_value="6600",
        folio_number=FOLIO,
    ), format="json").status_code == 201
    _nav("2025-01-01", "120")
    # Remaining 90 units × 120 = 10800 terminal.
    expected = _oracle([
        (date(2024, 1, 1), -15000.0),
        (date(2024, 7, 1), 6600.0),
        (date(2025, 1, 1), 10800.0),
    ])
    personal = _metrics(api_client, folio_number=FOLIO)["personal_metrics"]
    assert personal["xirr"] == pytest.approx(expected, abs=1e-9)
    assert personal["status"] == "calculated"


@pytest.mark.django_db
def test_personal_xirr_unavailable_for_missing_nav_and_oversell(api_client, legacy_seeded, monkeypatch, test_user):
    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2025, 1, 1))
    historical_mf_transaction(ensure_default_portfolio(test_user), _mf_payload(
        investment_date="2024-01-01", nav_date="2024-01-01", nav="100",
        units_allotted="100", paid_value="10000", market_value="10000",
        folio_number=FOLIO,
    ))
    missing = _metrics(api_client, folio_number=FOLIO)["personal_metrics"]
    assert missing["xirr"] is None
    assert missing["status"] == "unavailable"

    _nav("2025-01-01", "0")
    nonpositive = _metrics(api_client, folio_number=FOLIO)["personal_metrics"]
    assert nonpositive["xirr"] is None
    assert nonpositive["status"] == "unavailable"

    HistoricalPrice.objects.filter(asset_symbol=SCHEME).delete()
    _nav("2025-01-01", "120")
    cached_mf_nav("120503", '2024-06-01', '110')
    oversell = api_client.post("/api/v1/transactions", _mf_payload(
        type="SELL", investment_date="2024-06-01", nav_date="2024-06-01", nav="110",
        units_allotted="150", paid_value="16500", market_value="16500",
        folio_number=FOLIO,
    ), format="json")
    assert oversell.status_code == 201, oversell.json()
    bad = _metrics(api_client, folio_number=FOLIO)["personal_metrics"]
    assert bad["xirr"] is None
    assert bad["status"] == "unavailable"


@pytest.mark.django_db
def test_personal_xirr_folio_and_portfolio_scope_and_surface_parity(
    api_client, legacy_seeded, test_user, monkeypatch
):
    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2025, 1, 1))
    primary = Portfolio.objects.filter(user=test_user).order_by("id").first()
    secondary = Portfolio.objects.create(
        user=test_user, name="Secondary XIRR Scope", base_currency="EUR",
        cash_aware_enabled=False,
    )
    cached_mf_nav("120503", '2024-01-01', '100')
    assert api_client.post("/api/v1/transactions", _mf_payload(
        investment_date="2024-01-01", nav_date="2024-01-01", nav="100",
        units_allotted="100", paid_value="10000", market_value="10000",
        folio_number="F-A", portfolio_id=primary.id,
    ), format="json").status_code == 201
    cached_mf_nav("120503", '2024-01-01', '100')
    assert api_client.post("/api/v1/transactions", _mf_payload(
        investment_date="2024-01-01", nav_date="2024-01-01", nav="100",
        units_allotted="50", paid_value="10000", market_value="5000",
        folio_number="F-B", portfolio_id=primary.id,
    ), format="json").status_code == 201
    cached_mf_nav("120503", '2024-06-01', '110')
    assert api_client.post("/api/v1/transactions", _mf_payload(
        investment_date="2024-06-01", nav_date="2024-06-01", nav="110",
        units_allotted="40", paid_value="4400", market_value="4400",
        folio_number="F-A", portfolio_id=secondary.id,
    ), format="json").status_code == 201
    cached_mf_nav('120504', '2024-01-01', '100')
    assert api_client.post("/api/v1/transactions", _mf_payload(
        scheme_code="120504", scheme_name="Compare Peer Fund",
        investment_date="2024-01-01", nav_date="2024-01-01", nav="100",
        units_allotted="10", paid_value="1000", market_value="1000",
        folio_number="F-A", portfolio_id=primary.id,
    ), format="json").status_code == 201
    _nav("2025-01-01", "120")
    _nav("2025-01-01", "120", scheme="120504")

    expected_fa_primary = _oracle([
        (date(2024, 1, 1), -10000.0),
        (date(2025, 1, 1), 12000.0),
    ])
    expected_fb = _oracle([
        (date(2024, 1, 1), -10000.0),
        (date(2025, 1, 1), 6000.0),
    ])
    expected_fa_all = _oracle([
        (date(2024, 1, 1), -10000.0),
        (date(2024, 6, 1), -4400.0),
        (date(2025, 1, 1), 16800.0),  # 140 units
    ])

    fa_primary = _metrics(
        api_client, folio_number="F-A", portfolio_id=primary.id
    )["personal_metrics"]
    assert fa_primary["xirr"] == pytest.approx(expected_fa_primary, abs=1e-9)
    fb = _metrics(api_client, folio_number="F-B")["personal_metrics"]
    assert fb["xirr"] == pytest.approx(expected_fb, abs=1e-9)
    fa_all = _metrics(api_client, folio_number="F-A")["personal_metrics"]
    assert fa_all["xirr"] == pytest.approx(expected_fa_all, abs=1e-9)
    # Combined folio scope is not an average of position XIRRs.
    assert fa_all["xirr"] != pytest.approx(
        (expected_fa_primary + expected_fb) / 2, abs=1e-4
    )

    # Surface parity for identical folio/portfolio scope.
    assert _holding_xirr(api_client, folio="F-A", portfolio_id=primary.id) == pytest.approx(
        fa_primary["xirr"], abs=1e-9
    )
    assert _detail_xirr(api_client, folio="F-A", portfolio_id=primary.id) == pytest.approx(
        fa_primary["xirr"], abs=1e-9
    )

    compare = api_client.get("/api/v1/analytics/compare", {
        "subjects": f"asset:{SCHEME},asset:120504",
        "range": "ALL",
        "folio_number": "F-A",
        "portfolio_id": primary.id,
    })
    assert compare.status_code == 200, compare.json()
    subject = compare.json()["subjects"][0]
    assert subject["personal_metrics"]["xirr"] == pytest.approx(fa_primary["xirr"], abs=1e-9)
    assert subject["personal_metrics"]["basis"] == "native_inr"
    # Fund NAV block remains independent of personal scope selection.
    assert subject["metrics"]["return"]["xirr"] is None
    unknown_folio = api_client.get("/api/v1/analytics/compare", {
        "subjects": f"asset:{SCHEME},asset:120504", "range": "ALL",
        "folio_number": "NOT-OWNED", "portfolio_id": primary.id,
    })
    assert unknown_folio.status_code == 404


@pytest.mark.django_db
def test_personal_xirr_independent_of_display_currency_and_range(
    api_client, legacy_seeded, monkeypatch
):
    from fx.services import upsert_fx_rate

    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2026, 8, 16))
    cached_mf_nav("120503", '2024-01-01', '100')
    assert api_client.post("/api/v1/transactions", _mf_payload(
        investment_date="2024-01-01", nav_date="2024-01-01", nav="100",
        units_allotted="100", paid_value="10000", market_value="10000",
        folio_number=FOLIO,
    ), format="json").status_code == 201
    _nav("2026-08-16", "118.089530")
    upsert_fx_rate(
        from_currency="INR", to_currency="EUR",
        row_date=date(2024, 1, 1), rate=Decimal("0.01111111"),
    )
    eur_all = _metrics(api_client, folio_number=FOLIO, display_currency="EUR", range="ALL")
    inr_1y = _metrics(api_client, folio_number=FOLIO, display_currency="INR", range="1Y")
    assert eur_all["personal_metrics"]["xirr"] == pytest.approx(
        inr_1y["personal_metrics"]["xirr"], abs=1e-9
    )
    assert eur_all["personal_metrics"]["xirr_scope"] == "full_scope"
    assert inr_1y["personal_metrics"]["xirr_scope"] == "full_scope"
    assert eur_all["personal_metrics"]["basis"] == "native_inr"
    assert eur_all["metrics"] != inr_1y["metrics"] or eur_all["range"] != inr_1y["range"]


def _personal_returns_across_surfaces(client, *, folio: str = FOLIO):
    asset = _metrics(client, folio_number=folio)["personal_metrics"]
    response = client.get("/api/v1/analytics/compare", {
        "subjects": f"asset:{SCHEME},asset:120504",
        "range": "ALL",
        "folio_number": folio,
    })
    assert response.status_code == 200, response.json()
    compared = next(s for s in response.json()["subjects"] if s["asset_symbol"] == SCHEME)
    return {
        "holdings": _holding_xirr(client),
        "detail": _detail_xirr(client),
        "metrics": asset["xirr"],
        "compare": compared["personal_metrics"]["xirr"],
    }, [asset, compared["personal_metrics"]]


@pytest.mark.django_db
def test_unsolvable_same_day_cash_flows_are_unavailable_on_every_surface(
    api_client, legacy_seeded, monkeypatch,
):
    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2025, 1, 1))
    for kind in ("BUY", "SELL"):
        cached_mf_nav("120503", '2024-01-01', '100')
        response = api_client.post("/api/v1/transactions", _mf_payload(
            type=kind, investment_date="2024-01-01", nav_date="2024-01-01",
            nav="100", units_allotted="100", paid_value="10000", market_value="10000",
            folio_number=FOLIO,
        ), format="json")
        assert response.status_code == 201, response.json()
    cached_mf_nav('120504', "2026-03-15", "42.5")
    assert api_client.post("/api/v1/transactions", _mf_payload(
        scheme_code="120504", folio_number=FOLIO,
    ), format="json").status_code == 201
    # Equal same-day receipts/payments and no remaining units have no unique annual rate.
    values, blocks = _personal_returns_across_surfaces(api_client)
    assert values == dict.fromkeys(values)
    for block in blocks:
        assert block["status"] == "unavailable"
        assert block["basis"] == "native_inr"


@pytest.mark.django_db
def test_future_nav_and_future_only_cache_have_http_parity_on_every_surface(
    api_client, legacy_seeded, monkeypatch,
):
    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2026, 8, 16))
    for scheme in (SCHEME, "120504"):
        cached_mf_nav(scheme, '2024-01-01', '100')
        assert api_client.post("/api/v1/transactions", _mf_payload(
            scheme_code=scheme, investment_date="2024-01-01", nav_date="2024-01-01",
            nav="100", units_allotted="100", paid_value="10000", market_value="10000",
            folio_number=FOLIO,
        ), format="json").status_code == 201
        _nav("2026-08-16", "118.089530", scheme)
    before, _ = _personal_returns_across_surfaces(api_client)
    for result in before.values():
        assert result == pytest.approx(0.065399998671, abs=1e-10)
    _nav("2026-08-17", "200")
    after, _ = _personal_returns_across_surfaces(api_client)
    assert after == before
    HistoricalPrice.objects.filter(asset_symbol=SCHEME, date__lte=date(2026, 8, 16)).delete()
    future_only, blocks = _personal_returns_across_surfaces(api_client)
    assert future_only == dict.fromkeys(future_only)
    assert all(block["status"] == "unavailable" for block in blocks)


def _failed_provisional_attempt(client, *, scheme=SCHEME, day="2026-03-12"):
    provider = MockNavProvider()
    with patch(MF_NAV_FETCH_FACTORY, return_value=provider):
        data = client.post(
            "/api/v1/nav/fetch-missing",
            {"scheme_code": scheme, "nav_date": day},
            format="json",
        ).json()
    assert data["outcome"] == "date_unavailable", data
    return data["attempt_id"]


def _provisional_payload(attempt_id, **overrides):
    body = {
        "asset_type": "MUTUAL_FUND",
        "scheme_code": SCHEME,
        "scheme_name": "Test Fund",
        "folio_number": FOLIO,
        "type": "BUY",
        "investment_date": "2026-03-12",
        "nav_date": "2026-03-12",
        "units_allotted": "10",
        "paid_value": "500",
        "fees": "0",
        "currency": "INR",
        "provisional_nav": "42.5",
        "provisional_attempt_id": attempt_id,
        "confirm_provisional_nav": True,
        "confirm_paid_value": True,
    }
    body.update(overrides)
    return {k: v for k, v in body.items() if v is not None}


@pytest.mark.django_db
def test_provisional_overlay_xirr_parity_across_surfaces_independent_oracle(
    api_client, legacy_seeded, monkeypatch,
):
    """Reproduces #59: Metric Sheet used cached-only terminal while holdings used provisional."""
    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2026, 3, 20))
    cached_mf_nav(SCHEME, "2024-01-01", "100")
    assert api_client.post("/api/v1/transactions", _mf_payload(
        investment_date="2024-01-01", nav_date="2024-01-01", nav="100",
        units_allotted="100", paid_value="10000", market_value="10000",
        folio_number=FOLIO,
    ), format="json").status_code == 201
    cached_mf_nav(SCHEME, "2025-06-01", "80")
    attempt = _failed_provisional_attempt(api_client)
    assert api_client.post(
        "/api/v1/transactions",
        _provisional_payload(attempt),
        format="json",
    ).status_code == 201
    cached_mf_nav("120504", "2024-01-01", "100")
    assert api_client.post("/api/v1/transactions", _mf_payload(
        scheme_code="120504", scheme_name="Compare Peer Fund",
        investment_date="2024-01-01", nav_date="2024-01-01", nav="100",
        units_allotted="10", paid_value="1000", market_value="1000",
        folio_number=FOLIO,
    ), format="json").status_code == 201

    overlay_nav = 42.5
    remaining = 110.0
    terminal = remaining * overlay_nav
    scoped_oracle = _oracle([
        (date(2024, 1, 1), -10000.0),
        (date(2026, 3, 12), -500.0),
        (date(2026, 3, 20), terminal),
    ])
    cached_only_oracle = _oracle([
        (date(2024, 1, 1), -10000.0),
        (date(2026, 3, 12), -500.0),
        (date(2026, 3, 20), remaining * 80.0),
    ])
    assert scoped_oracle is not None and cached_only_oracle is not None
    assert scoped_oracle != pytest.approx(cached_only_oracle, abs=1e-4)

    surfaces, blocks = _personal_returns_across_surfaces(api_client)
    assert surfaces["holdings"] == pytest.approx(scoped_oracle, abs=1e-9)
    assert surfaces["detail"] == pytest.approx(scoped_oracle, abs=1e-9)
    assert surfaces["metrics"] == pytest.approx(scoped_oracle, abs=1e-9)
    assert surfaces["compare"] == pytest.approx(scoped_oracle, abs=1e-9)
    for surface, value in surfaces.items():
        assert value != pytest.approx(cached_only_oracle, abs=1e-4), surface
    for block in blocks:
        assert block["status"] == "calculated"
        assert block["basis"] == "native_inr"


@pytest.mark.django_db
def test_provisional_nav_conflict_makes_personal_xirr_unavailable_on_every_surface(
    api_client, legacy_seeded, monkeypatch,
):
    monkeypatch.setattr("portfolios.dates.current_date", lambda: date(2026, 3, 20))
    cached_mf_nav(SCHEME, "2024-01-01", "100")
    assert api_client.post("/api/v1/transactions", _mf_payload(
        investment_date="2024-01-01", nav_date="2024-01-01", nav="100",
        units_allotted="100", paid_value="10000", market_value="10000",
        folio_number=FOLIO,
    ), format="json").status_code == 201
    cached_mf_nav(SCHEME, "2025-06-01", "80")
    attempt = _failed_provisional_attempt(api_client, day="2026-03-12")
    assert api_client.post(
        "/api/v1/transactions",
        _provisional_payload(attempt, provisional_nav="42.5", units_allotted="5"),
        format="json",
    ).status_code == 201
    reused_attempt = str(MutualFundNavFetchState.objects.get().last_attempt_id)
    assert api_client.post(
        "/api/v1/transactions",
        _provisional_payload(
            reused_attempt, provisional_nav="43.0", units_allotted="5", paid_value="215",
        ),
        format="json",
    ).status_code == 201
    cached_mf_nav("120504", "2024-01-01", "100")
    assert api_client.post("/api/v1/transactions", _mf_payload(
        scheme_code="120504", scheme_name="Compare Peer Fund",
        investment_date="2024-01-01", nav_date="2024-01-01", nav="100",
        units_allotted="10", paid_value="1000", market_value="1000",
        folio_number=FOLIO,
    ), format="json").status_code == 201

    surfaces, blocks = _personal_returns_across_surfaces(api_client)
    assert surfaces == dict.fromkeys(surfaces)
    for block in blocks:
        assert block["status"] == "unavailable"
        assert block["basis"] == "native_inr"
