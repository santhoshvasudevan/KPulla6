#!/usr/bin/env python3
"""
Read-only FX coverage diagnostic (STAB-4).

Finds missing cached FX pairs needed to convert ledger/transaction currencies into the
requested display currency. Uses DB cache only — no external provider calls.
No database writes.

Usage:
  .venv/bin/python scripts/diagnose_fx_coverage.py
  .venv/bin/python scripts/diagnose_fx_coverage.py --display-currency EUR --portfolio-id 1
  .venv/bin/python scripts/diagnose_fx_coverage.py --as-json

Exit code: 0 when no gaps; 1 when any gap is found.
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
from diagnostics.fx_coverage import (
    build_fx_coverage_report,
    check_fx_coverage,
    format_fx_coverage_report,
)
from settings_app.services import get_settings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", help="Django username (default: first user)")
    parser.add_argument("--portfolio-id", type=int, help="Single portfolio id")
    parser.add_argument(
        "--portfolio-scope",
        choices=["all"],
        help="All active portfolios (default when --portfolio-id omitted)",
    )
    parser.add_argument("--display-currency", help="Target display currency (default: user settings)")
    parser.add_argument("--as-json", action="store_true", help="Emit JSON report")
    args = parser.parse_args()

    user = resolve_user(args.username)
    scope = resolve_diagnostic_scope(
        user,
        portfolio_id=args.portfolio_id,
        portfolio_scope=args.portfolio_scope or ("all" if args.portfolio_id is None else None),
    )
    disp = (args.display_currency or get_settings(user).display_currency or "EUR").upper()
    gaps = check_fx_coverage(
        user=user,
        scope=scope,
        display_currency=args.display_currency,
    )
    report = build_fx_coverage_report(gaps)
    report["display_currency"] = disp
    report["portfolio_ids"] = scope.portfolio_ids

    if args.as_json:
        emit_json(report)
    else:
        print("=== FX coverage (read-only) ===")
        print_scope_header(scope)
        format_fx_coverage_report(gaps, display_currency=disp)
        print("\n(read-only diagnostic complete)")

    return 1 if gaps else 0


if __name__ == "__main__":
    raise SystemExit(main())
