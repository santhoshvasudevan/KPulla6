# Development Workflow — KPulla6

**Documentation index:** [README.md](./README.md)

## Prerequisites
- Python 3.11+
- Node.js 20+
- Docker (for PostgreSQL only)

## Quick start
```bash
cp .env.example .env
make dev
```
- Backend: http://127.0.0.1:8000
- Frontend: http://127.0.0.1:5173
- API health: http://127.0.0.1:8000/api/v1/health

## Start and stop

| Action | Command |
|--------|---------|
| Start full dev stack | `make dev` |
| Stop backend + frontend only | `make stop-dev` |
| Stop backend, frontend, and Postgres | `make stop-all` |
| Check occupied dev ports | `make ports` |
| Clean stop + port check | `make clean-dev` |

Override ports: `BACKEND_PORT=8001 FRONTEND_PORT=5174 make dev`

Do **not** use `docker compose down -v` unless you intend to delete local database volumes. Normal stop (`make stop-all` or `make db-stop`) preserves DB data.

See **`docs/data-safety.md`** for the 2026-05-26 incident, forbidden commands, and backup/restore workflow.

## Data-sensitive phases

Before migration-heavy work, schema experiments, or any task that might touch live transaction data:

```bash
make backup-db
make db-safety-check
```

After the phase completes:

```bash
make db-safety-check
```

Compare transaction and portfolio counts to the pre-phase snapshot. If counts dropped unexpectedly, stop and restore from `backups/` (see `docs/data-safety.md`).

## Cash ledger work

Cash ledger changes can affect **transaction validity** (BUY sufficiency, settlements, future running balances) and portfolio analytics once Cash-6+ lands.

Before bulk cash ledger writes, bulk enable, migration-heavy ledger schema work, or any script that mutates `cash_ledger_entries` / linked settlements on the live dev database:

1. Run `make backup-db` and `make db-safety-check` (record counts).
2. Obtain **explicit user approval** for bulk or destructive steps.

**Policy:**

- Do **not** bulk-flip existing portfolios to `cash_aware_enabled=true` without per-portfolio user confirmation (Settings enable or Cash page status).
- Do **not** delete users, profiles, or portfolios as part of cash feature work.
- Unit tests: `make test-backend` (SQLite). Ad-hoc scripts: scratch DB or `DJANGO_TEST_USE_SQLITE=1` — not default dev Postgres unless the user asks.

Agent rules: `.cursor/rules/320-cash-ledger.mdc` · design: [cash-ledger.md](./cash-ledger.md).

## Make targets
| Target | Description |
|--------|-------------|
| `make db` | Start PostgreSQL container |
| `make db-stop` | Stop PostgreSQL |
| `make db-logs` | Follow Postgres logs |
| `make db-shell` | `psql` in container |
| `make backup-db` | `pg_dump` to `backups/kpulla6_YYYYMMDD_HHMMSS.sql` |
| `make db-safety-check` | Print DB name, row counts, last 5 transactions |
| `make migrate` | Django migrations (requires db) |
| `make backend` | Run Django dev server |
| `make frontend` | Run Vite dev server |
| `make test` | Backend pytest + frontend Vitest (SQLite, no Docker) |
| `make test-backend` | Backend pytest only (`DJANGO_TEST_USE_SQLITE=1`) |
| `make test-frontend` | Frontend Vitest only (`npm test -- --run`) |
| `make test-fast` | Finance unit + cash service pytest subset (~1 min) |
| `make test-critical` | Golden-flow backend APIs + key frontend page tests |
| `make test-all` | Full `make test` + frontend production build |
| `make graphify` | Regenerate code graph (`graphify update .`) — see § Graphify Usage |
| `make dev` | db + migrate + backend + frontend |
| `make ports` | Show processes on backend/frontend dev ports |
| `make stop-backend` | Stop process on `BACKEND_PORT` (default 8000) |
| `make stop-frontend` | Stop process on `FRONTEND_PORT` (default 5173) |
| `make stop-dev` | Stop backend and frontend only |
| `make stop-all` | Stop backend, frontend, and Postgres container |
| `make clean-dev` | `stop-all` then `ports` |

## Market data sync (manual)

Cached stock prices, benchmark indices, FX rates, and mutual fund NAVs live in PostgreSQL. Read APIs (holdings, dashboard, summary, performance) use the DB cache only — they do not call external providers. Refresh cache explicitly:

| Target | Description |
|--------|-------------|
| `make refresh` | **All valuation data:** stocks + benchmarks + FX + mutual fund NAVs (runs `sync_market_data`) |
| `make sync-market-data` | Same as `refresh` without the completion banner |
| `make sync-prices` | Stock `HistoricalPrice` rows only |
| `make sync-benchmarks` | Benchmark index prices only |
| `make sync-fx` | FX rate pairs only |
| `make sync-mutual-fund-navs` | Mutual fund NAV rows only (`asset_type=MUTUAL_FUND`) |

HTTP equivalents: `POST /api/v1/prices/refresh` (stocks), `POST /api/v1/nav/refresh` (MF NAVs), `POST /api/v1/portfolio/force-sync` (combined, same as `sync_market_data`).

`sync_market_data` accepts `--skip-fx` and `--skip-mutual-funds` to opt out of FX or MF NAV sync. Per-scheme MF failures are logged and counted (`failed=N`); the batch continues and the command prints a warning when `failed > 0`.

### Incremental sync behavior (`make refresh`)

`make refresh` runs `python manage.py sync_market_data` → `sync_all_market_data()` in order: **stocks → benchmarks → FX → mutual fund NAVs**. Read APIs never trigger sync; they use cached DB rows only.

| Cache type | First run (no rows) | Warm cache (up to date) | Coverage gap |
|------------|---------------------|-------------------------|--------------|
| **Stocks** | Earliest stock/ETF transaction date per symbol | Latest stock price + 1 day through today; provider skipped if already current | Backfill from earliest stock transaction when cache starts later |
| **Benchmarks** | Earliest **non-MF** transaction date (portfolio anchor) | Latest index price + 1 day; skipped if current | Backfill from anchor when cached index rows start later |
| **FX** | Earliest required valuation date per pair | Latest FX row + 1 day | Backfill from required date when cache starts later |
| **MF NAVs** | Earliest MF `nav_date` / transaction date per scheme | Latest cached NAV + 1 day | Separate AMFI/MFAPI path; MF scheme codes never sent to yfinance |

**Mutual funds:** stock/yfinance sync collects symbols from stock/ETF transactions only. AMFI scheme codes sync via `sync_mutual_fund_navs` only.

**Repeat refresh:** when all caches are current for a symbol/pair/scheme, `start > today` and that provider call is skipped (no full-history re-download).

## Access from iPad / home LAN (frontend only)

Use the **full app** on another device on the same Wi‑Fi without opening Django port 8000 in the browser. Vite serves the UI on the LAN; `/api` requests are proxied to Django on the Mac.

| Step | Action |
|------|--------|
| Start stack | `make dev` on the Mac mini |
| Mac LAN IP | `ipconfig getifaddr en0` (Wi‑Fi; IP may change after DHCP) |
| iPad URL | `http://<mac-lan-ip>:5173` — not `localhost`, not `:8000` |
| `.env` | Keep `VITE_API_BASE_URL` **empty** (see `.env.example`) |
| Firewall | Allow incoming for Node (Vite) if macOS prompts |
| Network | Same Wi‑Fi; avoid guest/isolated VLAN |

Smoke check on iPad: app loads; network requests go to `http://<mac-ip>:5173/api/v1/...` only.

Dev-only; do not expose to the public internet.

## Generic feature workflow
Same discipline as KPulla5 (`../KPulla5/docs/workflows.md`):

1. Read `AGENTS.md`, `docs/current-state.md`, `docs/architecture.md`, `docs/api-design.md`
2. Define behavior, API, DB, and test impact
3. Protect existing features / contracts
4. Add tests first where practical
5. Minimal implementation; finance logic in `backend/finance/`
6. Run `make test`, frontend tests, `make dev` smoke check
7. Update docs and `docs/changelog.md`

## Graphify Usage

Graphify is an **optional navigation aid**, not source of truth. Code, tests, migrations, and docs are authoritative.

**When to regenerate**

- After **significant** changes: new Django apps, large service refactors, API flow changes, model/migration changes, frontend routing or page-structure changes, architecture shifts.
- **Do not** regenerate for: small one-file bug fixes, UI copy/style tweaks, docs-only edits, or test-only changes.

**Command**

```bash
graphify update .
# or
make graphify
```

AST-only rebuild; no LLM/API cost.

**Inspect**

- `graphify-out/GRAPH_REPORT.md` — broad architecture review
- `graphify-out/graph.json` — machine-readable graph (gitignored locally)
- `graphify-out/graph.html` — interactive view (gitignored locally)
- `graphify query "<question>"` — scoped subgraph for specific questions

**Commit policy:** `graphify-out/GRAPH_REPORT.md` is tracked; commit it after significant structural changes. Do not commit large ignored artifacts (`graph.json`, `graph.html`, `cache/`) unless project convention changes.

## TDD / test workflow

1. Read `docs/product-rules.md` and affected contract docs before coding.
2. Define test impact alongside API/DB behavior.
3. **Backend** logic, API, or calculation changes → add or update **pytest** (`backend/tests/`).
4. **Frontend** UI or `api.js` changes → add or update **Vitest**.
5. **Calculation changes** → deterministic regression tests (finance unit tests or API golden cases).
6. **Data-sensitive work** → SQLite tests only; `make backup-db` + `make db-safety-check` before live DB mutations.
7. Run relevant suites before marking work complete:
   - `make test-backend` or targeted `pytest tests/test_….py`
   - `cd frontend && npm test -- --run`
   - `cd frontend && npm run build` when UI changes affect build
8. Every Cursor implementation summary must **report tests run and pass/fail**.

### Test Makefile targets (STAB-3)

| Target | When to use |
|--------|-------------|
| `make test-fast` | Daily dev — pure `backend/finance/` + `test_cash_services.py` |
| `make test-critical` | Before major merges — cash, summary, performance, analytics, transactions, CSV cash preview + key frontend pages |
| `make test-all` | Release — full suites + `npm run build` |
| `make test` / `make test-backend` / `make test-frontend` | Full backend and/or frontend as before |

**Fixture hygiene (cash-aware default):** New portfolios default to `cash_aware_enabled=true`. Tests that only need historical BUY/MF setup (filters, holdings, splits, MF NAV) should use the `legacy_seeded` fixture. Tests that assert cash-aware enforcement or deposit-funded BUY behavior should use `seeded` plus explicit `CASH_DEPOSIT` rows in the transaction currency. See `backend/tests/conftest.py`.

Release checklist: [mvp-release-checklist.md](./mvp-release-checklist.md).

## Diagnostics

Read-only scripts for local investigation against dev Postgres or SQLite scratch data. **They never mutate data** (no saves, deletes, or external market-data calls). Run from `backend/` with the project venv.

| Script | Purpose |
|--------|---------|
| `manage.py sync_cash_settlements` | Backfill missing historical BUY/SELL settlements (dry-run default; `--apply` after backup) |
| `scripts/diagnose_cash_aware_returns.py` | Cash-aware summary, performance, XIRR, external flows, balances |
| `scripts/diagnose_settlement_integrity.py` | Cash-aware BUY/SELL settlement orphans, duplicates, amount/date mismatches |
| `scripts/diagnose_negative_cash.py` | Per-portfolio/currency chronological running balance below zero |
| `scripts/diagnose_summary_vs_performance.py` | Summary `current_value` vs latest performance `metric=value` (cash-inclusive) |
| `scripts/diagnose_fx_coverage.py` | Cached FX gaps for ledger/transaction → display currency conversion |
| `scripts/diagnose_nav_coverage.py` | Held MF scheme NAV missing/stale rows (cached DB only) |
| `scripts/profile_dashboard_read_paths.py` | Dashboard read-path timing + SQL query baseline (STAB-5A) |

See [performance/dashboard-read-paths.md](./performance/dashboard-read-paths.md) and [performance/dashboard-read-baseline.md](./performance/dashboard-read-baseline.md).

**When to use**

| Situation | Script |
|-----------|--------|
| After enabling cash-aware on an existing portfolio, or odd BUY/SELL errors | `diagnose_settlement_integrity.py`; if `missing_settlement`, run `sync_cash_settlements` (see [cash-ledger.md](./cash-ledger.md) § CASH-HIST-1) |
| Cash page shows unexpected balances or “future negative” errors | `diagnose_negative_cash.py` |
| Dashboard headline value disagrees with value chart | `diagnose_summary_vs_performance.py` |
| Holdings/summary show `fx_unavailable` or wrong display-currency totals | `diagnose_fx_coverage.py` then `make sync-fx` if gaps are confirmed |
| MF holdings show zero value or NAV warnings | `diagnose_nav_coverage.py` then `make sync-mutual-fund-navs` if gaps are confirmed |
| Return metric debugging (TWROR/XIRR/external flows) | `diagnose_cash_aware_returns.py` |
| Dashboard latency or SQL regressions (before/after optimization) | `profile_dashboard_read_paths.py` |

**Example commands** (Postgres dev DB — omit `DJANGO_TEST_USE_SQLITE`):

```bash
cd backend
.venv/bin/python scripts/diagnose_settlement_integrity.py --username demo
.venv/bin/python scripts/diagnose_negative_cash.py --portfolio-id 1 --currency EUR
.venv/bin/python scripts/diagnose_summary_vs_performance.py --portfolio-scope=all --display-currency EUR --tolerance 0.01
.venv/bin/python scripts/diagnose_fx_coverage.py --display-currency EUR --as-json
.venv/bin/python scripts/diagnose_nav_coverage.py --stale-days 5
.venv/bin/python scripts/profile_dashboard_read_paths.py --username demo --verbose \
  --json-out tmp/dashboard_read_baseline.json
```

Exit codes: integrity scripts exit `1` when issues found; profiler exits `0` (measurement only). JSON: `--as-json` on diagnostics; `--json-out` on profiler.

SQLite scratch run: prefix with `DJANGO_TEST_USE_SQLITE=1` only when intentionally using the test database.

See [data-safety.md](./data-safety.md) and [mvp-release-checklist.md](./mvp-release-checklist.md) § B2 Optional diagnostics.

## Performance profiling (STAB-5A)

Before optimizing Dashboard read paths (STAB-5B), capture a baseline on the **same** database you care about:

```bash
cd backend
.venv/bin/python scripts/profile_dashboard_read_paths.py --username YOUR_USER --verbose
```

Interpret results using [performance/dashboard-read-paths.md](./performance/dashboard-read-paths.md). Refresh [performance/dashboard-read-baseline.md](./performance/dashboard-read-baseline.md) when re-profiling on representative Postgres dev data. **STAB-5B decision:** current latency is MVP-acceptable; do not optimize until targets are exceeded (see decision record in that doc).

## Release readiness

- Before releases or major merges to `main`, follow [mvp-release-checklist.md](./mvp-release-checklist.md).
- For endpoint → frontend client → test lookup, use [api-contracts.md](./api-contracts.md) (detail remains in [api-design.md](./api-design.md)).

## KPulla6-specific rules
- Do not modify `../KPulla5/`
- Use Django migrations for all schema changes
- Port finance logic into `backend/finance/` without Django imports
- Frontend remains API-driven only
