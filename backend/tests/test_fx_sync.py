from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command

from fx.lookup import convert_amount_on_date, get_fx_rate_on_date
from fx.models import FXRate
from fx.providers.base import DailyFxRate
from fx.services import (
    earliest_required_fx_date,
    resolve_fx_sync_start_date,
    sync_fx_pair,
    sync_fx_rates,
    upsert_fx_rate,
)


class MockFxProvider:
    def __init__(self, data: dict[tuple[str, str], list[DailyFxRate]] | None = None):
        self.data = data or {}
        self.calls: list[tuple[str, str, date, date]] = []

    def fetch_rates(self, from_currency: str, to_currency: str, start: date, end: date):
        self.calls.append((from_currency, to_currency, start, end))
        return [
            r
            for r in self.data.get((from_currency, to_currency), [])
            if start <= r.date <= end
        ]


@pytest.mark.django_db
def test_fx_upsert_idempotent():
    d = date(2026, 1, 1)
    upsert_fx_rate(from_currency="USD", to_currency="EUR", row_date=d, rate=Decimal("0.9"))
    upsert_fx_rate(from_currency="USD", to_currency="EUR", row_date=d, rate=Decimal("0.91"))
    assert FXRate.objects.filter(from_currency="USD", to_currency="EUR", date=d).count() == 1
    assert FXRate.objects.get(from_currency="USD", to_currency="EUR", date=d).rate == Decimal(
        "0.91"
    )


@pytest.mark.django_db
def test_fx_unique_pair_date():
    d = date(2026, 1, 2)
    upsert_fx_rate(from_currency="USD", to_currency="EUR", row_date=d, rate=Decimal("1"))
    upsert_fx_rate(from_currency="USD", to_currency="EUR", row_date=d, rate=Decimal("2"))
    assert FXRate.objects.filter(from_currency="USD", to_currency="EUR").count() == 1


@pytest.mark.django_db
def test_same_date_fx_lookup():
    d = date(2026, 2, 1)
    upsert_fx_rate(from_currency="USD", to_currency="EUR", row_date=d, rate=Decimal("0.85"))
    rate = get_fx_rate_on_date("USD", "EUR", d)
    assert rate == Decimal("0.85")
    amount, status = convert_amount_on_date(100, "USD", "EUR", d)
    assert status == "ok"
    assert amount == Decimal("85")


@pytest.mark.django_db
def test_missing_fx_lookup_returns_none():
    d = date(2026, 3, 1)
    assert get_fx_rate_on_date("USD", "INR", d) is None
    amount, status = convert_amount_on_date(10, "USD", "INR", d)
    assert amount is None
    assert status == "fx_unavailable"


@pytest.mark.django_db
def test_no_latest_fx_fallback_for_historical_date():
    d1 = date(2026, 1, 1)
    d2 = date(2026, 1, 10)
    upsert_fx_rate(from_currency="USD", to_currency="EUR", row_date=d2, rate=Decimal("0.99"))
    assert get_fx_rate_on_date("USD", "EUR", d1) is None


@pytest.mark.django_db
def test_sync_fx_rates_command_calls_service():
    with patch("fx.management.commands.sync_fx_rates.sync_fx_rates") as m:
        m.return_value = type(
            "R", (), {"success": True, "partial": False, "pairs_attempted": 0}
        )()
        call_command("sync_fx_rates", stdout=StringIO())
    m.assert_called_once()


@pytest.mark.django_db
def test_sync_fx_rates_incremental(seeded):
    from market_data.models import AssetType, HistoricalPrice
    from portfolios.seed import ensure_default_portfolio
    from transactions.models import Transaction, TransactionType

    today = date.today()
    portfolio = ensure_default_portfolio()
    txn_day = today - timedelta(days=5)
    Transaction.objects.create(
        portfolio=portfolio,
        asset_symbol="AAPL",
        date=txn_day,
        type=TransactionType.BUY,
        quantity=Decimal("1"),
        price_per_share=Decimal("100"),
        currency="EUR",
        fees=Decimal("0"),
    )
    HistoricalPrice.objects.create(
        asset_symbol="AAPL",
        date=txn_day,
        close_price=Decimal("100"),
        currency="USD",
        asset_type=AssetType.STOCK,
        source="test",
    )
    provider = MockFxProvider(
        {
            ("USD", "EUR"): [
                DailyFxRate(today - timedelta(days=1), Decimal("0.9")),
            ]
        }
    )
    result = sync_fx_rates(pairs={("USD", "EUR")}, provider=provider)
    assert result.success is True
    assert provider.calls[0][2] == txn_day
    assert FXRate.objects.filter(from_currency="USD", to_currency="EUR").exists()


@pytest.mark.django_db
def test_sync_fx_backfills_when_required_predates_earliest_cached(seeded):
    from market_data.models import AssetType, HistoricalPrice
    from portfolios.seed import ensure_default_portfolio
    from transactions.models import Transaction, TransactionType

    txn_date = date(2022, 5, 2)
    fx_start = date(2022, 12, 20)
    portfolio = ensure_default_portfolio()
    Transaction.objects.create(
        portfolio=portfolio,
        asset_symbol="GOOG",
        date=txn_date,
        type=TransactionType.BUY,
        quantity=Decimal("1"),
        price_per_share=Decimal("2149"),
        currency="EUR",
        fees=Decimal("0"),
    )
    HistoricalPrice.objects.create(
        asset_symbol="GOOG",
        date=txn_date,
        close_price=Decimal("107.45"),
        currency="USD",
        asset_type=AssetType.STOCK,
        source="test",
    )
    upsert_fx_rate(
        from_currency="USD",
        to_currency="EUR",
        row_date=fx_start,
        rate=Decimal("0.95"),
    )
    provider = MockFxProvider(
        {
            ("USD", "EUR"): [
                DailyFxRate(date(2022, 5, 3), Decimal("0.90")),
                DailyFxRate(date(2022, 12, 19), Decimal("0.92")),
            ]
        }
    )
    sync_fx_rates(pairs={("USD", "EUR")}, provider=provider)
    assert provider.calls[0][2] == txn_date
    assert FXRate.objects.filter(
        from_currency="USD", to_currency="EUR", date=date(2022, 5, 3)
    ).exists()


@pytest.mark.django_db
def test_sync_fx_starts_from_earliest_required_when_no_cache(seeded):
    from market_data.models import AssetType, HistoricalPrice
    from portfolios.seed import ensure_default_portfolio
    from transactions.models import Transaction, TransactionType

    txn_date = date(2022, 5, 2)
    portfolio = ensure_default_portfolio()
    Transaction.objects.create(
        portfolio=portfolio,
        asset_symbol="GOOG",
        date=txn_date,
        type=TransactionType.BUY,
        quantity=Decimal("1"),
        price_per_share=Decimal("2149"),
        currency="EUR",
        fees=Decimal("0"),
    )
    HistoricalPrice.objects.create(
        asset_symbol="GOOG",
        date=txn_date,
        close_price=Decimal("107.45"),
        currency="USD",
        asset_type=AssetType.STOCK,
        source="test",
    )
    provider = MockFxProvider(
        {("USD", "EUR"): [DailyFxRate(date(2022, 5, 3), Decimal("0.90"))]}
    )
    sync_fx_rates(pairs={("USD", "EUR")}, provider=provider)
    assert provider.calls[0][2] == txn_date


@pytest.mark.django_db
def test_sync_fx_incremental_when_coverage_from_inception(seeded):
    txn_date = date(2022, 5, 2)
    covered_until = date(2022, 12, 31)
    upsert_fx_rate(
        from_currency="USD",
        to_currency="EUR",
        row_date=txn_date,
        rate=Decimal("0.90"),
    )
    upsert_fx_rate(
        from_currency="USD",
        to_currency="EUR",
        row_date=covered_until,
        rate=Decimal("0.95"),
    )
    provider = MockFxProvider(
        {
            ("USD", "EUR"): [
                DailyFxRate(date(2023, 1, 1), Decimal("0.96")),
            ]
        }
    )
    sync_fx_pair("USD", "EUR", txn_date, date(2023, 1, 5), provider)
    assert provider.calls[0][2] == covered_until + timedelta(days=1)


def test_resolve_fx_sync_start_date_rules():
    required = date(2022, 5, 2)
    fx_start = date(2022, 12, 20)
    fx_end = date(2026, 3, 15)
    assert (
        resolve_fx_sync_start_date(
            min_required_date=required,
            min_fx_date=None,
            max_fx_date=None,
        )
        == required
    )
    assert (
        resolve_fx_sync_start_date(
            min_required_date=required,
            min_fx_date=fx_start,
            max_fx_date=fx_end,
        )
        == required
    )
    assert (
        resolve_fx_sync_start_date(
            min_required_date=required,
            min_fx_date=required,
            max_fx_date=fx_end,
        )
        == fx_end + timedelta(days=1)
    )


@pytest.mark.django_db
def test_earliest_required_fx_date_usd_price_eur_holding(seeded):
    from market_data.models import AssetType, HistoricalPrice
    from portfolios.seed import ensure_default_portfolio
    from transactions.models import Transaction, TransactionType

    txn_date = date(2022, 5, 2)
    portfolio = ensure_default_portfolio()
    Transaction.objects.create(
        portfolio=portfolio,
        asset_symbol="GOOG",
        date=txn_date,
        type=TransactionType.BUY,
        quantity=Decimal("1"),
        price_per_share=Decimal("2149"),
        currency="EUR",
        fees=Decimal("0"),
    )
    HistoricalPrice.objects.create(
        asset_symbol="GOOG",
        date=txn_date,
        close_price=Decimal("107.45"),
        currency="USD",
        asset_type=AssetType.STOCK,
        source="test",
    )
    assert earliest_required_fx_date("USD", "EUR") == txn_date


@pytest.mark.django_db
def test_summary_null_value_when_fx_missing_for_usd_price(api_client, seeded):
    from market_data.models import AssetType, HistoricalPrice
    from portfolios.seed import ensure_default_portfolio
    from transactions.models import Transaction, TransactionType

    txn_date = date(2022, 5, 2)
    portfolio = ensure_default_portfolio()
    Transaction.objects.create(
        portfolio=portfolio,
        asset_symbol="GOOG",
        date=txn_date,
        type=TransactionType.BUY,
        quantity=Decimal("1"),
        price_per_share=Decimal("2149"),
        currency="EUR",
        fees=Decimal("0"),
    )
    HistoricalPrice.objects.create(
        asset_symbol="GOOG",
        date=txn_date,
        close_price=Decimal("107.45"),
        currency="USD",
        asset_type=AssetType.STOCK,
        source="test",
    )
    ts = api_client.get("/api/v1/portfolio/summary?include_timeseries=true").json()[
        "timeseries"
    ]
    pt = next(p for p in ts if p["date"] == txn_date.isoformat())
    assert pt["portfolio_value"] is None
    assert pt["fx_status"] == "fx_unavailable"


@pytest.mark.django_db
def test_summary_value_after_fx_backfill(api_client, seeded):
    from market_data.models import AssetType, HistoricalPrice
    from portfolios.seed import ensure_default_portfolio
    from transactions.models import Transaction, TransactionType

    txn_date = date(2022, 5, 2)
    portfolio = ensure_default_portfolio()
    Transaction.objects.create(
        portfolio=portfolio,
        asset_symbol="GOOG",
        date=txn_date,
        type=TransactionType.BUY,
        quantity=Decimal("1"),
        price_per_share=Decimal("2149"),
        currency="EUR",
        fees=Decimal("0"),
    )
    HistoricalPrice.objects.create(
        asset_symbol="GOOG",
        date=txn_date,
        close_price=Decimal("100"),
        currency="USD",
        asset_type=AssetType.STOCK,
        source="test",
    )
    upsert_fx_rate(
        from_currency="USD",
        to_currency="EUR",
        row_date=txn_date,
        rate=Decimal("0.90"),
    )
    ts = api_client.get("/api/v1/portfolio/summary?include_timeseries=true").json()[
        "timeseries"
    ]
    pt = next(p for p in ts if p["date"] == txn_date.isoformat())
    assert pt["portfolio_value"] == pytest.approx(90.0, rel=1e-4)
    assert pt["fx_status"] == "ok"


@pytest.mark.django_db
@patch("yfinance.Ticker")
def test_summary_no_yfinance_when_fx_missing(mock_ticker, api_client, seeded):
    from market_data.models import AssetType, HistoricalPrice
    from portfolios.seed import ensure_default_portfolio
    from transactions.models import Transaction, TransactionType

    txn_date = date(2022, 5, 2)
    portfolio = ensure_default_portfolio()
    Transaction.objects.create(
        portfolio=portfolio,
        asset_symbol="GOOG",
        date=txn_date,
        type=TransactionType.BUY,
        quantity=Decimal("1"),
        price_per_share=Decimal("2149"),
        currency="EUR",
        fees=Decimal("0"),
    )
    HistoricalPrice.objects.create(
        asset_symbol="GOOG",
        date=txn_date,
        close_price=Decimal("107.45"),
        currency="USD",
        asset_type=AssetType.STOCK,
        source="test",
    )
    api_client.get("/api/v1/portfolio/summary?include_timeseries=true")
    mock_ticker.assert_not_called()
