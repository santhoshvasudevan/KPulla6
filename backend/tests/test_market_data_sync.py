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
from market_data.providers.mutual_fund_nav_provider import NavPoint
from market_data.services.benchmark_sync import sync_benchmark_prices
from market_data.services.market_data_sync import sync_all_market_data
from market_data.services.price_sync import (
    resolve_stock_sync_start_date,
    sync_one_stock_symbol,
    sync_stock_prices,
)
from market_data.services.symbols import stock_transaction_symbols
from portfolios.seed import ensure_default_portfolio
from tests.test_mutual_fund_nav_sync import MockNavProvider, _mf_buy_with_detail
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
def test_sync_uses_latest_stored_date_plus_one_when_coverage_from_inception(seeded):
    today = date.today()
    _buy("AAPL", today - timedelta(days=5))
    HistoricalPrice.objects.create(
        asset_symbol="AAPL",
        date=today - timedelta(days=5),
        close_price=Decimal("154"),
        currency="USD",
        asset_type=AssetType.STOCK,
    )
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
    assert HistoricalPrice.objects.filter(asset_symbol="AAPL").count() == 4


@pytest.mark.django_db
def test_sync_backfills_when_transaction_predates_earliest_cached_price(seeded):
    txn_date = date(2022, 5, 2)
    cache_start = date(2022, 12, 23)
    _buy("GOOG", txn_date)
    HistoricalPrice.objects.create(
        asset_symbol="GOOG",
        date=cache_start,
        close_price=Decimal("90"),
        currency="USD",
        asset_type=AssetType.STOCK,
    )
    HistoricalPrice.objects.create(
        asset_symbol="GOOG",
        date=date(2022, 12, 24),
        close_price=Decimal("91"),
        currency="USD",
        asset_type=AssetType.STOCK,
    )
    provider = MockPriceProvider(
        {
            "GOOG": [
                DailyPrice(date(2022, 5, 3), Decimal("100"), "USD"),
                DailyPrice(date(2022, 12, 22), Decimal("89"), "USD"),
            ]
        }
    )
    sync_one_stock_symbol("GOOG", provider, end=date(2022, 12, 24))
    assert provider.calls[0][1] == txn_date
    assert HistoricalPrice.objects.filter(asset_symbol="GOOG", date=date(2022, 5, 3)).exists()
    assert HistoricalPrice.objects.filter(asset_symbol="GOOG", date=date(2022, 12, 22)).exists()


@pytest.mark.django_db
def test_sync_backfills_only_symbols_with_coverage_gaps(seeded):
    gap_txn = date(2022, 5, 2)
    ok_txn = date.today() - timedelta(days=5)
    _buy("GOOG", gap_txn)
    _buy("AAPL", ok_txn)
    HistoricalPrice.objects.create(
        asset_symbol="GOOG",
        date=date(2022, 12, 23),
        close_price=Decimal("90"),
        currency="USD",
        asset_type=AssetType.STOCK,
    )
    HistoricalPrice.objects.create(
        asset_symbol="AAPL",
        date=ok_txn,
        close_price=Decimal("150"),
        currency="USD",
        asset_type=AssetType.STOCK,
    )
    provider = MockPriceProvider(
        {
            "GOOG": [DailyPrice(date(2022, 5, 3), Decimal("100"), "USD")],
            "AAPL": [DailyPrice(ok_txn + timedelta(days=1), Decimal("151"), "USD")],
        }
    )
    sync_stock_prices(provider=provider)
    calls = {sym: start for sym, start, _ in provider.calls}
    assert calls["GOOG"] == gap_txn
    assert calls["AAPL"] == ok_txn + timedelta(days=1)


def test_resolve_stock_sync_start_date_rules():
    txn = date(2022, 5, 2)
    cache_start = date(2022, 12, 23)
    cache_end = date(2026, 3, 15)
    assert (
        resolve_stock_sync_start_date(
            min_txn_date=txn,
            min_hist_date=None,
            max_hist_date=None,
        )
        == txn
    )
    assert (
        resolve_stock_sync_start_date(
            min_txn_date=txn,
            min_hist_date=cache_start,
            max_hist_date=cache_end,
        )
        == txn
    )
    assert (
        resolve_stock_sync_start_date(
            min_txn_date=txn,
            min_hist_date=txn,
            max_hist_date=cache_end,
        )
        == cache_end + timedelta(days=1)
    )


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
    assert "^NSEI" in symbols
    assert "^BSESN" in symbols
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
    anchor = date(2026, 1, 1)
    cached_through = date(2026, 1, 5)
    _buy("AAPL", anchor)
    HistoricalPrice.objects.create(
        asset_symbol="^GSPC",
        date=anchor,
        close_price=Decimal("90"),
        currency="USD",
        asset_type=AssetType.INDEX,
    )
    HistoricalPrice.objects.create(
        asset_symbol="^GSPC",
        date=cached_through,
        close_price=Decimal("100"),
        currency="USD",
        asset_type=AssetType.INDEX,
    )
    provider = MockPriceProvider(
        {
            "^GSPC": [
                DailyPrice(date(2026, 1, 6), Decimal("106"), "USD"),
                DailyPrice(date(2026, 1, 7), Decimal("107"), "USD"),
            ]
        }
    )
    sync_benchmark_prices(provider=provider, end=date(2026, 1, 7))
    gspc_calls = [c for c in provider.calls if c[0] == "^GSPC"]
    assert gspc_calls[0][1] == cached_through + timedelta(days=1)
    assert (
        HistoricalPrice.objects.filter(
            asset_symbol="^GSPC", asset_type=AssetType.INDEX
        ).count()
        == 4
    )


@pytest.mark.django_db
def test_benchmark_sync_warm_cache_starts_at_latest_plus_one(seeded):
    anchor = date(2026, 1, 1)
    cached_through = date(2026, 1, 10)
    _buy("AAPL", anchor)
    HistoricalPrice.objects.create(
        asset_symbol="^GSPC",
        date=anchor,
        close_price=Decimal("90"),
        currency="USD",
        asset_type=AssetType.INDEX,
    )
    HistoricalPrice.objects.create(
        asset_symbol="^GSPC",
        date=cached_through,
        close_price=Decimal("100"),
        currency="USD",
        asset_type=AssetType.INDEX,
    )
    provider = MockPriceProvider(
        {"^GSPC": [DailyPrice(date(2026, 1, 11), Decimal("101"), "USD")]}
    )
    sync_benchmark_prices(provider=provider, end=date(2026, 1, 11))
    gspc_calls = [c for c in provider.calls if c[0] == "^GSPC"]
    assert gspc_calls[0][1] == cached_through + timedelta(days=1)


@pytest.mark.django_db
def test_benchmark_sync_backfills_when_anchor_predates_earliest_cached(seeded):
    anchor = date(2022, 5, 2)
    cache_start = date(2022, 12, 23)
    _buy("AAPL", anchor)
    HistoricalPrice.objects.create(
        asset_symbol="^GSPC",
        date=cache_start,
        close_price=Decimal("4000"),
        currency="USD",
        asset_type=AssetType.INDEX,
    )
    provider = MockPriceProvider(
        {
            "^GSPC": [
                DailyPrice(date(2022, 5, 3), Decimal("3900"), "USD"),
                DailyPrice(date(2022, 12, 22), Decimal("3950"), "USD"),
            ]
        }
    )
    sync_benchmark_prices(provider=provider, end=date(2022, 12, 24))
    gspc_calls = [c for c in provider.calls if c[0] == "^GSPC"]
    assert gspc_calls[0][1] == anchor
    assert HistoricalPrice.objects.filter(
        asset_symbol="^GSPC", date=date(2022, 5, 3)
    ).exists()
    assert HistoricalPrice.objects.filter(
        asset_symbol="^GSPC", date=date(2022, 12, 22)
    ).exists()


@pytest.mark.django_db
def test_benchmark_sync_anchor_uses_earliest_transaction_including_mf(seeded):
    mf_date = date(2019, 10, 24)
    stock_date = date(2022, 5, 2)
    _mf_buy_with_detail(scheme_code="119062", nav_date=mf_date)
    _buy("AAPL", stock_date)
    provider = MockPriceProvider(
        {"^GSPC": [DailyPrice(mf_date, Decimal("3000"), "USD")]}
    )
    sync_benchmark_prices(provider=provider, end=stock_date)
    gspc_calls = [c for c in provider.calls if c[0] == "^GSPC"]
    assert gspc_calls[0][1] == mf_date


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


@pytest.mark.django_db
def test_stock_transaction_symbols_exclude_mutual_fund_scheme_codes(seeded):
    today = date.today()
    _buy("AAPL", today - timedelta(days=2))
    _mf_buy_with_detail(scheme_code="119062", nav_date=today - timedelta(days=3))

    symbols = stock_transaction_symbols()
    assert "AAPL" in symbols
    assert "119062" not in symbols


@pytest.mark.django_db
def test_sync_stock_prices_does_not_fetch_mutual_fund_scheme_codes(seeded):
    today = date.today()
    _buy("AAPL", today - timedelta(days=2))
    _mf_buy_with_detail(scheme_code="119062", nav_date=today - timedelta(days=3))

    provider = MockPriceProvider(
        {
            "AAPL": [DailyPrice(today - timedelta(days=1), Decimal("150"), "USD")],
            "119062": [DailyPrice(today - timedelta(days=1), Decimal("42"), "INR")],
        }
    )
    sync_stock_prices(provider=provider)

    called_symbols = {c[0] for c in provider.calls}
    assert called_symbols == {"AAPL"}
    assert "119062" not in called_symbols


@pytest.mark.django_db
def test_sync_all_market_data_routes_symbols_to_correct_providers(seeded):
    today = date.today()
    _buy("AAPL", today - timedelta(days=2))
    _mf_buy_with_detail(scheme_code="119062", nav_date=today - timedelta(days=3))

    stock_provider = MockPriceProvider(
        {"AAPL": [DailyPrice(today - timedelta(days=1), Decimal("150"), "USD")]}
    )
    nav_provider = MockNavProvider(
        {"119062": [NavPoint(today - timedelta(days=2), Decimal("42.50"), "INR")]}
    )

    with patch(
        "market_data.services.market_data_sync.default_price_provider",
        return_value=stock_provider,
    ):
        with patch(
            "market_data.services.market_data_sync.sync_benchmark_prices",
            return_value=True,
        ):
            with patch("fx.services.sync_fx_rates") as mock_fx:
                mock_fx.return_value = type(
                    "R", (), {"success": True, "partial": False}
                )()
                with patch(
                    "market_data.services.mutual_fund_nav_sync.default_mutual_fund_nav_provider",
                    return_value=nav_provider,
                ):
                    result = sync_all_market_data(run_mutual_funds=True)

    stock_symbols = {c[0] for c in stock_provider.calls}
    nav_codes = {c[0] for c in nav_provider.history_calls}

    assert stock_symbols == {"AAPL"}
    assert "119062" not in stock_symbols
    assert "119062" in nav_codes
    assert result.mutual_funds_synced >= 1
    assert result.mutual_funds_failed == 0


@pytest.mark.django_db
def test_sync_all_market_data_incremental_with_warm_caches(seeded):
    today = date.today()
    txn_date = today - timedelta(days=10)
    cache_through = today - timedelta(days=3)
    _buy("AAPL", txn_date)
    _mf_buy_with_detail(scheme_code="119062", nav_date=today - timedelta(days=8))

    HistoricalPrice.objects.create(
        asset_symbol="AAPL",
        date=txn_date,
        close_price=Decimal("150"),
        currency="USD",
        asset_type=AssetType.STOCK,
    )
    HistoricalPrice.objects.create(
        asset_symbol="AAPL",
        date=cache_through,
        close_price=Decimal("155"),
        currency="USD",
        asset_type=AssetType.STOCK,
    )
    HistoricalPrice.objects.create(
        asset_symbol="^GSPC",
        date=txn_date,
        close_price=Decimal("4000"),
        currency="USD",
        asset_type=AssetType.INDEX,
    )
    HistoricalPrice.objects.create(
        asset_symbol="^GSPC",
        date=cache_through,
        close_price=Decimal("4100"),
        currency="USD",
        asset_type=AssetType.INDEX,
    )

    expected_start = cache_through + timedelta(days=1)
    provider = MockPriceProvider(
        {
            "AAPL": [DailyPrice(expected_start, Decimal("156"), "USD")],
            "^GSPC": [DailyPrice(expected_start, Decimal("4110"), "USD")],
        }
    )
    nav_provider = MockNavProvider(
        {"119062": [NavPoint(expected_start, Decimal("42.50"), "INR")]}
    )

    with patch(
        "market_data.services.market_data_sync.default_price_provider",
        return_value=provider,
    ):
        with patch("fx.services.sync_fx_rates") as mock_fx:
            mock_fx.return_value = type(
                "R", (), {"success": True, "partial": False}
            )()
            with patch(
                "market_data.services.mutual_fund_nav_sync.default_mutual_fund_nav_provider",
                return_value=nav_provider,
            ):
                result = sync_all_market_data(run_mutual_funds=True)

    stock_calls = {sym: start for sym, start, _ in provider.calls}
    assert stock_calls["AAPL"] == expected_start
    assert stock_calls["^GSPC"] == expected_start
    assert "119062" not in stock_calls
    assert nav_provider.history_calls
    assert nav_provider.history_calls[0][0] == "119062"
    assert result.prices_success is True
    assert result.benchmarks_success is True
