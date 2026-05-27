from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from market_data.providers.base import PriceProvider
from market_data.providers.yfinance_provider import default_price_provider
from market_data.services.benchmark_sync import sync_benchmark_prices
from market_data.services.mutual_fund_nav_sync import (
    MutualFundNavSyncResult,
    sync_mutual_fund_navs,
)
from market_data.services.price_sync import sync_stock_prices


@dataclass
class MarketDataSyncResult:
    prices_success: bool
    benchmarks_success: bool
    fx_success: bool
    fx_partial: bool
    mutual_funds_synced: int = 0
    mutual_funds_skipped: int = 0
    mutual_funds_failed: int = 0

    @property
    def mutual_funds_success(self) -> bool:
        return self.mutual_funds_failed == 0

    @property
    def success(self) -> bool:
        return self.prices_success and self.benchmarks_success and self.fx_success


def sync_all_market_data(
    *,
    only_symbols: Optional[set[str]] = None,
    price_provider: PriceProvider | None = None,
    run_fx: bool = True,
    run_mutual_funds: bool = True,
) -> MarketDataSyncResult:
    """Run stock prices, benchmarks, optional FX, and optional mutual fund NAV sync."""
    provider = price_provider or default_price_provider()
    price_result = sync_stock_prices(
        only_symbols=only_symbols,
        provider=provider,
        update_last_sync=False,
    )
    bench_ok = sync_benchmark_prices(provider=provider)

    fx_ok = True
    fx_partial = False
    if run_fx:
        from fx.services import sync_fx_rates

        fx_result = sync_fx_rates()
        fx_ok = fx_result.success
        fx_partial = fx_result.partial

    mf_synced = 0
    mf_skipped = 0
    mf_failed = 0
    if run_mutual_funds:
        mf_result = sync_mutual_fund_navs()
        mf_synced = mf_result.synced
        mf_skipped = mf_result.skipped
        mf_failed = mf_result.failed

    if price_result.success and bench_ok and fx_ok:
        from django.utils import timezone

        from settings_app.models import AppSettings

        settings = AppSettings.objects.first()
        if settings:
            settings.last_sync_timestamp = timezone.now()
            settings.save(update_fields=["last_sync_timestamp", "updated_at"])

    return MarketDataSyncResult(
        prices_success=price_result.success,
        benchmarks_success=bench_ok,
        fx_success=fx_ok,
        fx_partial=fx_partial,
        mutual_funds_synced=mf_synced,
        mutual_funds_skipped=mf_skipped,
        mutual_funds_failed=mf_failed,
    )
