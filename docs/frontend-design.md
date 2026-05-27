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

- Hero metric row: Total Value emphasized, then Invested, Total P/L, XIRR
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

- Tear-sheet layout: hero KPIs → cost basis / market sections → transaction history
- Breadcrumb back to Assets

### Transactions

- Header with record count and primary actions (Import, Add)
- Row checkboxes + select-all on visible page; bulk toolbar when selected: assign to real portfolio (full PUT per row), clear selection on success
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
| **8B** | Legacy CSS alias removal (done) |

## Implementation Constraints

- Preserve `/api/v1` contracts; no backend changes for design work
- Do not modify KPulla5
- Inspect existing components before editing; smallest safe diff
- Update Vitest tests when selectors, roles, or visible text change
- Run `make test-frontend` and `npm run build` after changes
