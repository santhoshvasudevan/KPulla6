# Page Layouts — KPulla6

Source of truth for **current page structure, page information, API usage, and redesign preservation contracts** after the Institutional Slate migration.

Related: [frontend-design.md](./frontend-design.md) (tokens, components, color semantics), [api-design.md](./api-design.md) (API contracts), [auth.md](./auth.md) (session auth), and `frontend/src/api.js` (frontend API wrapper truth).

---

## 1. Purpose and governance

| Rule | Detail |
|------|--------|
| **Authority** | This file defines intended layout and preservation requirements for every current routed frontend page. |
| **Change order** | Propose route, layout, API-call, state, warning, empty-state, or user-action changes here **first** -> human approval -> then code. |
| **API-driven UI** | React renders `/api/v1` values only. `frontend/src/api.js` is the frontend wrapper source of truth. |
| **Forbidden in React** | FIFO, FX conversion, valuation, XIRR, TWROR, benchmark math, Sharpe, Sortino, drawdown, and performance calculations. Display formatting (currency, percent, chart axis labels, pie tooltip %) is allowed. |
| **Auth/session** | Redesigns must preserve session cookies, CSRF handling, protected/public route behavior, and 401 redirects. |
| **Scope/currency** | Data pages must preserve `portfolioContext.apiQuery` propagation and wait for `settingsLoaded && apiQuery` where current pages do so. |
| **Design system** | Use UI primitives in `frontend/src/components/ui/`; see [frontend-design.md](./frontend-design.md). `DataTable` is deferred/optional, not mandatory. |

---

## 2. Global page layout principles

- **Institutional Slate** — calm, analytics-first; not terminal/neon styling.
- **Hierarchy** — KPIs and charts lead; tables support comparison; spacing over decoration.
- **Primitives** — `PageHeader`, `KpiCard`, `MetricCard`, `AppCard`, `ChartCard`, `ChartFrame`, `DataTableShell`, `AppTable`, `SectionCard`, `StatusBadge`, `AssetClassPill`, `WarningBanner`, `EmptyState`, `LoadingState`, `ErrorState`, `CurrencyValue`, `PercentValue`, `Button`, `SegmentedControl`.
- **Numbers** — right-aligned in tables (`num-col`); tabular nums via `--font-metric`.
- **Status** — `StatusBadge` / `WarningBanner`; never rely on color alone.
- **Warnings** — backend `warnings`, `price_status`, `fx_status`, `holding_status`, NAV, benchmark, cash shortfall, and future-impact messages must remain visible.
- **Read paths** — no frontend or read-path external market/NAV/FX provider calls; all values come from API responses backed by cached data.

---

## 3. App shell layout

**Files:** `frontend/src/App.jsx` · `frontend/src/components/Layout.jsx` · `frontend/src/components/Layout.css`  
**Providers:** `ThemeProvider` -> `AuthProvider` -> `BrowserRouter`; protected app pages wrap `PortfolioProvider` and `ProtectedRoute`.

| Zone | Content |
|------|---------|
| **Brand** | KPulla6 + “Executive Portfolio OS” subtitle; compact cached-data note (prices, NAVs, benchmarks, FX). |
| **Top nav** | Dashboard (`/`), Transactions (`/transactions`), Cash (`/cash`), Assets (`/assets`), Fixed Deposits (`/fixed-deposits`), Compare (`/compare`), Settings (`/settings`). Single authoritative global navigation — no duplicate left sidebar. |
| **Header controls** | Portfolio View select, Display Currency select, Theme selector, signed-in user label, Log out. |
| **Notice** | `WarningBanner` if portfolio list fetch fails; shell falls back to All Portfolios copy. |
| **Main** | Centered `<Outlet />` in `app-main__inner` (max-width ~1520px, padded). No permanent left context sidebar. |

**Navigation architecture (P4.4):** One global top nav for all routes. Page-local navigation is in-page section anchors only (Dashboard, Assets, Asset Detail, Fixed Deposits, Compare, Settings) — not duplicate global route menus.

**Route behavior:** `/login`, `/register`, and `/forgot-password` are public-only routes. `/`, `/transactions`, `/cash`, `/assets`, `/assets/:assetSymbol`, `/fixed-deposits`, `/compare`, and `/settings` are protected routes. `/dashboard` redirects to `/`; unknown routes redirect to `/`.

**Auth/session preservation:** `AuthProvider` calls `ensureCsrfCookie()` then `fetchCurrentUser()` on load. Login/register call CSRF first, then auth APIs. `setUnauthorizedHandler()` redirects non-auth `/api/v1/*` 401 responses to `/login`. Logout calls `POST /auth/logout`, clears user state, and navigates to `/login`.

**Context/API preservation:** `PortfolioProvider` loads `fetchPortfolios()` and `getSettings()`. `apiQuery` is `null` until settings are loaded and a display currency exists; data pages that currently wait for `settingsLoaded && apiQuery` must keep that gate. Sidebar display currency is disabled while settings load and persists through `updateSettings()`.

**Tests:** `App.test.jsx`, `Layout.test.jsx`, `auth.test.js`, `portfolioContext.test.jsx`, `themeContext.test.jsx`, `theme/themeStorage.test.js`.

---

## 4. Dashboard (`/`)

**Files:** `pages/Dashboard.jsx` · `pages/Dashboard.css`

**Layout status:** **Implemented (P4)** — Executive Portfolio OS overview with performance center and Metric Sheet.

| Section | Layout |
|---------|--------|
| **Header** | `PageHeader` — title “Portfolio Overview”; subtitle: portfolio name · display currency · cached data note. |
| **Section nav** | Sticky in-page anchors: Overview, Performance, Allocation, Health, Metric Sheet. Anchor targets use shell offset (`scroll-margin-top`) so headings clear the sticky header and section nav. |
| **KPI row** | Grid of `KpiCard`: Current Value (hero), Total Invested, Total P/L, XIRR; optional Realized/Unrealized P/L when API provides. |
| **FX warning** | `WarningBanner` if `summary.fx_status === 'fx_unavailable'`. |
| **Primary chart** | `ChartFrame` performance chart; metric (`value` / `cumulative_return` / `twror`), range pills (`7D`-`ALL`), benchmark selector for return metrics, benchmark warnings, empty state. |
| **Metric Sheet** | Portfolio Metric Sheet section below the performance chart; independent loading/error state; summary cards, risk/return, benchmark, periodic returns, yearly return chart, drawdown chart/table, monthly heatmap. |
| **Secondary chart** | Compact `ChartFrame` “Invested vs Current” — horizontal bar comparison from backend summary totals. |

**States:** `LoadingState`, `ErrorState`, chart empty state, Metric Sheet section-local error, backend warnings, stale-response guards when scope/currency/range/benchmark changes.

**APIs:** `fetchDashboardSummary(apiQuery, { includeTimeseries: false })`, `fetchPortfolioPerformance(metric, benchmark, range, apiQuery)`, `fetchBenchmarkIndices()`, `getPortfolioMetricSheet(params)`.

**Preserve in redesign:** current behavior includes the Invested vs Current chart. Any future removal must be proposed in this file and approved before implementation. Dashboard must not request summary timeseries for KPI-only load and must not compute performance, FX, allocation, or Metric Sheet values in React.

**Tests:** `Dashboard.test.jsx`, `metricSheet.test.jsx`, `api.test.js`.

---

## 5. Assets (`/assets`)

**Files:** `pages/Assets.jsx` · `pages/Assets.css`

**Layout status:** **Implemented (P6)** — holdings and allocation hub using Executive Portfolio OS primitives.

| Section | Layout |
|---------|--------|
| **Header** | `PageHeader` — title “Assets Overview”; subtitle with portfolio, display currency, active position count; cached-price guidance note. |
| **Overview** | Compact `KpiCard` strip: active positions, allocation slices, cash currency count (display-only counts from API arrays). |
| **FX warning** | Warning when display currency differs from holdings and `fx_status === 'fx_unavailable'`. |
| **Cash balances** | `DataTableShell` + `AppTable` with `AssetClassPill` for cash rows; not clickable to asset detail. |
| **Section nav** | Sticky in-page anchors: Holdings, Allocation. |
| **Holdings** | `DataTableShell` + sortable `AppTable`: `AssetClassPill`, status badges, right-aligned numerics, row click → asset detail (except FD/bank cash). |
| **Allocation** | `ChartCard` donut from backend `allocation`; display-only tooltip percentages. |
| **Closed holdings** | `AppCard` + nested `DataTableShell` for previous holdings; collapsed by default. |

**States:** loading, API error, empty assets, chart empty when all current values are zero, price/NAV/FX warnings.

**API:** `fetchHoldings(apiQuery)`.

**Preserve in redesign:** cash rows may appear in allocation/cash balance sections but must not become clickable investment rows or Compare subjects. React may calculate display-only chart percentages, but not valuations.

**Tests:** `Assets.test.jsx`, `transactionDisplay.test.js`.

---

## 6. Asset Detail (`/assets/:assetSymbol`)

**Files:** `pages/AssetDetail.jsx` · `pages/AssetDetail.css`

**Layout status:** **Implemented (P6)** — premium asset Metric Sheet layout using Executive Portfolio OS primitives.

| Section | Layout |
|---------|--------|
| **Header** | Metric Sheet `PageHeader` with `AssetClassPill` eyebrow, symbol title, breadcrumb to Assets, scope/currency subtitle. |
| **Warnings** | FX and API `warnings[]` banners. |
| **Hero KPIs** | `KpiCard` grid: Current Value (hero), Quantity, Unrealized P/L, XIRR — backend values only. |
| **Section nav** | Sticky in-page anchors: Overview, Metrics, Details, Transactions. |
| **Metric Sheet** | `AssetDetailMetricSheet` at `#asset-metrics`; local range/benchmark; `folio_number` when present. |
| **Details** | `AppCard` grid: Position/Cost Basis, Market/Valuation, Data Quality badges. |
| **Transaction History** | `DataTableShell` + `AppTable` with `.ui-txn-type` badges and split column. |

**States:** waits for `settingsLoaded && apiQuery`, loading, API error, empty transaction history, Metric Sheet section-local error, folio guidance when backend requires `folio_number`.

**APIs:** `fetchAssetDetails(assetSymbol, apiQuery)`, `getAssetMetricSheet(assetSymbol, params)`.

**Preserve in redesign:** MF folio-specific behavior, backend warnings, split/price/NAV data quality, and no client-side FIFO/XIRR/Metric Sheet math.

**Tests:** `AssetDetail.test.jsx`, `metricSheet.test.jsx`, `transactionDisplay.test.js`.

---

## 7. Transactions (`/transactions`)

**Files:** `pages/Transactions.jsx` · `pages/Transactions.css` · `components/TransactionModal.jsx` · `components/TransactionModal.css`

**Layout status:** **Implemented (P5)** — premium activity ledger page using Executive Portfolio OS table primitives.

| Section | Layout |
|---------|--------|
| **Header** | `PageHeader` — title “Transactions”; subtitle with record count; actions: hidden file input, Import CSV, Add Transaction. |
| **Cash-aware** | `CashAwarePortfolioStatus`; enable button for single legacy portfolio; all-scope note otherwise. |
| **Import guidance** | Info banner (import target portfolio, stock split/SWAP rules); expandable “Supported CSV formats” with stock vs mutual fund columns, MF sample download. |
| **Filters** | `AppCard` + `TransactionFilterBar`: portfolio dropdown, searchable symbol multi-select, date modes Earlier than / Later than / Between, active chips, Clear filters. |
| **CSV cash preview** | On file select, `previewCsvImportCash`; shortfall modal with proposed deposits; confirmed import sends `create_cash_deposits=true` and `cash_preview_confirmed=true`. |
| **Import feedback** | Success/warning banner and row-level error list. |
| **Ledger table** | `DataTableShell` + `AppTable`: checkbox, Portfolio, Symbol/Scheme, Folio/NAV status for MF rows, Date, Type badges (`.ui-txn-type`), Qty/Units, Price/NAV, Fees, Total (`AppTableCell numeric`), Actions. |
| **Pagination** | `page_size` 20/50/100; Previous/Next when `total > page_size`; filters persist across pagination. |
| **Bulk assign** | Selected visible rows -> toolbar with real-portfolio dropdown; full PUT payload per selected row; preserves stock, MF, and `STOCK_SPLIT` fields; partial failure banner. |
| **Edit/delete** | Edit opens `TransactionModal`; delete confirms; future-impact 409 renders `CashFutureImpactDisplay`; generic errors use `WarningBanner`. |
| **Modal** | Add record type Cash / Stock / Mutual Fund. Stock supports BUY/SELL/DIVIDEND/STOCK_SPLIT; MF uses backend field names; cash posts to `/cash/*` and is edited on `/cash`. |

**States:** loading, API error, empty table, invalid Between date suppresses request, import success/error, CSV cash preview modal, delete future-impact, bulk partial failure, cash shortfall/add-and-continue states.

**APIs:** `fetchTransactions(page, pageSize, apiQuery, filters)`, `fetchTransactionFilterOptions(apiQuery)`, `createTransaction`, `updateTransaction`, `deleteTransaction`, `previewCsvImportCash`, `importTransactionsCsv`, `createCashDeposit`, `createCashWithdrawal`.

**Preserve in redesign:** filters apply before backend pagination; `portfolio_scope=all` and `portfolio_id` must not be sent together; MF CSV/manual fields must keep backend names; CSV cash deposits require user confirmation; cash is never posted as `asset_type=CASH`; no client-side cash balance/future-impact simulation. SELL proceeds preview is display-only; backend computes settlements and tax-withheld rows.

**Tests:** `Transactions.test.jsx`, `TransactionModal.test.jsx`, `csvImportGuidance.test.js`, `transactionPayload.test.js`, `transactionDisplay.test.js`, `purchaseShortfallHelpers.test.js`, `api.test.js`.

---

## 8. Cash (`/cash`)

**Files:** `pages/Cash.jsx` · `pages/Cash.css` · `components/CashBulkEntriesWizard.jsx`

**Layout status:** **Implemented (P5 + CASH-UNIFY-3..4A)** — unified Cash / Liquid Holdings page; stream complete (MILESTONE-CLOSEOUT-1). [cash-unification.md](./cash-unification.md) §5.

| Section | Layout |
|---------|--------|
| **Header** | `PageHeader` — title **Cash / Liquid Holdings**; subtitle explains separate broker vs bank ledgers; **Broker Cash actions**: Add Deposit, Add Withdrawal, Add Bulk Cash Entries, Transfer Cash. |
| **Overview** | `KpiCard` strip from `GET /cash/overview` totals: **Total Cash**, **Broker Cash**, **Bank Cash** (display currency when FX available). |
| **Cash-aware** | `CashAwarePortfolioStatus`; enable for selected legacy portfolio; all-scope explanatory note. |
| **Broker Cash** | `DataTableShell` + `AppTable` from overview `BROKER_CASH` rows (portfolio, account label, currency, native + display balance, available for, source). |
| **Bank Cash** | `DataTableShell` + `AppTable` from overview `BANK_CASH` rows — read-only; assignment status; include-in-portfolio-value; link → Settings → Bank Accounts. |
| **Exclusions** | Warnings/counts for unlinked/ambiguous banks; always-visible toggle **Show unassigned / ambiguous bank accounts** (`include_unassigned`); copy warns not to add duplicate bank cash when reversing mistaken broker entries |
| **Broker ledger** | `AppCard` with filter bar + nested `DataTableShell` + `AppTable`; manual edit/delete/**reverse** on eligible broker rows only. |
| **Bulk / transfer** | Unchanged broker write flows (`CashBulkEntriesWizard`, transfer modal). |

**States:** overview loading/error/empty, per-section empty (no broker / no bank / no cash), ledger loading/error/empty, write success/error, withdrawal shortfall, future-impact panel, FX partial warning, excluded bank account warning.

**APIs:** `fetchCashOverview` (overview KPIs + tables), `fetchCashLedger`, broker write endpoints. `fetchCashBalances` remains in `api.js` but Cash page no longer calls it.

**Preserve:** React displays backend overview/ledger only. Bank cash rows are **read-only** on this page. No bank movement CRUD here.

**Known verification (CASH-UNIFY-3A):** Resolved 2026-06-25 — overview `ledger_type` filtering, source diagnostics, broker actions in header, always-on unassigned toggle. See [004a-cash-unify-3a.md](./backlog/004a-cash-unify-3a.md).

**Tests:** `Cash.test.jsx`, `CashAwarePortfolioStatus.test.jsx`, `api.test.js`.

---

## 9. Fixed Deposits (`/fixed-deposits`)

**Files:** `pages/FixedDeposits.jsx` · `pages/FixedDeposits.css` · `pages/FixedDepositDetail.jsx` · `utils/fdDisplay.js`

**Status:** **Redesigned (P7)** — Executive Portfolio OS layout; FD-HOLDINGS-UX-1 adds maturity display fallback + action strip; **FD-DETAIL-CALC-1** adds `/fixed-deposits/:id` detail page.

| Section | Layout |
|---------|--------|
| **Holdings table** | Clickable data row → detail page; action strip below (stopPropagation) |
| **Detail page** | Breadcrumb, KPI strip, FD details card, FY filter, expected schedule table, detailed calculation, Record/Edit actual modal with 10% tax shortcut |

| Section | Layout |
|---------|--------|
| **Header** | `PageHeader` with FD/debt workflow subtitle and Add Fixed Deposit primary action. |
| **Overview** | `KpiCard` strip: total deposits, active, matured, settled/closed counts from backend status fields only (no finance math). |
| **Section nav** | Sticky Overview \| Deposits \| Interest & Tax anchor links (`#fd-overview`, `#fd-deposits`, `#fd-interest-report`). |
| **Table** | `DataTableShell` + `AppTable`: institution, deposit account, principal (right-aligned), rate, investment/maturity dates, payout frequency (`fdPayoutLabel`), **maturity value** (compounded uplift or payout principal) + source badge + interest sublines (`fdDisplay` helpers), `StatusBadge` lifecycle status. |
| **Create/edit preview (FD-INTEREST-MATURITY-LOGIC-1)** | Compounded: **Expected maturity value** card. Payout: **Expected interest payout** — principal returned at maturity, periodic + total interest estimates, simple payout method note. |
| **Action strip (FD-HOLDINGS-UX-1)** | Full-width row below each FD: grouped buttons (Record interest, Interest payments \| Mark matured, Settle/Close, Renew \| Edit, Cancel FD, Deactivate); responsive wrap; Cancel uses danger styling. |
| **Interest history** | Expandable nested `AppTable` per FD row; backend payment fields only. |
| **Bank account dependency** | Fetches active bank accounts and portfolios. Create is blocked/guided when no active bank account exists. |
| **Create modal** | Portfolio dropdown (required); bank account dropdown as funding source; copy explains funding vs tracking; currency read-only from selected bank account; principal/rate/dates/status; shows **current** and **as-of investment date** ledger balances (balance API); insufficient as-of balance shows missing amount + inline **Seed missing balance** panel (`seed-balance` API); Cash tab vs Bank Ledger note; structured insufficient-balance error panel with auto-scroll/focus. |
| **Edit modal** | Existing FD fields; principal/bank/currency/investment date/portfolio disabled when `has_opening_cash_movement`; backend errors remain visible. |
| **Cancel / Deactivate** | **Cancel FD** (`POST /fixed-deposits/{id}/cancel`) — mistaken ledger-backed `ACTIVE`/`MATURED` only; reverses `FD_OPENING`; confirmation explains bank debit reversal. **Deactivate** (`DELETE`) — legacy FDs without opening movement only (**409** when ledger-backed). **Not** settle/renew — those record real institution events. |
| **Interest payments** | Expand/list per-FD payments; Record Interest modal with payment date, gross interest, tax withheld, display-only net; backend warnings (e.g. compounded FD) shown. |
| **Maturity/settlement** | Mark Matured for active FDs; Settle/Close modal with principal returned, gross final interest, tax withheld, display-only net/total; settled/closed rows hide settlement actions. |
| **Renewal** | Renew action for eligible ACTIVE/MATURED FDs; modal with new terms, direct rollover, cash payout, tax fields, bank cash warnings; hidden when settled or already renewed. |
| **Interest & Tax report (FD-TAX-1 / FD-TAX-1A / FD-TAX-2)** | Default range = current calendar year; date + group-by filters (incl. **Bank account**); **Reset filters**; KPI cards (gross/tax/net/row count); grouped totals with readable labels; exclusion/disclaimer notes; FX/mixed-currency warnings near totals; improved empty state; **Export CSV** (header actions; uses current filters). Read-only — no accounting changes. |

**States:** waits for `settingsLoaded && apiQuery`, loading, API error, empty list, no-bank-account warning, unseeded opening balance warning, insufficient ledger warning/error, lifecycle success/error banners, report empty/error states.

**APIs:** `fetchFixedDeposits(apiQuery)`, `fetchPortfolios`, `fetchBankAccounts`, `createFixedDeposit`, `updateFixedDeposit`, `deleteFixedDeposit`, `cancelFixedDeposit`, `fetchFixedDepositInterestPayments`, `createFixedDepositInterestPayment`, `reverseFixedDepositInterestPayment`, `markFixedDepositMatured`, `settleFixedDeposit`, `renewFixedDeposit`, `fetchFixedDepositInterestReport`.

**Exported but not currently page-used:** `fetchFixedDepositInterestPayment`, `fetchFixedDepositSettlements`, `fetchFixedDepositSettlement` are API-client helpers for implemented detail endpoints and should be treated as intentional available wrappers unless removed in a future API cleanup.

**Accounting/cash display rules:** React displays backend FD principal, ledger balance, warning, lifecycle, and cash-impact fields only. No accrued interest, FD IRR, bank cash, settlement, tax, or portfolio value calculations in React. Interest/settlement credits and included bank cash behavior are backend-owned.

**Tests:** `FixedDeposits.test.jsx`, `BankAccountManagement.test.jsx`, `CashMovementManagement.test.jsx`, `api.test.js`.

**Preserve in redesign:** bank account dependency, ledger-derived balance copy, opening movement immutability, lifecycle action visibility, renewal constraints, backend warnings, and no frontend accounting math.

---

## 10. Compare (`/compare`)

**Files:** `pages/Compare.jsx` · `pages/Compare.css` · `utils/compareDisplay.js` · `components/metricSheet/*`

**Status:** **Redesigned (P8)** — Executive Portfolio OS analytics workstation; no backend/API behavior changes.

| Section | Layout |
|---------|--------|
| **Header** | `PageHeader` with portfolio scope, display currency, and quantitative comparison subtitle. |
| **Setup panel** | `AppCard` with asset pickers, selected-subject chips, `ChartControls` (range `SegmentedControl` + benchmark selector). |
| **Section nav** | Sticky Setup \| Chart \| Metrics \| Periods \| Drawdowns anchor links. |
| **Summary KPIs** | `KpiCard` strip: per-subject cumulative return and common point count from backend payload only. |
| **Normalized chart** | `ChartFrame` + `ChartLegend` + `CompareNormalizedChart` (`hideLegend`); backend `normalized_series` only. |
| **Metric comparison** | `AppCard` + `CompareMetricTable` side-by-side return, risk, drawdown, optional benchmark metrics. |
| **Periodic/drawdown sections** | `ComparePeriodicReturnsSection` and `CompareDrawdownPeriodsSection` unchanged in behavior. |
| **Warnings/context** | `MetricSheetWarnings`, subject-level warnings, common overlap note. |

**States:** waits for `settingsLoaded && apiQuery`, holdings loading/error, fewer-than-two holdings empty state, same-subject validation, compare loading/error, normalized chart empty, backend warnings, calm MF multi-folio error when backend requires folio selection.

**APIs:** `fetchHoldings(apiQuery)`, `fetchBenchmarkIndices()`, `getCompareMetricSheet({ subjects, range, benchmark, portfolio scope, display_currency })`.

**Preserve in redesign:** exactly two asset subjects, no cash subjects, current MF multi-folio backend-error handling, backend common-window semantics, XIRR full-scope note, benchmark propagation, and no frontend Sharpe/beta/return/drawdown calculations.

**Tests:** `Compare.test.jsx`, `metricSheet.test.jsx`, `compareMetricRanking.test.js`, `compareHoldings.test.js`, `metricSheetCopy.test.js`, `api.test.js`.

---

## 11. Settings (`/settings`)

**Files:** `pages/Settings.jsx` · `pages/Settings.css` · `components/PortfolioManagement.jsx` · `components/BankAccountManagement.jsx` · `components/CashMovementManagement.jsx`

**Status:** **Redesigned (P9)** — centered settings workspace; no backend/API behavior changes.

| Section | Layout |
|---------|--------|
| **Header** | `PageHeader` with workspace subtitle. |
| **Section nav** | Sticky Display \| Portfolios \| Bank Accounts \| Data Sync anchor links. |
| **Display & tax** | `AppCard` with responsive form grid: tax rate, display currency, Save button, success/error banners. |
| **Portfolios** | `AppCard` wrapping `PortfolioManagement` — CRUD, max active enforcement, cash-aware toggle. |
| **Bank accounts** | `AppCard` with `BankAccountManagement` (linked portfolio column; link/change-link **modal**; delink action; helper text) and nested `CashMovementManagement`. |
| **Portfolio / currency** | Header **Portfolio View** selector; **Display Currency** auto-syncs to portfolio `base_currency` on portfolio switch when supported (4B); **All Portfolios** preserves current display currency; unsupported base unchanged. |
| **Data & sync** | `AppCard` with cached-data and backend refresh guidance (no live sync UI). |

**States:** initial loading/error, settings save success/error, portfolio validation errors, bank-account ledger/unseeded warnings, cash movement errors.

**APIs:** `getSettings`, `updateSettings`, `createPortfolio`, `updatePortfolio`, `deletePortfolio`, `fetchBankAccounts`, `createBankAccount`, `updateBankAccount`, `deleteBankAccount`, `seedBankAccountOpeningBalance`, `fetchCashMovements`, `createCashMovement`, `reverseCashMovement`, `reloadPortfolios()`.

**Preserve in redesign:** display currency must stay synchronized with header portfolio/currency context; All Portfolios remains virtual and cannot be created/assigned; default portfolio cannot be deactivated; bank ledger/current balance rules are backend-owned.

**Tests:** `Settings.test.jsx`, `BankAccountManagement.test.jsx`, `CashMovementManagement.test.jsx`, `Layout.test.jsx`.

---

## 12. Auth pages (`/login`, `/register`, `/forgot-password`)

**Files:** `pages/auth/Login.jsx` · `pages/auth/Register.jsx` · `pages/auth/ForgotPassword.jsx` · `pages/auth/AuthShell.jsx` · `pages/auth/Auth.css`

**Status:** **Redesigned (P10)** — Executive Portfolio OS auth shell; no backend/API behavior changes.

| Route | Layout |
|-------|--------|
| `/login` | Centered `AuthShell` with KPulla6 brand, credential form, Google sign-in, forgot/register links. |
| `/register` | Registration form with validation errors and Google sign-in. |
| `/forgot-password` | Email reset form with success/error states and back-to-login link. |

**Global polish (P10):** sticky section-nav horizontal scroll on small screens; shared focus-visible states; dark-mode card border refinement; header nav scrollbar styling.

**Google OAuth:** `GoogleSignInButton` calls `window.location.assign('/accounts/google/login/?process=login')`; Vite proxies `/accounts` to Django/allauth. Successful allauth login redirects to `FRONTEND_URL/`.

**CSRF/session:** `AuthProvider` ensures CSRF cookie on app load and before login/register. `fetchWithHandling` uses `credentials: 'include'` and adds `X-CSRFToken` for unsafe methods when the `csrftoken` cookie exists.

**401 redirect:** non-auth API 401 responses call the unauthorized handler and navigate to `/login`.

**States:** auth loading in protected/public route wrappers, form submitting, inline error messages, password reset success/detail message.

**Tests:** `App.test.jsx`, `auth.test.js`, `Login.test.jsx`, `Register.test.jsx`, `ForgotPassword.test.jsx`, `AuthShell.test.jsx`.

**Preserve in redesign:** session-cookie auth, CSRF bootstrap, public-only auth pages, protected app redirects, post-login/register redirect to dashboard, Google OAuth path, and visible backend validation messages.

---

## 13. Frontend Redesign API Preservation Checklist

- `frontend/src/api.js` is the source of frontend API wrapper truth; do not infer endpoint usage from visual pages alone.
- Before redesigning a route, map every API wrapper it uses to a page/feature in this document.
- Exported but unused wrappers must be marked intentional, planned/deferred, or removed in an approved cleanup. Current intentionally available wrappers include `fetchHealth`, `refreshPrices`, `forceSyncPortfolio`, `fetchFixedDepositInterestPayment`, `fetchFixedDepositSettlements`, and `fetchFixedDepositSettlement`.
- Redesign work must not silently drop API calls, query params, warning fields, empty states, loading gates, or user actions documented here.
- Preserve `credentials: 'include'`, CSRF header behavior, auth endpoints, `setUnauthorizedHandler`, and protected/public route behavior.
- Preserve `portfolio_scope=all` vs `portfolio_id` exclusivity and `display_currency` propagation through `apiQuery`.
- Preserve `settingsLoaded` readiness gates where current pages wait before fetching scoped APIs.
- Preserve no-read-path external provider rules: no yfinance, AMFI/MFAPI, live FX, NAV, or benchmark provider calls from frontend/read pages.
- Preserve the no-frontend-finance rule: no FIFO, valuation, FX conversion, XIRR, TWROR, Sharpe, Sortino, beta, alpha, drawdown, cash balance, or future-impact calculations in React.

---

## 14. Layout change process

1. **Update** this file with the proposed layout/API/state/action change.
2. **Mark** the change **Proposed** (use template below).
3. **Wait** for user approval.
4. **Implement** approved change in React/CSS only after approval.
5. **Update** Vitest/RTL tests if structure, roles, visible text, API params, or state behavior changes.
6. **Record** in `docs/changelog.md`.
7. **Mark** the change **Implemented** in this file.

---

## 15. Proposed change template

```markdown
### [Short title]

- **Page:** (route)
- **Current layout:** (brief)
- **Proposed layout change:** (brief)
- **Reason:** (why)
- **API impact:** None | describe endpoint/field/query-param changes
- **Frontend state impact:** None | describe loading/error/empty/warning/action changes
- **Components affected:** (list)
- **Tests required:** (list)
- **Approval status:** Proposed | Approved | Implemented
```

---

## 16. Page ownership table

| Route | React | CSS | Primary components | API calls | Layout status |
|-------|-------|-----|-------------------|-----------|---------------|
| `/login` | `pages/auth/Login.jsx` | `auth/Auth.css` | AuthShell, GoogleSignInButton, Button | auth login via `useAuth`, CSRF | **Implemented (P10)** |
| `/register` | `pages/auth/Register.jsx` | `auth/Auth.css` | AuthShell, GoogleSignInButton, Button | auth register via `useAuth`, CSRF | **Implemented (P10)** |
| `/forgot-password` | `pages/auth/ForgotPassword.jsx` | `auth/Auth.css` | AuthShell, Button | password reset | **Implemented (P10)** |
| `/` | `pages/Dashboard.jsx` | `Dashboard.css` | PageHeader, KpiCard, ChartFrame, Metric Sheet, SegmentedControl | summary, performance, benchmarks, portfolio Metric Sheet | **Implemented (P4)** |
| `/transactions` | `pages/Transactions.jsx` | `Transactions.css` | PageHeader, AppCard, DataTableShell, AppTable, TransactionModal, filter bar, WarningBanner | transactions CRUD, filter options, CSV import, CSV cash preview | **Implemented (P5)** |
| `/cash` | `pages/Cash.jsx` | `Cash.css` | PageHeader, KpiCard, AppCard, DataTableShell, AppTable, CashBulkEntriesWizard, CashAwarePortfolioStatus | cash balances, ledger, deposits, withdrawals, transfers, bulk entries | **Implemented (P5)** |
| `/assets` | `pages/Assets.jsx` | `Assets.css` | PageHeader, KpiCard, DataTableShell, AppTable, AssetClassPill, ChartCard | holdings/allocation | **Implemented (P6)** |
| `/assets/:assetSymbol` | `pages/AssetDetail.jsx` | `AssetDetail.css` | PageHeader, KpiCard, AppCard, DataTableShell, AssetDetailMetricSheet | asset detail, asset Metric Sheet | **Implemented (P6)** |
| `/fixed-deposits` | `pages/FixedDeposits.jsx` | `FixedDeposits.css` | PageHeader, KpiCard, DataTableShell, AppTable, StatusBadge, lifecycle modals | fixed deposits, portfolios, bank accounts, interest, settlement, renewal | **Implemented (P7)** |
| `/compare` | `pages/Compare.jsx` | `Compare.css` | PageHeader, AppCard, ChartFrame, ChartLegend, KpiCard, CompareNormalizedChart, CompareMetricTable | holdings, benchmarks, compare Metric Sheet | **Implemented (P8)** |
| `/settings` | `pages/Settings.jsx` | `Settings.css` | PageHeader, AppCard, PortfolioManagement, BankAccountManagement, CashMovementManagement | settings, portfolios, bank accounts, cash movements | **Implemented (P9)** |
| `(shell)` | `components/Layout.jsx` | `components/Layout.css` | nav, selectors, ThemeSelector, WarningBanner | portfolios, settings, auth logout | **Implemented (P4.4)** |

**Shared:** `components/ui/*`, `components/metricSheet/*`, `components/charts/chartTheme.js`, `frontend/src/api.js`, `portfolioContext.jsx`, `authContext.jsx`, `themeContext.jsx`.

---

## Document history

| Date | Change | Status |
|------|--------|--------|
| 2026-05-25 | Initial layout spec post design migration | Implemented |
| 2026-05-27 | Settings portfolio CRUD; Transactions bulk assign | Implemented |
| 2026-06-19 | Frontend redesign readiness governance expansion: app shell, auth, Compare, Cash, Fixed Deposits, Transactions, API preservation checklist | Implemented |
| 2026-06-22 | P4.4 navigation architecture: single top nav, no duplicate left sidebar, Dashboard in-page anchors only | Implemented |
| 2026-06-22 | P4R: Dashboard anchor scroll offset; Settings left-heavy layout deferred to P9 | Implemented |
| 2026-06-23 | P5: Transactions and Cash redesigned as premium ledger/overview pages; no API/backend changes | Implemented |
| 2026-06-23 | P6: Assets and Asset Detail redesigned as holdings hub and asset Metric Sheet; no API/backend changes | Implemented |
| 2026-06-23 | P7: Fixed Deposits redesigned with KPI overview, lifecycle badges, premium table; no API/backend changes | Implemented |
| 2026-06-23 | P8: Compare redesigned as analytics workstation with setup panel, ChartFrame, KPI strip; no API/backend changes | Implemented |
| 2026-06-23 | P9: Settings redesigned as centered workspace with section nav and AppCard sections; no API/backend changes | Implemented |
| 2026-06-23 | P10: Auth pages redesigned; global responsive/dark-mode polish; no API/backend changes | Implemented |
| 2026-06-23 | P11: Final frontend redesign audit — all routes verified; docs aligned; redesign complete | Implemented |

---

## 17. Final redesign audit (P11)

**Verdict:** Executive Portfolio OS frontend redesign **complete** for all routed pages (P4–P10). No structural page changes in P11; documentation and minor label polish only.

| Area | Result |
|------|--------|
| **Route coverage** | 11/11 routes migrated: Dashboard (P4), Transactions/Cash (P5), Assets/Asset Detail (P6), Fixed Deposits (P7), Compare (P8), Settings (P9), Login/Register/Forgot Password (P10). |
| **Navigation** | Single top nav (7 authenticated routes); no permanent left sidebar; page-local anchors only; auth routes exclude app shell. |
| **Design system** | Shared primitives in `components/ui/` and `components/charts/`; token-based light/dark via `index.css` + `ThemeSelector`. |
| **Behavior/API** | `api.js` contracts unchanged; `settingsLoaded && apiQuery` gates preserved; CSRF/session/401 redirect intact. |
| **Finance safety** | No new client-side valuation, FIFO, FX, XIRR, drawdown, or benchmark math; display/format/sort/filter only. |
| **Tests** | `make test-frontend` — 534 passed at P11 audit; route inventory, Layout, auth, and per-page suites cover redesigned surfaces. |

### Deferred (post-redesign, not blockers)

| Item | Notes |
|------|--------|
| Compare per-folio MF selection | Backend requires `folio_number`; calm error only — no per-folio picker UX yet. |
| In-app data sync UI | Settings documents CLI/API refresh; no live sync button by design. |
| Unused API wrappers | `fetchHealth`, `refreshPrices`, `forceSyncPortfolio`, FD settlement detail helpers — intentional exports. |
| `DataTable` generic component | Deferred; `DataTableShell` + `AppTable` used instead. |
| CSS class prefix `app-sidebar__*` | Legacy naming on header controls; behavior is top-nav shell (rename optional cleanup). |
| `docs/current-state.md` test counts | May lag; trust `make test-frontend` for current totals. |

