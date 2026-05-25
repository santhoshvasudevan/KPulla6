from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from fx.models import FXRate
from market_data.models import AssetType, BenchmarkIndexConfig, HistoricalPrice
from portfolios.constants import DEFAULT_PORTFOLIO_NAME, VIRTUAL_ALL_PORTFOLIOS_NAME
from portfolios.models import Portfolio
from portfolios.seed import assert_no_virtual_portfolio_rows, ensure_default_portfolio
from market_data.seed import DEFAULT_BENCHMARK_INDICES, ensure_benchmark_indices
from settings_app.models import AppSettings, DisplayCurrency
from settings_app.seed import ensure_app_settings
from transactions.models import Transaction, TransactionType


def test_models_import():
    assert Portfolio._meta.db_table == "portfolios"
    assert Transaction._meta.db_table == "transactions"
    assert HistoricalPrice._meta.db_table == "historical_prices"
    assert FXRate._meta.db_table == "fx_rates"
    assert BenchmarkIndexConfig._meta.db_table == "benchmark_index_config"
    assert AppSettings._meta.db_table == "settings"


@pytest.mark.django_db
def test_default_portfolio_seed_idempotent():
    first = ensure_default_portfolio()
    second = ensure_default_portfolio()
    assert first.id == second.id
    assert Portfolio.objects.filter(is_default=True).count() == 1
    assert Portfolio.objects.get(is_default=True).name == DEFAULT_PORTFOLIO_NAME


@pytest.mark.django_db
def test_app_settings_seed_idempotent():
    first = ensure_app_settings()
    second = ensure_app_settings()
    assert first.id == second.id
    assert AppSettings.objects.count() == 1
    assert first.display_currency == DisplayCurrency.EUR


@pytest.mark.django_db
def test_benchmark_seed_idempotent():
    ensure_benchmark_indices()
    ensure_benchmark_indices()
    assert BenchmarkIndexConfig.objects.count() == len(DEFAULT_BENCHMARK_INDICES)
    symbols = set(BenchmarkIndexConfig.objects.values_list("symbol", flat=True))
    assert symbols == {row[0] for row in DEFAULT_BENCHMARK_INDICES}


@pytest.mark.django_db
def test_historical_price_uniqueness():
    HistoricalPrice.objects.create(
        asset_symbol="AAPL",
        date=date(2026, 1, 1),
        close_price=Decimal("150.00"),
        currency="USD",
        asset_type=AssetType.STOCK,
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            HistoricalPrice.objects.create(
                asset_symbol="AAPL",
                date=date(2026, 1, 1),
                close_price=Decimal("151.00"),
                currency="USD",
                asset_type=AssetType.STOCK,
            )


@pytest.mark.django_db
def test_fx_rate_uniqueness():
    FXRate.objects.create(
        from_currency="EUR",
        to_currency="USD",
        date=date(2026, 1, 1),
        rate=Decimal("1.10"),
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            FXRate.objects.create(
                from_currency="EUR",
                to_currency="USD",
                date=date(2026, 1, 1),
                rate=Decimal("1.11"),
            )


@pytest.mark.django_db
def test_transaction_requires_portfolio():
    portfolio = ensure_default_portfolio()
    txn = Transaction.objects.create(
        portfolio=portfolio,
        asset_symbol="AAPL",
        date=date(2026, 5, 1),
        type=TransactionType.BUY,
        quantity=Decimal("10"),
        price_per_share=Decimal("150.00"),
        currency="USD",
        fees=Decimal("0"),
    )
    assert txn.portfolio_id == portfolio.id

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Transaction.objects.create(
                portfolio_id=None,
                asset_symbol="MSFT",
                date=date(2026, 5, 2),
                type=TransactionType.BUY,
                quantity=Decimal("1"),
                price_per_share=Decimal("100"),
                currency="USD",
            )


@pytest.mark.django_db
def test_all_portfolios_not_stored():
    ensure_default_portfolio()
    assert_no_virtual_portfolio_rows()
    assert not Portfolio.objects.filter(name=VIRTUAL_ALL_PORTFOLIOS_NAME).exists()

    portfolio = Portfolio(name=VIRTUAL_ALL_PORTFOLIOS_NAME, base_currency="EUR")
    with pytest.raises(ValidationError):
        portfolio.full_clean()
