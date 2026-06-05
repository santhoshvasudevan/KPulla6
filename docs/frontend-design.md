# Frontend Design System — KPulla6

## Product Feel

KPulla6 is a premium portfolio analytics dashboard: professional, calm, data-rich, and trustworthy.
Visual direction: institutional wealth analytics, not a terminal toy or casual budgeting app.

**Page layouts:** per-page structure and layout governance live in [page-layouts.md](./page-layouts.md). Propose layout changes there before coding.

## Core Principles

1. Analytics first — charts and KPIs lead each page.
2. Hierarchy through spacing and typography, not decoration.
3. Backend renders truth — React displays `/api/v1` values only.
4. No finance domain logic in React (no FIFO, XIRR, TWROR, FX, benchmark, or valuation math).
5. Warnings are visible but calm — never alarmist.
6. Tables optimize scan and comparison; numbers right-aligned.
7. Accessible — do not rely on color alone for meaning.

## Theme: Institutional Slate

Phase 0 establishes CSS custom properties in `frontend/src/index.css`. Use only the canonical tokens below — legacy aliases were removed in Phase 8B.

### Appearance preference (Light / Dark / System)

- **UI:** Header theme select in the app shell (`ThemeSelector` in `Layout.jsx`) — options **System**, **Light**, **Dark**.
- **Storage:** `localStorage` key `kpulla6.themePreference` (default **`system`** when unset).
- **Resolution:** `system` follows `prefers-color-scheme`; `light` / `dark` force that mode.
- **Application:** `document.documentElement.dataset.theme` is set to `light` or `dark`; `color-scheme` is updated for native controls.
- **Flash prevention:** `frontend/public/theme-init.js` runs in `index.html` before the React bundle loads.
- **React:** `ThemeProvider` / `useTheme()` in `frontend/src/themeContext.jsx`; preference helpers in `frontend/src/theme/themeStorage.js`.
- **Tokens:** Dark mode preserves Institutional Slate (`:root` and `[data-theme='dark']`); light overrides live under `[data-theme='light']`.
- **Charts:** `chartTheme.js` reads computed CSS variables at render time so Recharts stays readable in both modes.

### Colors

| Token | Purpose |
|-------|---------|
| `--bg-app` | Page background |
| `--bg-surface` | Cards, sidebar |
| `--bg-surface-raised` | Hover, elevated panels |
| `--bg-surface-hover` | Row/button hover |
| `--border-subtle` / `--border-strong` | Borders and dividers |
| `--text-primary` / `--text-secondary` / `--text-muted` | Text hierarchy |
| `--accent` / `--accent-muted` | Active controls, focus rings |
| `--gain` / `--loss` / `--warn` | P/L and data-quality semantics only |
| `--chart-1` … `--chart-6` | Chart series (non-semantic) |

Recharts reads theme tokens via `getChartTooltipStyle()`, `getChartGridProps()`, etc. in `chartTheme.js` (computed from CSS variables).

### Typography

- **UI / body:** Inter (loaded in `index.html`), system-ui fallback
- **Metrics:** Same family with `font-variant-numeric: tabular-nums`
- **Large metric values (KPI cards):** `MetricCard` uses container-query `clamp()` sizing, `white-space: nowrap`, `max-width: 100%`, and ellipsis fallback; `CurrencyValue` exposes full formatted amount via `title`
- **Monospace (tables):** `--font-metric` for numeric columns
- Page titles: sentence case, 1.5–1.75rem (applied in later phases)
- Section labels: 0.6875rem uppercase, letter-spacing 0.06em, `--text-secondary`

### Spacing & surfaces

- Base unit: 4px; common gaps: 8, 12, 16, 24, 32 (`--space-1` … `--space-6`)
- Card radius: 8px (`--radius-md`); control radius: 6px (`--radius-sm`)
- Card padding: 20–24px
- Border: 1px `--border-subtle`; optional shadow: `--shadow-card`

## Layout Rules

### App shell

- Fixed sidebar (~260px): brand, portfolio/currency selectors directly below brand, main navigation, optional data note in footer
- Top header (main column): theme selector, signed-in user label, log out — always visible without scrolling the sidebar
- Main content: `--bg-app` background, inner padding (`--space-5` / `--space-6`), max-width ~1400px
- Active nav: left accent border + raised surface (not inverted high-contrast)
- Selectors: raised surface, strong border, accent focus ring
- Responsive: sidebar stacks above main below 900px; nav grid on very narrow screens

### Dashboard

- Hero metric row: Total Value emphasized, then Invested, Total P/L, XIRR — from `GET /portfolio/summary` with `include_timeseries=false` (no unused daily series payload)
- Value / return charts: `GET /portfolio/performance` only (metric, range, optional benchmark)
- Full-width performance chart is the visual centerpiece (~400px+)
- Controls grouped in chart toolbar: metric, range, benchmark
- FX and benchmark warnings directly under chart
- Omit redundant invested-vs-current bar chart (later phase)

### Assets

- Holdings table is primary; allocation donut supports analysis (~35% width on desktop)
- Closed holdings in collapsible section, default collapsed
- Status badges for oversold, price_missing, closed
- Empty state when prices missing — explain sync clearly

### Asset Detail

- Metric Sheet layout: hero KPIs → cost basis / market sections → transaction history
- Breadcrumb back to Assets

### Transactions

- Header with record count and primary actions (Import, Add)
- **CSV import (MF-11b):** Info banner (import target portfolio, stock split/SWAP rules); expandable “Supported CSV formats” with stock vs mutual fund columns, MF rules (no mixed file, date format, INR default, fees), inline example, and client-side “Download sample MF CSV” — no import logic or NAV math in React
- Row checkboxes + select-all on visible page; bulk toolbar when selected: assign to real portfolio (full PUT per row), clear selection on success
- **Column filters (`TransactionFilterBar`):** Portfolio dropdown (single-select; empty = follow current view), searchable Symbol multi-select (options from `GET /transactions/filter-options`), and Date filter with modes Earlier than / Later than / Between. Filters auto-apply, reset to page 1, and persist across pagination; active-filter chips (removable) + Clear filters. Invalid Between range (from > to) shows an inline error and suppresses the request. No finance/date math beyond mapping modes to `date_from`/`date_to`.
- Right-aligned numeric columns; type badges
- Pagination when `total > page_size`
- **Mutual funds (MF-8):** Add/Edit modal supports `asset_type` Stock (default) or Mutual fund; MF form uses backend field names (`scheme_code`, `scheme_name`, `folio_number`, `investment_date`, `nav_date`, `nav`, `units_allotted`, `paid_value`, `market_value`). Stock form unchanged. List shows scheme/folio, units/NAV columns, calm `nav_verification_status` badge. No client-side NAV math or external AMFI calls.

### Settings

- Section cards: Display & tax; **Portfolios** (CRUD for real portfolios); Data & sync (explainer)
- Portfolio table: name, base currency, default flag; create form (name, optional description, base currency default EUR); edit modal; deactivate for non-default only
- Display currency must stay in sync with sidebar selector
- **All Portfolios** remains virtual — not created or assignable as a target portfolio

## Component Catalog

Implemented in `frontend/src/components/ui/` (Phase 1–3B):

| Component | Props (summary) |
|-----------|-----------------|
| `Button` | `variant`: primary \| secondary \| ghost \| danger; `disabled`, `type`, `onClick` |
| `PageHeader` | `title`, `subtitle`, `eyebrow`, `breadcrumb`, `actions` |
| `MetricCard` | `label`, `value`, `helperText`, `tone`, `size`, `icon`, `trend` |
| `SectionCard` | `title`, `subtitle`, `actions`, `children`, `compact` |
| `ChartCard` | `title`, `subtitle`, `toolbar`, `children`, `footer`, `compact` |
| `SegmentedControl` | `ariaLabel`, `options`, `value`, `onChange` |
| `StatusBadge` | `status`, optional `label` |
| `WarningBanner` | `severity`: info \| warning \| error \| success; `title`, `message`, `action` |
| `EmptyState` | `title`, `description`, `action`, `icon` |
| `LoadingState` | `message`, `variant`: spinner \| skeleton |
| `ErrorState` | `title`, `message`, `action`, `onRetry` |
| `CurrencyValue` | `value`, `currency`, `tone`, `fallback`, `showSign` |
| `PercentValue` | `value`, `tone`, `fallback`, `showSign` |

Shared table styling (not a component): page-local table CSS; `DataTable` deferred.

Transaction type badges: `.ui-txn-type` + modifiers in `ui.css` (BUY / SELL / DIVIDEND / STOCK_SPLIT).

Chart theme: `frontend/src/components/charts/chartTheme.js`

Planned for later phases:

| Component | Responsibility |
|-----------|----------------|
| `DataTable` | Sortable table, numeric alignment, empty state |

## Color Semantics

- **Green (`--gain`):** positive P/L values only
- **Red (`--loss`):** negative P/L values only
- **Amber (`--warn`):** missing prices, FX unavailable, oversold, API warnings
- **Accent (`--accent`):** navigation, active pills, focus — not P/L
- Always pair color with text labels or icons

## Charts (Recharts)

- Disable line animation (`isAnimationActive={false}`)
- Tooltip: surface background, subtle border, tabular numbers
- Benchmark comparison: portfolio + index lines from API series only
- Allocation % in tooltips may divide backend `current_value` by sum — display only

## Future — Metric Sheet UI (Phase 8A foundation implemented)

Backend analytics APIs (`GET /api/v1/analytics/*`) supply all metrics; React **displays only** — no Sharpe, Sortino, beta, drawdown, or periodic-return calculations in the client.

### Phase 8A — Reusable foundation (implemented)

| Item | Location |
|------|----------|
| API client | `getPortfolioMetricSheet`, `getAssetMetricSheet`, `getCompareMetricSheet` in `frontend/src/api.js` |
| Display formatters | `frontend/src/utils/metricFormatters.js` — fractions → `%`, ratios → plain numbers, null → `—` |
| Components | `frontend/src/components/metricSheet/` — `MetricSheetSection`, `MetricSheetSummaryCards`, `MetricSheetRiskReturnTable`, `MetricSheetBenchmarkTable`, `MetricSheetWarnings` |
| Test fixture | `samplePortfolioMetricSheetPayload.js` |
| Tests | `metricSheet.test.jsx`, `metricFormatters.test.js`, API client tests in `api.test.js` |

Pages are wired on **Dashboard** (Phase 8B) and **Asset Detail** (Phase 8C). **Compare** (Phase 8D) implemented.

### Dashboard — Performance Quality (Phase 8B — implemented)

- **Metric Sheet section** below the main performance chart on Dashboard.
- Independent fetch via `getPortfolioMetricSheet` (does not block chart/summary).
- Reuses Dashboard portfolio scope, display currency, time range, and benchmark selection.
- Phase 8A components: summary cards, risk/drawdown/period tables, optional benchmark table, warnings.
- Metric Sheet errors shown inside the section only (`ErrorState`).
- Performance chart unchanged (`GET /portfolio/performance` for series).

### Asset Detail — Metric Sheet section (Phase 8C — implemented)

- **Metric Sheet section** below hero KPIs, above Position/Cost Basis and transaction history.
- Independent fetch via `getAssetMetricSheet` with section-local loading and error states.
- Local controls in section header: range (`SegmentedControl`) and benchmark selector.
- Reuses portfolio scope and display currency from `PortfolioProvider`.
- Passes `folio_number` from asset detail payload when present; shows folio guidance on backend 400.
- Phase 8A components for display; benchmark table only when benchmark selected and API returns block.

### Compare page (Phase 8D — implemented)

- Route `/compare` with sidebar nav **Compare**.
- Subject pickers: two dropdowns from `fetchHoldings` (unique symbols); same-asset validation; empty state when fewer than two holdings.
- `getCompareMetricSheet` with `subjects=asset:A,asset:B`, range, benchmark, portfolio scope, display currency.
- `CompareNormalizedChart` — Recharts line chart from `normalized_series` (fractions; axis/tooltip as percent).
- `CompareMetricTable` — side-by-side return, risk, and optional benchmark metrics; `MetricSheetWarnings` for global and per-subject messages.
- Common overlap note from `common_start_date` / `common_end_date`.
- MF multi-folio backend error: calm `ErrorState` (no per-folio UX in this phase).
- No client-side ranking or finance calculations.

### Metric Sheet UX hardening (Phase 8E — implemented)

- Compare pickers: active holdings first via `buildCompareAssetOptions`; closed labeled `(closed)` in optgroup.
- Compare range note: `Requested range: … · Compared over common dates: …` (`formatCompareRangeContext`).
- XIRR full-scope helper: `XIRR is full-scope; other Metric Sheet values follow the selected range.`
- `MetricSheetWarnings`: calm `warning` severity for split/FX/NAV/price/benchmark overlap messages; `info` for compare alignment notices.

### Metric Sheet periodic returns and drawdown periods (Phase 9B — implemented)

- `MetricSheetPeriodicReturnsTable` — monthly + yearly tables (fractions → `formatMetricPercentFraction`).
- `MetricSheetDrawdownPeriodsTable` — worst episodes (peak/trough/recovery, status).
- Dashboard + Asset Detail: both sections below summary/risk/benchmark.
- Compare: `ComparePeriodicReturnsSection` (yearly side-by-side); `CompareDrawdownPeriodsSection` (per subject).
- Missing/empty backend arrays: inline empty messages; no client-side calculations.

### Metric Sheet polish (Phase 10B — implemented)

- Dashboard Metric Sheet benchmark selector always visible in section header (`metric-sheet-benchmark`); chart overlay still uses the same selection when return metrics are active.
- Wide Metric Sheet tables use `.metric-sheet-table-scroll` horizontal scroll wrappers (drawdown, compare tables).
- Asset Detail waits for `settingsLoaded && apiQuery` before fetching asset detail (aligned with Metric Sheet).
- Backend analytics warnings distinguish missing cached stock prices vs missing MF NAVs (calm copy).

### Metric Sheet monthly returns grid (Phase 11A — implemented)

- `MetricSheetMonthlyReturnsGrid` — year × month grid from backend `periodic_returns.monthly`; optional full-year column from `periodic_returns.yearly` (display only, no client-side return math).
- `metricSheetMonthlyGrid.js` — period parsing and cell placement helpers; tested in `metricSheetMonthlyGrid.test.js`.
- Dashboard + Asset Detail: monthly list table replaced by scrollable grid (`max-height` + horizontal scroll); yearly fallback table only when monthly is empty but yearly exists.
- Compare page unchanged (yearly side-by-side only).

### Metric Sheet visualization charts (Phase 13C — implemented)

- **Monthly heatmap scale** — five-band tone mapping in `metricSheetMonthlyHeatmap.js` (≤−10% strong red, −10% to −3% soft red, −3% to +3% neutral/yellow, +3% to +10% soft green, ≥+10% strong green); percentage text remains visible in every cell with aria labels.
- **`MetricSheetYearlyReturnChart`** — Recharts bar chart from `periodic_returns.yearly`; title **Calendar-Year Return**; helper *Cash-flow adjusted return using daily TWROR.*; placed above Periodic Returns on Dashboard and Asset Detail.
- **`MetricSheetDrawdownChart`** — Recharts area chart from `drawdown_series`; worst episodes shaded via `ReferenceArea` using `drawdown_periods.worst` ranks (rank 1 strongest); unrecovered episodes shade through series end; placed above Worst Drawdowns table.
- Compare page unchanged (yearly table + drawdown tables only).

### Compare metric highlighting (Phase 11B — implemented)

- `compareMetricRanking.js` — display-only helper comparing exactly two backend metric values; returns `better` / `worse` / `tie` / `neutral` / `unknown` per cell (no new analytics).
- `CompareMetricTable` — subtle per-cell highlights where metric direction is unambiguous; legend note above tables.
- **Higher is better:** cumulative return, CAGR, TWROR, XIRR, Sharpe, Sortino, Calmar, alpha, information ratio, and related return/ratio keys in the direction map.
- **Lower is better:** volatility, downside deviation (when shown).
- **Less negative is better:** max drawdown (e.g. −10% beats −25%).
- **Neutral (no highlight):** beta, correlation, tracking error, paired count, days, null/missing values, unknown keys.
- **Tie:** equal values within tolerance — soft tie styling + “Equal values” label.
- Accessible labels: `title` + visually hidden text on highlighted cells (`Best value in this row`, etc.); not color-only.
- Styling: soft background + thin left border via design tokens (`--accent-muted`, `--border-subtle`); no aggressive gain/loss blocks.
- Compare drawdown sections: per-subject tables keep `.metric-sheet-table-scroll`; no cross-asset episode ranking.
- Monthly grid yearly column header: **Year Return** (distinct from row year label).

### Metric Sheet release readiness (Phase 12A — implemented)

- Compare API TWROR aligned to common overlapping window (backend fix).
- Compare table labels aligned with Dashboard/Asset Detail risk metrics.
- Yearly fallback table uses `.metric-sheet-table-scroll`.
- Dashboard benchmark table requires active benchmark selection (matches Asset Detail).
- Contract tests for compare payload shape, `xirr_scope`, and common-window warning.

### Dashboard Metric Sheet full-width layout (Phase 12B — implemented)

- Metric Sheet section spans full main content width on Dashboard (`.metric-sheet.ui-section-card { max-width: none }`); placed between performance chart and secondary charts (not nested in chart column).
- Increased subsection spacing via `.metric-sheet .ui-section-card__body` flex gap.
- MF NAV warnings: freshness-based only (`MF_NAV_STALE_AFTER_DAYS = 5`); no warning for weekend/holiday NAV gaps when latest cached NAV is recent.

### Data rules

- All Metric Sheet numbers: backend APIs only.
- Charts: Recharts with `isAnimationActive={false}`; series from API arrays.
- Partial data: show available metrics; do not infer missing values.

## Implementation Phases

| Phase | Scope |
|-------|--------|
| **0** | Docs + CSS tokens |
| **1** | Primitive components + Settings integration (done) |
| **2** | App shell / sidebar polish (done) |
| **3** | Dashboard migration |
| **3A** | Dashboard states, header, KPI cards (done) |
| **3B** | Dashboard chart container, controls, theme (done) |
| **4–6** | Assets, Asset Detail, Transactions page migration (done) |
| **7B** | Modal polish, dead CSS, shared txn type badges (done) |
| **8A** | Metric Sheet API client + reusable display components (done) |
| **8B** | Dashboard Metric Sheet integration (done) |
| **8C** | Asset Detail Metric Sheet integration (done) |
| **8D** | Compare UI (done) |
| **8E** | Metric Sheet visual QA / UX hardening (done) |
| **9B** | Periodic returns + worst drawdown periods display (done) |
| **10B** | Metric Sheet polish — benchmark UX, table scroll, settings gate, warnings (done) |
| **11A** | Monthly returns grid / heatmap display (done) |
| **11B** | Compare metric scanability — subtle better/worse highlighting (done) |
| **12A** | Metric Sheet release readiness audit (done) |
| **12B** | Dashboard full-width Metric Sheet + MF NAV freshness warnings (done) |
| **13A** | Sidebar context controls moved below brand (done) |
| **13B** | Metric Sheet drawdown series + Calendar-Year Return API contract (done) |
| **13C** | Metric Sheet charts: Calendar-Year Return bar, Drawdown area, monthly heatmap scale (done) |

## Cash Ledger — frontend guardrails

These rules apply to all Cash phases (see [cash-ledger.md](./cash-ledger.md), `.cursor/rules/320-cash-ledger.mdc`):

| Rule | Requirement |
|------|-------------|
| **Balances** | React **does not compute** cash balances, running totals, or future-impact simulation. Display `GET /cash/balances` and ledger API fields only. |
| **Shortfall** | Use API `required`, `available`, `shortfall`, `currency` (and `affected_entries` on 409). Guide user to add or edit **same-currency** cash on `/cash` — no implicit FX in the UI. |
| **`/transactions`** | Asset transaction table + unified **Add/Edit** modal (Stock, MF, Cash deposit/withdrawal). **Not** a merged client-side ledger; no fake pagination across cash + asset rows. |
| **`/cash`** | Cash balance table, ledger, manual edit/delete, cash-aware status. Primary place to manage ledger rows after a cash deposit from Transactions. |
| **API routing** | Cash branch → `/api/v1/cash/*`. Stock/MF → `/api/v1/transactions`. Never `asset_type=CASH` on `/transactions`. |
| **Analytics surfaces** | Cash must not appear on Compare or Asset Metric Sheet. Dashboard `current_value` and Assets allocation chart use backend `allocation` / summary (Cash-6A). |
| **Future Activity** | If a unified timeline is needed, use a backend activity endpoint — do not join cash + transactions in the client. |

## Transactions — unified Add modal (Cash-3G) — **Implemented**

Route `/transactions` — primary entry for recording activity:

| Record type | Submit API | Edit from this modal |
|-------------|----------|----------------------|
| **Cash** | `POST /cash/deposits` or `POST /cash/withdrawals` | No — edit on `/cash` |
| **Stock** | `POST/PUT /transactions` | Yes |
| **Mutual Fund** | `POST/PUT /transactions` (`asset_type: MUTUAL_FUND`) | Yes |

- Default record type: **Stock** (existing flow).
- Cash: Action (Deposit / Withdrawal), portfolio (required when All Portfolios scope), date, currency (20 codes), amount, source of funds, note.
- Insufficient withdrawal: `CashApiError` shortfall display (required / available / shortfall).
- Stock / MF **BUY** on cash-aware portfolios: `TransactionApiError` with shortfall panel; **Recommended action** (Cash-4C): **Add missing cash and continue** — `POST /cash/deposits` with backend `shortfall` amount and `currency` (same-currency only), then retries original BUY; partial-success warning if deposit succeeds but retry fails; link **Open Cash page** → `/cash`.
- `CashShortfallDisplay.jsx` — shared shortfall panel for cash withdrawal (amounts only) and asset BUY (`purchase` guidance).
- `ApiError` / `TransactionApiError` / `CashApiError` — structured errors; transaction create/update parse response JSON once.
- After cash success: success banner on Transactions page; asset table **not** refetched; link to `/cash` ledger.
- React does not compute cash balances; no unified activity list in this phase.

Component: `CashEntryFormFields.jsx` (shared cash form fields); `TransactionModal.jsx`.

## Cash-aware portfolio status (Cash-4A.2) — **Implemented**

`CashAwarePortfolioStatus.jsx` — shown on **Cash** and **Transactions** when a single portfolio is selected in the sidebar:

| State | Copy | Actions |
|-------|------|---------|
| **On** | “Cash-aware mode is on. Purchases require available cash.” | None |
| **Off** | “Cash-aware mode is off. Purchases can be recorded without cash balance checks.” | **Enable cash-aware mode** (confirm → `PUT /portfolios/{id}`) |
| **All Portfolios** | “Cash-aware mode is configured per portfolio. Select a single portfolio to enable it.” | No enable button |

**Settings** → Portfolios: table column **Cash-aware** (On/Off) + **Enable cash-aware** per legacy row (`PortfolioManagement.jsx`).

Existing portfolios stay legacy until enabled; new portfolios default on (Cash-4A.1). No disable button in UI.

## Cash page (`/cash`) — **Implemented** (Cash-3B)

Route: `pages/Cash.jsx` · `pages/Cash.css` · sidebar nav **Cash** (after Transactions).

Backend supplies balances and ledger rows. React **displays only** — no cash balance math or display-currency totals on this page. `CurrencyValue` formats native amounts.

| Section | Behavior |
|---------|----------|
| **Balances** | `GET /cash/balances` with `portfolioContext.apiQuery`; table + `totals_by_currency` for all scope |
| **Ledger** | `GET /cash/ledger` with filters and backend pagination |
| **Cash-aware status** | `CashAwarePortfolioStatus` below header (Cash-4A.2) |
| **Deposit / withdrawal** | Modals → `POST /cash/deposits`, `POST /cash/withdrawals`; insufficient withdrawal shows API shortfall fields |
| **Edit / delete** | Manual rows only → `PUT`/`DELETE /cash/ledger/{id}`; edit reuses modal; delete confirm; **Cash-4D** future-impact panel (`CashFutureImpactDisplay`) with `affected_entries` — no cascade delete |
| **Backfill wizard (Cash-7C)** | **Backfill Cash** → `CashBackfillWizard` modal: configure dates → `previewCashBackfill` → review API tables (read-only amounts) → `applyCashBackfill` (`confirmed: true`) → optional **Enable cash-aware** via `PUT /portfolios/{id}`; refreshes balances/ledger after apply; no React backfill math |

Page layout: [page-layouts.md](./page-layouts.md) §12. Design: [cash-ledger.md](./cash-ledger.md).

## Future — Cash Ledger UI (remaining phases)

| Surface | Phase | Behavior |
|---------|-------|----------|
| **Cash on Dashboard / allocation** | Cash-6A **done** | Dashboard KPI `current_value` from summary; Assets donut from `allocation` (`Cash EUR`, etc.); no React cash math |
| **Manual BUY add missing cash + continue** | Cash-4C | **Done** — `PurchaseShortfallAction` on `TransactionModal` |
| **CSV import cash preview** | Cash-5 | **Done** — `previewCsvImportCash` + `CsvImportCashPreviewModal`; confirmed import only |
| **Backfill wizard** | Cash-7C **done** | `CashBackfillWizard` on `/cash`; preview/apply APIs only; explicit enable |
| **Transfers** | Cash-8 | Cross-portfolio / FX transfer form → `POST /cash/transfers` |

Cash must **not** appear on Compare or Asset Metric Sheet as an investment subject.

## Implementation Constraints

- Preserve `/api/v1` contracts; no backend changes for design work
- Do not modify KPulla5
- Inspect existing components before editing; smallest safe diff
- Update Vitest tests when selectors, roles, or visible text change
- Run `make test-frontend` and `npm run build` after changes

## Display currency loading (FIX-1)

- `PortfolioProvider` exposes `settingsLoaded` and keeps `apiQuery` as `null` until `GET /settings` resolves (or `disableFetch` test mode).
- Dashboard and other scoped pages should not fetch portfolio APIs until `settingsLoaded && apiQuery`.
- Dashboard ignores stale summary/performance responses via request sequence refs when scope or currency changes mid-flight.
- Sidebar display currency `<select>` is disabled until settings load; changing it still persists via `PUT /settings`.
