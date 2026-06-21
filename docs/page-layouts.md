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
- **Primitives** — `PageHeader`, `MetricCard`, `ChartCard`, `SectionCard`, `StatusBadge`, `WarningBanner`, `EmptyState`, `LoadingState`, `ErrorState`, `CurrencyValue`, `PercentValue`, `Button`, `SegmentedControl`.
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
| **Brand** | “Portfolio Insight” + subtitle. |
| **Sidebar controls** | Portfolio View select (`All Portfolios` virtual + active real portfolios) and Display Currency select (`EUR`, `USD`, `INR`, `GBP`, `CHF`) directly below brand. |
| **Nav** | Dashboard (`/`), Transactions (`/transactions`), Cash (`/cash`), Assets (`/assets`), Fixed Deposits (`/fixed-deposits`), Compare (`/compare`), Settings (`/settings`). Active route uses left accent + raised surface. |
| **Notice** | `WarningBanner` if portfolio list fetch fails; shell falls back to All Portfolios copy. |
| **Footer** | Cached prices/FX note. |
| **Top header** | `ThemeSelector` (System / Light / Dark), signed-in user label (`email` or `username`), Log out button. |
| **Main** | `<Outlet />` in `app-main__inner` (max-width ~1400px, padded). |

**Route behavior:** `/login`, `/register`, and `/forgot-password` are public-only routes. `/`, `/transactions`, `/cash`, `/assets`, `/assets/:assetSymbol`, `/fixed-deposits`, `/compare`, and `/settings` are protected routes. `/dashboard` redirects to `/`; unknown routes redirect to `/`.

**Auth/session preservation:** `AuthProvider` calls `ensureCsrfCookie()` then `fetchCurrentUser()` on load. Login/register call CSRF first, then auth APIs. `setUnauthorizedHandler()` redirects non-auth `/api/v1/*` 401 responses to `/login`. Logout calls `POST /auth/logout`, clears user state, and navigates to `/login`.

**Context/API preservation:** `PortfolioProvider` loads `fetchPortfolios()` and `getSettings()`. `apiQuery` is `null` until settings are loaded and a display currency exists; data pages that currently wait for `settingsLoaded && apiQuery` must keep that gate. Sidebar display currency is disabled while settings load and persists through `updateSettings()`.

**Tests:** `App.test.jsx`, `Layout.test.jsx`, `auth.test.js`, `portfolioContext.test.jsx`, `themeContext.test.jsx`, `theme/themeStorage.test.js`.

---

## 4. Dashboard (`/`)

**Files:** `pages/Dashboard.jsx` · `pages/Dashboard.css`

| Section | Layout |
|---------|--------|
| **Header** | `PageHeader` — title “Portfolio Overview”; subtitle: portfolio name · display currency. |
| **KPI row** | Grid of `MetricCard`: Current Value (hero), Total Invested, Total P/L, XIRR; optional Realized/Unrealized P/L when API provides. |
| **FX warning** | `WarningBanner` if `summary.fx_status === 'fx_unavailable'`. |
| **Primary chart** | `ChartCard` performance chart; metric (`value` / `cumulative_return` / `twror`), range pills (`7D`-`ALL`), benchmark selector for return metrics, benchmark warnings, empty state. |
| **Metric Sheet** | Portfolio Metric Sheet section below the performance chart; independent loading/error state; summary cards, risk/return, benchmark, periodic returns, yearly return chart, drawdown chart/table, monthly heatmap. |
| **Secondary chart** | Compact `ChartCard` “Invested vs Current” — horizontal bar comparison from backend summary totals. |

**States:** `LoadingState`, `ErrorState`, chart empty state, Metric Sheet section-local error, backend warnings, stale-response guards when scope/currency/range/benchmark changes.

**APIs:** `fetchDashboardSummary(apiQuery, { includeTimeseries: false })`, `fetchPortfolioPerformance(metric, benchmark, range, apiQuery)`, `fetchBenchmarkIndices()`, `getPortfolioMetricSheet(params)`.

**Preserve in redesign:** current behavior includes the Invested vs Current chart. Any future removal must be proposed in this file and approved before implementation. Dashboard must not request summary timeseries for KPI-only load and must not compute performance, FX, allocation, or Metric Sheet values in React.

**Tests:** `Dashboard.test.jsx`, `metricSheet.test.jsx`, `api.test.js`.

---

## 5. Assets (`/assets`)

**Files:** `pages/Assets.jsx` · `pages/Assets.css`

| Section | Layout |
|---------|--------|
| **Header** | `PageHeader` + cached prices / `make refresh` guidance. |
| **FX warning** | Warning when display currency differs from holdings and `fx_status === 'fx_unavailable'`. |
| **Main grid** | Holdings table primary, allocation donut supporting analysis. |
| **Active holdings** | Rows for stock/MF/FD investment assets; status badges for oversold, price missing, closed; row click -> asset detail where applicable. |
| **Allocation** | Donut from backend `allocation`; includes cash/bank cash/FD allocation rows from API. |
| **Closed holdings** | “Previous holdings” collapsed by default. |

**States:** loading, API error, empty assets, chart empty when all current values are zero, price/NAV/FX warnings.

**API:** `fetchHoldings(apiQuery)`.

**Preserve in redesign:** cash rows may appear in allocation/cash balance sections but must not become clickable investment rows or Compare subjects. React may calculate display-only chart percentages, but not valuations.

**Tests:** `Assets.test.jsx`.

---

## 6. Asset Detail (`/assets/:assetSymbol`)

**Files:** `pages/AssetDetail.jsx` · `pages/AssetDetail.css`

| Section | Layout |
|---------|--------|
| **Header** | `PageHeader` with symbol/scheme title, breadcrumb to Assets, scope/currency subtitle. |
| **Warnings** | FX and API `warnings[]` banners. |
| **Hero KPIs** | Current Value, Quantity/Units, Unrealized P/L, XIRR. |
| **Metric Sheet** | Asset Metric Sheet below hero KPIs; local range and benchmark controls; passes `folio_number` when asset detail payload includes it. |
| **Position / Cost Basis** | FIFO/invested/avg cost/realized/quantity fields from API. |
| **Market / Valuation** | Latest price/NAV, current value, currency. |
| **Data Quality** | Holding, price/NAV, FX status badges. |
| **Transaction History** | Scoped transaction table with `.ui-txn-type` badges and split ratio column. |

**States:** waits for `settingsLoaded && apiQuery`, loading, API error, empty transaction history, Metric Sheet section-local error, folio guidance when backend requires `folio_number`.

**APIs:** `fetchAssetDetails(assetSymbol, apiQuery)`, `getAssetMetricSheet(assetSymbol, params)`.

**Preserve in redesign:** MF folio-specific behavior, backend warnings, split/price/NAV data quality, and no client-side FIFO/XIRR/Metric Sheet math.

**Tests:** `AssetDetail.test.jsx`, `metricSheet.test.jsx`.

---

## 7. Transactions (`/transactions`)

**Files:** `pages/Transactions.jsx` · `pages/Transactions.css` · `components/TransactionModal.jsx` · `components/TransactionModal.css`

| Section | Layout |
|---------|--------|
| **Header** | `PageHeader` with record count; actions: hidden file input, Import CSV, Add Transaction. |
| **Cash-aware** | `CashAwarePortfolioStatus`; enable button for single legacy portfolio; all-scope note otherwise. |
| **Filters** | `TransactionFilterBar`: portfolio dropdown, searchable symbol multi-select, date modes Earlier than / Later than / Between, active chips, Clear filters. |
| **CSV guidance** | Expandable stock and MF CSV format guidance, MF sample download, target portfolio / split/SWAP notes. |
| **CSV cash preview** | On file select, `previewCsvImportCash`; shortfall modal with proposed deposits; confirmed import sends `create_cash_deposits=true` and `cash_preview_confirmed=true`. |
| **Import feedback** | Success/warning banner and row-level error list. |
| **Table** | Checkbox, Portfolio, Symbol/Scheme, Folio/NAV status for MF rows, Date, Type, Qty/Units, Price/NAV, Fees, Total, Actions. |
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

| Section | Layout |
|---------|--------|
| **Header** | `PageHeader` — native balances by portfolio/currency; no display-currency cash totals on this page. |
| **Cash-aware** | `CashAwarePortfolioStatus`; enable for selected legacy portfolio; all-scope explanatory note. |
| **Actions** | Add Deposit, Add Withdrawal, Add Bulk Cash Entries, Transfer Cash. |
| **Balances** | Full-width `SectionCard`; balance table by portfolio/currency; `totals_by_currency` for all scope when API returns it. |
| **Ledger** | Full-width `SectionCard`; filters for currency, entry type, date from/to; backend pagination; Details column from API. |
| **Manual edit/delete** | Manual deposit/withdrawal rows only; edit modal reuses cash fields; delete confirm; future-impact 409 panel; linked/system/transfer rows are protected. |
| **Bulk cash entries** | Configure -> `previewCashBulkEntries`; Review schedule/warnings/totals -> `applyCashBulkEntries`; Result summary; refresh balances + ledger. |
| **Transfer Cash** | Same- or cross-currency transfer; user-entered target amount; implied rate informational only; no market FX. |

**States:** balance loading/error/empty, ledger loading/error/empty, write success/error, withdrawal shortfall, future-impact panel, transfer shortfall/future-impact, bulk preview warnings/result.

**APIs:** `fetchCashBalances`, `fetchCashLedger`, `createCashDeposit`, `createCashWithdrawal`, `createCashTransfer`, `updateCashLedgerEntry`, `deleteCashLedgerEntry`, `previewCashBulkEntries`, `applyCashBulkEntries`.

**Preserve in redesign:** React displays backend cash balances, ledger rows, details, shortfalls, and future-impact payloads only. Do not compute running balances, join cash and asset transactions client-side, silently create deposits, or add implicit FX conversion.

**Tests:** `Cash.test.jsx`, `CashAwarePortfolioStatus.test.jsx`, `api.test.js`.

---

## 9. Fixed Deposits (`/fixed-deposits`)

**Files:** `pages/FixedDeposits.jsx` · `pages/FixedDeposits.css`

| Section | Layout |
|---------|--------|
| **Header** | `PageHeader` with FD/debt workflow context and Add Fixed Deposit action. |
| **Table/list** | Backend FD fields: institution, deposit account, principal, rate, investment/maturity dates, payout frequency, status, linked portfolio/bank account, lifecycle flags. |
| **Bank account dependency** | Fetches active bank accounts and portfolios. Create is blocked/guided when no active bank account exists. |
| **Create modal** | Portfolio and bank account dropdowns; currency read-only from selected bank account; principal/rate/dates/status; shows ledger balance from API and as-of-date/backdated guidance. |
| **Edit modal** | Existing FD fields; principal/bank/currency/investment date/portfolio disabled when `has_opening_cash_movement`; backend errors remain visible. |
| **Deactivate** | `DELETE /fixed-deposits/{id}` soft deactivates where allowed. |
| **Interest payments** | Expand/list per-FD payments; Record Interest modal with payment date, gross interest, tax withheld, display-only net; backend warnings (e.g. compounded FD) shown. |
| **Maturity/settlement** | Mark Matured for active FDs; Settle/Close modal with principal returned, gross final interest, tax withheld, display-only net/total; settled/closed rows hide settlement actions. |
| **Renewal** | Renew action for eligible ACTIVE/MATURED FDs; modal with new terms, direct rollover, cash payout, tax fields, bank cash warnings; hidden when settled or already renewed. |

**States:** waits for `settingsLoaded && apiQuery`, loading, API error, empty list, no-bank-account warning, unseeded opening balance warning, insufficient ledger warning/error, lifecycle success/error banners.

**APIs:** `fetchFixedDeposits(apiQuery)`, `fetchPortfolios`, `fetchBankAccounts`, `createFixedDeposit`, `updateFixedDeposit`, `deleteFixedDeposit`, `fetchFixedDepositInterestPayments`, `createFixedDepositInterestPayment`, `markFixedDepositMatured`, `settleFixedDeposit`, `renewFixedDeposit`.

**Exported but not currently page-used:** `fetchFixedDepositInterestPayment`, `fetchFixedDepositSettlements`, `fetchFixedDepositSettlement` are API-client helpers for implemented detail endpoints and should be treated as intentional available wrappers unless removed in a future API cleanup.

**Accounting/cash display rules:** React displays backend FD principal, ledger balance, warning, lifecycle, and cash-impact fields only. No accrued interest, FD IRR, bank cash, settlement, tax, or portfolio value calculations in React. Interest/settlement credits and included bank cash behavior are backend-owned.

**Tests:** `FixedDeposits.test.jsx`, `BankAccountManagement.test.jsx`, `CashMovementManagement.test.jsx`, `api.test.js`.

**Preserve in redesign:** bank account dependency, ledger-derived balance copy, opening movement immutability, lifecycle action visibility, renewal constraints, backend warnings, and no frontend accounting math.

---

## 10. Compare (`/compare`)

**Files:** `pages/Compare.jsx` · `pages/Compare.css` · `components/metricSheet/*`

| Section | Layout |
|---------|--------|
| **Header** | `PageHeader` with selected portfolio scope and display currency. |
| **Subject pickers** | Two dropdowns built from `fetchHoldings(apiQuery)` via `buildCompareAssetOptions`; active holdings first; closed holdings labeled `(closed)`; same-asset validation. |
| **Cash exclusion** | Cash and bank cash rows (`is_cash`, `asset_type=CASH` / `BANK_CASH`) are excluded from comparison subjects. |
| **Controls** | Range segmented control and optional benchmark selector from `fetchBenchmarkIndices()`. |
| **Normalized chart** | `CompareNormalizedChart` renders backend `normalized_series` as percent axis/tooltips; no client-side normalization/math beyond display mapping. |
| **Metric comparison** | `CompareMetricTable` side-by-side return, risk, drawdown, and optional benchmark metrics; subtle better/worse highlighting is display-only. |
| **Periodic/drawdown sections** | `ComparePeriodicReturnsSection` (yearly side-by-side) and `CompareDrawdownPeriodsSection` (per subject worst drawdowns). |
| **Warnings/context** | `MetricSheetWarnings`, subject-level warnings, common overlap note from `common_start_date` / `common_end_date`, requested-vs-common range copy. |

**States:** waits for `settingsLoaded && apiQuery`, holdings loading/error, fewer-than-two holdings empty state, same-subject validation, compare loading/error, normalized chart empty, backend warnings, calm MF multi-folio error when backend requires folio selection.

**APIs:** `fetchHoldings(apiQuery)`, `fetchBenchmarkIndices()`, `getCompareMetricSheet({ subjects, range, benchmark, portfolio scope, display_currency })`.

**Preserve in redesign:** exactly two asset subjects, no cash subjects, current MF multi-folio backend-error handling, backend common-window semantics, XIRR full-scope note, benchmark propagation, and no frontend Sharpe/beta/return/drawdown calculations.

**Tests:** `Compare.test.jsx`, `metricSheet.test.jsx`, `compareMetricRanking.test.js`, `compareHoldings.test.js`, `metricSheetCopy.test.js`, `api.test.js`.

---

## 11. Settings (`/settings`)

**Files:** `pages/Settings.jsx` · `pages/Settings.css` · `components/PortfolioManagement.jsx` · `components/BankAccountManagement.jsx` · `components/CashMovementManagement.jsx`

| Section | Layout |
|---------|--------|
| **Header** | `PageHeader` “Settings”. |
| **Display & tax** | `SectionCard` with tax rate input, display currency select, sidebar sync hint, Save button. |
| **Portfolios** | Real portfolio CRUD, max active portfolio enforcement, default portfolio protected, Cash-aware On/Off and Enable action for legacy rows. |
| **Bank accounts** | Active account list, create/edit/deactivate, full account number display, ledger-derived current balance, seed opening balance, include-in-portfolio-value toggle. |
| **Cash movements** | Per-account expandable ledger via `CashMovementManagement`; manual deposit/withdrawal/adjustment modal; immutable rows. |
| **Feedback** | Success/error `WarningBanner` after writes. |

**States:** initial loading/error, settings save success/error, portfolio validation errors, bank-account ledger/unseeded warnings, cash movement errors.

**APIs:** `getSettings`, `updateSettings`, `createPortfolio`, `updatePortfolio`, `deletePortfolio`, `fetchBankAccounts`, `createBankAccount`, `updateBankAccount`, `deleteBankAccount`, `seedBankAccountOpeningBalance`, `fetchCashMovements`, `createCashMovement`, `reloadPortfolios()`.

**Preserve in redesign:** display currency must stay synchronized with sidebar context; All Portfolios remains virtual and cannot be created/assigned; default portfolio cannot be deactivated; bank ledger/current balance rules are backend-owned.

**Tests:** `Settings.test.jsx`, `BankAccountManagement.test.jsx`, `CashMovementManagement.test.jsx`, `Layout.test.jsx`.

---

## 12. Auth pages (`/login`, `/register`, `/forgot-password`)

**Files:** `pages/auth/Login.jsx` · `pages/auth/Register.jsx` · `pages/auth/ForgotPassword.jsx` · `pages/auth/AuthShell.jsx` · `pages/auth/Auth.css`

| Route | Layout and behavior |
|-------|---------------------|
| `/login` | Public-only auth shell; email/username + password form; submit calls `useAuth().login`; success navigates to `/`; error shown inline; links to forgot password and register; Google sign-in button. |
| `/register` | Public-only auth shell; registration form; submit calls `useAuth().register`; success navigates to `/`; backend validation errors shown; Google sign-in button. |
| `/forgot-password` | Public-only auth shell; email form; submit calls `requestPasswordReset`; success/detail message shown; errors shown; link back to login. |

**Google OAuth:** `GoogleSignInButton` calls `window.location.assign('/accounts/google/login/?process=login')`; Vite proxies `/accounts` to Django/allauth. Successful allauth login redirects to `FRONTEND_URL/`.

**CSRF/session:** `AuthProvider` ensures CSRF cookie on app load and before login/register. `fetchWithHandling` uses `credentials: 'include'` and adds `X-CSRFToken` for unsafe methods when the `csrftoken` cookie exists.

**401 redirect:** non-auth API 401 responses call the unauthorized handler and navigate to `/login`.

**States:** auth loading in protected/public route wrappers, form submitting, inline error messages, password reset success/detail message.

**Tests:** `App.test.jsx`, `auth.test.js`, `Register.test.jsx`, `AuthShell.test.jsx`. Current gap before a major redesign: add direct `Login.jsx` and `ForgotPassword.jsx` page tests.

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
| `/login` | `pages/auth/Login.jsx` | `auth/Auth.css` | AuthShell, GoogleSignInButton, Button | auth login via `useAuth`, CSRF | **Implemented** |
| `/register` | `pages/auth/Register.jsx` | `auth/Auth.css` | AuthShell, GoogleSignInButton, Button | auth register via `useAuth`, CSRF | **Implemented** |
| `/forgot-password` | `pages/auth/ForgotPassword.jsx` | `auth/Auth.css` | AuthShell, Button | password reset | **Implemented** |
| `/` | `pages/Dashboard.jsx` | `Dashboard.css` | PageHeader, MetricCard, ChartCard, Metric Sheet, SegmentedControl | summary, performance, benchmarks, portfolio Metric Sheet | **Implemented** |
| `/transactions` | `pages/Transactions.jsx` | `Transactions.css` | PageHeader, TransactionModal, filter bar, WarningBanner | transactions CRUD, filter options, CSV import, CSV cash preview | **Implemented** |
| `/cash` | `pages/Cash.jsx` | `Cash.css` | PageHeader, SectionCard, CashBulkEntriesWizard, CashAwarePortfolioStatus | cash balances, ledger, deposits, withdrawals, transfers, bulk entries | **Implemented** |
| `/assets` | `pages/Assets.jsx` | `Assets.css` | PageHeader, ChartCard, SectionCard, StatusBadge | holdings/allocation | **Implemented** |
| `/assets/:assetSymbol` | `pages/AssetDetail.jsx` | `AssetDetail.css` | PageHeader, MetricCard, AssetDetailMetricSheet, SectionCard | asset detail, asset Metric Sheet | **Implemented** |
| `/fixed-deposits` | `pages/FixedDeposits.jsx` | `FixedDeposits.css` | PageHeader, SectionCard, lifecycle modals | fixed deposits, portfolios, bank accounts, interest, settlement, renewal | **Implemented** |
| `/compare` | `pages/Compare.jsx` | `Compare.css` | PageHeader, CompareNormalizedChart, CompareMetricTable, MetricSheetWarnings | holdings, benchmarks, compare Metric Sheet | **Implemented** |
| `/settings` | `pages/Settings.jsx` | `Settings.css` | PageHeader, PortfolioManagement, BankAccountManagement, CashMovementManagement | settings, portfolios, bank accounts, cash movements | **Implemented** |
| `(shell)` | `components/Layout.jsx` | `components/Layout.css` | nav, selectors, ThemeSelector, WarningBanner | portfolios, settings, auth logout | **Implemented** |

**Shared:** `components/ui/*`, `components/metricSheet/*`, `components/charts/chartTheme.js`, `frontend/src/api.js`, `portfolioContext.jsx`, `authContext.jsx`, `themeContext.jsx`.

---

## Document history

| Date | Change | Status |
|------|--------|--------|
| 2026-05-25 | Initial layout spec post design migration | Implemented |
| 2026-05-27 | Settings portfolio CRUD; Transactions bulk assign | Implemented |
| 2026-06-19 | Frontend redesign readiness governance expansion: app shell, auth, Compare, Cash, Fixed Deposits, Transactions, API preservation checklist | Implemented |
