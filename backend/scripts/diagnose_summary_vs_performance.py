#!/usr/bin/env python3
"""
Read-only summary vs performance value diagnostic (STAB-4).

Compares portfolio summary ``current_value`` with the latest performance ``metric=value`` point.
Both paths include cash when applicable. No database writes.

Usage:
  .venv/bin/python scripts/diagnose_summary_vs_performance.py
  .venv/bin/python scripts/diagnose_summary_vs_performance.py --portfolio-id 1 --display-currency EUR
  .venv/bin/python scripts/diagnose_summary_vs_performance.py --tolerance 0.05

Exit code: 0 when values match within tolerance; 1 on mismatch or missing performance value.
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
from diagnostics.summary_vs_performance import (
    build_summary_performance_report,
    check_summary_vs_performance,
    format_summary_performance_report,
    mismatch_detected,
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
    parser.add_argument("--display-currency", help="Display currency (default: user settings)")
    parser.add_argument(
        "--tolerance",
        type=float,
        default=0.01,
        help="Absolute difference allowed (default: 0.01)",
    )
    parser.add_argument("--as-json", action="store_true", help="Emit JSON report")
    args = parser.parse_args()

    user = resolve_user(args.username)
    scope = resolve_diagnostic_scope(
        user,
        portfolio_id=args.portfolio_id,
        portfolio_scope=args.portfolio_scope or ("all" if args.portfolio_id is None else None),
    )
    result = check_summary_vs_performance(
        user=user,
        scope=scope,
        display_currency=args.display_currency,
        tolerance=args.tolerance,
    )
    report = build_summary_performance_report(result)

    if args.as_json:
        emit_json(report)
    else:
        print("=== Summary vs performance value (read-only) ===")
        print_scope_header(scope)
        format_summary_performance_report(result)
        print("\n(read-only diagnostic complete)")

    return 1 if mismatch_detected(result) else 0


if __name__ == "__main__":
    raise SystemExit(main())
