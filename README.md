# Portfolio Insight — KPulla6

Portfolio Insight is a local-first personal portfolio tracker built with Django REST Framework, PostgreSQL, and a React/Vite frontend. It is designed to track investments across stocks, mutual funds, broker cash, fixed deposits, and bank cash while keeping return calculations and accounting rules explicit and testable.

The app is API-driven: the backend owns portfolio math, ledger rules, valuation, and analytics; the frontend focuses on workflows, display, and user interaction.

## What This Repo Includes

- **Portfolio dashboard:** current value, invested amount, realized/unrealized P/L, XIRR, allocation buckets, value history, cumulative return, and TWROR charts.
- **Multi-portfolio support:** a virtual All Portfolios view plus real portfolio scoping for transactions, holdings, summary, performance, and analytics.
- **Stock transactions:** BUY, SELL, stock split handling, CSV import, FIFO holdings, cached price valuation, and cash-aware settlements.
- **Indian mutual funds:** scheme/folio transactions, NAV cache, NAV validation, holdings, summary/performance integration, classification, CSV import, and AMFI/MFAPI sync support.
- **Broker cash ledger:** deposits, withdrawals, bulk cash entries, cash-aware BUY/SELL enforcement, same/cross-currency transfers, cash holdings, XIRR, TWROR, and performance integration.
- **Fixed deposits:** bank accounts, FD CRUD, mandatory FD opening debit, interest payments with gross/TDS/net, maturity settlement, direct renewal with partial payout, principal-only valuation, and debt allocation.
- **Bank cash accounting:** immutable bank cash movements, opening-balance seeding, ledger-derived balance, optional bank cash inclusion in portfolio value, holdings, value history, XIRR, TWROR, and Metric Sheet alignment.
- **Metric Sheet analytics:** portfolio, asset, and comparison metrics including returns, drawdowns, risk metrics, monthly returns, benchmark-relative metrics, and warnings for incomplete data.
- **Market data cache:** stock prices, benchmarks, FX rates, and mutual fund NAVs are stored in PostgreSQL and refreshed manually.
- **Local-first safety:** explicit database backup/safety commands, SQLite test mode, no destructive reset workflow for real dev data.

## Architecture At A Glance

- **Backend:** Django 5, Django REST Framework, django-allauth session auth, PostgreSQL, pytest.
- **Frontend:** React 19, Vite, Vitest, reusable UI components, dashboard/asset/transaction/settings workflows.
- **Finance layer:** pure Python helpers under `backend/finance/` for calculations that should stay framework-independent.
- **Domain apps:** `transactions`, `cash`, `debt`, `portfolios`, `analytics`, `market_data`, `fx`, and auth/settings APIs.
- **Docs:** MkDocs Material portal (Diátaxis navigation). Run `make dev`, open http://127.0.0.1:8002 — or http://docs.kpulla6.com:8002 after adding local `/etc/hosts`. Source files live in `docs/`.

## Key Screens

- **Dashboard:** headline metrics, allocation, performance chart, benchmark overlays, Metric Sheet preview.
- **Assets:** holdings table, allocation, bank cash rows, stock/MF/FD detail support.
- **Transactions:** stock/MF/cash transaction workflows, CSV import, filters, pagination, cash-aware shortfall guidance.
- **Cash:** broker cash balances, ledger, deposits/withdrawals, bulk entries, transfers.
- **Fixed Deposits:** FD lifecycle workflows: create, interest payment, mark matured, settle/close, renew.
- **Settings:** portfolio management, display currency, bank account management, bank ledger movements, bank cash inclusion toggle.

## Quick Start

```bash
cp .env.example .env
make bootstrap   # db + migrate + seed
make dev         # Postgres + Django :8000 + Vite :5173 + Docs :8002
make stop-dev    # stop Django + Vite + docs (keeps Postgres running)
make stop-all    # stop Django + Vite + Postgres container (preserves DB volume)
make ports       # show processes on dev ports
```

Do not use `docker compose down -v` unless you intend to delete local database data.

- API health check: http://127.0.0.1:8000/api/v1/health
- App: http://127.0.0.1:5173
- Docs: http://127.0.0.1:8002 (or http://docs.kpulla6.com:8002 with `/etc/hosts` — see `docs/how-to/local-docs-domain.md`)

### iPad / Home LAN

On the Mac: `make dev`, then `ipconfig getifaddr en0` for your LAN IP.

On iPad or another device on the same Wi-Fi: open `http://<mac-lan-ip>:5173`. Do not use `:8000` directly from the device.

Keep `VITE_API_BASE_URL` empty in `.env` so API calls use the Vite proxy. See `docs/workflows.md` for details.

## Tests

```bash
make test          # backend pytest + frontend vitest
make test-backend
make test-frontend
cd frontend && npm run build
```

Backend tests use SQLite with `DJANGO_TEST_USE_SQLITE=1` in the project test workflow.

## Documentation

Browse project documentation with MkDocs Material:

1. Run `make dev` (or `make docs-serve` for docs only)
2. Open http://127.0.0.1:8002
3. Or, after adding `127.0.0.1 docs.kpulla6.com` to `/etc/hosts`, open http://docs.kpulla6.com:8002

**Update policy:** every change must decide if docs need updates. See [Documentation update policy](docs/maintenance/documentation-update-policy.md). After doc edits: `make docs-build` and `make docs-check`.

```bash
make docs-build    # static output in site/
make docs-check    # strict build + link/API/stale-phrase checks
```

Source files remain in `docs/`; `mkdocs.yml` at the repo root defines navigation. Install deps via `make setup-docs` (uses backend venv + `requirements-docs.txt`). Local domain details: `docs/how-to/local-docs-domain.md`.

## Market Data Sync

Stock prices, benchmark indices, FX rates, and mutual fund NAVs are cached in PostgreSQL. Sync is manual; there is no background scheduler.

```bash
make refresh                 # stocks + benchmarks + FX + mutual fund NAVs
make sync-market-data        # same combined sync (no completion banner)
make sync-prices             # stocks only
make sync-benchmarks
make sync-fx
make sync-mutual-fund-navs   # mutual fund NAVs only
```

You can also trigger sync through the API with `POST /api/v1/prices/refresh`, `POST /api/v1/nav/refresh`, or `POST /api/v1/portfolio/force-sync`.

## Data Safety

This project treats the local PostgreSQL database as production-like personal data.

```bash
make backup-db
make db-safety-check
```

Avoid destructive commands such as `docker compose down -v`, database flushes, truncation, or bulk deletes unless you intentionally want to remove local data and have a backup.

## Frontend API Base URL

Set `VITE_API_BASE_URL` in `.env` only when needed. Empty uses the Vite proxy to Django (`/api` to `:8000`). For iPad/LAN access, leave it empty and use `http://<mac-lan-ip>:5173`.
