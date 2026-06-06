#!/usr/bin/env python3
"""
Read-only settlement / cash ledger link integrity diagnostic (STAB-4).

Checks cash-aware BUY/SELL settlement rows, orphans, duplicates, and amount/date mismatches.
No database writes.

Usage:
  .venv/bin/python scripts/diagnose_settlement_integrity.py
  .venv/bin/python scripts/diagnose_settlement_integrity.py --username demo --portfolio-id 1
  .venv/bin/python scripts/diagnose_settlement_integrity.py --as-json

Exit code: 0 when no issues; 1 when any issue is found (suitable for optional CI gates).
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
from diagnostics.settlement_integrity import (
    build_settlement_report,
    check_settlement_integrity,
    format_settlement_report,
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
    parser.add_argument("--as-json", action="store_true", help="Emit JSON report")
    args = parser.parse_args()

    user = resolve_user(args.username)
    scope, portfolios = portfolios_for_scope(
        user,
        portfolio_id=args.portfolio_id,
        portfolio_scope=args.portfolio_scope or ("all" if args.portfolio_id is None else None),
    )
    issues = check_settlement_integrity(portfolios)
    report = build_settlement_report(portfolios, issues)

    if args.as_json:
        emit_json(report)
    else:
        print("=== Settlement integrity (read-only) ===")
        print_scope_header(scope)
        format_settlement_report(issues)
        print("\n(read-only diagnostic complete)")

    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
