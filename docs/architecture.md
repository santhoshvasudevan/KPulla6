# Architecture — KPulla6 (Portfolio Insight)

## Overview
Local-first portfolio tracker. **KPulla6** uses Django + DRF + PostgreSQL + React, preserving KPulla5 domain rules and `/api/v1` contracts where practical.

## Backend
- **Framework:** Django 5 + Django REST Framework
- **Domain apps (Phase 2 models in place):**
  - `portfolios` — `Portfolio`
  - `transactions` — `Transaction` (FK to real portfolio only)
  - `market_data` — `HistoricalPrice`, `BenchmarkIndexConfig`
  - `fx` — `FXRate`
  - `settings_app` — `AppSettings`
  - `analytics` — read models / services (future)
  - `api` — HTTP routing (`/api/v1/health` today)
- **Finance logic:** `backend/finance/` — framework-independent (Phase 6)
  - `types.py`, `splits.py`, `fifo.py`, `xirr.py`, `twror.py`
  - Django adapter: `transactions/finance_adapter.py` (DTO mapping only)

## Database
- PostgreSQL 16 via Docker Compose
- Django migrations only
- Seed: `manage.py seed_initial_data` / `make seed`

## Virtual vs real portfolios
- **All Portfolios** is a virtual aggregate (API `portfolio_scope=all`); never stored in `portfolios`.
- Only real portfolios exist as rows; **Default Portfolio** is seeded with `is_default=True`.

## Finance domain (Phase 6)
- Pure Python; no Django ORM in `backend/finance/`.
- **FIFO** (`calculate_fifo_cost_basis_metrics`): cumulative qty/invested, avg cost, realized/unrealized P/L; fees ignored in FIFO (KPulla5 parity).
- **Splits** (`apply_stock_split_adjustments`): `split_to/split_from` on prior same-symbol BUY/SELL before split date.
- **Value history** (`build_split_adjusted_lot_snapshots`): daily portfolio valuation pairs cached split-adjusted prices with split-adjusted quantities; `STOCK_SPLIT` rows are not cash flows.
- **XIRR** (`calculate_xirr`): BUY negative, SELL positive, terminal holding value; uses `pyxirr`.
- **TWROR** (`compute_twror_series`): chain-linked daily series helper; not wired to HTTP yet.

## Data flow (target)
1. **Transactions** → holdings, cost basis, realized P/L (finance layer ready; APIs next).
2. **HistoricalPrice** + **FXRate** → cached valuation inputs.
3. **AppSettings.display_currency** → API display layer (future).
4. Manual sync (`POST /prices/refresh`, management commands) writes prices/FX/benchmarks; holdings and future dashboard reads DB only.

## Frontend
- React + Vite; API-driven; no finance calculations in the client.

## API
- Base: `/api/v1`
- Implemented: health, settings, portfolios CRUD, transactions CRUD, CSV import, holdings, asset detail
- Services: `portfolios/services.py`, `portfolios/holdings_service.py`, `portfolios/scope.py`, `settings_app/services.py`, `transactions/services.py`, `transactions/csv_import.py`, `market_data/price_lookup.py`
- Phase 8: `market_data/services/`, `market_data/providers/`, `fx/services/`, `fx/lookup.py`
- Phase 9: `portfolios/summary_service.py` — summary + timeseries from cached prices/FX
- `GET /api/v1/portfolio/performance` — value / cumulative return / TWROR time series; optional benchmark comparison (`portfolios/performance_service.py`, `finance/benchmarks.py`, `finance/performance_range.py`)
- **Frontend** (`frontend/src/`): API-driven pages; `portfolioContext` builds `portfolio_scope=all` or `portfolio_id` query params; charts render backend series only

## Development
- `make bootstrap` — db, migrate, seed
- `make dev` — full stack (migrate; seed manually or via bootstrap first)

## Constraints
- Do not modify KPulla5
- No runtime schema patching
- Transactions = source of truth
