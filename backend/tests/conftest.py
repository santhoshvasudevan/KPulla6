import os

import pytest
from rest_framework.test import APIClient

# Use in-memory SQLite for unit tests (no Docker required for `make test`).
os.environ.setdefault("DJANGO_TEST_USE_SQLITE", "1")


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
