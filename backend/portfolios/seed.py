from django.contrib.auth.models import AbstractBaseUser

from portfolios.constants import (
    DEFAULT_BASE_CURRENCY,
    DEFAULT_CASH_AWARE_ENABLED_FOR_NEW,
    DEFAULT_PORTFOLIO_NAME,
    VIRTUAL_ALL_PORTFOLIOS_NAME,
)
from portfolios.models import Portfolio


def ensure_default_portfolio(user: AbstractBaseUser) -> Portfolio:
    portfolio = Portfolio.objects.filter(user=user, is_default=True).first()
    if portfolio is not None:
        return portfolio
    portfolio = Portfolio.objects.create(
        user=user,
        name=DEFAULT_PORTFOLIO_NAME,
        description=None,
        base_currency=DEFAULT_BASE_CURRENCY,
        is_default=True,
        is_active=True,
        cash_aware_enabled=DEFAULT_CASH_AWARE_ENABLED_FOR_NEW,
    )
    return portfolio


def assert_no_virtual_portfolio_rows() -> None:
    if Portfolio.objects.filter(name=VIRTUAL_ALL_PORTFOLIOS_NAME).exists():
        raise RuntimeError(f'Virtual portfolio "{VIRTUAL_ALL_PORTFOLIOS_NAME}" must not exist in DB.')
