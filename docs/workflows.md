# Development Workflow — KPulla6

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

Before cash-aware **backfill**, bulk enable, migration-heavy ledger schema work, or any script that mutates `cash_ledger_entries` / linked settlements on the live dev database:

1. Run `make backup-db` and `make db-safety-check` (record counts).
2. Obtain **explicit user approval** for bulk or destructive steps.

**Policy:**

- Do **not** bulk-flip existing portfolios to `cash_aware_enabled=true` without per-portfolio user confirmation (Settings enable or backfill wizard).
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
| `make test` | Backend pytest (SQLite, no Docker) |
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

## KPulla6-specific rules
- Do not modify `../KPulla5/`
- Use Django migrations for all schema changes
- Port finance logic into `backend/finance/` without Django imports
- Frontend remains API-driven only
