from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command

from market_data.models import AssetType, BenchmarkIndexConfig, HistoricalPrice
from market_data.price_lookup import latest_historical_price, normalize_asset_symbol
from market_data.providers.base import DailyPrice
from market_data.services.benchmark_sync import sync_benchmark_prices
from market_data.services.price_sync import sync_one_stock_symbol, sync_stock_prices
from portfolios.seed import ensure_default_portfolio
from transactions.models import Transaction, TransactionType


class MockPriceProvider:
    def __init__(self, histories: dict[str, list[DailyPrice]] | None = None, *, fail: set[str] | None = None):
        self.histories = histories or {}
        self.fail = fail or set()
        self.calls: list[tuple[str, date, date]] = []

    def fetch_history(self, symbol: str, start: date, end: date):
        self.calls.append((symbol, start, end))
        if symbol in self.fail:
            raise RuntimeError(f"provider error for {symbol}")
        rows = self.histories.get(symbol, [])
        filtered = [r for r in rows if start <= r.date <= end]
        ccy = filtered[0].currency if filtered else "USD"
        return filtered, ccy


def _buy(symbol: str, d: date, *, currency: str = "EUR"):
    portfolio = ensure_default_portfolio()
    Transaction.objects.create(
        portfolio=portfolio,
        asset_symbol=symbol,
        date=d,
        type=TransactionType.BUY,
        quantity=Decimal("10"),
        price_per_share=Decimal("100"),
        currency=currency,
        fees=Decimal("0"),
    )


@pytest.mark.django_db
def test_sync_uses_earliest_transaction_date_when_no_rows(seeded):
    today = date.today()
    _buy("aapl", today - timedelta(days=5))
    provider = MockPriceProvider(
        {
            "AAPL": [
                DailyPrice(today - timedelta(days=4), Decimal("101"), "USD"),
                DailyPrice(today - timedelta(days=3), Decimal("102"), "USD"),
            ]
        }
    )
    sync_one_stock_symbol("aapl", provider)
    assert provider.calls[0][1] == today - timedelta(days=5)
    rows = HistoricalPrice.objects.filter(asset_symbol="AAPL", asset_type=AssetType.STOCK)
    assert rows.count() == 2


@pytest.mark.django_db
def test_sync_uses_latest_stored_date_plus_one(seeded):
    today = date.today()
    _buy("AAPL", today - timedelta(days=5))
    HistoricalPrice.objects.create(
        asset_symbol="AAPL",
        date=today - timedelta(days=3),
        close_price=Decimal("155"),
        currency="USD",
        asset_type=AssetType.STOCK,
    )
    provider = MockPriceProvider(
        {
            "AAPL": [
                DailyPrice(today - timedelta(days=2), Decimal("156"), "USD"),
                DailyPrice(today - timedelta(days=1), Decimal("157"), "USD"),
            ]
        }
    )
    sync_one_stock_symbol("AAPL", provider)
    assert provider.calls[0][1] == today - timedelta(days=2)
    assert HistoricalPrice.objects.filter(asset_symbol="AAPL").count() == 3


@pytest.mark.django_db
def test_sync_normalizes_stock_symbols(seeded):
    today = date.today()
    _buy("msft", today - timedelta(days=2))
    provider = MockPriceProvider(
        {"MSFT": [DailyPrice(today - timedelta(days=1), Decimal("200"), "USD")]}
    )
    sync_one_stock_symbol("msft", provider)
    assert HistoricalPrice.objects.filter(asset_symbol="MSFT").exists()
    assert normalize_asset_symbol("msft") == "MSFT"


@pytest.mark.django_db
def test_sync_stores_daily_close_prices(seeded):
    today = date.today()
    _buy("AAPL", today - timedelta(days=2))
    provider = MockPriceProvider(
        {"AAPL": [DailyPrice(today - timedelta(days=1), Decimal("123.45"), "USD")]}
    )
    sync_one_stock_symbol("AAPL", provider)
    row = HistoricalPrice.objects.get(asset_symbol="AAPL", date=today - timedelta(days=1))
    assert row.close_price == Decimal("123.45")


@pytest.mark.django_db
def test_sync_upsert_without_duplicates(seeded):
    today = date.today()
    d = today - timedelta(days=1)
    _buy("AAPL", today - timedelta(days=3))
    provider = MockPriceProvider({"AAPL": [DailyPrice(d, Decimal("100"), "USD")]})
    sync_one_stock_symbol("AAPL", provider)
    sync_one_stock_symbol("AAPL", provider)
    assert HistoricalPrice.objects.filter(asset_symbol="AAPL", date=d).count() == 1


@pytest.mark.django_db
def test_sync_idempotent_when_run_twice(seeded):
    today = date.today()
    _buy("AAPL", today - timedelta(days=3))
    rows = [
        DailyPrice(today - timedelta(days=2), Decimal("10"), "USD"),
        DailyPrice(today - timedelta(days=1), Decimal("11"), "USD"),
    ]
    provider = MockPriceProvider({"AAPL": rows})
    sync_one_stock_symbol("AAPL", provider)
    sync_one_stock_symbol("AAPL", provider)
    assert HistoricalPrice.objects.filter(asset_symbol="AAPL").count() == 2


@pytest.mark.django_db
def test_sync_handles_empty_provider_response(seeded):
    today = date.today()
    _buy("AAPL", today - timedelta(days=2))
    provider = MockPriceProvider({"AAPL": []})
    assert sync_one_stock_symbol("AAPL", provider) is True
    assert HistoricalPrice.objects.filter(asset_symbol="AAPL").count() == 0


@pytest.mark.django_db
def test_sync_handles_provider_error(seeded):
    today = date.today()
    _buy("AAPL", today - timedelta(days=2))
    provider = MockPriceProvider(fail={"AAPL"})
    assert sync_one_stock_symbol("AAPL", provider) is False


@pytest.mark.django_db
def test_prices_refresh_without_symbols(api_client, seeded):
    today = date.today()
    _buy("AAPL", today - timedelta(days=2))
    with patch("market_data.views.sync_stock_prices") as mock_sync:
        r = api_client.post("/api/v1/prices/refresh", {}, format="json")
    assert r.status_code == 202
    assert r.json()["message"] == "Price sync scheduled"
    mock_sync.assert_called_once()
    assert mock_sync.call_args.kwargs.get("only_symbols") is None


@pytest.mark.django_db
def test_prices_refresh_with_symbols(api_client, seeded):
    with patch("market_data.views.sync_stock_prices") as mock_sync:
        r = api_client.post(
            "/api/v1/prices/refresh",
            {"symbols": ["AAPL", "MSFT"]},
            format="json",
        )
    assert r.status_code == 202
    only = mock_sync.call_args.kwargs.get("only_symbols")
    assert only == {"AAPL", "MSFT"}


@pytest.mark.django_db
def test_latest_price_returns_newest_by_date(seeded):
    today = date.today()
    HistoricalPrice.objects.create(
        asset_symbol="MSFT",
        date=today - timedelta(days=2),
        close_price=Decimal("100"),
        currency="USD",
        asset_type=AssetType.STOCK,
    )
    HistoricalPrice.objects.create(
        asset_symbol="MSFT",
        date=today - timedelta(days=1),
        close_price=Decimal("200"),
        currency="USD",
        asset_type=AssetType.STOCK,
    )
    row = latest_historical_price("msft")
    assert row is not None
    assert row.close_price == Decimal("200")


@pytest.mark.django_db
def test_missing_latest_price_returns_none(seeded):
    assert latest_historical_price("ZZZ") is None


@pytest.mark.django_db
def test_holdings_price_status_uses_latest_helper(api_client, seeded):
    today = date.today()
    _buy("AAPL", today - timedelta(days=5), currency="EUR")
    HistoricalPrice.objects.create(
        asset_symbol="AAPL",
        date=today - timedelta(days=1),
        close_price=Decimal("150"),
        currency="EUR",
        asset_type=AssetType.STOCK,
    )
    r = api_client.get("/api/v1/portfolio/holdings?display_currency=EUR")
    h = r.json()["holdings"][0]
    assert h["price_status"] == "ok"
    assert h["current_price"] == 150.0


@pytest.mark.django_db
def test_benchmark_indices_returns_enabled_seeded(api_client, seeded):
    r = api_client.get("/api/v1/benchmarks/indices")
    assert r.status_code == 200
    symbols = {i["symbol"] for i in r.json()["indices"]}
    assert "^GSPC" in symbols
    assert all("name" in i for i in r.json()["indices"])


@pytest.mark.django_db
def test_disabled_benchmark_not_listed(api_client, seeded):
    BenchmarkIndexConfig.objects.filter(symbol="^IXIC").update(enabled=False)
    r = api_client.get("/api/v1/benchmarks/indices")
    symbols = {i["symbol"] for i in r.json()["indices"]}
    assert "^IXIC" not in symbols


@pytest.mark.django_db
def test_benchmark_sync_stores_index_rows(seeded):
    _buy("AAPL", date(2026, 1, 1))
    provider = MockPriceProvider(
        {
            "^GSPC": [
                DailyPrice(date(2026, 1, 1), Decimal("4000"), "USD"),
                DailyPrice(date(2026, 1, 2), Decimal("4100"), "USD"),
            ]
        }
    )
    sync_benchmark_prices(provider=provider)
    rows = HistoricalPrice.objects.filter(
        asset_symbol="^GSPC", asset_type=AssetType.INDEX
    )
    assert rows.count() == 2


@pytest.mark.django_db
def test_benchmark_sync_incremental_idempotent(seeded):
    _buy("AAPL", date(2026, 1, 1))
    provider = MockPriceProvider(
        {
            "^GSPC": [
                DailyPrice(date(2026, 1, 1), Decimal("100"), "USD"),
                DailyPrice(date(2026, 1, 2), Decimal("110"), "USD"),
            ]
        }
    )
    sync_benchmark_prices(provider=provider)
    sync_benchmark_prices(provider=provider)
    assert (
        HistoricalPrice.objects.filter(
            asset_symbol="^GSPC", asset_type=AssetType.INDEX
        ).count()
        == 2
    )


@pytest.mark.django_db
def test_benchmark_symbol_caret_preserved(seeded):
    _buy("AAPL", date(2026, 1, 1))
    provider = MockPriceProvider(
        {"^GSPC": [DailyPrice(date(2026, 1, 1), Decimal("100"), "USD")]}
    )
    sync_benchmark_prices(provider=provider)
    assert HistoricalPrice.objects.filter(asset_symbol="^GSPC").exists()


@pytest.mark.django_db
def test_sync_prices_command_calls_service(seeded):
    with patch("market_data.management.commands.sync_prices.sync_stock_prices") as m:
        call_command("sync_prices", stdout=StringIO())
    m.assert_called_once()


@pytest.mark.django_db
def test_sync_benchmarks_command_calls_service(seeded):
    with patch(
        "market_data.management.commands.sync_benchmarks.sync_benchmark_prices"
    ) as m:
        call_command("sync_benchmarks", stdout=StringIO())
    m.assert_called_once()


@pytest.mark.django_db
def test_sync_stock_prices_filters_to_transaction_symbols(seeded):
    today = date.today()
    _buy("AAPL", today - timedelta(days=2))
    provider = MockPriceProvider(
        {"AAPL": [DailyPrice(today - timedelta(days=1), Decimal("1"), "USD")]}
    )
    sync_stock_prices(only_symbols={"AAPL", "MSFT"}, provider=provider)
    assert "MSFT" not in {c[0] for c in provider.calls}
