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
