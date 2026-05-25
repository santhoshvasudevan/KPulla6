# Changelog — KPulla6

## 2026-05-25 — Dev stack stop commands

### Added
- Makefile targets: `ports`, `stop-backend`, `stop-frontend`, `stop-dev`, `stop-all`, `clean-dev`
- Configurable `BACKEND_PORT` and `FRONTEND_PORT` for dev server start/stop

### Notes
- `stop-all` uses `docker compose stop postgres` (no volume removal)
- Documented in `docs/workflows.md` and `README.md`

## 2026-05-25 — Phase 8B: Legacy CSS alias removal

### Changed
- **Tokens:** removed legacy alias block from `frontend/src/index.css`; canonical Institutional Slate tokens only
- **Docs:** frontend design migration marked complete

### Notes
- No app behavior changes; `chartTheme.js` unchanged (Recharts hex mirrors); `DataTable` still deferred

## 2026-05-25 — Phase 7B: Frontend cleanup

### Changed
- **TransactionModal:** canonical Institutional Slate tokens, Slate overlay, modal-local form styles, error styling, `Button` for Cancel/Save
- **Shared styles:** transaction type badges (`.ui-txn-type`) in `ui.css`; used on Transactions and Asset Detail
- **Dead CSS removed:** unused globals from `index.css`; unused `.needs-review-banner` from modal CSS

### Notes
- Legacy alias block in `index.css` retained for Phase 8; `DataTable` still deferred

## 2026-05-25 — Phase 6: Transactions page polish

### Changed
- **Transactions:** `PageHeader` with record count and Add/Import actions; `LoadingState` / `ErrorState` / `EmptyState`; CSV import feedback via `WarningBanner`
- Table uses Institutional Slate styling, type badges (BUY/SELL/DIVIDEND/STOCK_SPLIT), `CurrencyValue`, and `Button` edit/delete controls

### Notes
- Transaction CRUD, CSV import API, pagination params, modal, and line-total display semantics unchanged; `DataTable` still deferred

## 2026-05-25 — Phase 5B: Assets allocation chart and closed holdings polish

### Changed
- **Assets:** allocation pie chart wrapped in `ChartCard` with Institutional Slate colors from `chartTheme.js`, Dashboard-aligned tooltip/legend, and responsive table-primary layout (~35% chart width on desktop)
- Previous holdings section uses `SectionCard` + `Button` toggle; legacy chart CSS and neon pie colors removed

### Notes
- Holdings fetch, sorting, row navigation, chart data filtering, and closed-holdings logic unchanged; `DataTable` still deferred

## 2026-05-25 — Phase 5A: Assets page structure and holdings table

### Changed
- **Assets:** `PageHeader` with portfolio/currency subtitle; `LoadingState` / `ErrorState`; FX warning via `WarningBanner`
- Holdings table uses Institutional Slate styling, `StatusBadge`, `CurrencyValue`, `PercentValue`; avg cost from `avg_cost_per_share` when present
- Empty holdings and chart unavailable states use `EmptyState`; closed-holdings toggle restyled

### Notes
- `fetchHoldings`, sorting, row navigation, and allocation chart data unchanged; chart color polish deferred to Phase 5B

## 2026-05-25 — Phase 4: Asset Detail tear-sheet migration

### Changed
- **Asset Detail:** tear-sheet layout with `PageHeader` (symbol title, Assets breadcrumb, portfolio/currency subtitle), hero KPI row (`MetricCard` + `CurrencyValue` / `PercentValue`), grouped `SectionCard` sections (position, market, data quality, transactions), `StatusBadge` for holding/price/FX status, `WarningBanner` for API warnings, `LoadingState` / `ErrorState` / `EmptyState`
- Transaction table styling improved with type badges and right-aligned numeric columns

### Notes
- `fetchAssetDetails` and API params unchanged; no client-side finance calculations
- Assets list and other pages unchanged; `DataTable` deferred

## 2026-05-25 — Phase 3B: Dashboard chart container and theme

### Added
- `ChartCard` and `SegmentedControl` UI primitives with tests
- `frontend/src/components/charts/chartTheme.js` — centralized Recharts colors and styles

### Changed
- **Dashboard:** performance chart wrapped in `ChartCard`; metric and range controls use `SegmentedControl`; benchmark select styled via CSS class
- Chart empty state uses `EmptyState`; loading/benchmark warnings remain `WarningBanner`
- Recharts grid, axis, tooltip, and series colors use Institutional Slate palette
- “Invested vs Current” bar chart demoted to compact secondary `ChartCard`

### Notes
- API fetch params, `mergeComparisonSeries`, and chart data semantics unchanged
- Assets, other pages unchanged

## 2026-05-25 — Phase 3A: Dashboard structure, states, and KPI cards

### Changed
- **Dashboard:** `PageHeader`, `MetricCard`, `CurrencyValue`, `PercentValue`, `LoadingState`, `ErrorState`, and `WarningBanner` replace raw header, KPI cards, loading/error, and FX/chart warnings
- KPI row shows Current Value (hero), Total Invested, Total P/L, XIRR, plus Realized/Unrealized P/L when present in summary API
- Chart controls, Recharts logic, and Invested vs Current bar chart unchanged

### Notes
- No API, fetch params, or finance calculation changes
- Chart theme, SegmentedControl, and ChartCard deferred to Phase 3B+

## 2026-05-25 — Phase 2: App shell / sidebar polish

### Changed
- **Layout:** Institutional Slate sidebar with brand area, navigation, bottom context controls, and cached-data footer note
- Active nav uses accent left border and raised surface (replaces inverted high-contrast style)
- Portfolio and display currency selectors restyled with focus rings and custom chevron; logic unchanged
- Main content area uses consistent padding and surface separation from sidebar
- Responsive stacking below 900px; compact nav grid on very narrow screens
- Portfolio load warning uses `WarningBanner` primitive

### Notes
- Routing, `portfolioContext`, API calls, and page content unchanged
- Dashboard, Assets, AssetDetail, Transactions page markup unchanged

## 2026-05-25 — Phase 1: UI primitive components

### Added
- Reusable UI primitives in `frontend/src/components/ui/`: Button, PageHeader, MetricCard, SectionCard, StatusBadge, WarningBanner, EmptyState, LoadingState, ErrorState, CurrencyValue, PercentValue
- Shared `ui.css` styled with Institutional Slate tokens; barrel export via `index.js`
- Vitest/RTL tests for UI primitives (`ui.test.jsx`)

### Changed
- **Settings page:** uses PageHeader, SectionCard, Button, LoadingState, ErrorState, and WarningBanner (form behavior and API calls unchanged)
- `docs/frontend-design.md` — component catalog updated with implemented APIs

### Notes
- Dashboard, Assets, AssetDetail, and Transactions unchanged
- No finance calculations, API, or backend changes

## 2026-05-19 — Assets page fixes (post Phase 11)

### Fixed
- **Holdings price lookup:** converts cached `HistoricalPrice` from stored currency (e.g. USD) into each asset's transaction currency via cached FX — same pattern as summary service
- **`fx_status` false positive:** no longer reports `fx_unavailable` when `display_currency` matches holding currency but prices are stored in USD
- **Oversold false positives:** `detect_oversell` now passes `STOCK_SPLIT` rows into split adjustment (ANET/TSLA-style 1:N splits no longer flagged)
- **Assets UI:** allocation chart empty state when all `current_value` are zero; chart CSS; price-missing message (no polling/"fetching"); FX warning only when display currency differs from holdings

### Tests
- Backend: USD→EUR price conversion, FX ok with matching display currency, split-adjusted oversell, price missing without FX
- Frontend: chart render/empty state, FX warning gating, oversold row, price-missing wording

## 2026-05-19 — Phase 11: React frontend integration

### Added
- Full React UI ported from KPulla5 patterns: Layout, Dashboard, Assets, AssetDetail, Transactions, Settings
- `portfolioContext.jsx`, centralized `api.js` with `VITE_API_BASE_URL`
- Vitest/RTL tests (API client, layout, dashboard, assets, transactions, settings)
- `make test-frontend`; `make test` runs backend + frontend

### Notes
- No finance, FX, or benchmark calculations in the browser
- Dev: Vite proxies `/api` to Django when `VITE_API_BASE_URL` is empty

## 2026-05-19 — Phase 10: Portfolio performance API

### Added
- `GET /api/v1/portfolio/performance` — `value`, `cumulative_return`, `twror`, `range`, optional benchmark
- `portfolios/performance_service.py`, `portfolios/performance_views.py`, `portfolios/dates.py`
- `finance/performance_range.py`, `finance/benchmarks.py`
- `market_data/price_repository.list_index_prices_in_range`

### Tests
- `backend/tests/test_portfolio_performance_api.py`
- `backend/tests/test_performance_range.py`, `backend/tests/test_benchmarks_finance.py`

### Not included
- Frontend performance charts, automatic background scheduler

## 2026-05-19 — Phase 9: Portfolio summary API

### Added
- `GET /api/v1/portfolio/summary` — FIFO metrics, XIRR, optional timeseries, display currency
- `portfolios/summary_service.py`, `portfolios/summary_views.py`
- `market_data/price_repository.py` — bulk historical / latest price queries
- `fx/lookup.convert_amount_with_fill`, `load_fx_rate_maps`, `fx_lookup_from_maps`
- `finance/xirr.calculate_portfolio_xirr` — multi-asset portfolio XIRR

### Tests
- `backend/tests/test_portfolio_summary_api.py` (28 cases)

### Not included
- Performance/TWROR endpoint, benchmark overlay, frontend, auto-sync on read

## 2026-05-19 — Phase 8: Historical prices, FX cache, benchmark sync

### Added
- `POST /api/v1/prices/refresh`, `POST /api/v1/portfolio/force-sync`, `GET /api/v1/benchmarks/indices`
- `market_data/services/` (`price_sync`, `benchmark_sync`, `market_data_sync`)
- `market_data/providers/yfinance_provider.py` (mockable)
- `fx/lookup.py`, `fx/services.py`, `fx/providers/yfinance_fx.py`
- Commands: `sync_prices`, `sync_benchmarks`, `sync_fx_rates`, `sync_market_data`
- Makefile: `sync-prices`, `sync-benchmarks`, `sync-fx`, `sync-market-data`
- Dependencies: `yfinance`, `pandas`

### Tests
- `backend/tests/test_market_data_sync.py`, `backend/tests/test_fx_sync.py`

### Notes
- Manual API sync is synchronous (no Celery/RQ)
- Holdings/summary reads still do not call external market-data APIs

## 2026-05-19 — Phase 7: Holdings and asset detail APIs

### Added
- `GET /api/v1/portfolio/holdings` — FIFO metrics, XIRR, price_status, holding_status, oversell warnings
- `GET /api/v1/portfolio/assets/{asset_symbol}` — per-asset FIFO metrics + transaction history
- `portfolios/holdings_service.py`, `portfolios/holdings_views.py`, `market_data/price_lookup.py`, `finance/oversell.py`

### Tests
- `backend/tests/test_holdings_api.py` (30 cases)

### Not included
- Summary/performance APIs, price/FX sync, frontend

## 2026-05-19 — Phase 6: Finance domain layer

### Added
- `backend/finance/` — `types`, `splits`, `fifo`, `xirr`, `twror` (framework-independent)
- `transactions/finance_adapter.py` — Django Transaction → finance DTO
- Dependency: `pyxirr`

### Tests
- `backend/tests/test_finance_domain.py` — FIFO, splits, XIRR, TWROR
- `backend/tests/test_finance_adapter.py`

### Not included
- Holdings/summary/performance APIs, sync, frontend

## 2026-05-19 — Phase 5 assumptions closed (pre–Phase 6)

### Docs
- `docs/api-design.md` — Phase 5 closed assumptions table (direct `STOCK_SPLIT`, `SWAP`, currency, 404, UTF-8/MIME)
- `docs/current-state.md` — Phase 5 marked closed for Phase 6
- `docs/database.md` — split `currency` note

### Tests
- `test_csv_import_api.py` — direct split EUR/`quantity`/`price_per_share`; currency in `Price/Share` rejected; import `portfolio_id` 404 shape

## 2026-05-19 — Phase 5: CSV import and stock splits

### Added
- `POST /api/v1/transactions/import-csv` — multipart upload, optional `portfolio_id`, all-or-nothing import
- `transactions/csv_import.py` — CSV parsing, SWAP→`STOCK_SPLIT`, direct `STOCK_SPLIT` rows
- `import_transactions_from_csv` in `transactions/services.py` (atomic DB transaction)

### Tests
- `backend/tests/test_csv_import_api.py` — import success/validation, SWAP pairs, all-or-nothing

### Docs updated
- `docs/api-design.md`, `docs/architecture.md`, `docs/current-state.md`, `docs/database.md`

### Not included
- Holdings/summary/performance, XIRR/TWROR, price/FX/benchmark sync, frontend

## 2026-05-19 — Phase 4 contracts documented and tested

### Added
- Explicit Phase 4 behavioral contracts in `docs/api-design.md` and `docs/current-state.md`
- Tests: PUT preserves portfolio when `portfolio_id` omitted; transaction hard delete vs portfolio soft delete

### Docs updated
- `docs/database.md` — split fields; hard vs soft DELETE semantics

## 2026-05-19 — Phase 4: Transaction CRUD APIs

### Added
- `GET/POST /api/v1/transactions` — pagination, portfolio scope, asset filter
- `PUT/DELETE /api/v1/transactions/{id}`
- `portfolios/scope.py` — portfolio scope resolution
- `transactions/services.py`, serializers, views

### Tests
- `backend/tests/test_transactions_api.py`

### Docs updated
- `docs/api-design.md`, `docs/architecture.md`, `docs/current-state.md`

### Not included
- CSV import, market price validation, sync, analytics, frontend

## 2026-05-19 — Phase 3: Settings and Portfolios APIs

### Added
- `GET/PUT /api/v1/settings` — singleton AppSettings, display currency validation
- `GET/POST/PUT/DELETE /api/v1/portfolios` — active list, create, update, soft deactivate
- `portfolios/services.py`, `settings_app/services.py` with DRF serializers/views

### Tests
- `backend/tests/test_settings_api.py`
- `backend/tests/test_portfolios_api.py`

### Docs updated
- `docs/api-design.md`, `docs/architecture.md`, `docs/current-state.md`

### Not included
- Transactions, analytics, sync, frontend

## 2026-05-19 — Phase 2: Django models, migrations, seed

### Added
- Models: `Portfolio`, `Transaction`, `HistoricalPrice`, `FXRate`, `BenchmarkIndexConfig`, `AppSettings`
- Initial migrations per app (`0001_initial.py`)
- `manage.py seed_initial_data` — Default Portfolio, AppSettings (`pk=1`), five benchmark indices
- `make seed`, `make bootstrap` (db + migrate + seed)
- `portfolios/constants.py` — default/virtual portfolio names

### Tests
- `backend/tests/test_models_phase2.py` — seed idempotency, uniqueness, portfolio FK, virtual portfolio guard

### Docs updated
- `docs/database.md`, `docs/architecture.md`, `docs/current-state.md`

### Not included
- REST APIs, finance calculations, sync workers, frontend features

## 2026-05-19 — Initial foundation (Django + DRF + React + Docker PostgreSQL)

### Added
- KPulla6 project structure separate from KPulla5
- `docker-compose.yml` — PostgreSQL 16 (`postgres` service)
- `Makefile` — `db`, `db-stop`, `db-logs`, `db-shell`, `backend`, `frontend`, `migrate`, `test`, `dev`
- Django project (`backend/config/`) with DRF
- Django apps: `portfolios`, `transactions`, `market_data`, `fx`, `analytics`, `settings_app`
- `backend/finance/` package placeholder for framework-independent logic
- `GET /api/v1/health` endpoint
- `.env.example` for PostgreSQL and Django settings
- React + Vite frontend scaffold with API proxy and health check UI
- `AGENTS.md` and docs adapted from KPulla5 for the new stack

### Tests
- Backend: `backend/tests/test_health.py`
- Frontend: `frontend/src/App.test.jsx`

### Docs updated
- `docs/current-state.md`, `docs/architecture.md`, `docs/api-design.md`, `docs/database.md`
- `docs/workflows.md`, `docs/decisions.md`, `docs/migration-readiness.md`, `docs/project-summary.md`

### Not included (by design)
- Business logic port (transactions, portfolios, analytics, sync)
- SQLAlchemy / FastAPI code copy
- Production secrets or data migration from KPulla5 SQLite
