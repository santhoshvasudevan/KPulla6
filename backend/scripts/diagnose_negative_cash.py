#!/usr/bin/env python3
"""
Read-only negative cash balance diagnostic (STAB-4).

Finds portfolios/currencies where chronological running ledger balance drops below zero.
No database writes.

Usage:
  .venv/bin/python scripts/diagnose_negative_cash.py
  .venv/bin/python scripts/diagnose_negative_cash.py --portfolio-id 1 --currency EUR
  .venv/bin/python scripts/diagnose_negative_cash.py --as-json

Exit code: 0 when no negative balances; 1 when any case is found.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from diagnostics.common import emit_json, print_scope_header, resolve_user
from diagnostics.common import portfolios_for_scope
from diagnostics.negative_cash import (
    build_negative_cash_report,
    check_negative_cash,
    format_negative_cash_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", help="Django username (default: first user)")
    parser.add_argument("--portfolio-id", type=int, help="Limit to one portfolio")
    parser.add_argument(
        "--portfolio-scope",
        choices=["all"],
        help="All active portfolios (default when --portfolio-id omitted)",
    )
    parser.add_argument("--currency", help="Filter to one ledger currency (e.g. EUR)")
    parser.add_argument("--as-json", action="store_true", help="Emit JSON report")
    args = parser.parse_args()

    user = resolve_user(args.username)
    scope, portfolios = portfolios_for_scope(
        user,
        portfolio_id=args.portfolio_id,
        portfolio_scope=args.portfolio_scope or ("all" if args.portfolio_id is None else None),
    )
    issues = check_negative_cash(portfolios, currency_filter=args.currency)
    report = build_negative_cash_report(issues)

    if args.as_json:
        emit_json(report)
    else:
        print("=== Negative cash (read-only) ===")
        print_scope_header(scope)
        format_negative_cash_report(issues)
        print("\n(read-only diagnostic complete)")

    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
