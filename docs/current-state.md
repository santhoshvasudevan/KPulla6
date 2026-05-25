# Current State — KPulla6 (Portfolio Insight)

## Last Updated
2026-05-25 (Phase 8B)

## Stack
- **Backend:** Django 5 + Django REST Framework
- **Frontend:** React 19 + Vite 6 (Dashboard, Assets, Transactions, Settings, portfolio/currency selectors)
- **Database:** PostgreSQL 16 (Docker Compose)
- **Reference:** KPulla5 (read-only)

## Backend Status
- **Models + migrations + seed** (Phase 2)
- **Settings + Portfolios APIs** (Phase 3)
- **Transaction CRUD APIs** (Phase 4):
  - `GET/POST /api/v1/transactions`
  - `PUT/DELETE /api/v1/transactions/{id}`
  - Portfolio scoping: `portfolio_scope=all` (default) or `portfolio_id`
- **CSV import + stock splits** (Phase 5):
  - `POST /api/v1/transactions/import-csv` — all-or-nothing; row-level errors
  - SWAP pair → `STOCK_SPLIT`; direct `STOCK_SPLIT` CSV rows
  - `transactions/csv_import.py`, `import_transactions_from_csv` in services
- **Finance domain** (Phase 6):
  - `backend/finance/` — FIFO, splits, XIRR, TWROR helpers (no Django imports)
  - `transactions/finance_adapter.py` — Transaction model → finance DTO
- **Holdings + asset detail** (Phase 7):
  - `GET /api/v1/portfolio/holdings`
  - `GET /api/v1/portfolio/assets/{asset_symbol}`
  - `portfolios/holdings_service.py`, `market_data/price_lookup.py`, `finance/oversell.py`
- **Market data cache + sync** (Phase 8):
  - `POST /api/v1/prices/refresh`, `POST /api/v1/portfolio/force-sync`, `GET /api/v1/benchmarks/indices`
  - `market_data/services/` (price + benchmark sync), `market_data/providers/` (yfinance, mockable)
  - `fx/lookup.py`, `fx/services.py`, `fx/providers/` (FX upsert + yfinance)
  - Management: `sync_prices`, `sync_benchmarks`, `sync_fx_rates`, `sync_market_data`
  - Manual refresh/sync is **synchronous**; holdings/dashboard reads use DB cache only
- **Portfolio summary** (Phase 9):
  - `GET /api/v1/portfolio/summary` — FIFO metrics, optional daily timeseries, display currency
  - `portfolios/summary_service.py`, `portfolios/summary_views.py`
  - `market_data/price_repository.py`, `fx/lookup.convert_amount_with_fill`
  - Read path: no external market-data calls; no auto-sync on summary request
- **Portfolio performance** (Phase 10):
  - `GET /api/v1/portfolio/performance` — `value`, `cumulative_return`, `twror`, `range`, optional benchmark
  - `portfolios/performance_service.py`, `portfolios/performance_views.py`
  - `finance/performance_range.py`, `finance/benchmarks.py` (pure comparison math)
  - Reuses Phase 9 value timeseries; benchmark levels from `HistoricalPrice` (`asset_type=INDEX`)
  - Read path: no external market-data calls
- `GET /api/v1/health`
- Services: `transactions/services.py`, `portfolios/scope.py`, `portfolios/holdings_service.py`

## Frontend (Phase 11 + design migration)
- React Router app shell with virtual **All Portfolios** + real portfolio selector
- Display currency from settings (sidebar + Settings page)
- Dashboard: summary cards, performance chart (value / cumulative return / TWROR), range pills, benchmark overlay
- Assets: holdings table, allocation chart, closed/oversold/price_missing states
- Asset detail: FIFO metrics + transaction history (scoped)
- Transactions: CRUD, CSV import, STOCK_SPLIT form
- API client: `VITE_API_BASE_URL` + `/api/v1` (no client-side finance/FX/benchmark math)
- **Manual sync:** run `make refresh` (or `make sync-prices`, `make sync-benchmarks`, `make sync-fx`) to populate cached prices/FX; Assets page shows a clear empty state when prices are missing

### Frontend design (Institutional Slate — complete)
- CSS tokens, UI primitives (`PageHeader`, `MetricCard`, `ChartCard`, `SectionCard`, `StatusBadge`, etc.)
- All pages migrated: Dashboard, Assets, Asset Detail, Transactions, Settings, app shell
- `TransactionModal` polished with canonical tokens and shared `Button`
- Shared transaction type badges (`.ui-txn-type`) in `ui.css`
- Legacy CSS aliases removed from `index.css` (Phase 8B); canonical tokens only
- `DataTable` deferred

## Not Yet Implemented
- Automatic background sync scheduler (Celery/RQ not configured)

## Phase 6 contracts (verified in tests)
- FIFO cost basis, realized/unrealized P/L, stock split adjustments
- XIRR cashflow rules; TWROR chain-link helper (not exposed via API)
- Oversell: no hard reject; realized P/L uses full sell proceeds vs FIFO cost of held lots only
- TWROR: `compute_twror_series` in `finance/twror.py`; exposed via performance API (Phase 10)

## Phase 10 contracts (verified in tests)
- Performance scoping/validation matches summary (default `all`, 400/404/422 rules)
- `metric=value` list points; `display_currency` conversion via cached FX
- `cumulative_return` / `twror` percentage series; BUY/SELL flows with fees
- `range` filters (`7D`–`ALL`); never before first transaction; TWROR re-chains on non-`ALL` windows
- Benchmark comparison for return metrics; `metric=value` ignores benchmark params
- Unknown/disabled benchmark → **422**; missing index prices → warnings + portfolio-only series
- No yfinance on performance reads

## Phase 7 contracts (verified in tests)
- Holdings/asset detail use Phase 6 FIFO + split adjustments
- `holding_status`: `ok` / `closed` / `oversold` with warnings on oversell
- `price_status` from cached `HistoricalPrice` only; converts price currency → holding currency via cached FX when needed
- `current_value=0` when latest price absent or price→holding FX missing
- `fx_unavailable` when `display_currency` ≠ holding currency (holdings amounts not converted to display currency)
- `fx_status` remains `ok` when display currency matches holding currency even if stored prices are USD

## Phase 9 contracts (verified in tests)
- Summary scoping matches holdings (default `all`, `portfolio_id`, 422/404 rules)
- `include_timeseries=false` omits series; `true` builds daily value history
- FIFO `total_invested`, forward-filled prices, 7-day FX gap fill for timeseries
- Display-currency conversion via cached FX; `fx_unavailable` when missing
- No yfinance on summary reads

## Phase 8 contracts (verified in tests)
- Incremental, idempotent `HistoricalPrice` upsert (stocks + INDEX benchmarks)
- Stock symbols uppercased; benchmark symbols preserve `^` (e.g. `^GSPC`)
- FX: same-date lookup only (no latest-rate fallback for historical dates)
- All sync tests mock providers — no real network calls

## Test Status
- Backend: `make test-backend` — 245 pytest tests
- Frontend: `make test-frontend` — 79 vitest tests; `npm run build` passes

## Phase 4 contracts (verified in tests)
- `portfolio_scope=all` + `portfolio_id` → **422**
- Unknown/inactive `portfolio_id` → **404**
- `DELETE /api/v1/transactions/{id}` → hard delete, **204**
- `DELETE /api/v1/portfolios/{id}` → soft deactivate, **200**
- `PUT /api/v1/transactions/{id}` → full body; omitted `portfolio_id` keeps current portfolio
- Stock splits use `split_from` / `split_to` only (no `conversion_ratio`, `needs_review`)
- Not in Phase 5: daily high/low validation, yfinance, sync, holdings/summary/XIRR/TWROR

## Phase 5 contracts (verified in tests — closed for Phase 6)
- CSV import all-or-nothing (`@transaction.atomic`)
- Row-level validation errors; `success` / `imported_count` response shape
- SWAP → `STOCK_SPLIT` with `split_from` / `split_to` only (no `conversion_ratio`, `needs_review`)
- Direct `STOCK_SPLIT`: `Qty`/`Price/Share` = plain ratio → `split_from`/`split_to`; not currency-parsed
- Direct `STOCK_SPLIT`: `currency` stored as `EUR` (schema only); `quantity`/`price_per_share` = `0`
- Invalid/inactive import `portfolio_id` → **404** `detail` (not CSV row errors)
- UTF-8 + required columns validated; MIME/extension not enforced
- Full assumption table: `docs/api-design.md` → Phase 5 closed assumptions

## Constraints
- Transactions = source of truth; each links to one real active portfolio
- **All Portfolios** is virtual only
