"""#52 — provisional MF valuation across scopes, folios, currencies and analytics readouts.

Persisted provisional rows are synthetic fixtures (the confirmed write path is covered by
#50/#51 tests). Every oracle below is a literal computed by hand from units × NAV × FX.
"""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from cash.models import CashEntryType, CashLedgerEntry
from fx.services import upsert_fx_rate
from market_data.models import AssetType, HistoricalPrice
from portfolios.models import Portfolio
from portfolios.seed import ensure_default_portfolio
from tests.conftest import cached_mf_nav, historical_mf_transaction
from tests.test_mf_provisional_buy_api import FACTORY, client_for, mf_cache_rows
from transactions.models import MutualFundNavSource, MutualFundTransactionDetail, Transaction

SCHEME = "120503"
OTHER_SCHEME = "118989"
TODAY = date(2026, 3, 20)  # Friday; 2026-03-14/15 is a weekend without provider NAVs
PROVISIONAL_SERIES_WARNING = (
    "Some portfolio values in this range use unverified provisional mutual fund NAVs; "
    "results are not fully verified."
)


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch):
    monkeypatch.setattr("portfolios.dates.current_date", lambda: TODAY)


def mf_txn(portfolio, day, units, nav, *, type="BUY", folio="F1", scheme=SCHEME,
           payment=None, paid=None, provisional=False):
    market = Decimal(nav) * Decimal(units)
    txn = historical_mf_transaction(portfolio, {
        "scheme_code": scheme, "scheme_name": f"Fund {scheme}", "folio_number": folio,
        "type": type, "investment_date": payment or day, "nav_date": day, "nav": nav,
        "units_allotted": units, "paid_value": paid or str(market), "market_value": str(market),
        "fees": "0",
    })
    source = MutualFundNavSource.PROVISIONAL_USER if provisional else MutualFundNavSource.PROVIDER_CACHE
    MutualFundTransactionDetail.objects.filter(transaction=txn).update(nav_source=source)
    return txn


def cached(portfolio, day, units, nav, **kw):
    cached_mf_nav(kw.get("scheme", SCHEME), day, nav)
    return mf_txn(portfolio, day, units, nav, **kw)


def provisional(portfolio, day, units, nav, **kw):
    return mf_txn(portfolio, day, units, nav, provisional=True, **kw)


def inr_portfolio(user, name):
    return Portfolio.objects.create(user=user, name=name, base_currency="INR")


def get(client, url, **params):
    response = client.get(url, {"display_currency": "INR", **params})
    assert response.status_code == 200, response.json()
    return response.json()


def summary(client, **params):
    return get(client, "/api/v1/portfolio/summary", **params)


def holdings(client, **params):
    return get(client, "/api/v1/portfolio/holdings", **params)


def holding(client, folio="F1", scheme=SCHEME, **params):
    data = holdings(client, **params)
    return next(h for h in data["holdings"]
                if h.get("folio_number") == folio and h.get("scheme_code") == scheme)


def history(data):
    return {p["date"]: p["portfolio_value"] for p in data["timeseries"]}


def flagged(data):
    return sorted(p["date"] for p in data["timeseries"] if p.get("nav_provisional"))


def performance(client, metric="value", period="ALL", **params):
    data = get(client, "/api/v1/portfolio/performance", metric=metric, range=period, **params)
    if isinstance(data, list):
        return {p["date"]: p["value"] for p in data}, []
    return {p["date"]: p["value"] for p in data["points"]}, data.get("warnings", [])


def ledger_and_cache_state():
    return (
        sorted(Transaction.objects.values_list("id", "portfolio_id", "date", "type", "quantity",
                                               "price_per_share")),
        sorted(MutualFundTransactionDetail.objects.values_list("transaction_id", "nav", "nav_date",
                                                               "nav_source", "market_value")),
        sorted(CashLedgerEntry.objects.values_list("id", "amount")),
        mf_cache_rows(),
    )


def days(start, end):
    return [date(2026, 3, d).isoformat() for d in range(start, end + 1)]


# --- boundaries -------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("scope_kind", ["single", "all"])
def test_multiple_observations_resume_at_provider_boundaries_with_same_date_parity(
    api_client, legacy_seeded, test_user, scope_kind
):
    portfolio = ensure_default_portfolio(test_user)
    scope = {"portfolio_id": portfolio.id} if scope_kind == "single" else {"portfolio_scope": "all"}
    cached(portfolio, "2026-03-10", "100", "40")
    provisional(portfolio, "2026-03-12", "40", "42.5", type="SELL")  # 60 units left
    cached_mf_nav(SCHEME, "2026-03-16", "45")                        # older provider ...
    provisional(portfolio, "2026-03-17", "10", "44")                 # ... newer provisional: 70 units
    cached(portfolio, "2026-03-10", "50", "20", folio="G1", scheme=OTHER_SCHEME)
    cached_mf_nav(OTHER_SCHEME, "2026-03-18", "22")
    before = ledger_and_cache_state()

    data = summary(api_client, **scope)
    values = history(data)
    assert values["2026-03-11"] == 5000          # 100×40 + 50×20
    assert values["2026-03-12"] == 3550          # 60×42.5 + 1000
    assert values["2026-03-14"] == values["2026-03-15"] == 3550  # weekend carries per-unit NAV
    assert values["2026-03-16"] == 3700          # 60×45 + 1000: provider resumes
    assert values["2026-03-17"] == 4080          # 70×44 + 1000: newer provisional wins
    assert values["2026-03-18"] == 4180          # 70×44 + 50×22
    assert values["2026-03-20"] == data["current_value"] == 4180
    assert flagged(data) == days(12, 15) + days(17, 20)
    assert data["nav_provisional"] is True
    assert any("folio F1" in w and "2026-03-17" in w for w in data["warnings"])

    rows = holdings(api_client, **scope)
    a = next(h for h in rows["holdings"] if h["scheme_code"] == SCHEME)
    b = next(h for h in rows["holdings"] if h["scheme_code"] == OTHER_SCHEME)
    assert (a["quantity"], a["latest_nav"], a["current_value"]) == (70, 44, 3080)
    assert (a["nav_source"], a["nav_date"]) == ("PROVISIONAL_USER", "2026-03-17")
    assert (b["latest_nav"], b["current_value"]) == (22, 1100)
    assert "nav_provisional" not in b
    assert rows["nav_provisional"] is True
    assert sum(r["current_value"] for r in rows["allocation"]) == 4180
    perf, warnings = performance(api_client, **scope)
    assert perf["2026-03-12"] == 3550 and perf["2026-03-16"] == 3700 and perf["2026-03-20"] == 4180
    assert PROVISIONAL_SERIES_WARNING in warnings

    cached_mf_nav(SCHEME, "2026-03-19", "46")
    data = summary(api_client, **scope)
    values = history(data)
    assert values["2026-03-18"] == 4180          # history is not rewritten
    assert values["2026-03-19"] == values["2026-03-20"] == data["current_value"] == 4320  # 70×46 + 1100
    assert flagged(data) == days(12, 15) + days(17, 18)
    assert "nav_provisional" not in data
    assert not any("provisional" in w for w in data.get("warnings", []))
    assert holding(api_client, **scope)["current_value"] == 3220
    assert "nav_provisional" not in holdings(api_client, **scope)
    _, warnings = performance(api_client, **scope)
    assert PROVISIONAL_SERIES_WARNING in warnings  # ALL still spans provisional days
    _, warnings = performance(api_client, period="7D", **scope)
    assert PROVISIONAL_SERIES_WARNING in warnings  # 03-13 … 03-18 still provisional
    assert ledger_and_cache_state()[:3] == before[:3]


@pytest.mark.django_db
def test_leading_gap_and_allotment_timing(api_client, legacy_seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    mf_txn(portfolio, "2026-03-05", "100", "40")  # legacy row; provider history starts later
    provisional(portfolio, "2026-03-07", "20", "41", payment="2026-03-06")
    cached_mf_nav(SCHEME, "2026-03-10", "42")
    data = summary(api_client, portfolio_id=portfolio.id)
    values = history(data)
    assert values["2026-03-05"] is None and values["2026-03-06"] is None  # unknown, not zero
    assert values["2026-03-07"] == 4920  # 120×41 from the allotment (NAV) date, not payment
    assert values["2026-03-09"] == 4920
    assert values["2026-03-10"] == values["2026-03-20"] == data["current_value"] == 5040
    assert flagged(data) == days(7, 9)
    assert "nav_provisional" not in data


@pytest.mark.django_db
def test_selected_range_start_bootstraps_provisional_nav_before_window(
    api_client, legacy_seeded, test_user
):
    portfolio = ensure_default_portfolio(test_user)
    provisional(portfolio, "2026-03-05", "100", "42.5")  # first-time fund, no provider NAV
    values, warnings = performance(api_client, period="7D", portfolio_id=portfolio.id)
    assert min(values) == "2026-03-13"
    assert set(values.values()) == {4250}
    assert PROVISIONAL_SERIES_WARNING in warnings
    for metric in ("cumulative_return", "twror"):
        _, warnings = performance(api_client, metric=metric, period="7D", portfolio_id=portfolio.id)
        assert PROVISIONAL_SERIES_WARNING in warnings, metric

    cached_mf_nav(SCHEME, "2026-03-10", "45")  # provider resumes before the window starts
    values, warnings = performance(api_client, period="7D", portfolio_id=portfolio.id)
    assert set(values.values()) == {4500}
    assert PROVISIONAL_SERIES_WARNING not in warnings
    _, warnings = performance(api_client, period="ALL", portfolio_id=portfolio.id)
    assert PROVISIONAL_SERIES_WARNING in warnings


@pytest.mark.django_db
def test_metric_sheet_and_benchmark_comparison_carry_quality_warning(
    api_client, legacy_seeded, test_user
):
    from market_data.models import BenchmarkIndexConfig

    portfolio = ensure_default_portfolio(test_user)
    cached(portfolio, "2026-03-02", "100", "40")
    provisional(portfolio, "2026-03-12", "10", "42.5")
    sheet = get(api_client, "/api/v1/analytics/performance-metrics", range="ALL",
                portfolio_id=portfolio.id)
    assert PROVISIONAL_SERIES_WARNING in sheet["warnings"]
    BenchmarkIndexConfig.objects.update_or_create(
        symbol="^NSEI", defaults={"display_name": "Nifty 50", "enabled": True})
    for day, close in [("2026-03-02", "100"), ("2026-03-20", "110")]:
        HistoricalPrice.objects.create(asset_symbol="^NSEI", asset_type=AssetType.INDEX,
                                       date=date.fromisoformat(day), close_price=Decimal(close),
                                       currency="INR", source="test")
    compared = get(api_client, "/api/v1/portfolio/performance", metric="twror", range="ALL",
                   benchmark="^NSEI", portfolio_id=portfolio.id)
    assert PROVISIONAL_SERIES_WARNING in compared["warnings"]


@pytest.mark.django_db
def test_cache_only_portfolio_readouts_are_unchanged(api_client, legacy_seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    cached(portfolio, "2026-03-10", "100", "40")
    cached_mf_nav(SCHEME, "2026-03-16", "45")
    data = summary(api_client, portfolio_id=portfolio.id)
    assert data["current_value"] == history(data)["2026-03-20"] == 4500
    assert flagged(data) == [] and "nav_provisional" not in data
    rows = holdings(api_client, portfolio_id=portfolio.id)
    assert "nav_provisional" not in rows
    assert "nav_source" not in rows["holdings"][0]
    perf = api_client.get("/api/v1/portfolio/performance",
                          {"display_currency": "INR", "range": "ALL", "portfolio_id": portfolio.id})
    assert isinstance(perf.json(), list)  # no warnings wrapper for clean cache-only data
    sheet = get(api_client, "/api/v1/analytics/performance-metrics", range="ALL",
                portfolio_id=portfolio.id)
    assert PROVISIONAL_SERIES_WARNING not in sheet["warnings"]


# --- isolation ----------------------------------------------------------------------


@pytest.mark.django_db
def test_portfolios_folios_and_users_are_isolated_without_averaging(
    api_client, legacy_seeded, test_user, other_user
):
    p1 = ensure_default_portfolio(test_user)
    p2 = inr_portfolio(test_user, "Second")
    p3 = inr_portfolio(test_user, "Third")
    for p in (p1, p2, p3):
        cached(p, "2026-03-10", "100", "40", folio="F3" if p is p3 else "F1")
    provisional(p1, "2026-03-12", "10", "42.5")              # same scheme/date/folio number ...
    provisional(p2, "2026-03-12", "10", "43")                # ... different NAV, different folio
    provisional(p3, "2026-03-12", "10", "42.5", folio="F3")  # same folio: conflicting entries
    provisional(p3, "2026-03-12", "10", "43", folio="F3")
    other = ensure_default_portfolio(other_user)
    other.cash_aware_enabled = False
    other.save(update_fields=["cash_aware_enabled"])
    cached(other, "2026-03-10", "100", "40")
    provisional(other, "2026-03-12", "10", "50")
    other_client = client_for(other_user)

    assert summary(api_client, portfolio_id=p1.id)["current_value"] == 4675  # 110×42.5
    assert summary(api_client, portfolio_id=p2.id)["current_value"] == 4730  # 110×43
    third = summary(api_client, portfolio_id=p3.id)
    assert third["current_value"] == 0
    assert history(third)["2026-03-11"] == 4000
    assert history(third)["2026-03-12"] is None and history(third)["2026-03-20"] is None
    assert any("conflicting provisional NAVs on 2026-03-12" in w for w in third["warnings"])
    conflicted = holding(api_client, folio="F3", portfolio_id=p3.id)
    # The older 03-10 provider NAV (40) must not take over the conflicted interval.
    assert (conflicted["nav_status"], conflicted["latest_nav"], conflicted["current_value"]) == (
        "nav_missing", None, 0)
    assert conflicted["xirr"] is None
    detail = get(api_client, f"/api/v1/portfolio/assets/{SCHEME}", folio_number="F3",
                 portfolio_id=p3.id)
    assert (detail["nav_status"], detail["latest_nav"], detail["current_value"]) == (
        "nav_missing", None, 0)
    assert summary(other_client)["current_value"] == 5500  # 110×50, own folio only

    merged = holding(api_client, portfolio_scope="all")
    assert (merged["current_value"], merged["nav_source"], merged["latest_nav"]) == (9405, "MIXED", None)
    everything = summary(api_client, portfolio_scope="all")
    assert everything["current_value"] == 9405  # 4675 + 4730; conflicted folio unavailable
    assert any(w.startswith("Third: ") and "conflicting" in w for w in everything["warnings"])
    assert history(everything)["2026-03-11"] == 12000
    assert history(everything)["2026-03-12"] is None  # no silent averaging or zero fill

    cached_mf_nav(SCHEME, "2026-03-16", "45")
    assert summary(api_client, portfolio_id=p3.id)["current_value"] == 5400  # 120×45
    everything = summary(api_client, portfolio_scope="all")
    assert everything["current_value"] == history(everything)["2026-03-20"] == 15300
    assert history(everything)["2026-03-15"] is None and history(everything)["2026-03-16"] == 15300
    assert "nav_provisional" not in everything
    assert summary(other_client)["current_value"] == 4950  # provider is shared, provisional is not


@pytest.mark.django_db
def test_closed_folio_stays_out_while_open_folio_carries_provisional(
    api_client, legacy_seeded, test_user
):
    p1 = ensure_default_portfolio(test_user)
    p2 = inr_portfolio(test_user, "Second")
    cached(p1, "2026-03-10", "100", "40")
    provisional(p1, "2026-03-12", "100", "42.5", type="SELL")  # closed
    cached(p2, "2026-03-10", "100", "40")
    provisional(p2, "2026-03-13", "10", "44")
    merged = holding(api_client, portfolio_scope="all")
    assert (merged["quantity"], merged["current_value"]) == (110, 4840)  # 110×44
    assert merged["nav_source"] == "PROVISIONAL_USER" and merged["latest_nav"] == 44
    assert merged["portfolio_names"] == ["Second"]
    assert not any("2026-03-12" in w for w in merged["warnings"])
    closed = summary(api_client, portfolio_id=p1.id)
    assert closed["current_value"] == 0 and "nav_provisional" not in closed
    assert flagged(closed) == []
    everything = summary(api_client, portfolio_scope="all")
    assert everything["current_value"] == history(everything)["2026-03-20"] == 4840
    assert history(everything)["2026-03-12"] == 4000  # p1 sold at 42.5; p2 still 100×40


# --- components and currency ---------------------------------------------------------


@pytest.mark.django_db
def test_cash_pending_purchase_and_fixed_deposit_stay_effective(api_client, seeded, test_user):
    from tests.debt_test_helpers import create_test_bank_account, fund_bank_account
    from debt.services import create_fixed_deposit

    portfolio = ensure_default_portfolio(test_user)
    portfolio.cash_aware_enabled = True
    portfolio.save(update_fields=["cash_aware_enabled", "updated_at"])
    CashLedgerEntry.objects.create(portfolio=portfolio, date=date(2026, 3, 1), currency="INR",
                                   entry_type=CashEntryType.CASH_DEPOSIT, amount=Decimal("10000"))
    buy = provisional(portfolio, "2026-03-16", "100", "42.5", payment="2026-03-12")
    CashLedgerEntry.objects.create(portfolio=portfolio, date=date(2026, 3, 12), currency="INR",
                                   entry_type=CashEntryType.BUY_SETTLEMENT, amount=Decimal("-4250"),
                                   linked_transaction=buy)
    bank = create_test_bank_account(test_user, portfolio=portfolio)
    fund_bank_account(test_user, bank, Decimal("150000"), movement_date=date(2026, 1, 1))
    create_fixed_deposit(
        test_user, portfolio_id=portfolio.id, bank_account_id=bank.id, institution_name="HDFC",
        deposit_account_number="FD-1", principal_amount=Decimal("100000"), currency="INR",
        interest_rate_percent=Decimal("0"), interest_payout_frequency="QUARTERLY",
        investment_date=date(2026, 3, 1), maturity_date=date(2027, 3, 1), status="ACTIVE",
    )

    data = summary(api_client, portfolio_id=portfolio.id)
    values = history(data)
    assert values["2026-03-11"] == 110000   # 10000 cash + 100000 FD
    assert values["2026-03-13"] == 110000   # 5750 cash + 4250 pending purchase + FD
    assert values["2026-03-16"] == 110000   # 5750 cash + 100×42.5 provisional + FD
    assert values["2026-03-20"] == data["current_value"] == 110000
    assert flagged(data) == days(16, 20)

    cached_mf_nav(SCHEME, "2026-03-18", "45")
    data = summary(api_client, portfolio_id=portfolio.id)
    values = history(data)
    assert values["2026-03-17"] == 110000
    assert values["2026-03-18"] == values["2026-03-20"] == data["current_value"] == 110250
    perf, _ = performance(api_client, portfolio_id=portfolio.id)
    assert perf["2026-03-13"] == 110000 and perf["2026-03-18"] == 110250


def _fx(day, rate, frm="INR", to="EUR"):
    upsert_fx_rate(from_currency=frm, to_currency=to, row_date=date.fromisoformat(day),
                   rate=Decimal(rate))


@pytest.mark.django_db
@pytest.mark.parametrize("scope_kind", ["single", "all"])
def test_native_inr_portfolio_converts_to_display_exactly_once(
    api_client, legacy_seeded, test_user, scope_kind
):
    portfolio = ensure_default_portfolio(test_user)
    scope = {"portfolio_id": portfolio.id} if scope_kind == "single" else {"portfolio_scope": "all"}
    provisional(portfolio, "2026-03-12", "100", "42.5")  # 4250 INR
    for d in range(1, 21):
        _fx(f"2026-03-{d:02d}", "0.010" if d < 15 else "0.012")
    data = summary(api_client, display_currency="EUR", **scope)
    assert data["display_currency"] == "EUR"
    assert data["current_value"] == pytest.approx(51.0)     # 4250 × 0.012
    assert history(data)["2026-03-12"] == pytest.approx(42.5)  # 4250 × 0.010
    assert history(data)["2026-03-20"] == pytest.approx(data["current_value"])
    rows = holdings(api_client, display_currency="EUR", **scope)
    row = rows["holdings"][0]
    assert row["currency"] == "INR" and row["current_value"] == 4250  # native amount
    assert row["display_current_value"] == pytest.approx(51.0)
    perf, _ = performance(api_client, display_currency="EUR", **scope)
    assert perf["2026-03-13"] == pytest.approx(42.5) and perf["2026-03-20"] == pytest.approx(51.0)


def _eur_base_portfolio(api_client, user):
    portfolio = ensure_default_portfolio(user)
    response = api_client.post("/api/v1/transactions", {
        "asset_symbol": "AAPL", "date": "2026-03-01", "type": "BUY", "quantity": "10",
        "price_per_share": "100", "currency": "EUR", "fees": "0", "portfolio_id": portfolio.id,
    }, format="json")
    assert response.status_code == 201, response.json()
    HistoricalPrice.objects.create(asset_symbol="AAPL", asset_type=AssetType.STOCK,
                                   date=date(2026, 3, 1), close_price=Decimal("110"),
                                   currency="EUR", source="test")
    return portfolio


@pytest.mark.django_db
def test_eur_base_portfolio_values_first_time_provisional_fund_with_cached_fx(
    api_client, legacy_seeded, test_user
):
    portfolio = _eur_base_portfolio(api_client, test_user)
    provisional(portfolio, "2026-03-05", "100", "42.5")  # older than the 7-day FX lookback
    for d in range(1, 21):
        _fx(f"2026-03-{d:02d}", "0.01")
    data = summary(api_client, display_currency="EUR", portfolio_id=portfolio.id)
    assert data["base_currency"] == "EUR"
    assert data["fx_status"] == "ok"
    assert data["current_value"] == pytest.approx(1142.5)  # 10×110 + 4250×0.01
    assert history(data)["2026-03-05"] == pytest.approx(1142.5)
    assert history(data)["2026-03-20"] == pytest.approx(data["current_value"])
    assert data["nav_provisional"] is True


@pytest.mark.django_db
def test_missing_fx_is_reported_not_zero_filled_in_history(api_client, legacy_seeded, test_user):
    portfolio = _eur_base_portfolio(api_client, test_user)
    provisional(portfolio, "2026-03-12", "100", "42.5")
    data = summary(api_client, display_currency="EUR", portfolio_id=portfolio.id)
    assert data["fx_status"] == "fx_unavailable"
    assert data["nav_provisional"] is True
    assert history(data)["2026-03-12"] is None and history(data)["2026-03-20"] is None
    _fx("2026-03-12", "0.01")
    data = summary(api_client, display_currency="EUR", portfolio_id=portfolio.id)
    assert history(data)["2026-03-12"] == pytest.approx(1142.5)
    assert history(data)["2026-03-13"] is None  # filled FX keeps the established MF policy


# --- read safety ---------------------------------------------------------------------


@pytest.mark.django_db
def test_reads_across_scopes_never_contact_providers_or_write(api_client, legacy_seeded, test_user):
    p1 = ensure_default_portfolio(test_user)
    p2 = inr_portfolio(test_user, "Second")
    cached(p1, "2026-03-10", "100", "40")
    provisional(p2, "2026-03-12", "10", "42.5")
    before = ledger_and_cache_state()
    with patch(FACTORY) as factory, patch(
        "market_data.providers.mutual_fund_nav_provider.AmfiNavProvider.get_nav_history"
    ) as history_call:
        for scope in ({"portfolio_id": p1.id}, {"portfolio_id": p2.id}, {"portfolio_scope": "all"}):
            for currency in ("INR", "EUR"):
                summary(api_client, display_currency=currency, **scope)
                holdings(api_client, display_currency=currency, **scope)
                for metric in ("value", "cumulative_return", "twror"):
                    performance(api_client, metric=metric, display_currency=currency, **scope)
                get(api_client, "/api/v1/analytics/performance-metrics", range="ALL",
                    display_currency=currency, **scope)
    factory.assert_not_called()
    history_call.assert_not_called()
    assert ledger_and_cache_state() == before
