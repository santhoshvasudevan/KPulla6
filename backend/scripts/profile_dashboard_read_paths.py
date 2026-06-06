#!/usr/bin/env python3
"""
Read-only Dashboard backend read-path profiler (STAB-5A).

Measures service-layer equivalents of Dashboard API endpoints: elapsed time, SQL query
count, result size, and high-level notes. No database writes.

Usage:
  cd backend
  .venv/bin/python scripts/profile_dashboard_read_paths.py
  .venv/bin/python scripts/profile_dashboard_read_paths.py --username demo --display-currency EUR
  .venv/bin/python scripts/profile_dashboard_read_paths.py --json-out tmp/dashboard_read_baseline.json

For SQLite scratch data:
  DJANGO_TEST_USE_SQLITE=1 .venv/bin/python scripts/profile_dashboard_read_paths.py

See docs/performance/dashboard-read-paths.md for interpretation and STAB-5B options.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from diagnostics.common import resolve_user
from diagnostics.dashboard_read_profile import (
    format_profile_table,
    profile_dashboard_read_paths,
    profiles_to_baseline_payload,
)
from portfolios.scope import resolve_portfolio_scope


def _print_detail(profiles) -> None:
    print("\n=== Endpoint details ===")
    for p in profiles:
        print(f"\n--- {p.id} ---")
        print(f"  {p.http_method} {p.path}")
        print(f"  elapsed_ms={p.elapsed_ms} sql_queries={p.sql_query_count} "
              f"points={p.result_point_count} warnings={p.warnings_count}")
        n = p.notes
        print(
            f"  notes: cash_series={n.cash_inclusive_value_series} "
            f"external_flows={n.uses_external_flows} benchmark={n.uses_benchmark} "
            f"all_scope={n.all_scope} range_slicing={n.range_slicing}"
        )
        repeated = p.top_query_patterns[0]["repeated_sql"] if p.top_query_patterns else []
        if repeated:
            print("  top repeated SQL:")
            for row in repeated[:5]:
                print(f"    x{row['count']:3d}  {row['sql_prefix']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", help="Django username (default: first user)")
    parser.add_argument("--portfolio-id", type=int, help="Single portfolio id")
    parser.add_argument(
        "--portfolio-scope",
        choices=["all"],
        help="All active portfolios (default when --portfolio-id omitted)",
    )
    parser.add_argument("--display-currency", default="EUR")
    parser.add_argument(
        "--json-out",
        help="Write baseline JSON (e.g. tmp/dashboard_read_baseline.json)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print per-endpoint SQL pattern details",
    )
    args = parser.parse_args()

    if args.portfolio_id is not None and args.portfolio_scope:
        parser.error("Provide --portfolio-id or --portfolio-scope=all, not both")

    user = resolve_user(args.username)
    scope = resolve_portfolio_scope(
        user,
        portfolio_scope=args.portfolio_scope or ("all" if args.portfolio_id is None else None),
        portfolio_id=args.portfolio_id,
    )
    disp = args.display_currency.upper()

    print("Dashboard read-path profiling (STAB-5A, read-only)")
    print(f"  user={user.username!r} scope={scope.kind} portfolio_ids={scope.portfolio_ids}")
    print(f"  display_currency={disp}")

    profiles = profile_dashboard_read_paths(
        scope=scope,
        display_currency=disp,
        user=user,
    )

    print("\n" + format_profile_table(profiles))

    if args.verbose:
        _print_detail(profiles)

    payload = profiles_to_baseline_payload(
        profiles,
        username=user.username,
        scope=scope,
        display_currency=disp,
        captured_at=datetime.now(timezone.utc).isoformat(),
    )

    if args.json_out:
        out_path = Path(args.json_out)
        if not out_path.is_absolute():
            out_path = BACKEND / out_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"\nWrote baseline JSON: {out_path}")

    print("\n(read-only profiling complete)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
