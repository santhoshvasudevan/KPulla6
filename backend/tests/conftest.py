import os
from datetime import date
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

# Use in-memory SQLite for unit tests (no Docker required for `make test`).
os.environ.setdefault("DJANGO_TEST_USE_SQLITE", "1")


def cached_mf_nav(scheme_code, nav_date, nav):
    """Seed a real exact-date INR NAV explicitly for transaction write fixtures."""
    from market_data.models import AssetType, HistoricalPrice

    return HistoricalPrice.objects.update_or_create(
        asset_symbol=scheme_code,
        asset_type=AssetType.MUTUAL_FUND,
        date=date.fromisoformat(nav_date) if isinstance(nav_date, str) else nav_date,
        defaults={"close_price": Decimal(nav), "currency": "INR", "source": "test"},
    )[0]


def historical_mf_transaction(portfolio, payload, *, status="NAV_MISSING"):
    """Create pre-enforcement history without inventing NAV cache coverage."""
    from market_data.models import Asset, AssetType, MutualFundProfile
    from portfolios.models import Portfolio
    from transactions.models import Folio, MutualFundTransactionDetail, Transaction

    if payload.get("portfolio_id") is not None:
        portfolio = Portfolio.objects.get(pk=payload["portfolio_id"], user=portfolio.user)

    asset, _ = Asset.objects.get_or_create(
        asset_type=AssetType.MUTUAL_FUND, symbol=payload["scheme_code"],
        defaults={"display_name": payload["scheme_name"], "currency": "INR"},
    )
    MutualFundProfile.objects.get_or_create(
        asset=asset,
        defaults={
            "scheme_code": payload["scheme_code"],
            "scheme_name": payload["scheme_name"],
            "fund_house": payload.get("fund_house", ""),
        },
    )
    folio, _ = Folio.objects.get_or_create(
        portfolio=portfolio, asset=asset, folio_number=payload["folio_number"],
    )
    nav = Decimal(payload["nav"])
    units = Decimal(payload["units_allotted"])
    paid = Decimal(payload["paid_value"])
    market = Decimal(payload["market_value"])
    txn = Transaction.objects.create(
        portfolio=portfolio, asset_symbol=payload["scheme_code"],
        date=payload["nav_date"], type=payload["type"], quantity=units,
        price_per_share=nav, currency="INR",
        fees=Decimal(payload.get("fees", paid - market)),
        actual_cash_received=payload.get("actual_cash_received"),
    )
    MutualFundTransactionDetail.objects.create(
        transaction=txn, folio=folio, investment_date=payload["investment_date"],
        nav_date=payload["nav_date"], nav=nav, units_allotted=units,
        paid_value=paid, market_value=market, nav_verification_status=status,
    )
    txn.refresh_from_db()
    return txn


@pytest.fixture
def test_user(db):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
    )


@pytest.fixture
def other_user(db):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    return User.objects.create_user(
        username="otheruser",
        email="other@example.com",
        password="testpass123",
    )


@pytest.fixture
def api_client(test_user):
    client = APIClient()
    client.force_authenticate(user=test_user)
    return client


@pytest.fixture
def anon_client():
    return APIClient()


@pytest.fixture
def seeded(db, test_user):
    from market_data.seed import ensure_benchmark_indices
    from portfolios.seed import ensure_default_portfolio
    from settings_app.seed import ensure_app_settings

    ensure_default_portfolio(test_user)
    ensure_app_settings(test_user)
    ensure_benchmark_indices()


@pytest.fixture
def cash_aware_portfolio(seeded, test_user):
    from portfolios.seed import ensure_default_portfolio

    portfolio = ensure_default_portfolio(test_user)
    if not portfolio.cash_aware_enabled:
        portfolio.cash_aware_enabled = True
        portfolio.save(update_fields=["cash_aware_enabled", "updated_at"])
    return portfolio


@pytest.fixture
def legacy_seeded(seeded, test_user):
    """Default portfolio in legacy cash mode (pre–Cash-4A.1 rows).

    Use for tests that set up BUY/SELL/MF transactions without exercising cash
    ledger enforcement (holdings, filters, split valuation, MF NAV, etc.).
    Use ``seeded`` plus explicit ``CASH_DEPOSIT`` rows when testing cash-aware behavior.
    """
    from portfolios.seed import ensure_default_portfolio

    portfolio = ensure_default_portfolio(test_user)
    if portfolio.cash_aware_enabled:
        portfolio.cash_aware_enabled = False
        portfolio.save(update_fields=["cash_aware_enabled", "updated_at"])
