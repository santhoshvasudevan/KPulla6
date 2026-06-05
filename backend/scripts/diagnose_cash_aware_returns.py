#!/usr/bin/env python3
"""
Read-only cash-aware portfolio return diagnostic (Cash-6D).

Prints summary current value, latest value-history point, cumulative_return,
TWROR, XIRR, cash balances, and external flows used for return metrics.
No database writes.

Usage:
  DJANGO_TEST_USE_SQLITE=1 .venv/bin/python scripts/diagnose_cash_aware_returns.py
  DJANGO_TEST_USE_SQLITE=1 .venv/bin/python scripts/diagnose_cash_aware_returns.py --username demo
  DJANGO_TEST_USE_SQLITE=1 .venv/bin/python scripts/diagnose_cash_aware_returns.py --portfolio-id 1

For local Postgres, omit DJANGO_TEST_USE_SQLITE and ensure DATABASE_URL points at
the intended database. This script never mutates data.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.contrib.auth import get_user_model

from cash.services import cash_balances_for_scope
from portfolios.cash_ledger_flows import (
    build_cash_aware_twror_external_flows,
    build_cash_aware_xirr_external_flows,
)
from portfolios.external_flows_service import (
    build_all_scope_external_flows,
    build_legacy_transaction_external_flows,
)
from portfolios.models import Portfolio
from portfolios.performance_service import build_portfolio_performance
from portfolios.scope import resolve_portfolio_scope
from portfolios.summary_service import build_portfolio_summary, fifo_eligible_queryset
from portfolios.xirr_service import compute_scope_xirr_detail

User = get_user_model()


def _last_valid(points: list) -> tuple[str | None, float | None]:
    for p in reversed(points):
        if p.value is not None:
            return p.date, float(p.value)
    return None, None


def _resolve_user(username: str | None):
    if username:
        user = User.objects.filter(username=username).first()
        if not user:
            raise SystemExit(f"User not found: {username!r}")
        return user
    user = User.objects.order_by("id").first()
    if not user:
        raise SystemExit("No users in database")
    return user


def _print_flows(label: str, flows: dict[date, Decimal]) -> None:
    if not flows:
        print(f"  {label}: (none)")
        return
    print(f"  {label}:")
    for d in sorted(flows):
        print(f"    {d.isoformat()}: {flows[d]}")


def diagnose(
    *,
    user,
    portfolio_id: int | None,
    portfolio_scope: str | None,
    display_currency: str,
) -> None:
    scope = resolve_portfolio_scope(
        user,
        portfolio_scope=portfolio_scope,
        portfolio_id=portfolio_id,
    )
    disp = display_currency.upper()
    today = date.today()

    portfolios = Portfolio.objects.filter(id__in=scope.portfolio_ids).order_by("id")
    print("=== Scope ===")
    print(f"  kind={scope.kind} portfolio_ids={scope.portfolio_ids} display_currency={disp}")
    for p in portfolios:
        print(
            f"  portfolio id={p.id} name={p.name!r} "
            f"cash_aware_enabled={p.cash_aware_enabled} base_currency={p.base_currency}"
        )

    summary = build_portfolio_summary(
        scope=scope,
        include_timeseries=False,
        display_currency=disp,
        user=user,
    )
    print("\n=== Summary ===")
    print(f"  current_value: {summary.current_value}")
    print(f"  xirr: {summary.xirr}")
    if summary.cash_summary:
        print(f"  cash_summary: {json.dumps(summary.cash_summary, indent=2, default=str)}")
    if summary.warnings:
        print(f"  warnings: {summary.warnings}")

    cash_bal = cash_balances_for_scope(scope, as_of_date=today)
    print("\n=== Cash balances (as of today) ===")
    if cash_bal.kind == "single":
        for ccy, bal in cash_bal.balances:
            print(f"  {ccy}: {bal}")
    else:
        for row in cash_bal.balances:
            print(f"  portfolio {row.portfolio_id} ({row.portfolio_name}) {row.currency}: {row.balance}")

    xirr_detail = compute_scope_xirr_detail(scope, display_currency=disp)
    print("\n=== XIRR (full scope) ===")
    print(f"  value: {xirr_detail.value}")
    if xirr_detail.warnings:
        print(f"  warnings: {xirr_detail.warnings}")

    for metric in ("value", "cumulative_return", "twror"):
        result = build_portfolio_performance(
            scope=scope,
            metric=metric,
            range_code="ALL",
            display_currency=disp,
            today=today,
        )
        last_date, last_val = _last_valid(result.points)
        print(f"\n=== Performance metric={metric} (ALL) ===")
        print(f"  latest: date={last_date} value={last_val}")
        if result.warnings:
            print(f"  warnings: {result.warnings}")

    if scope.kind == "single" and portfolios:
        pid = portfolios[0].id
        p = portfolios[0]
        if p.cash_aware_enabled:
            twror_flows, _ = build_cash_aware_twror_external_flows(
                pid, calculation_currency=disp
            )
            xirr_flows, _ = build_cash_aware_xirr_external_flows(
                pid, calculation_currency=disp
            )
            _print_flows("TWROR external flows (cash ledger)", twror_flows)
            _print_flows("XIRR external flows (cash ledger)", xirr_flows)
        else:
            txns = list(fifo_eligible_queryset([pid]))
            base = p.base_currency
            legacy, _ = build_legacy_transaction_external_flows(txns, base)
            _print_flows(f"Legacy external flows ({base})", legacy)
    else:
        flows, unknown = build_all_scope_external_flows(scope, disp)
        _print_flows("All-scope external flows (TWROR convention)", flows)
        if unknown:
            print(f"  flows_unknown_from: {unknown}")

    print("\n(read-only diagnostic complete)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", help="Django username (default: first user)")
    parser.add_argument("--portfolio-id", type=int, help="Single portfolio id")
    parser.add_argument(
        "--portfolio-scope",
        choices=["all"],
        help="Use all active portfolios (mutually exclusive with --portfolio-id)",
    )
    parser.add_argument("--display-currency", default="EUR")
    args = parser.parse_args()

    if args.portfolio_id is not None and args.portfolio_scope:
        parser.error("Provide --portfolio-id or --portfolio-scope=all, not both")

    user = _resolve_user(args.username)
    diagnose(
        user=user,
        portfolio_id=args.portfolio_id,
        portfolio_scope=args.portfolio_scope or ("all" if args.portfolio_id is None else None),
        display_currency=args.display_currency,
    )


if __name__ == "__main__":
    main()
