"""Shared helpers for read-only diagnostic scripts."""

from __future__ import annotations

import json
from typing import Any

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractBaseUser

from portfolios.models import Portfolio
from portfolios.scope import PortfolioScopeError, ResolvedPortfolioScope, resolve_portfolio_scope

User = get_user_model()


def resolve_user(username: str | None) -> AbstractBaseUser:
    if username:
        user = User.objects.filter(username=username).first()
        if not user:
            raise SystemExit(f"User not found: {username!r}")
        return user
    user = User.objects.order_by("id").first()
    if not user:
        raise SystemExit("No users in database")
    return user


def resolve_diagnostic_scope(
    user: AbstractBaseUser,
    *,
    portfolio_id: int | None,
    portfolio_scope: str | None,
) -> ResolvedPortfolioScope:
    if portfolio_id is not None and portfolio_scope:
        raise SystemExit("Provide --portfolio-id or --portfolio-scope=all, not both")
    try:
        return resolve_portfolio_scope(
            user,
            portfolio_scope=portfolio_scope,
            portfolio_id=portfolio_id,
        )
    except PortfolioScopeError as exc:
        raise SystemExit(str(exc)) from exc


def portfolios_for_scope(
    user: AbstractBaseUser,
    *,
    portfolio_id: int | None,
    portfolio_scope: str | None,
) -> tuple[ResolvedPortfolioScope, list[Portfolio]]:
    scope = resolve_diagnostic_scope(
        user, portfolio_id=portfolio_id, portfolio_scope=portfolio_scope
    )
    qs = Portfolio.objects.filter(id__in=scope.portfolio_ids, user=user).order_by("id")
    return scope, list(qs)


def emit_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, default=str))


def print_scope_header(scope: ResolvedPortfolioScope) -> None:
    print("=== Scope ===")
    print(f"  kind={scope.kind} portfolio_ids={scope.portfolio_ids}")
