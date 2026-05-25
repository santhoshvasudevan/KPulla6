from __future__ import annotations

from portfolios.constants import (
    DEFAULT_BASE_CURRENCY,
    MAX_ACTIVE_PORTFOLIOS,
    VIRTUAL_ALL_PORTFOLIOS_NAME,
)
from portfolios.models import Portfolio
from portfolios.seed import ensure_default_portfolio


class PortfolioNotFoundError(Exception):
    pass


class PortfolioValidationError(Exception):
    pass


def list_active_portfolios() -> list[Portfolio]:
    ensure_default_portfolio()
    return list(
        Portfolio.objects.filter(is_active=True).order_by("-is_default", "id")
    )


def get_portfolio(portfolio_id: int) -> Portfolio:
    ensure_default_portfolio()
    portfolio = Portfolio.objects.filter(pk=portfolio_id).first()
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


def _active_name_exists(name: str, *, exclude_id: int | None = None) -> bool:
    qs = Portfolio.objects.filter(is_active=True, name__iexact=name)
    if exclude_id is not None:
        qs = qs.exclude(pk=exclude_id)
    return qs.exists()


def _active_count() -> int:
    return Portfolio.objects.filter(is_active=True).count()


def create_portfolio(
    *,
    name: str,
    description: str | None = None,
    base_currency: str | None = None,
) -> Portfolio:
    ensure_default_portfolio()
    nm = _normalize_name(name)

    if _active_name_exists(nm):
        raise PortfolioValidationError("Duplicate active portfolio name")

    if _active_count() >= MAX_ACTIVE_PORTFOLIOS:
        raise PortfolioValidationError(
            f"Max active portfolios is {MAX_ACTIVE_PORTFOLIOS}"
        )

    bc = (base_currency or DEFAULT_BASE_CURRENCY).strip().upper() or DEFAULT_BASE_CURRENCY
    portfolio = Portfolio(
        name=nm,
        description=description,
        base_currency=bc,
        is_default=False,
        is_active=True,
    )
    portfolio.save()
    return portfolio


def update_portfolio(
    portfolio_id: int,
    *,
    name: str | None = None,
    description: str | None = None,
    base_currency: str | None = None,
    is_active: bool | None = None,
) -> Portfolio:
    portfolio = get_portfolio(portfolio_id)

    if name is not None:
        nm = _normalize_name(name)
        if _active_name_exists(nm, exclude_id=portfolio.id):
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
        if is_active and not portfolio.is_active and _active_count() >= MAX_ACTIVE_PORTFOLIOS:
            raise PortfolioValidationError(
                f"Max active portfolios is {MAX_ACTIVE_PORTFOLIOS}"
            )
        portfolio.is_active = bool(is_active)

    portfolio.save()
    return portfolio


def deactivate_portfolio(portfolio_id: int) -> Portfolio:
    portfolio = get_portfolio(portfolio_id)
    if portfolio.is_default:
        raise PortfolioValidationError("Default portfolio cannot be deleted")
    portfolio.is_active = False
    portfolio.save()
    return portfolio
