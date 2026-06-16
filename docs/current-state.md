# Current State — KPulla6 (Portfolio Insight)

## Last Updated
2026-06-14 (FD-ACC-9 — FD accounting stabilization and audit)

**Documentation index:** [README.md](./README.md)

## MVP Status

**MVP release-ready** (local-first dev; **not** marked production-deployed). Sign-off: **2026-06-06**.

**Ready with accepted limitations** — automated tests, diagnostics, and performance gates passed (STAB-6); manual golden-flow browser QA completed (MVP-RELEASE-1). Commit stabilization work before tagging.

**KPulla6 has reached MVP maturity** for local-first portfolio tracking with:

- Quantitative Statistics / **Metric Sheet** (portfolio, asset, Compare — backend + frontend)
- Full **cash ledger** (deposits, withdrawals, edit/delete, cash-aware BUY/SELL, summary/performance/XIRR integration)
- Same- and cross-currency **portfolio transfers**
- **Bulk Cash Entries** for historical funding (backfill wizard/APIs **removed**)
- Stock + mutual fund transactions, CSV import, holdings, dashboard performance
- **Fixed Deposits (FD MVP):** bank accounts, fixed deposit CRUD, principal-only summary/holdings integration, dashboard allocation buckets — see [fixed-deposits.md](./fixed-deposits.md)
- **FD Accounting Phase 1 (FD-ACC-1..8C):** bank cash ledger, mandatory FD opening debit, interest/TDS, maturity/settlement, renewal, opt-in bank cash in portfolio value, value history + return metrics — [fixed-deposits-accounting.md](./fixed-deposits-accounting.md); **implemented and audited (FD-ACC-9)**

Product rules index: [product-rules.md](./product-rules.md). Release checklist: [mvp-release-checklist.md](./mvp-release-checklist.md). API contract index: [api-contracts.md](./api-contracts.md).

### Accepted limitations (MVP)

| Limitation | Status |
|------------|--------|
| Transfer fees | Deferred (Cash-8C) |
| Same-portfolio FX conversion | Deferred |
| Dashboard read-path optimization | Deferred — STAB-5B baseline acceptable (< 1 s critical paths) |
| Background sync scheduler (Celery/RQ) | Not configured |
| Full browser E2E suite (Playwright/Cypress) | Not present |
| Display-currency cash totals on `/cash` | Deferred |
| Dividends / interest / taxes ledger types | Deferred |

See [performance/dashboard-read-paths.md](./performance/dashboard-read-paths.md) for optimization backlog (STAB-5C+ when targets exceeded).

## Stack
- **Backend:** Django 5 + Django REST Framework + django-allauth (session auth, Google OAuth)
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
  - **Column filters:** `asset_symbol`, `symbols` (comma-separated, case-insensitive), `date_from` / `date_to` (+ `date_after` / `date_before` aliases) applied before pagination; invalid date or `date_from > date_to` → `400`
  - `GET /api/v1/transactions/filter-options` — distinct portfolios / symbols / types / date bounds for the current scope
- **CSV import + stock splits** (Phase 5):
  - `POST /api/v1/transactions/import-csv` — all-or-nothing; row-level errors
  - Stock CSV: `Action`, `Date`, `ASSET SYMBOL`, `Qty`, `Price/Share`, optional `FEES`
  - **Mutual fund CSV (MF-11a):** detected by `Scheme Code` + `Folio Number` headers; BUY/SELL only; routes to `create_mutual_fund_transaction()`; no mixed stock+MF file
  - SWAP pair → `STOCK_SPLIT`; direct `STOCK_SPLIT` CSV rows
  - `transactions/csv_import.py`, `import_transactions_from_csv` in services
- **Finance domain** (Phase 6 + Phase 2 analytics foundation):
  - `backend/finance/` — FIFO, splits, XIRR, TWROR, **returns** helpers (no Django imports)
  - `finance/returns.py` — daily/monthly/yearly fractional return series from values, flows, or TWROR points
  - `finance/performance_stats.py`, `finance/risk_metrics.py`, `finance/drawdowns.py` — Metric Sheet risk/drawdown from daily return fractions; headline `cumulative_return` / `cagr` align with performance chart money-weighted return (2026-06-01)
  - `finance/comparison.py` — benchmark-relative metrics: beta, alpha, correlation, tracking error, etc. (Phase 4); `finance/benchmarks.py` remains chart-overlay rebasing only
  - `transactions/finance_adapter.py` — Transaction model → finance DTO
- **Holdings + asset detail** (Phase 7):
  - `GET /api/v1/portfolio/holdings`
  - `GET /api/v1/portfolio/assets/{asset_symbol}`
  - `portfolios/holdings_service.py`, `market_data/price_lookup.py`, `finance/oversell.py`
- **Market data cache + sync** (Phase 8):
  - `POST /api/v1/prices/refresh`, `POST /api/v1/nav/refresh`, `POST /api/v1/portfolio/force-sync`, `GET /api/v1/benchmarks/indices`
  - `market_data/services/` (price + benchmark sync), `market_data/providers/` (yfinance, mockable)
  - Stock `sync_prices` backfills from earliest transaction date when cached prices start later than first transaction (GOOG-style gaps); otherwise incremental from latest cached date + 1
  - Benchmark `sync_benchmarks` uses the same backfill/incremental rules with anchor = earliest transaction date (stocks and MF)
  - FX `sync_fx_rates` backfills from earliest required valuation date when cached FX starts later than needed (USD price + EUR holding with late FX rows); otherwise incremental from latest cached date + 1
  - `fx/lookup.py`, `fx/services.py`, `fx/providers/` (FX upsert + yfinance)
  - Management: `sync_prices`, `sync_benchmarks`, `sync_fx_rates`, `sync_market_data`
  - Manual refresh/sync is **synchronous**; holdings/dashboard reads use DB cache only
- **Portfolio summary** (Phase 9):
  - `GET /api/v1/portfolio/summary` — FIFO metrics, optional daily timeseries, display currency
  - **FIX-2:** `portfolio_scope=all` headline monetary fields sum per-active-portfolio summaries in requested `display_currency` (fixes mixed EUR stock + INR MF under-count)
  - `portfolios/summary_service.py`, `portfolios/summary_views.py`
  - Value timeseries uses `build_split_adjusted_lot_snapshots` with cached split-adjusted prices so pre-split holdings are quantity-adjusted before daily valuation
  - **Stock price invariant:** yfinance sync stores **Adj Close** (split-adjusted); raw nominal pre-split prices are unsupported for valuation/Metric Sheet analytics — see `test_stock_split_valuation_api.py`, `test_analytics_split_metrics_api.py`
  - `market_data/price_repository.py`, `fx/lookup.convert_amount_with_fill`
  - Read path: no external market-data calls; no auto-sync on summary request
- **Portfolio performance** (Phase 10):
  - `GET /api/v1/portfolio/performance` — `value`, `cumulative_return`, `twror`, `range`, optional benchmark
  - `GET /api/v1/analytics/performance-metrics` — Metric Sheet metrics (Phase 5); `analytics/services.py`; `metrics.return.xirr_scope: "full_scope"` (Phase 5B)
  - `GET /api/v1/analytics/assets/{asset_symbol}/performance-metrics` — asset Metric Sheet (Phase 6); stocks + MFs; optional `folio_number`; warns on likely raw split prices (Phase 6B)
  - `portfolios/performance_service.py`, `portfolios/performance_views.py`
  - `finance/performance_range.py`, `finance/benchmarks.py` (pure comparison math)
  - Reuses Phase 9 value timeseries; benchmark levels from `HistoricalPrice` (`asset_type=INDEX`)
  - **Phase B1:** all-scope display-currency conversion uses bulk FX maps (no per-day DB lookups)
  - **Phase B2B:** non-ALL `range` builds bootstrap opening holdings/prices/NAV/FX at range start and emit only the window (~366 days for 1Y vs ~2,426 for ALL); XIRR remains full-scope
  - Read path: no external market-data calls
- `GET /api/v1/health`
- **Auth (session):** `GET /api/v1/auth/me`, `POST /api/v1/auth/login|logout|register|password-reset`, `GET /api/v1/auth/csrf` — see `docs/auth.md`
- Google OAuth: `GET /accounts/google/login/` (django-allauth; redirect after login to `FRONTEND_URL`)
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
  - **Not wired:** holdings/summary/performance MF-specific metrics beyond cached NAV rows
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
  - **Not wired:** scheme search, allocation redesign
  - MF CSV import guidance on Transactions page (MF-11b)
- **Live mutual fund NAV provider** (Phase MF-10):
  - `AmfiNavProvider` — MFAPI fetch for latest NAV + date-range history; injectable `http_get`
  - Parser: `amfi_nav_parser.py`; timeout/network/malformed response handling
  - Tests: `backend/tests/test_amfi_nav_provider.py` (20 cases); all HTTP mocked
  - **Not wired:** scheme search, grouping setting
- **Mutual fund CSV import** (Phase MF-11a):
  - `POST /api/v1/transactions/import-csv` — dedicated MF CSV headers; `parse_mutual_fund_transaction_csv` + `create_mutual_fund_transaction()`
  - Cached NAV verification only on import; all-or-nothing; same `portfolio_id` query rules as stock CSV
  - Tests: `backend/tests/test_mutual_fund_csv_import.py` (16 cases)
- **Mutual fund CSV import guidance** (Phase MF-11b):
  - Transactions page — expandable stock vs MF format panel, rules, inline example, client-side sample MF CSV download
  - `frontend/src/utils/csvImportGuidance.js`; tests in `csvImportGuidance.test.js`, `Transactions.test.jsx`
  - **Not wired:** stock sample CSV download

## Frontend (Phase 11 + design migration)
- React Router app shell with virtual **All Portfolios** + real portfolio selector
- **Portfolio management (Settings):** create, rename/edit, deactivate non-default portfolios; max 5 active; Default Portfolio cannot be deactivated; sidebar selector refreshes via `reloadPortfolios()`
- **Bulk transaction assignment (Transactions):** row selection + assign selected rows to a real portfolio via full PUT payloads (stock, MF, STOCK_SPLIT)
- Display currency from settings (sidebar + Settings page); **`portfolioContext` waits for `GET /settings` before exposing `apiQuery`**; Dashboard summary/performance fetches use request-sequence guards so stale responses cannot overwrite newer currency scope
- **Sidebar layout (Phase 13A):** Portfolio View and Display Currency selectors sit directly below the brand header, above navigation links, so primary context controls are visible without scrolling
- **App shell header:** Theme selector (Light / Dark / System, persisted in `localStorage`), signed-in user label, and Log out — top-right of the main column, always visible without scrolling the sidebar
- Dashboard: summary cards via `GET /portfolio/summary?include_timeseries=false` (headline metrics only; chart uses performance API), performance chart (value / cumulative return / TWROR), range pills, benchmark overlay
- Assets: holdings table, allocation chart, closed/oversold/price_missing states
- Asset detail: FIFO metrics + transaction history (scoped)
- Transactions: CRUD, CSV import (stock + MF formats documented in UI), STOCK_SPLIT form, bulk assign to portfolio, **column filters** (portfolio dropdown, searchable symbol multi-select, date Earlier than / Later than / Between) with active-filter chips and Clear filters; filters apply to the full dataset before pagination and persist across page navigation
- API client: `VITE_API_BASE_URL` + `/api/v1` (no client-side finance/FX/benchmark math)
- **Manual sync:** run `make refresh` (or `make sync-market-data`) for stocks, benchmarks, FX, and mutual fund NAVs; stock-only: `make sync-prices`; MF NAV only: `sync_mutual_fund_navs` or `POST /api/v1/nav/refresh`

### Frontend design (Institutional Slate — complete)
- CSS tokens, UI primitives (`PageHeader`, `MetricCard`, `ChartCard`, `SectionCard`, `StatusBadge`, etc.)
- All pages migrated: Dashboard, Assets, Asset Detail, Transactions, Settings, app shell
- `TransactionModal` polished with canonical tokens and shared `Button`
- Shared transaction type badges (`.ui-txn-type`) in `ui.css`
- Legacy CSS aliases removed from `index.css` (Phase 8B); canonical tokens only
- `DataTable` deferred

## Cash Ledger (Cash-1 implemented)

Design doc: [cash-ledger.md](./cash-ledger.md).

| Topic | Status |
|-------|--------|
| Django app `cash` + migrations | **Done** — `cash/migrations/0001_initial.py` |
| `Portfolio.cash_aware_enabled` | **Done** — DB default `false` for existing rows; **new** portfolios/users default `true` (Cash-4A.1, no data migration) |
| `CashLedgerEntry` / `CashTransferGroup` models + validation | **Done** |
| `cash.constants.SUPPORTED_CASH_CURRENCIES` (20 codes) | **Done** |
| `finance/cash.py` pure balance helpers | **Done** |
| `cash/services.py` ORM skeleton (no HTTP) | **Done** |
| Tests | `test_cash_ledger_models.py`, `test_finance_cash.py`, `test_cash_services.py` |
| `GET /api/v1/cash/balances`, `GET /api/v1/cash/ledger` | **Done** (Cash-2) |
| `cash_aware_enabled` on portfolio API | **Done** (Cash-2) — editable via PUT; drives settlement enforcement when true |
| `POST /api/v1/cash/deposits`, `POST /api/v1/cash/withdrawals` | **Done** (Cash-3A) — withdrawal blocked when insufficient cash |
| Cash page UI (`/cash`) — balances, ledger, deposit/withdrawal modals | **Done** (Cash-3B) |
| Manual ledger edit/delete (`PUT`/`DELETE /cash/ledger/{id}`) | **Done** (Cash-3D + **Cash-4D**) — manual rows only; future-impact **409** with `affected_entries`; no cascade delete |
| Unified Add Transaction modal on `/transactions` (Cash / Stock / MF) | **Done** (Cash-3G) — cash via `/cash/deposits` and `/cash/withdrawals`; cash edit on `/cash` only |
| Cash-aware BUY/SELL settlements (`cash_aware_enabled`) | **Done** (Cash-4A, CASH-SELL-1B) — `BUY_SETTLEMENT` / `SELL_SETTLEMENT`; optional SELL `actual_cash_received` + `TAX_WITHHELD`; insufficient BUY → 400 + shortfall payload |
| Transaction edit/delete future-impact errors + UX | **Done** (TXN-AUDIT-2/3) — **409** structured payload; `/transactions` + `TransactionModal` panels |
| CSV import cash shortfall preview + confirmed deposits | **Done** (Cash-5) |
| Cash transfers (same + cross currency) | **Done** (Cash-8A/8B) — user-entered amounts; no market FX |
| Transaction modal insufficient-cash UX (stock/MF) | **Done** (Cash-4B) — BUY shortfall panel + `/cash` link in `TransactionModal` |
| Same-currency BUY enforcement + guidance | **Done** (Cash-4E) — USD does not fund EUR BUY; purchase shortfall copy; no implicit FX |
| BUY shortfall add cash + continue | **Done** (Cash-4C) — `TransactionModal` deposit in shortfall currency then retry BUY |
| Cash-aware status + per-portfolio enable UI | **Done** (Cash-4A.2) — Cash / Transactions / Settings; `PUT` to repair legacy portfolios |
| CSV import cash preview | **Done** (Cash-5) |
| Summary `current_value` + holdings `allocation` cash (Cash-6A) | **Done** |
| Performance `metric=value` + summary timeseries cash (Cash-6B) | **Done** |
| Portfolio-level XIRR cash-aware (Cash-6C.1) | **Done** |
| TWROR/cumulative_return cash-aware (Cash-6C.2) | **Done** |
| Cash-aware return QA regression + diagnostic script (Cash-6D) | **Done** |
| Cash shortfall backfill APIs + wizard (Cash-7A/7B/7C) | **Removed** |
| Bulk cash entries API + wizard (Cash-7D) | **Done** — `/cash` → Add Bulk Cash Entries |
| Bulk quarterly/yearly frequencies | **Planned** |
| Transfer HTTP APIs | **Done** (Cash-8A/8B) — fees / same-portfolio FX conversion deferred |
| Historical settlement backfill (`sync_cash_settlements`) | **Done** (CASH-HIST-1) — dry-run default; `--apply` after backup |
| Assets Overview cash balances card | **Done** (CASH-HIST-1) — `allocation[]` cash rows; not in holdings table |

**Runtime:** Legacy portfolios — investment-only TWROR/cumulative return; cash in `current_value` / `metric=value`. Cash-aware portfolios — ledger external flows and cash-inclusive daily values for XIRR (6C.1), TWROR, and cumulative return (6C.2).

**Tester repair:** `PUT /api/v1/portfolios/{id}` with `"cash_aware_enabled": true` on the tester default portfolio (no user deletion).

**Next recommended phase:** transfer fees (Cash-8C); optional bulk quarterly/yearly frequencies.

## Fixed Deposits — Accounting (FD-ACC-1..9)

Design doc: [fixed-deposits-accounting.md](./fixed-deposits-accounting.md). MVP: [fixed-deposits.md](./fixed-deposits.md).

| Phase | Scope | Status |
|-------|--------|--------|
| **FD-ACC-0** | Architecture + API proposal docs | **Done** |
| **FD-ACC-0.1** | Approved product decisions (status flow, rollover, balances, inclusion rules) | **Done** |
| **FD-ACC-1** | `CashMovement` model + bank ledger balance + APIs | **Done** |
| **FD-ACC-2** | Manual cash movements UI | **Done** |
| **FD-ACC-3** | Mandatory FD opening bank debit | **Done** |
| **FD-ACC-3.1** | FD opening as-of-date UX/docs | **Done** |
| **FD-ACC-4** | FD interest payments | **Done** |
| **FD-ACC-5** | FD maturity / closure settlement | **Done** |
| **FD-ACC-6** | FD renewal workflow | **Done** |
| **FD-ACC-7** | Optional bank cash in portfolio value | **Done** |
| **FD-ACC-8A** | FD/bank cash performance design review | **Done** (docs only) |
| **FD-ACC-8B** | Value history — FD principal + included bank cash in `metric=value` | **Done** |
| **FD-ACC-8C** | Cashflow-aware XIRR/TWROR for FD/bank events | **Done** |
| **FD-ACC-9** | Stabilization, E2E audit, docs verification, Graphify refresh | **Done** |

**Performance:** Summary/holdings, **`metric=value`**, **XIRR**, **TWROR**, and **cumulative return** include FD principal + opt-in bank cash where applicable (FD-ACC-8B/8C). Internal FD/bank movements are excluded from external-flow maps; manual deposits/withdrawals and opening-balance seeds are external.

**E2E audit (FD-ACC-9):** `test_fixed_deposit_end_to_end_accounting.py` — full lifecycle, renewal, excluded bank cash, unseeded balance, portfolio scope.

---

## Deferred / Not Yet Implemented

| Topic | Status |
|-------|--------|
| FD bank cash ledger (FD-ACC-1) | **Done** — `CashMovement`, `/cash-movements`, seed opening balance |
| Manual cash movement UI (FD-ACC-2) | **Done** — Settings bank account ledger panel |
| FD opening bank debit (FD-ACC-3) | **Done** — atomic on FD create; ledger balance as of `investment_date`; legacy FDs unchanged |
| FD interest/maturity/renewal (FD-ACC-5+) | **Done** (FD-ACC-4..6) |
| Transfer fees (Cash-8C) | Deferred |
| Same-portfolio FX conversion | Deferred |
| Display-currency cash totals on `/cash` page | Deferred |
| Dividends / interest / taxes ledger types | Deferred |
| Bulk quarterly/yearly frequencies | Planned |
| Automatic background sync (Celery/RQ) | Not configured |
| Dashboard performance optimization (shared series builder) | **Deferred** — acceptable for MVP (STAB-5B); backlog P1–P6 in [performance/dashboard-read-paths.md](./performance/dashboard-read-paths.md) |
| Expanded read-only diagnostics (settlement integrity, FX/NAV coverage) | **Done** (STAB-4) |
| Golden unit tests for all analytics formulas | Partial — see `test_finance_domain.py` |

## Quantitative Statistics / Metric Sheet — implemented

| Topic | Status |
|-------|--------|
| Portfolio / asset / compare APIs (Phase 5–7) | **Done** |
| Dashboard / Asset Detail / Compare Metric Sheet UI (Phase 8B–8D, 9B–13C) | **Done** |
| Periodic returns, drawdown periods/series, monthly grid, charts | **Done** |

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
| Scheme-only grouping / frontend MF CSV UX | MF-11 |

## Phase 6 contracts (verified in tests)
- FIFO cost basis, realized/unrealized P/L, stock split adjustments
- XIRR cashflow rules; TWROR chain-link helper (not exposed via API)
- Oversell: no hard reject; realized P/L uses full sell proceeds vs FIFO cost of held lots only
- TWROR: `compute_twror_series` in `finance/twror.py`; golden unit tests in `test_finance_domain.py`; exposed via performance API (Phase 10)
- Analytics Metric Sheet: **implemented** (Phase 5–13C) — see `docs/architecture.md` § Quantitative Statistics / Metric Sheet architecture

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
- All-scope `metric=value` performance uses per-portfolio timeseries → display-currency aggregation (matches summary; avoids pooled-base FX gaps e.g. PLN stock in EUR portfolio + INR MF)
- All-scope `metric=cumulative_return` / `twror` and portfolio Metric Sheet use the same display-currency value/flow aggregation for `portfolio_scope=all`
- All-scope display-currency conversion uses bulk `load_fx_rate_maps()` + in-memory 7-day FX fill (not per-day DB lookups)
- Display-currency conversion via cached FX; `fx_unavailable` when missing
- No yfinance on summary reads

## Phase 8 contracts (verified in tests)
- Incremental, idempotent `HistoricalPrice` upsert (stocks + INDEX benchmarks)
- Stock sync start date: earliest transaction when no cache; backfill from earliest transaction when cache starts later than first transaction; else latest cached date + 1
- Benchmark sync start date: earliest transaction anchor when no cache; backfill when anchor predates earliest cached index row; else latest cached index date + 1
- Stock symbols uppercased; benchmark symbols preserve `^` (e.g. `^GSPC`)
- FX: same-date lookup only (no latest-rate fallback for historical dates); sync backfills when earliest required date precedes earliest cached FX row
- All sync tests mock providers — no real network calls

## Test Status
- Backend: `make test-backend` — **1052 passed** (`DJANGO_TEST_USE_SQLITE=1`)
- Frontend: `make test-frontend` — **447 passed**; `npm run build` passes
- **STAB-3 targets:** `make test-fast` · `make test-critical` · `make test-all` — all green (STAB-6 verified 2026-06-06)
- Graphify: `make graphify` → `graphify update .`; `graphify-out/GRAPH_REPORT.md` tracked (refreshed FD-ACC-9 2026-06-14)

## MVP release QA (STAB-6 — 2026-06-06)

| Gate | Result |
|------|--------|
| Migrations | `makemigrations --check --dry-run` — no pending changes |
| DB safety | `make db-safety-check` — 67 transactions, 5 portfolios, 29277 prices |
| `make test-fast` | **127 passed** |
| `make test-critical` | **302 backend + 239 frontend passed** |
| `make test-all` | **840 backend + 384 frontend + build passed** |
| Diagnostics (Postgres, `santhoshkgvasudevan`) | All **exit 0** — settlement, negative cash, summary vs performance, FX, NAV clean |
| Dashboard profiler | No major regression vs STAB-5B; default parallel max ~433 ms (Metric Sheet 1Y) |
| Graphify | `make graphify` OK; `GRAPH_REPORT.md` updated |
| Manual golden-flow QA | **Complete** (MVP-RELEASE-1 — user browser sign-off) |
| Git working tree | **Dirty** — stabilization commit pending |

**Release verdict:** **MVP release-ready with accepted limitations** — ready to commit STAB/MVP stabilization; not production-deployed.

### Commit-prep summary (single stabilization commit)

| Area | Contents |
|------|----------|
| Docs / rules | `product-rules.md`, STAB-1 doc cleanup, `AGENTS.md`, `.cursor/rules/*`, `workflows.md`, `architecture.md`, `api-design.md` |
| Release artifacts | `mvp-release-checklist.md`, `api-contracts.md`, performance baseline docs |
| Test infrastructure | `make test-fast` / `test-critical` / `test-all`; `legacy_seeded` fixture hygiene (STAB-3B); 840 backend tests |
| Diagnostics | `backend/diagnostics/*`, five `diagnose_*.py` scripts, `test_diagnostics_integrity.py` |
| Performance | `profile_dashboard_read_paths.py`, STAB-5A/5B baseline and decision record |
| Frontend tests | Bulk Cash Entries coverage in `Cash.test.jsx` |
| Graphify | `Makefile` fix, `graphify-out/GRAPH_REPORT.md` |

## STAB maintenance (documentation)

| Phase | Status |
|-------|--------|
| STAB-0 | MVP maintenance baseline audit — **Done** |
| STAB-1 | Product rules index, doc cleanup, Graphify policy, TDD guardrails — **Done** |
| STAB-2 | MVP release checklist + API contracts index — **Done** |
| STAB-3 | `make test-fast` / `make test-critical` / `make test-all`; Bulk Cash Entries frontend tests — **Done** |
| STAB-3B | Full backend suite after cash-aware default — `legacy_seeded` fixture hygiene + MF XIRR FX setup — **Done** |
| STAB-4 | Read-only diagnostics scripts (settlement, negative cash, summary vs performance, FX/NAV coverage) — **Done** |
| STAB-5A | Dashboard read-path profiler + bottleneck report — **Done** |
| STAB-5B | Performance decision + optimization backlog (Postgres baseline; no refactor now) — **Done** |
| STAB-6 | MVP release QA execution (automated + diagnostics + profiler) — **Done** |
| MVP-RELEASE-1 | Manual golden-flow QA + release sign-off — **Done** (2026-06-06) |
| STAB-7 | Documentation index (`docs/README.md`) + cross-links — **Done** (2026-06-07) |
| CASH-HIST-1 | Historical settlement sync command + Assets cash balances UI — **Done** (2026-06-07) |
| CASH-UI-1 | Cash page full-width sections + ledger `details` column — **Done** (2026-06-07) |
| STAB-5C | Summary bulk loading / shared read context (when targets exceeded) — Planned |

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
