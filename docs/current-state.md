# Current State — KPulla6 (Portfolio Insight)

## Last Updated
2026-05-27 (Portfolio CRUD UI + bulk transaction assignment)

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
  - `POST /api/v1/prices/refresh`, `POST /api/v1/nav/refresh`, `POST /api/v1/portfolio/force-sync`, `GET /api/v1/benchmarks/indices`
  - `market_data/services/` (price + benchmark sync), `market_data/providers/` (yfinance, mockable)
  - Stock `sync_prices` backfills from earliest transaction date when cached prices start later than first transaction (GOOG-style gaps); otherwise incremental from latest cached date + 1
  - FX `sync_fx_rates` backfills from earliest required valuation date when cached FX starts later than needed (USD price + EUR holding with late FX rows); otherwise incremental from latest cached date + 1
  - `fx/lookup.py`, `fx/services.py`, `fx/providers/` (FX upsert + yfinance)
  - Management: `sync_prices`, `sync_benchmarks`, `sync_fx_rates`, `sync_market_data`
  - Manual refresh/sync is **synchronous**; holdings/dashboard reads use DB cache only
- **Portfolio summary** (Phase 9):
  - `GET /api/v1/portfolio/summary` — FIFO metrics, optional daily timeseries, display currency
  - `portfolios/summary_service.py`, `portfolios/summary_views.py`
  - Value timeseries uses `build_split_adjusted_lot_snapshots` with cached split-adjusted prices so pre-split holdings are quantity-adjusted before daily valuation
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
- **Mutual fund schema foundation** (Phase MF-1):
  - `market_data.models`: `Asset`, `MutualFundProfile`, `PrimaryAssetClass`; `AssetType.MUTUAL_FUND`; nullable `HistoricalPrice.asset` FK
  - `transactions.models`: `Folio`, `MutualFundTransactionDetail`, `NavVerificationStatus`
  - Migrations: `market_data/0002_mutual_fund_schema`, `transactions/0002_mutual_fund_schema`
  - Tests: `backend/tests/test_models_mutual_funds.py` (12 cases)
  - **Not wired:** MF transaction API, holdings/summary/performance integration, frontend
- **Mutual fund NAV cache + sync** (Phase MF-2):
  - `market_data/providers/mutual_fund_nav_provider.py` — `NavPoint`, `MutualFundNavProvider`, live `AmfiNavProvider` (MFAPI)
  - `market_data/providers/amfi_nav_parser.py` — MFAPI response parsing (MF-10)
  - `market_data/services/mutual_fund_nav_sync.py` — incremental sync, idempotent upsert to `HistoricalPrice` (`MUTUAL_FUND`)
  - `market_data/nav_lookup.py`, `market_data/nav_repository.py` — DB-only latest/range NAV lookup
  - Management: `sync_mutual_fund_navs` (`--scheme-code` optional)
  - Tests: `backend/tests/test_mutual_fund_nav_sync.py` (12 cases)
  - **Not wired:** NAV refresh HTTP endpoint, `sync_market_data` MF inclusion, holdings/summary/performance reads, live AMFI download
- **Mutual fund transaction API** (Phase MF-3):
  - `POST/PUT /api/v1/transactions` with `asset_type=MUTUAL_FUND` — BUY/SELL with scheme, folio, dual dates, NAV, units, paid/market value
  - `transactions/mutual_fund_services.py`, `MutualFundTransactionWriteSerializer`
  - Auto upsert Asset, MutualFundProfile, Folio; atomic Transaction + detail
  - Optional cached NAV compare sets `nav_verification_status` (no external provider)
  - Tests: `backend/tests/test_mutual_fund_transactions_api.py` (16 cases)
  - **Not wired:** summary/performance integration, frontend MF form, CSV import
- **Mutual fund holdings + asset detail** (Phase MF-4):
  - `GET /api/v1/portfolio/holdings` — MF rows grouped by `scheme_code` + `folio_number`; cached NAV via `latest_nav_for_asset`
  - `GET /api/v1/portfolio/assets/{scheme_code}?folio_number=...` — folio-scoped MF detail; `folio_number` required when multiple folios exist
  - `portfolios/holdings_service.py` — stock path unchanged; MF FIFO per folio; `nav_status`, `holding_key`, `latest_nav`
  - Tests: `backend/tests/test_mutual_fund_holdings_api.py` (14 cases)
  - **Not wired:** frontend MF form, CSV import
- **Mutual fund summary + performance** (Phase MF-5):
  - `GET /api/v1/portfolio/summary` — MF totals, timeseries (NAV forward-fill), XIRR with `investment_date`/`paid_value` cash flows
  - `GET /api/v1/portfolio/performance` — `value`, `cumulative_return`, `twror` include MF via shared timeseries builder
  - `finance/mutual_fund_cashflows.py`, `market_data/nav_repository.py` batch helpers
  - Tests: `backend/tests/test_mutual_fund_summary_performance_api.py` (14 cases)
  - **Not wired:** frontend MF form, CSV import
- **Mutual fund NAV validation** (Phase MF-6):
  - `transactions/mf_nav_validation.py` — cached NAV + market_value compare on MF create/update
  - Status: `VERIFIED`, `NAV_MISSING`, `NAV_MISMATCH`, `VALUE_MISMATCH` (+ legacy MF-3 values)
  - Tolerances: 0.01 INR NAV, 1 INR market value; mismatch does not block save
  - Tests: `backend/tests/test_mutual_fund_nav_validation.py` (11 cases)
  - **Not wired:** frontend validation UX, CSV import
- **Mutual fund classification** (Phase MF-7):
  - `finance/mutual_fund_classification.py` — metadata inference (HYBRID ≠ EQUITY)
  - MF holdings/asset detail: `primary_asset_class`, `classification_source`, optional `classification_notes`
  - Create/update upserts `Asset.primary_asset_class` when unset/UNKNOWN
  - Tests: `backend/tests/test_mutual_fund_classification.py` (16 cases)
  - **Not wired:** allocation chart, exposure split, tax classification
- **Mutual fund NAV refresh + combined sync** (Phase MF-9):
  - `POST /api/v1/nav/refresh` — optional `scheme_codes`; synced/skipped/failed counts
  - `sync_market_data` / `force-sync` include MF NAV sync (`--skip-mutual-funds` to opt out)
  - `market_data/nav_refresh.py`; per-scheme failure does not fail stock/FX/benchmark sync
  - Tests: `backend/tests/test_mutual_fund_nav_refresh_api.py` (11 cases)
  - **Not wired:** live AMFI provider, scheme search, MF CSV import
- **Mutual fund frontend** (Phase MF-8):
  - `TransactionModal` — asset type selector (Stock default, Mutual fund); MF create/edit with backend field names
  - Transactions table — scheme/folio/NAV status display; stock rows unchanged
  - Assets holdings — safe MF row labels (`scheme_name`, folio) without stock regression
  - Tests: `TransactionModal.test.jsx`, `Transactions.test.jsx`, `transactionDisplay.test.js`
  - **Not wired:** scheme search, MF CSV import, allocation redesign
- **Live mutual fund NAV provider** (Phase MF-10):
  - `AmfiNavProvider` — MFAPI fetch for latest NAV + date-range history; injectable `http_get`
  - Parser: `amfi_nav_parser.py`; timeout/network/malformed response handling
  - Tests: `backend/tests/test_amfi_nav_provider.py` (20 cases); all HTTP mocked
  - **Not wired:** scheme search, MF CSV import, grouping setting

## Frontend (Phase 11 + design migration)
- React Router app shell with virtual **All Portfolios** + real portfolio selector
- **Portfolio management (Settings):** create, rename/edit, deactivate non-default portfolios; max 5 active; Default Portfolio cannot be deactivated; sidebar selector refreshes via `reloadPortfolios()`
- **Bulk transaction assignment (Transactions):** row selection + assign selected rows to a real portfolio via full PUT payloads (stock, MF, STOCK_SPLIT)
- Display currency from settings (sidebar + Settings page)
- Dashboard: summary cards, performance chart (value / cumulative return / TWROR), range pills, benchmark overlay
- Assets: holdings table, allocation chart, closed/oversold/price_missing states
- Asset detail: FIFO metrics + transaction history (scoped)
- Transactions: CRUD, CSV import, STOCK_SPLIT form, bulk assign to portfolio
- API client: `VITE_API_BASE_URL` + `/api/v1` (no client-side finance/FX/benchmark math)
- **Manual sync:** run `make refresh` (or `make sync-market-data`) for stocks, benchmarks, FX, and mutual fund NAVs; stock-only: `make sync-prices`; MF NAV only: `sync_mutual_fund_navs` or `POST /api/v1/nav/refresh`

### Frontend design (Institutional Slate — complete)
- CSS tokens, UI primitives (`PageHeader`, `MetricCard`, `ChartCard`, `SectionCard`, `StatusBadge`, etc.)
- All pages migrated: Dashboard, Assets, Asset Detail, Transactions, Settings, app shell
- `TransactionModal` polished with canonical tokens and shared `Button`
- Shared transaction type badges (`.ui-txn-type`) in `ui.css`
- Legacy CSS aliases removed from `index.css` (Phase 8B); canonical tokens only
- `DataTable` deferred

## Not Yet Implemented
- Automatic background sync scheduler (Celery/RQ not configured)

## Planned — Indian Mutual Funds (MF-4+)

Design doc: [mutual-funds.md](./mutual-funds.md). **MF-1 schema, MF-2 NAV sync, and MF-3 transaction API implemented.**

| Topic | Status |
|-------|--------|
| Schema (Asset, Profile, Folio, MF txn detail) | **MF-1 done** |
| NAV cache + sync command + DB lookup | **MF-2 done** |
| MF transaction API (POST/PUT/GET list/DELETE) | **MF-3 done** |
| Holdings grouped by scheme + folio | **MF-4 done** |
| Summary / performance integration | **MF-5 done** |
| NAV validation tolerance UX | **MF-6 done** |
| Classification mapping | **MF-7 done** |
| Frontend MF transaction form + list display | **MF-8 done** |
| NAV refresh HTTP + combined sync | **MF-9 done** |
| Live NAV provider (MFAPI) | **MF-10 done** |
| Scheme-only grouping / CSV | MF-11 |

## Phase 6 contracts (verified in tests)
- FIFO cost basis, realized/unrealized P/L, stock split adjustments
- XIRR cashflow rules; TWROR chain-link helper (not exposed via API)
- Oversell: no hard reject; realized P/L uses full sell proceeds vs FIFO cost of held lots only
- TWROR: `compute_twror_series` in `finance/twror.py`; exposed via performance API (Phase 10)

## Phase 10 contracts (verified in tests)
- Performance scoping/validation matches summary (default `all`, 400/404/422 rules)
- `metric=value` list points; `display_currency` conversion via cached FX
- `cumulative_return` / `twror` percentage series; BUY/SELL flows with fees; no artificial split-induced drops when prices are split-adjusted
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
- Split-adjusted cached prices paired with split-adjusted transaction quantities in value history (GOOG-style 1:20 scenarios)
- Display-currency conversion via cached FX; `fx_unavailable` when missing
- No yfinance on summary reads

## Phase 8 contracts (verified in tests)
- Incremental, idempotent `HistoricalPrice` upsert (stocks + INDEX benchmarks)
- Stock sync start date: earliest transaction when no cache; backfill from earliest transaction when cache starts later than first transaction; else latest cached date + 1
- Stock symbols uppercased; benchmark symbols preserve `^` (e.g. `^GSPC`)
- FX: same-date lookup only (no latest-rate fallback for historical dates); sync backfills when earliest required date precedes earliest cached FX row
- All sync tests mock providers — no real network calls

## Test Status
- Backend: `make test-backend` — 393 pytest tests
- Frontend: `make test-frontend` — vitest tests; `npm run build` passes

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
