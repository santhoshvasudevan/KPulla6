#!/usr/bin/env python3
"""
Read-only mutual fund NAV coverage diagnostic (STAB-4).

Finds held MF schemes with missing or stale cached NAV rows. Uses DB cache only.
No database writes.

Usage:
  .venv/bin/python scripts/diagnose_nav_coverage.py
  .venv/bin/python scripts/diagnose_nav_coverage.py --portfolio-id 1 --stale-days 7
  .venv/bin/python scripts/diagnose_nav_coverage.py --as-json

Exit code: 0 when no issues; 1 when any issue is found.
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
from diagnostics.common import resolve_diagnostic_scope
from diagnostics.nav_coverage import (
    build_nav_coverage_report,
    check_nav_coverage,
    format_nav_coverage_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", help="Django username (default: first user)")
    parser.add_argument("--portfolio-id", type=int, help="Single portfolio id")
    parser.add_argument(
        "--portfolio-scope",
        choices=["all"],
        help="All active portfolios (default when --portfolio-id omitted)",
    )
    parser.add_argument(
        "--stale-days",
        type=int,
        default=5,
        help="Flag NAV older than this many days (default: 5)",
    )
    parser.add_argument("--as-json", action="store_true", help="Emit JSON report")
    args = parser.parse_args()

    user = resolve_user(args.username)
    scope = resolve_diagnostic_scope(
        user,
        portfolio_id=args.portfolio_id,
        portfolio_scope=args.portfolio_scope or ("all" if args.portfolio_id is None else None),
    )
    issues = check_nav_coverage(
        scope.portfolio_ids,
        stale_days=args.stale_days,
    )
    report = build_nav_coverage_report(issues, stale_days=args.stale_days)
    report["portfolio_ids"] = scope.portfolio_ids

    if args.as_json:
        emit_json(report)
    else:
        print("=== MF NAV coverage (read-only) ===")
        print_scope_header(scope)
        format_nav_coverage_report(issues)
        print("\n(read-only diagnostic complete)")

    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
