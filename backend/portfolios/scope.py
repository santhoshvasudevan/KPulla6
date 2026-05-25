from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from portfolios.models import Portfolio
from portfolios.services import PortfolioNotFoundError, list_active_portfolios
from portfolios.seed import ensure_default_portfolio


class PortfolioScopeError(Exception):
    pass


@dataclass(frozen=True)
class ResolvedPortfolioScope:
    kind: Literal["all_active", "single"]
    portfolio_ids: list[int]


def resolve_portfolio_scope(
    *,
    portfolio_scope: str | None = None,
    portfolio_id: int | None = None,
) -> ResolvedPortfolioScope:
    if portfolio_scope and portfolio_id is not None:
        raise PortfolioScopeError("Provide either portfolio_scope=all or portfolio_id, not both")

    if portfolio_scope is None and portfolio_id is None:
        portfolio_scope = "all"

    if portfolio_scope is not None:
        if str(portfolio_scope).strip().lower() != "all":
            raise PortfolioScopeError("portfolio_scope must be 'all'")
        ensure_default_portfolio()
        ids = [p.id for p in list_active_portfolios()]
        return ResolvedPortfolioScope(kind="all_active", portfolio_ids=ids)

    assert portfolio_id is not None
    portfolio = _get_active_portfolio(portfolio_id)
    return ResolvedPortfolioScope(kind="single", portfolio_ids=[portfolio.id])


def resolve_portfolio_id_or_default(portfolio_id: int | None) -> int:
    ensure_default_portfolio()
    if portfolio_id is None:
        default = Portfolio.objects.filter(is_default=True).order_by("id").first()
        if not default:
            raise PortfolioNotFoundError("Default portfolio not found")
        return default.id
    return _get_active_portfolio(portfolio_id).id


def _get_active_portfolio(portfolio_id: int) -> Portfolio:
    portfolio = Portfolio.objects.filter(pk=portfolio_id).first()
    if not portfolio:
        raise PortfolioNotFoundError(f"Portfolio not found: {portfolio_id}")
    if not portfolio.is_active:
        raise PortfolioNotFoundError(f"Portfolio is inactive: {portfolio_id}")
    return portfolio
