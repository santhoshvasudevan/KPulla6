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

Recharts uses hex mirrors in `chartTheme.js` — not CSS variables.

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

- Fixed sidebar (~260px): brand, main navigation, portfolio/currency selectors at bottom, optional data note in footer
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
