from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser

from portfolios.constants import (
    DEFAULT_BASE_CURRENCY,
    DEFAULT_CASH_AWARE_ENABLED_FOR_NEW,
    MAX_ACTIVE_PORTFOLIOS,
    VIRTUAL_ALL_PORTFOLIOS_NAME,
)
from portfolios.models import Portfolio
from portfolios.seed import ensure_default_portfolio


class PortfolioNotFoundError(Exception):
    pass


class PortfolioValidationError(Exception):
    pass


def list_active_portfolios(user: AbstractBaseUser) -> list[Portfolio]:
    ensure_default_portfolio(user)
    return list(
        Portfolio.objects.filter(user=user, is_active=True).order_by("-is_default", "id")
    )


def get_portfolio(user: AbstractBaseUser, portfolio_id: int) -> Portfolio:
    ensure_default_portfolio(user)
    portfolio = Portfolio.objects.filter(user=user, pk=portfolio_id).first()
    if not portfolio:
        raise PortfolioNotFoundError(f"Portfolio not found: {portfolio_id}")
    return portfolio


def _normalize_name(name: str) -> str:
    nm = (name or "").strip()
    if not nm:
        raise PortfolioValidationError("name must not be empty")
    if nm == VIRTUAL_ALL_PORTFOLIOS_NAME:
        raise PortfolioValidationError(
            "All Portfolios is a virtual aggregate and is not stored in DB"
        )
    return nm


def _active_name_exists(user: AbstractBaseUser, name: str, *, exclude_id: int | None = None) -> bool:
    qs = Portfolio.objects.filter(user=user, is_active=True, name__iexact=name)
    if exclude_id is not None:
        qs = qs.exclude(pk=exclude_id)
    return qs.exists()


def _active_count(user: AbstractBaseUser) -> int:
    return Portfolio.objects.filter(user=user, is_active=True).count()


def create_portfolio(
    user: AbstractBaseUser,
    *,
    name: str,
    description: str | None = None,
    base_currency: str | None = None,
    cash_aware_enabled: bool = DEFAULT_CASH_AWARE_ENABLED_FOR_NEW,
) -> Portfolio:
    ensure_default_portfolio(user)
    nm = _normalize_name(name)

    if _active_name_exists(user, nm):
        raise PortfolioValidationError("Duplicate active portfolio name")

    if _active_count(user) >= MAX_ACTIVE_PORTFOLIOS:
        raise PortfolioValidationError(
            f"Max active portfolios is {MAX_ACTIVE_PORTFOLIOS}"
        )

    bc = (base_currency or DEFAULT_BASE_CURRENCY).strip().upper() or DEFAULT_BASE_CURRENCY
    portfolio = Portfolio(
        user=user,
        name=nm,
        description=description,
        base_currency=bc,
        is_default=False,
        is_active=True,
        cash_aware_enabled=bool(cash_aware_enabled),
    )
    portfolio.save()
    return portfolio


def update_portfolio(
    user: AbstractBaseUser,
    portfolio_id: int,
    *,
    name: str | None = None,
    description: str | None = None,
    base_currency: str | None = None,
    is_active: bool | None = None,
    cash_aware_enabled: bool | None = None,
) -> Portfolio:
    portfolio = get_portfolio(user, portfolio_id)

    if name is not None:
        nm = _normalize_name(name)
        if _active_name_exists(user, nm, exclude_id=portfolio.id):
            raise PortfolioValidationError("Duplicate active portfolio name")
        portfolio.name = nm

    if description is not None:
        portfolio.description = description

    if base_currency is not None:
        bc = (base_currency or DEFAULT_BASE_CURRENCY).strip().upper() or DEFAULT_BASE_CURRENCY
        portfolio.base_currency = bc

    if is_active is not None:
        if portfolio.is_default and not is_active:
            raise PortfolioValidationError("Default portfolio cannot be deactivated")
        if is_active and not portfolio.is_active and _active_count(user) >= MAX_ACTIVE_PORTFOLIOS:
            raise PortfolioValidationError(
                f"Max active portfolios is {MAX_ACTIVE_PORTFOLIOS}"
            )
        portfolio.is_active = bool(is_active)

    if cash_aware_enabled is not None:
        portfolio.cash_aware_enabled = bool(cash_aware_enabled)

    portfolio.save()
    return portfolio


def deactivate_portfolio(user: AbstractBaseUser, portfolio_id: int) -> Portfolio:
    portfolio = get_portfolio(user, portfolio_id)
    if portfolio.is_default:
        raise PortfolioValidationError("Default portfolio cannot be deleted")
    portfolio.is_active = False
    portfolio.save()
    return portfolio
