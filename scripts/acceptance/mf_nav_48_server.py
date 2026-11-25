#!/usr/bin/env python3
"""
Synthetic SQLite acceptance server for cache-first provisional MF NAV (#48 / #54).

Never touches Postgres or real portfolios:
  - refuses to start when DATABASE_URL is set and forces a new SQLite *file* database
    inside --run-dir (created fresh; an existing database file is never reused);
  - seeds synthetic users, portfolios, NAV cache and FX only;
  - replaces the MF NAV provider with a stub driven by <run-dir>/provider_book.json and
    logs every provider call to <run-dir>/provider_calls.jsonl;
  - blocks every non-loopback socket connection (logged to <run-dir>/blocked_network.jsonl).

Usage (repo root; backend venv):
  backend/.venv/bin/python scripts/acceptance/mf_nav_48_server.py serve \
      --run-dir /tmp/kp-mfnav-48 --port 18000 --frontend-origin http://127.0.0.1:15173
  backend/.venv/bin/python scripts/acceptance/mf_nav_48_server.py manage \
      --run-dir /tmp/kp-mfnav-48 -- preview_mf_nav_corrections --user-id 1
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import os
import socket
import subprocess
import sys
import threading
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
DB_NAME = "acceptance.sqlite3"
ACCEPTANCE_PASSWORD = "acceptance-only-48"
SCHEMES = {
    "990101": "Acceptance Alpha Fund - Direct Growth",
    "990202": "Acceptance Beta Fund - Direct Growth",
    "990303": "Acceptance Gamma Fund - Direct Growth",
}
_log_lock = threading.Lock()


def _append_jsonl(path: Path, record: dict) -> None:
    record = {"at": datetime.now(timezone.utc).isoformat(), **record}
    with _log_lock, path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, default=str) + "\n")


def _weekdays(start: date, end: date):
    day = start
    while day <= end:
        if day.weekday() < 5:
            yield day
        day += timedelta(days=1)


def initial_provider_book() -> dict:
    """Synthetic upstream: Alpha publishes 2026-11-19, Beta has no NAV, Gamma times out."""
    alpha = {d.isoformat(): f"{Decimal('18') + Decimal(i) / 10:.4f}"
             for i, d in enumerate(_weekdays(date(2026, 11, 2), date(2026, 11, 16)))}
    alpha.update({"2026-11-17": "20.0000", "2026-11-19": "21.5000"})
    return {
        "990101": {"mode": "rows", "rows": alpha},
        "990202": {"mode": "rows", "rows": {}},
        "990303": {"mode": "timeout", "rows": {}},
    }


def install_guards(run_dir: Path) -> None:
    blocked_log = run_dir / "blocked_network.jsonl"

    def is_loopback(host) -> bool:
        if host in ("localhost", ""):
            return True
        try:
            return ipaddress.ip_address(str(host).split("%")[0]).is_loopback
        except ValueError:
            return False

    original_connect = socket.socket.connect
    original_getaddrinfo = socket.getaddrinfo

    def guarded_connect(self, address):
        if self.family in (socket.AF_INET, socket.AF_INET6) and not is_loopback(address[0]):
            _append_jsonl(blocked_log, {"blocked": "connect", "address": address})
            raise ConnectionRefusedError(f"acceptance harness blocks network to {address!r}")
        return original_connect(self, address)

    def guarded_getaddrinfo(host, *args, **kwargs):
        if host is not None and not is_loopback(host if isinstance(host, str) else host.decode()):
            _append_jsonl(blocked_log, {"blocked": "getaddrinfo", "host": host})
            raise socket.gaierror(f"acceptance harness blocks DNS for {host!r}")
        return original_getaddrinfo(host, *args, **kwargs)

    socket.socket.connect = guarded_connect
    socket.getaddrinfo = guarded_getaddrinfo


def install_provider_stub(run_dir: Path) -> None:
    from market_data.providers import mutual_fund_nav_provider as provider_module
    from market_data.providers.mutual_fund_nav_provider import (
        AmfiNavFetchError,
        AmfiNavTimeoutError,
        NavPoint,
    )
    from market_data.services import missing_nav_fetch, mutual_fund_nav_sync

    book_path = run_dir / "provider_book.json"
    calls_log = run_dir / "provider_calls.jsonl"

    class BookNavProvider:
        """MFAPI stand-in; reads the synthetic book on every call so phases can change it."""

        def _entry(self, scheme_code: str) -> dict:
            book = json.loads(book_path.read_text(encoding="utf-8"))
            entry = book.get(str(scheme_code))
            if entry is None:
                raise AmfiNavFetchError(f"unknown synthetic scheme {scheme_code}")
            if entry.get("mode") == "timeout":
                raise AmfiNavTimeoutError(f"synthetic timeout for {scheme_code}")
            if entry.get("mode") == "failure":
                raise AmfiNavFetchError(f"synthetic failure for {scheme_code}")
            return entry

        def get_nav_history(self, scheme_code: str, start: date, end: date):
            _append_jsonl(calls_log, {"method": "get_nav_history", "scheme_code": scheme_code,
                                      "start": start, "end": end})
            rows = self._entry(scheme_code).get("rows", {})
            return [NavPoint(date=date.fromisoformat(d), nav=Decimal(v), currency="INR")
                    for d, v in sorted(rows.items()) if start <= date.fromisoformat(d) <= end]

        def get_latest_nav(self, scheme_code: str):
            _append_jsonl(calls_log, {"method": "get_latest_nav", "scheme_code": scheme_code})
            rows = self._entry(scheme_code).get("rows", {})
            if not rows:
                return None
            day = max(rows)
            return NavPoint(date=date.fromisoformat(day), nav=Decimal(rows[day]), currency="INR")

    factory = BookNavProvider
    provider_module.default_mutual_fund_nav_provider = factory
    missing_nav_fetch.default_mutual_fund_nav_provider = factory
    mutual_fund_nav_sync.default_mutual_fund_nav_provider = factory


def configure_django(run_dir: Path, *, frontend_origin: str | None, fresh: bool) -> Path:
    if os.environ.get("DATABASE_URL"):
        sys.exit("Refusing to run: DATABASE_URL is set. Acceptance uses a disposable SQLite file only.")
    db_path = (run_dir / DB_NAME).resolve()
    if fresh and db_path.exists():
        sys.exit(f"Refusing to reuse existing database {db_path}; pass a new --run-dir.")
    if not fresh and not db_path.exists():
        sys.exit(f"No acceptance database at {db_path}; run 'serve' first.")
    os.environ.pop("DJANGO_TEST_USE_SQLITE", None)
    os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
    if frontend_origin:
        os.environ["FRONTEND_URL"] = frontend_origin
        localhost_origin = frontend_origin.replace("127.0.0.1", "localhost")
        os.environ["CSRF_TRUSTED_ORIGINS"] = f"{frontend_origin},{localhost_origin}"
    sys.path.insert(0, str(BACKEND_DIR))
    os.chdir(BACKEND_DIR)

    import config.settings as project_settings

    project_settings.DATABASES = {
        "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": str(db_path)}
    }
    import django

    django.setup()
    from django.db import connection

    import portfolios.dates as portfolio_dates

    portfolio_dates.current_date = lambda: date(2026, 11, 25)

    if connection.vendor != "sqlite" or Path(connection.settings_dict["NAME"]) != db_path:
        sys.exit(f"Refusing to run: unexpected database {connection.vendor} "
                 f"{connection.settings_dict['NAME']}")
    return db_path


def seed() -> dict:
    from django.contrib.auth import get_user_model

    from cash.models import CashEntryType, CashLedgerEntry
    from fx.services import upsert_fx_rate
    from market_data.models import Asset, AssetType, HistoricalPrice
    from market_data.seed import ensure_benchmark_indices
    from portfolios.models import Portfolio
    from settings_app.seed import ensure_app_settings

    User = get_user_model()
    user = User.objects.create_user("mfnav_acceptance", "mfnav-acceptance@example.invalid",
                                    ACCEPTANCE_PASSWORD)
    other = User.objects.create_user("mfnav_other", "mfnav-other@example.invalid",
                                     ACCEPTANCE_PASSWORD)
    for account in (user, other):
        settings = ensure_app_settings(account)
        settings.display_currency = "INR"
        settings.save()
    ensure_benchmark_indices()

    inr = Portfolio.objects.create(user=user, name="Acceptance INR", base_currency="INR",
                                   is_default=True, is_active=True, cash_aware_enabled=True)
    usd = Portfolio.objects.create(user=user, name="Acceptance USD", base_currency="USD",
                                   is_default=False, is_active=True, cash_aware_enabled=False)
    eur = Portfolio.objects.create(user=user, name="Acceptance EUR", base_currency="EUR",
                                   is_default=False, is_active=True, cash_aware_enabled=False)
    other_portfolio = Portfolio.objects.create(user=other, name="Other user INR",
                                               base_currency="INR", is_default=True,
                                               is_active=True, cash_aware_enabled=False)
    CashLedgerEntry.objects.create(portfolio=inr, date=date(2026, 11, 1), currency="INR",
                                   entry_type=CashEntryType.CASH_DEPOSIT, amount=Decimal("200000"))

    for code, name in SCHEMES.items():
        Asset.objects.get_or_create(asset_type=AssetType.MUTUAL_FUND, symbol=code,
                                    defaults={"display_name": name, "currency": "INR"})
    Asset.objects.get_or_create(asset_type=AssetType.STOCK, symbol="ACC_STK",
                                defaults={"display_name": "Acceptance EUR Stock", "currency": "EUR"})
    for stock_day in (date(2026, 11, 5), date(2026, 11, 25)):
        HistoricalPrice.objects.create(asset_symbol="ACC_STK", asset_type=AssetType.STOCK,
                                       date=stock_day, close_price=Decimal("110"),
                                       currency="EUR", source="acceptance")
    book = initial_provider_book()
    # Provider cache before acceptance: Alpha up to 2026-11-17 (not 11-19), Gamma to 11-10.
    cache = {"990101": {d: v for d, v in book["990101"]["rows"].items() if d <= "2026-11-17"},
             "990303": {d.isoformat(): f"{Decimal('29') + Decimal(i) / 5:.4f}"
                        for i, d in enumerate(_weekdays(date(2026, 11, 2), date(2026, 11, 10)))}}
    cache["990303"]["2026-11-10"] = "30.0000"
    for code, rows in cache.items():
        for day, nav in rows.items():
            HistoricalPrice.objects.create(asset_symbol=code, asset_type=AssetType.MUTUAL_FUND,
                                           date=date.fromisoformat(day), close_price=Decimal(nav),
                                           currency="INR", source="acceptance")
    day = date(2026, 10, 25)
    while day <= date(2026, 11, 30):
        upsert_fx_rate(from_currency="INR", to_currency="USD", row_date=day,
                       rate=Decimal("0.0119"), source="acceptance")
        upsert_fx_rate(from_currency="USD", to_currency="INR", row_date=day,
                       rate=Decimal("84.0336"), source="acceptance")
        day += timedelta(days=1)
    return {
        "users": {"acceptance": {"id": user.id, "username": user.username},
                  "other": {"id": other.id, "username": other.username}},
        "password": ACCEPTANCE_PASSWORD,
        "portfolios": {"inr": inr.id, "usd": usd.id, "eur": eur.id, "other": other_portfolio.id},
        "schemes": SCHEMES,
    }


def checkout_evidence() -> dict:
    def git(*args):
        return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()

    return {"repo_root": str(REPO_ROOT), "head": git("rev-parse", "HEAD"),
            "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
            "status_porcelain": git("status", "--porcelain", "--untracked-files=no")}


def cmd_serve(args) -> None:
    run_dir = Path(args.run_dir).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    install_guards(run_dir)
    db_path = configure_django(run_dir, frontend_origin=args.frontend_origin, fresh=True)
    from django.core.management import call_command
    from django.db import connection
    from django.db.migrations.recorder import MigrationRecorder

    call_command("migrate", interactive=False, verbosity=0)
    applied = {f"{app}.{name}" for app, name in MigrationRecorder(connection).applied_migrations()}
    (run_dir / "provider_book.json").write_text(json.dumps(initial_provider_book(), indent=2))
    fixtures = seed()
    install_provider_stub(run_dir)
    server = {
        "pid": os.getpid(), "cwd": os.getcwd(), "python": sys.executable,
        "database": {"vendor": connection.vendor, "name": str(db_path)},
        "port": args.port, "started_at": datetime.now(timezone.utc).isoformat(),
        "checkout": checkout_evidence(),
        "required_migrations_applied": {
            m: m in applied for m in ("market_data.0007_mutualfundnavfetchstate",
                                      "transactions.0006_mutualfundtransactiondetail_nav_provenance")},
        "fixtures": fixtures,
    }
    (run_dir / "server.json").write_text(json.dumps(server, indent=2))
    print(json.dumps(server, indent=2), flush=True)
    call_command("runserver", f"127.0.0.1:{args.port}", use_reloader=False, use_threading=True)


def cmd_manage(args) -> None:
    run_dir = Path(args.run_dir).resolve()
    install_guards(run_dir)
    configure_django(run_dir, frontend_origin=None, fresh=False)
    install_provider_stub(run_dir)
    from django.core.management import execute_from_command_line

    execute_from_command_line(["manage.py", *args.command])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = parser.add_subparsers(dest="action", required=True)
    serve = sub.add_parser("serve")
    serve.add_argument("--run-dir", required=True)
    serve.add_argument("--port", type=int, default=18000)
    serve.add_argument("--frontend-origin", default="http://127.0.0.1:15173")
    manage = sub.add_parser("manage")
    manage.add_argument("--run-dir", required=True)
    manage.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.action == "manage" and args.command[:1] == ["--"]:
        args.command = args.command[1:]
    (cmd_serve if args.action == "serve" else cmd_manage)(args)


if __name__ == "__main__":
    main()
