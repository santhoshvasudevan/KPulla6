import os

import pytest
from rest_framework.test import APIClient

# Use in-memory SQLite for unit tests (no Docker required for `make test`).
os.environ.setdefault("DJANGO_TEST_USE_SQLITE", "1")


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def seeded(db):
    from market_data.seed import ensure_benchmark_indices
    from portfolios.seed import ensure_default_portfolio
    from settings_app.seed import ensure_app_settings

    ensure_default_portfolio()
    ensure_app_settings()
    ensure_benchmark_indices()
