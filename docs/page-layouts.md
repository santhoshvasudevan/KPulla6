# Page Layouts — KPulla6

Source of truth for **page structure and layout decisions** after the Institutional Slate migration (Phases 0–8B).

Related: [frontend-design.md](./frontend-design.md) (tokens, components, color semantics), [api-design.md](./api-design.md) (API contracts).

---

## 1. Purpose and governance

| Rule | Detail |
|------|--------|
| **Authority** | This file defines intended layout for each routed page. |
| **Change order** | Propose layout changes here **first** → human approval → then code. |
| **API-driven UI** | React renders `/api/v1` values only. |
| **Forbidden in React** | FIFO, FX conversion, valuation, XIRR, TWROR, benchmark math, performance calculations. Display formatting (currency, percent, chart axis labels, pie tooltip %) is allowed. |
| **Design system** | Use UI primitives in `frontend/src/components/ui/`; see [frontend-design.md](./frontend-design.md). |

---

## 2. Global page layout principles

- **Institutional Slate** — calm, analytics-first; not terminal/neon styling.
- **Hierarchy** — KPIs and charts lead; tables support comparison; spacing over decoration.
- **Primitives** — `PageHeader`, `MetricCard`, `ChartCard`, `SectionCard`, `StatusBadge`, `WarningBanner`, `EmptyState`, `LoadingState`, `ErrorState`, `CurrencyValue`, `PercentValue`, `Button`, `SegmentedControl`.
- **Numbers** — right-aligned in tables (`num-col`); tabular nums via `--font-metric`.
- **Status** — `StatusBadge` / `WarningBanner`; never rely on color alone.
- **Scope** — portfolio view and display currency from `portfolioContext` (`apiQuery`) apply to all data pages once `settingsLoaded` is true.

---

## 3. App shell layout

**File:** `frontend/src/components/Layout.jsx` · **CSS:** `Layout.css`

| Zone | Content |
|------|---------|
| **Brand** | “Portfolio Insight” + subtitle |
| **Nav** | Dashboard, Transactions, Assets, Settings (active: left accent + raised surface) |
| **Controls (bottom)** | Portfolio View select (`all` / single portfolio); Display Currency select (syncs with settings API) |
| **Notice** | `WarningBanner` if portfolio list fetch fails |
| **Footer** | Cached prices/FX note |
| **Main** | `<Outlet />` in `app-main__inner` (max-width ~1400px, padded) |

**Responsive:** Sidebar stacks above main below 900px; nav 2-column grid below 540px; footer hidden on narrow sidebar.

**Context APIs:** `fetchPortfolios`, `getSettings` / `updateSettings` (via `portfolioContext`).

---

## 4. Dashboard (`/`)

**Files:** `Dashboard.jsx` · `Dashboard.css`

| Section | Layout |
|---------|--------|
| **Header** | `PageHeader` — title “Portfolio Overview”; subtitle: portfolio name · display currency |
| **KPI row** | Grid of `MetricCard`: Current Value (hero), Total Invested, Total P/L, XIRR; optional Realized/Unrealized P/L when API provides. Values use fluid typography (`clamp()` + `nowrap`) so large INR amounts stay inside card bounds. |
| **FX warning** | `WarningBanner` if `summary.fx_status === 'fx_unavailable'` |
| **Primary chart** | `ChartCard` — performance line chart (~300px); toolbar: benchmark select (return metrics only); controls: metric (`value` / `cumulative_return` / `twror`) + range pills (`7D`–`ALL`); footer: loading + benchmark warnings; empty: `EmptyState` |
| **Secondary chart** | Compact `ChartCard` “Invested vs Current” — horizontal bar comparison |

**States:** `LoadingState` · `ErrorState` · chart empty when no series points.

**APIs:** `fetchDashboardSummary(apiQuery)` · `fetchPortfolioPerformance(metric, benchmark, range, apiQuery)` · `fetchBenchmarkIndices()` (when benchmark picker shown).

**Notes:** Chart merges comparison series for display only; no client-side performance math.

---

## 5. Assets (`/assets`)

**Files:** `Assets.jsx` · `Assets.css`

| Section | Layout |
|---------|--------|
| **Header** | `PageHeader` + short description (cached prices / `make refresh`) |
| **FX warning** | When display currency ≠ holding currencies and `fx_status === 'fx_unavailable'` |
| **Main grid** | ~65% table (primary) · ~35% allocation donut (`ChartCard`) on desktop; chart stacks first on mobile |
| **Active table** | Sortable columns: Symbol, Qty, Avg Cost, Latest Price, Current Value, Unrealized P/L, XIRR; `StatusBadge` for oversold / price_missing; row click → asset detail |
| **Allocation chart** | Donut from active holdings `current_value`; tooltip shows API value + display-only % of sum |
| **Closed holdings** | `SectionCard` “Previous holdings” — **collapsed by default**; toggle reveals table (closed badge, zero qty) |

**States:** `LoadingState` · `ErrorState` · table `EmptyState` · chart empty states (no holdings / no prices).

**Behavior:** Client-side sort only; filters `closed` / zero-qty to previous section; navigation to `/assets/:symbol`.

**API:** `fetchHoldings(apiQuery)`.

---

## 6. Asset Detail (`/assets/:assetSymbol`)

**Files:** `AssetDetail.jsx` · `AssetDetail.css`

| Section | Layout |
|---------|--------|
| **Header** | `PageHeader` — symbol title; breadcrumb link to Assets; subtitle: scope · currency |
| **Warnings** | FX + API `warnings[]` banners |
| **Hero KPIs** | Grid: Current Value (hero), Quantity, Unrealized P/L, XIRR |
| **Position / Cost Basis** | `SectionCard` — invested (FIFO), avg cost, realized P/L, quantity |
| **Market / Valuation** | `SectionCard` — latest price, current value, currency |
| **Data Quality** | `SectionCard` — `StatusBadge` for holding, price, FX status |
| **Transaction History** | `SectionCard` — table with `.ui-txn-type` badges; numeric cols right-aligned; split ratio column |

**States:** `LoadingState` · `ErrorState` · empty transaction `EmptyState`.

**API:** `fetchAssetDetails(assetSymbol, apiQuery)`.

---

## 7. Transactions (`/transactions`)

**Files:** `Transactions.jsx` · `Transactions.css` · `TransactionModal.jsx` / `.css`

| Section | Layout |
|---------|--------|
| **Header** | `PageHeader` — record count subtitle; actions: hidden file input + Import CSV + Add Transaction |
| **Import info** | Info `WarningBanner` (target portfolio, stock split/SWAP rules); expandable “Supported CSV formats” (stock + MF columns, rules, MF example, sample MF download) |
| **Import feedback** | Success/warning banner; error block with row-level list |
| **Table** | Checkbox, Portfolio, Symbol, Date, Type (`.ui-txn-type`), Qty, Price, Fees, Total, Actions (edit/delete icon buttons) |
| **Bulk actions** | Toolbar when rows selected: portfolio dropdown (active real only), Apply, Clear; partial failure banner |
| **Modal** | `TransactionModal` — add/edit; STOCK_SPLIT field swap; Cancel/Save `Button`s |

**States:** `LoadingState` · `ErrorState` · table `EmptyState`.

**Behavior:** Paginated list (`page`, `page_size` 20/50/100); Previous/Next when `total > page_size`; resets to page 1 on portfolio scope change and after CSV import; delete confirms; modal refresh on success; bulk assign uses `buildTransactionUpdatePayload` + `updateTransaction` per selected row; line total = display-only `qty × price + fees` (not for splits).

**APIs:** `fetchTransactions` · `createTransaction` / `updateTransaction` · `deleteTransaction` · `importTransactionsCsv`.

---

## 8. Settings (`/settings`)

**Files:** `Settings.jsx` · `Settings.css`

| Section | Layout |
|---------|--------|
| **Header** | `PageHeader` “Settings” |
| **Display & tax** | `SectionCard` — tax rate input, display currency select, hint linking to sidebar selector, Save `Button` |
| **Portfolios** | `SectionCard` + `PortfolioManagement` — active portfolio table, create form, edit modal, deactivate (non-default); backend errors surfaced via `WarningBanner` |
| **Feedback** | Success / error `WarningBanner` after save |

**States:** `LoadingState` · `ErrorState` on initial load failure.

**APIs:** `getSettings` · `updateSettings` (also updates `portfolioContext` display currency) · `createPortfolio` / `updatePortfolio` / `deletePortfolio` via `PortfolioManagement` + `reloadPortfolios()`.

**Note:** Cached-data explainer lives in app shell sidebar footer, not on this page.

---

## 9. Layout change process

1. **Update** this file with the proposed layout change.
2. **Mark** the change **Proposed** (use template below).
3. **Wait** for user approval.
4. **Implement** approved change in React/CSS only after approval.
5. **Update** Vitest/RTL tests if structure, roles, or visible text change.
6. **Record** in `docs/changelog.md`.
7. **Mark** the change **Implemented** in this file.

---

## 10. Proposed change template

```markdown
### [Short title]

- **Page:** (route)
- **Current layout:** (brief)
- **Proposed layout change:** (brief)
- **Reason:** (why)
- **API impact:** None | describe endpoint/field changes
- **Frontend state impact:** None | describe
- **Components affected:** (list)
- **Tests required:** (list)
- **Approval status:** Proposed | Approved | Implemented
```

---

## 11. Page ownership table

| Route | React | CSS | Primary components | API calls | Layout status |
|-------|-------|-----|-------------------|-----------|---------------|
| `/` | `pages/Dashboard.jsx` | `Dashboard.css` | PageHeader, MetricCard, ChartCard, SegmentedControl, WarningBanner, EmptyState | summary, performance, benchmarks | **Implemented** |
| `/assets` | `pages/Assets.jsx` | `Assets.css` | PageHeader, ChartCard, SectionCard, StatusBadge, CurrencyValue, PercentValue | holdings | **Implemented** |
| `/assets/:assetSymbol` | `pages/AssetDetail.jsx` | `AssetDetail.css` | PageHeader, MetricCard, SectionCard, StatusBadge, `.ui-txn-type` | asset detail | **Implemented** |
| `/transactions` | `pages/Transactions.jsx` | `Transactions.css` | PageHeader, Button, WarningBanner, TransactionModal, `.ui-txn-type` | transactions CRUD, CSV import, bulk assign | **Implemented** |
| `/settings` | `pages/Settings.jsx` | `Settings.css` | PageHeader, SectionCard, PortfolioManagement, Button, WarningBanner | settings GET/PUT, portfolio CRUD | **Implemented** |
| (shell) | `components/Layout.jsx` | `Layout.css` | WarningBanner, nav, selectors | portfolios, settings (context) | **Implemented** |

**Shared:** `components/ui/*` · `components/charts/chartTheme.js` · `portfolioContext.jsx`

---

## Document history

| Date | Change | Status |
|------|--------|--------|
| 2026-05-25 | Initial layout spec post design migration | Implemented |
| 2026-05-27 | Settings portfolio CRUD; Transactions bulk assign | Implemented |
