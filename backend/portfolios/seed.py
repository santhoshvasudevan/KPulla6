from portfolios.constants import (
    DEFAULT_BASE_CURRENCY,
    DEFAULT_PORTFOLIO_NAME,
    VIRTUAL_ALL_PORTFOLIOS_NAME,
)
from portfolios.models import Portfolio


def ensure_default_portfolio() -> Portfolio:
    portfolio, _ = Portfolio.objects.get_or_create(
        is_default=True,
        defaults={
            "name": DEFAULT_PORTFOLIO_NAME,
            "description": None,
            "base_currency": DEFAULT_BASE_CURRENCY,
            "is_active": True,
        },
    )
    return portfolio


def assert_no_virtual_portfolio_rows() -> None:
    if Portfolio.objects.filter(name=VIRTUAL_ALL_PORTFOLIOS_NAME).exists():
        raise RuntimeError(f'Virtual portfolio "{VIRTUAL_ALL_PORTFOLIOS_NAME}" must not exist in DB.')
