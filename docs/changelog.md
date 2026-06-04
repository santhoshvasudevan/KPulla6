# Changelog — KPulla6

## 2026-06-03 — FEAT: App shell theme selector (Light / Dark / System)

- Header theme select (System / Light / Dark) with `localStorage` key `kpulla6.themePreference` (default system)
- Early `theme-init.js` + `ThemeProvider` apply `data-theme` on `<html>`; light token overrides under `[data-theme='light']`
- Recharts `chartTheme.js` reads CSS variables per resolved theme
- Docs: `docs/frontend-design.md`, `docs/current-state.md`

---

## 2026-06-03 — FEAT: User authentication and per-user data scoping

### Added
- Session auth API: `/api/v1/auth/login`, `logout`, `register`, `me`, `password-reset`, `csrf`
- Google OAuth via django-allauth (`/accounts/google/login/`)
- `Portfolio.user` FK and `AppSettings.user` OneToOne (per-user settings)
- Data migration assigning existing portfolios/settings to `santhoshkgvasudevan@gmail.com`
- Management command: `set_user_password` (uses `INITIAL_USER_PASSWORD` env var)
- Frontend login/register/forgot-password pages, auth context, protected routes, sidebar logout
- Docs: `docs/auth.md`

### Changed
- All `/api/v1` portfolio/transaction/settings/analytics routes require authentication (`401`/`403` when unauthenticated)
- DRF default: `SessionAuthentication` + `IsAuthenticated`; health + auth endpoints remain public
- Frontend API client sends `credentials: 'include'` and CSRF token on mutating requests

### Impact
- Unauthenticated users land on `/login`; existing dashboard remains at `/` after sign-in
- Transaction count unchanged after migration (verified via `make db-safety-check`)

## 2026-06-02 — FEAT: Metric Sheet visualization charts (Phase 13C)

### Added
- `MetricSheetYearlyReturnChart` — Calendar-Year Return bar chart from `periodic_returns.yearly` with TWROR helper copy
- `MetricSheetDrawdownChart` — drawdown area chart from `drawdown_series` with worst-episode shading by `drawdown_periods.worst` rank
- `metricSheetMonthlyHeatmap.js` — five-band monthly return heatmap tone mapping
- `metricSheetChartHelpers.js` — display-only chart data organization helpers

### Changed
- `MetricSheetMonthlyReturnsGrid` — stronger heatmap background scale (red / yellow / green bands) with visible cell text
- Dashboard + Asset Detail Metric Sheet — Calendar-Year Return chart above Periodic Returns; Drawdown chart above Worst Drawdowns

### Impact
- Metric Sheet periodic/drawdown sections are easier to scan; Compare page unchanged (tables only)

## 2026-06-02 — FEAT: Metric Sheet drawdown series + Calendar-Year Return contract (Phase 13B)

### Changed
- `periodic_returns.yearly` documented as **Calendar-Year Return** — cash-flow-adjusted daily TWROR returns compounded per calendar year (existing `resample_yearly_returns` semantics; no duplicate calculation)
- `drawdown_periods.worst` entries now include `rank` (1 = deepest drawdown)

### Added
- `drawdown_series` top-level array on portfolio, asset, and compare Metric Sheet responses — dated running drawdown fractions (0 or negative) from `finance/drawdowns.drawdown_series`
- Compare subjects include `drawdown_series` on the aligned common window
- Tests: drawdown series shape/fractions, worst-period rank, calendar-year return cash-flow regression in `test_finance_returns.py`

### Impact
- Backend contract ready for Phase 13C frontend charts (Calendar-Year Return bar chart, drawdown line chart with worst-region shading)

## 2026-06-02 — Phase 13A: Sidebar context controls at top

### Changed
- **Layout:** Portfolio View and Display Currency selectors moved from sidebar bottom to directly below the Portfolio Insight brand header, above main navigation
- **Layout.css:** Controls use compact spacing with bottom divider; footer keeps `margin-top: auto` so the cached-data note stays at the sidebar bottom on desktop

### Added
- `Layout.test.jsx` — verifies portfolio view and display currency appear before navigation links in DOM order

### Impact
- Primary portfolio scope and display currency controls are immediately visible without scrolling the sidebar

## 2026-06-01 — FIX: Metric Sheet cumulative return and CAGR aligned with performance chart

### Changed
- `build_metric_sheet_from_daily_returns` — `metrics.return.cumulative_return` uses the money-weighted terminal formula from `GET /portfolio/performance?metric=cumulative_return` (not compounded TWROR daily returns); removed TWROR fallback when compounding was unavailable
- `metrics.return.cagr` — annualizes that economic cumulative return over the selected range (`cagr_from_total_return`), not TWROR compounding
- `finance/performance_stats.py` — `economic_cumulative_return_fraction`, `contributions_and_withdrawals_through`, `cagr_from_total_return`; shared flow rollup used by `performance_service`

### Added
- Backend regression: Metric Sheet cumulative return matches performance API; cumulative return ≠ TWROR with staggered buys
- Frontend regression: Metric Sheet summary cards render distinct cumulative return, CAGR, TWROR, and XIRR values

### Impact
- Dashboard Metric Sheet headline return metrics now match the performance chart for the same portfolio, range, and display currency

## 2026-05-31 — PERF: Range-aware all-scope value series builder (Phase B2B)

### Changed
- `_build_portfolio_value_timeseries` / `build_all_scope_portfolio_value_timeseries` — optional `emit_start_date`; non-ALL ranges bootstrap opening holdings/prices/NAV/FX at range start and emit only the requested window (ALL unchanged)
- `last_stock_prices_on_or_before` / `last_mutual_fund_navs_on_or_before` — bootstrap helpers for price/NAV forward-fill before range start
- `build_portfolio_performance` / `build_portfolio_performance_metrics` — pass `emit_start_date` for non-ALL ranges; cumulative return iterates the shorter series only
- `_slice_timeseries_for_range` — accepts optional true `inception` when series is pre-sliced

### Added
- `backend/tests/test_range_aware_series_b2b.py` — parity vs full-build+slice, opening holdings, NAV/FX bootstrap, split, TWROR re-chain, 1Y bulk-FX query guard

### Impact
- Non-ALL performance/Metric Sheet paths emit ~366 days instead of ~2,426; service-layer 1Y latency roughly halved with unchanged API shapes and financial semantics

## 2026-05-31 — PERF: All-scope bulk FX maps for performance and Metric Sheet (Phase B1)

### Changed
- `build_all_scope_portfolio_value_timeseries` — preloads `load_fx_rate_maps()` per child portfolio and converts daily values via `convert_amount_with_fill_from_maps()` / `fx_lookup_from_maps()` instead of per-day `convert_amount_with_fill()` DB lookups
- `build_all_scope_external_flows` — same bulk FX map approach for flow conversion
- `fx.lookup.convert_amount_with_fill_from_maps()` — in-memory 7-day fill helper matching `convert_amount_with_fill` semantics

### Added
- Regression: `test_performance_all_scope_value_history_uses_bulk_fx_lookup` (query count guard)

### Impact
- All-scope performance and Metric Sheet read paths drop from ~9,000 FX SELECTs to a handful of bulk loads; endpoint latency reduced with unchanged financial semantics and API shapes

## 2026-05-31 — FIX: All Portfolios cumulative_return and TWROR gaps (Phase 12B follow-up #3)

### Fixed
- `build_portfolio_performance` (`metric=cumulative_return` / `twror`, `portfolio_scope=all`) — uses the same all-scope display-currency value series as `metric=value`, plus aggregated per-portfolio external flows converted to display currency (`build_all_scope_external_flows`)
- `build_portfolio_performance_metrics` (Metric Sheet) — same all-scope display-currency value/flow path for `portfolio_scope=all`

### Added
- `build_all_scope_external_flows()` in `portfolios/performance_service.py`
- Regressions: `test_performance_all_scope_cumulative_return_no_gap_with_pln_stock_and_inr_mf`, `test_performance_all_scope_twror_no_gap_with_pln_stock_and_inr_mf`, `test_performance_all_scope_value_cumulative_twror_share_valid_calendar`, `test_analytics_scope_all_pln_stock_uses_display_currency_series`

### Impact
- All-scope TWROR semantics: computed from aggregated display-currency portfolio value and external cash-flow series
- Dashboard Cumulative Return and TWROR charts no longer show multi-year null gaps when PLN/EUR/INR portfolios are combined

## 2026-05-31 — FIX: All Portfolios value history gap after DNP.WA buy (Phase 12B follow-up #2)

### Fixed
- `build_portfolio_performance` (`metric=value`, `portfolio_scope=all`) — uses per-portfolio value timeseries converted to display currency and aggregated (same strategy as summary), instead of one pooled series in a single `portfolio_base`
- Root cause: pooled all-scope build used INR as base (earliest transaction); Scalablefolio `DNP.WA` (PLN-denominated) required missing `PLN→INR` FX from 2024-03-27 until 2026-05-28, nulling 792 daily points
- `build_all_scope_portfolio_value_timeseries` in `portfolios/summary_service.py`; shared `_aggregate_timeseries_lists` helper

### Added
- Regression: `test_performance_all_scope_eur_value_history_no_gap_with_pln_stock`

### Impact
- Dashboard Value History line is continuous for All Portfolios + EUR display; last chart point equals Current Value KPI (same valuation/FX path as summary)

## 2026-05-31 — FIX: All Portfolios value history vs summary current value (Phase 12B follow-up)

### Fixed
- `build_portfolio_value_timeseries` — stock holdings now convert to `portfolio_base` before summing with mutual fund values (fixes mixed EUR stock + INR MF portfolios under `portfolio_scope=all` where EUR amounts were added to INR totals)
- Regression: `test_all_scope_summary_current_value_matches_performance_last_value`

### Impact
- Dashboard Value History last point now aligns with Current Value KPI for All Portfolios + display currency EUR (within FX timing tolerance)

## 2026-05-31 — FIX: Dashboard Metric Sheet layout + MF NAV freshness warnings (Phase 12B)

### Fixed
- Dashboard Metric Sheet uses full content width (overrides SectionCard 480px cap); section moved outside chart wrapper with increased internal spacing
- MF NAV Metric Sheet warnings use freshness rule (`MF_NAV_STALE_AFTER_DAYS = 5`): no warning for weekend/holiday gaps when latest cached NAV is recent; stale vs missing copy separated

### Added
- Tests: `test_analytics_mf_nav_freshness.py`; asset metrics NAV freshness API cases; Dashboard full-width layout assertion

### Changed
- `docs/api-design.md`, `docs/architecture.md`, `docs/frontend-design.md`, `docs/current-state.md`

### Impact
- UX/data-quality refinement only; no new metrics, caching, exports, or read-path external calls

## 2026-05-31 — AUDIT: Metric Sheet release readiness (Phase 12A)

### Fixed
- Compare API: TWROR (and cumulative fallback) now computed on the aligned common window, not the independent range slice (`analytics/services.py`)
- Compare metric table labels aligned with Dashboard/Asset Detail (`Volatility (annualized)`, `Sharpe Ratio`, etc.)
- Yearly fallback table wrapped in `.metric-sheet-table-scroll`
- Dashboard benchmark table guard matches Asset Detail (`selectedBenchmark` required)

### Added
- Compare API contract tests: common-window warning, `xirr_scope`, metrics shape, aligned TWROR
- Frontend tests: warning severity mapping, XIRR note on Compare, yearly scroll wrapper, empty yearly compare state

### Changed
- `docs/api-design.md`, `docs/frontend-design.md`, `docs/current-state.md`

### Impact
- Regression audit and small consistency fixes only; no new metrics, routes, exports, or caching

## 2026-05-31 — FEAT: Compare metric scanability (Phase 11B)

### Added
- `compareMetricRanking.js` — display-only two-subject metric comparison for highlight state (`better` / `worse` / `tie` / `neutral` / `unknown`)
- Subtle per-cell highlights in `CompareMetricTable` with accessible labels and legend note
- Tests: `compareMetricRanking.test.js`; Compare + monthly grid updates in `metricSheet.test.jsx`

### Changed
- `MetricSheetMonthlyReturnsGrid` — yearly total column header renamed to **Year Return**
- Compare drawdown sections verified to use `.metric-sheet-table-scroll` wrappers
- `docs/frontend-design.md`, `docs/current-state.md`

### Impact
- Frontend display enhancement only; no backend APIs, exports, or client-side analytics calculations

## 2026-05-31 — FEAT: Metric Sheet monthly returns grid (Phase 11A)

### Added
- `MetricSheetMonthlyReturnsGrid` — year × month grid from backend `periodic_returns.monthly`; full-year column from `periodic_returns.yearly`
- `metricSheetMonthlyGrid.js` — display-only period parsing and grid layout helpers
- Tests: `metricSheetMonthlyGrid.test.js`; updates to `metricSheet.test.jsx`, `Dashboard.test.jsx`

### Changed
- `MetricSheetPeriodicReturnsTable` — monthly list replaced by grid; compact yearly table only when monthly is empty
- Compare page unchanged (yearly side-by-side only)
- `docs/frontend-design.md`, `docs/current-state.md`

### Impact
- Frontend display enhancement only; no backend APIs, caching, exports, or client-side return calculations

## 2026-05-31 — FIX: Metric Sheet polish (Phase 10B)

### Changed
- Dashboard Metric Sheet benchmark selector moved to section header (always visible/editable); chart overlay still uses the same benchmark when cumulative return or TWROR is selected
- `.metric-sheet-table-scroll` wrappers on wide Metric Sheet / Compare tables
- Asset Detail waits for `settingsLoaded && apiQuery` before fetching asset detail
- Dashboard stale Metric Sheet response test added
- `analytics/services.py` — clearer missing cached price / NAV warnings; split-warning path reuses pre-built asset timeseries
- Tests: Dashboard, Asset Detail, Metric Sheet component, analytics asset API

### Impact
- UX/reliability polish only; no new metrics, caching, or schema changes

## 2026-05-31 — FEAT: Metric Sheet periodic returns and drawdown periods UI (Phase 9B)

### Added
- `MetricSheetPeriodicReturnsTable`, `MetricSheetDrawdownPeriodsTable`
- `ComparePeriodicReturnsSection` (yearly side-by-side), `CompareDrawdownPeriodsSection` (per subject)
- Dashboard, Asset Detail, and Compare integration; fixture and test updates

### Changed
- `docs/frontend-design.md`, `docs/current-state.md`

### Impact
- Display-only; no backend or finance logic changes

## 2026-05-31 — FEAT: Metric Sheet periodic returns and drawdown periods (Phase 9A)

### Added
- `worst_drawdown_periods` in `finance/drawdowns.py` — peak/trough/recovery episodes from dated daily returns
- `periodic_returns` (`monthly`, `yearly`) and `drawdown_periods.worst` on portfolio, asset, and compare Metric Sheet APIs
- Tests: `test_finance_drawdowns.py` (worst periods), analytics API tests for new blocks

### Changed
- `analytics/services.py` — `build_periodic_returns_block`, `build_drawdown_periods_block`, empty payloads
- `docs/api-design.md`, `docs/current-state.md`

### Impact
- Fractional returns only; no DB migrations; no frontend changes; existing `metrics` fields unchanged

## 2026-05-31 — FEAT: Metric Sheet UX hardening (Phase 8E)

### Changed
- Compare asset pickers prefer open holdings; closed labeled `(closed)` with optgroups
- Compare range context: requested range + common aligned dates in one note
- XIRR full-scope helper text clarified across summary cards and compare table
- `MetricSheetWarnings` severity mapping for FX, NAV, price, and benchmark overlap messages
- Tests: `compareHoldings.test.js`, `metricSheetCopy.test.js`; updates to Compare and Metric Sheet tests

### Impact
- No backend or finance logic changes; display-only UX pass before Phase 9

## 2026-05-31 — FEAT: Compare Metric Sheet UI (Phase 8D)

### Added
- `/compare` route and sidebar **Compare** navigation
- `Compare.jsx` — dual asset pickers from holdings, range/benchmark controls, `getCompareMetricSheet` fetch
- `CompareNormalizedChart`, `CompareMetricTable`, compare CSS and test fixture
- Tests: `Compare.test.jsx`, `metricSheet.test.jsx` compare cases, Layout nav test

### Changed
- `frontend/src/App.jsx`, `frontend/src/components/Layout.jsx`, `metricSheet/index.js`
- `docs/frontend-design.md`, `docs/current-state.md`

### Impact
- Normalized cumulative return chart and side-by-side metrics from backend only; MF multi-folio shows friendly error without folio picker UX

## 2026-05-30 — FEAT: Asset Detail Metric Sheet integration (Phase 8C)

### Added
- `AssetDetailMetricSheet` component with local range and benchmark controls
- Asset Detail page integration below hero KPIs via `getAssetMetricSheet`
- `AssetDetail.test.jsx` Metric Sheet tests (9 cases)

### Changed
- `frontend/src/pages/AssetDetail.jsx`, `AssetDetail.css`
- `docs/frontend-design.md`, `docs/current-state.md`

### Impact
- Independent Metric Sheet loading/errors; folio_number passed for MF assets; Compare UI deferred

## 2026-05-30 — FEAT: Dashboard Metric Sheet integration (Phase 8B)

### Added
- Portfolio Metric Sheet section on Dashboard below the main performance chart
- Independent `getPortfolioMetricSheet` fetch with section-local loading and error states
- Dashboard tests for Metric Sheet API params, rendering, warnings, null metrics, and isolated failures

### Changed
- `frontend/src/pages/Dashboard.jsx`, `Dashboard.css`, `Dashboard.test.jsx`
- `docs/frontend-design.md`, `docs/current-state.md`

### Impact
- Reuses Dashboard scope, currency, range, and benchmark controls; no finance calculations in React
- Asset Detail and Compare UI deferred to Phase 8C+

## 2026-05-30 — FEAT: Metric Sheet frontend foundation (Phase 8A)

### Added
- `getPortfolioMetricSheet`, `getAssetMetricSheet`, `getCompareMetricSheet` in `frontend/src/api.js`
- `frontend/src/utils/metricFormatters.js` — display-only fraction/ratio/day formatting
- `frontend/src/components/metricSheet/` — reusable Metric Sheet section, summary cards, risk/return tables, benchmark table, warnings
- Tests: `metricFormatters.test.js`, `metricSheet.test.jsx`; API client tests in `api.test.js`

### Changed
- `docs/frontend-design.md`, `docs/current-state.md` — Phase 8A status

### Impact
- No page integration yet; no backend changes; no finance calculations in React

## 2026-05-30 — FEAT: Compare API for Quantitative Statistics (Phase 7)

### Added
- `GET /api/v1/analytics/compare` — two-asset side-by-side Metric Sheet comparison
- `align_multi_subject_returns`, `normalized_cumulative_return_series` in `finance/comparison.py`
- `_prepare_asset_daily_metrics_inputs`, `build_analytics_compare`, `parse_compare_subjects` in `analytics/services.py`
- `CompareAnalyticsView` in `analytics/views.py`
- `backend/tests/test_analytics_compare_api.py` (15 cases); finance compare alignment tests

### Changed
- Asset Metric Sheet path refactored to shared `_prepare_asset_daily_metrics_inputs`
- `docs/api-design.md`, `docs/current-state.md`, `docs/architecture.md`

### Impact
- No DB migrations; no frontend; portfolio/asset Metric Sheet response shapes unchanged
- Compare metrics computed over common overlapping dates only; unknown asset in scope → 404

## 2026-05-30 — HARDENING: Metric Sheet stock split × cached price invariant (Phase 6B)

### Added
- `_split_adjusted_price_inconsistency_warnings` in `analytics/services.py` — detects likely raw nominal prices around splits
- `backend/tests/test_analytics_split_metrics_api.py` (6 cases): adjusted-price stability, raw-price warning, split flow neutrality

### Changed
- `docs/architecture.md`, `docs/api-design.md`, `docs/current-state.md` — split-adjusted price invariant documented
- Metric Sheet portfolio + asset endpoints append warning when raw split-price mismatch detected

### Impact
- No formula changes; no migrations; yfinance sync already stores Adj Close
- Raw manually inserted nominal prices: metrics may compute but API warns — not silently trusted

## 2026-05-30 — FEAT: Asset-level analytics Metric Sheet API (Phase 6)

### Added
- `GET /api/v1/analytics/assets/{asset_symbol}/performance-metrics` — stock + MF asset Metric Sheet
- `build_asset_performance_metrics`, `build_metric_sheet_from_daily_returns` in `analytics/services.py`
- `AssetPerformanceMetricsView` in `analytics/views.py`
- `backend/tests/test_analytics_asset_metrics_api.py` (11 cases)

### Changed
- Portfolio Metric Sheet assembly refactored to shared `build_metric_sheet_from_daily_returns`
- `docs/api-design.md`, `docs/current-state.md`, `docs/architecture.md`

### Impact
- No DB migrations; no frontend; summary/performance API shapes unchanged
- Asset series built from scoped transactions + cached prices/NAV/FX (reuses `build_portfolio_value_timeseries` for single asset/MF holding)

## 2026-05-30 — REFACTOR: Analytics Metric Sheet API boundaries (Phase 5B)

### Changed
- `portfolios/summary_service.py` — public `compute_scope_xirr()` wrapper (full-scope XIRR shared by summary and analytics)
- `backend/analytics/services.py` — import public XIRR helper; `metrics.return.xirr_scope: "full_scope"`; docstring notes on ratio vs currency
- `backend/tests/test_analytics_performance_metrics_api.py` — public-import guard + `xirr_scope` assertions (12 cases)
- `docs/api-design.md` — XIRR full-scope vs range-based metrics; ratio/currency wording

### Impact
- No finance formula changes; summary/performance response shapes unchanged
- Analytics clients can distinguish range-sliced metrics from full-scope XIRR before Phase 6 asset-level work

## 2026-05-30 — FEAT: Portfolio analytics API (Phase 5)

### Added
- `GET /api/v1/analytics/performance-metrics` — portfolio Metric Sheet (return, risk, drawdown, period metrics; optional benchmark block)
- `backend/analytics/services.py`, `views.py`, `urls.py`, `serializers.py` (placeholder)
- `backend/tests/test_analytics_performance_metrics_api.py` (10 cases)
- `portfolios/performance_service.py` — `portfolio_external_flows`, `portfolio_flows_known_on_date` public helpers

### Changed
- `backend/api/urls.py` — include `analytics.urls`
- `docs/api-design.md`, `docs/current-state.md`, `docs/architecture.md`

### Impact
- Read path uses cached DB only; metrics computed on query from value/flow → `daily_returns_from_values`. No frontend UI. Summary/performance API shapes unchanged.

## 2026-05-30 — FEAT: Benchmark-relative Metric Sheet metrics (Phase 4)

### Added
- `backend/finance/comparison.py` — `align_return_series`, `correlation`, `beta`, `alpha`, `tracking_error`, `active_return`, `information_ratio`, `treynor_ratio`, `benchmark_summary`
- `backend/tests/test_finance_comparison.py` — alignment, correlation, beta, alpha, tracking error, active return, information ratio, Treynor, summary tests

### Changed
- `backend/finance/__init__.py` — export comparison helpers
- `docs/current-state.md`, `docs/architecture.md` — Phase 4 status; clarify `benchmarks.py` vs `comparison.py`

### Impact
- Pure finance only; no API/UI/DB. `finance/benchmarks.py` unchanged (performance chart rebasing).

## 2026-05-30 — FEAT: Core Metric Sheet performance metrics (Phase 3)

### Added
- `backend/finance/performance_stats.py` — `cumulative_return`, `cagr`, `best_return`, `worst_return`, `win_rate`, `average_return`, `period_summary`
- `backend/finance/risk_metrics.py` — `annualized_volatility`, `downside_deviation`, `sharpe_ratio`, `sortino_ratio`
- `backend/finance/drawdowns.py` — `drawdown_series`, `max_drawdown`, `longest_drawdown_days`, `calmar_ratio`
- `backend/finance/_return_inputs.py` — shared parsing for `DailyReturnPoint` / bare fractions
- Tests: `test_finance_performance_stats.py`, `test_finance_risk_metrics.py`, `test_finance_drawdowns.py`

### Changed
- `backend/finance/__init__.py` — export Phase 3 helpers
- `docs/current-state.md`, `docs/architecture.md`

### Impact
- Pure finance only; no API, UI, DB persistence, or benchmark-relative metrics (Phase 4).

## 2026-05-30 — FEAT: Finance return-series foundation (Phase 2)

### Added
- `backend/finance/returns.py` — framework-independent helpers: `period_return`, `daily_returns_from_values`, `daily_returns_from_twror_series`, `compound_return`, `chain_returns`, `resample_monthly_returns`, `resample_yearly_returns`; datatypes `ValuePoint`, `DailyReturnPoint`, `PeriodReturnPoint`.
- `backend/tests/test_finance_returns.py` — golden tests for period/daily/TWROR-derived returns, compounding, monthly/yearly resampling, and `None` handling.

### Changed
- `backend/finance/__init__.py` — export new return helpers.
- `docs/current-state.md`, `docs/architecture.md` — Phase 2 return module documented.

### Impact
- No API routes, frontend UI, DB migrations, or persisted derived metrics. Metrics layer (`performance_stats`, `risk_metrics`, etc.) not wired yet.

## 2026-05-30 — DOCS: Analytics documentation terminology cleanup (Phase 1B)

### Changed
- Replaced external package/report terminology (`QuantStats`, `tear sheet`, etc.) with app-owned terms: **Quantitative Statistics**, **Metric Sheet**, **performance metric sheet**, **analytics metrics** across `docs/architecture.md`, `docs/current-state.md`, `docs/api-design.md`, `docs/frontend-design.md`, and the Phase 1 changelog entry.

### Impact
- Documentation only. No code, API, or runtime behavior change.

## 2026-05-30 — DOCS: Quantitative Statistics / Metric Sheet architecture (Phase 1)

### Added
- `docs/architecture.md` — **Quantitative Statistics / Metric Sheet architecture**: subject levels (portfolio, asset, compare), TWROR-derived daily returns as primary technical input, separate XIRR/FIFO roles, planned `finance/` modules (`returns`, `performance_stats`, `risk_metrics`, `drawdowns`, `comparison`), `analytics/services` orchestration, proposed API routes, frontend surfaces, warning behavior, MVP on-query calculation (no persistence of derived metrics), deferred cache design.
- `docs/api-design.md` — **Proposed** analytics endpoints (`performance-metrics`, asset metrics, `compare`) with rough JSON shapes; marked not implemented.
- `docs/frontend-design.md` — Future Metric Sheet UI: Performance Quality cards, risk/return table, drawdown and periodic return tables, asset detail section, compare page; API-only values.
- `docs/current-state.md` — Analytics Metric Sheet planned; Phase 1 docs complete; no runtime change.

### Impact
- Documentation/design only. No migrations, models, API routes, `finance/` implementation, or frontend UI in this phase.

## 2026-05-29 — PERF: Dashboard summary skips unused timeseries

### Changed
- Dashboard `fetchDashboardSummary` now passes `include_timeseries=false` — KPI cards and XIRR do not need summary timeseries; charts continue to use `GET /portfolio/performance`.
- `api.js` — `fetchDashboardSummary(scopeParams, options)` supports `{ includeTimeseries: false }`; summary in-flight cache key includes `include_timeseries` so lightweight and full responses do not collide.

### Impact
- All-scope summary load drops from ~20s to ~0.1s on typical dev data (investigation); Dashboard initial load is no longer blocked on unused daily series computation.

## 2026-05-29 — FEAT: Transactions page column filters (portfolio / symbol / date)

### Added
- **Transactions filter bar** — filter the full transaction dataset (not just the visible page) by portfolio, symbol (searchable multi-select), and date (Earlier than / Later than / Between). Active filter chips + Clear filters; filters reset to page 1 and are preserved across pagination.
- `GET /api/v1/transactions` query params: `symbols` (comma-separated, case-insensitive), `date_from`, `date_to`, plus `date_after` / `date_before` aliases. Existing `asset_symbol` and scope params unchanged.
- `GET /api/v1/transactions/filter-options` — distinct portfolios / symbols / types / date bounds for the current scope.
- Frontend `TransactionFilterBar` component (+ CSS); `fetchTransactionFilterOptions` and `filters` arg on `fetchTransactions` in `api.js`.

### Changed
- `transactions/services.py` — `list_transactions` accepts `symbols` / `date_from` / `date_to` (applied before pagination); new `get_transaction_filter_options`.
- `transactions/views.py` — date format / range validation returns `400`; new `TransactionFilterOptionsView`; route registered in `api/urls.py`.

### Tests
- `backend/tests/test_transaction_filters_api.py` — symbol/date/portfolio filters, pagination ordering, `400` validation, MF scheme code, filter-options scoping.
- `frontend/src/pages/Transactions.test.jsx` — filter controls, per-filter API params, page reset, pagination preservation, clear, chips.

## 2026-05-28 — FIX-2: All Portfolios summary aggregation (mixed currency / MF)

### Fixed
- **`portfolio_scope=all` under-counted headline totals** when active portfolios mixed EUR stocks and INR mutual funds — stock EUR and MF INR were merged before FX alignment, then treated as one base currency
- All Portfolios `current_value` / `total_invested` / P/L fields now equal the sum of individual active portfolio summaries in the requested `display_currency`

### Changed
- `portfolios/summary_service.py` — `_build_all_active_portfolio_summary()` aggregates per-portfolio `_build_single_portfolio_summary()` results; single-portfolio path unchanged
- All-scope response `base_currency` set to `display_currency`; `fx_status` combined from child summaries; warnings prefixed with portfolio name

### Added
- `backend/tests/test_portfolio_summary_all_scope_aggregation.py` — mixed stock/MF, INR display, inactive exclusion, fx_status, monetary field sums

## 2026-05-28 — FIX-1: Dashboard display-currency flicker and stale API responses

### Fixed
- **Dashboard currency flicker** — `PortfolioProvider` no longer fires scoped API calls before `GET /settings` completes; `apiQuery` is `null` until `settingsLoaded`
- **Stale summary/performance overwrite** — Dashboard uses monotonic request IDs so older in-flight responses are ignored when `apiQuery` changes

### Changed
- `portfolioContext.jsx` — `settingsLoaded`, `selectedDisplayCurrency` starts `null`, optional `initialDisplayCurrency` for test harnesses with `disableFetch`
- `Dashboard.jsx` — waits for settings readiness; sequence guards on summary and performance effects
- `Layout.jsx` — display currency selector disabled until settings load

### Added
- Frontend tests: `portfolioContext.test.jsx`, stale-response and settings-delay cases in `Dashboard.test.jsx`, sidebar currency tests in `Layout.test.jsx`

## 2026-05-28 — SYNC-1: Incremental sync correctness and benchmark backfill parity

### Fixed
- **Benchmark sync** — same start-date rules as stock sync: warm cache → latest index date + 1; backfill when earliest non-MF transaction anchor predates first cached index row
- **Benchmark anchor** — uses `earliest_stock_transaction_date()` (excludes mutual fund buys) instead of global `earliest_transaction_date()`

### Added
- `earliest_stock_transaction_date()` in `market_data/services/symbols.py`
- Benchmark warm-cache, backfill, anchor, and combined `sync_all_market_data` incremental tests in `test_market_data_sync.py`

### Changed
- Docs: `workflows.md`, `current-state.md`, `database.md`, `api-design.md` — refresh / incremental sync behavior

### Notes
- Stock, FX, and MF NAV sync behavior unchanged in this phase
- MF scheme codes remain excluded from yfinance stock sync

## 2026-05-28 — Dashboard KPI overflow for large INR amounts

### Fixed
- **MetricCard / CurrencyValue** — fluid `clamp()` typography, `nowrap`, grid `min-width: 0`, and ellipsis fallback so large INR KPI values stay inside card bounds
- **CurrencyValue** — `title` attribute carries full formatted amount for hover when truncated

### Added
- Frontend tests: `ui.test.jsx`, `Dashboard.test.jsx`

## 2026-05-28 — Stock price sync excludes mutual fund scheme codes

### Fixed
- **`make refresh` / `sync_market_data`** — stock/yfinance price sync no longer collects AMFI scheme codes from mutual fund transactions; MF NAV sync continues to handle those codes separately via AMFI
- **`stock_transaction_symbols()`** in `market_data/services/symbols.py` — excludes transactions with `MutualFundTransactionDetail` and symbols registered as `AssetType.MUTUAL_FUND`

### Added
- Regression tests in `test_market_data_sync.py` — stock symbol collection, stock sync, and combined `sync_all_market_data` routing

### Notes
- Fixes yfinance 404 / “possibly delisted” warnings for numeric MF scheme codes (e.g. 119062) during `make refresh`
- Benchmark, FX, and MF NAV sync unchanged

## 2026-05-27 — LAN / iPad access via Vite (port 5173)

### Changed
- **Vite** — `server.host: true` in `vite.config.js`; `make frontend` / `make dev` pass `--host 0.0.0.0`
- **Docs** — iPad/home LAN section in `workflows.md`, `README.md`; `.env.example` notes for empty `VITE_API_BASE_URL`

### Notes
- iPad opens `http://<mac-lan-ip>:5173` only; `/api` proxied to Django on the Mac (no CORS or `ALLOWED_HOSTS` LAN IP required for that path)

## 2026-05-27 — Makefile: `make refresh` includes mutual fund NAVs

### Changed
- **Makefile** — removed duplicate sync targets that bypassed `.env` / `setup-backend`; `make refresh` and `make sync-market-data` run `sync_market_data` (stocks, benchmarks, FX, mutual fund NAVs) with clear echo output
- **`make sync-mutual-fund-navs`** — runs `manage.py sync_mutual_fund_navs`
- **`sync_market_data` command** — WARNING styling when `mutual_funds_failed > 0` (failures visible in stdout)
- Docs: `workflows.md`, `README.md`, `current-state.md`

### Notes
- Backend `sync_all_market_data()` already included MF NAV sync by default (MF-9); Makefile now documents and routes through that single command
- Opt out: `python manage.py sync_market_data --skip-mutual-funds`

## 2026-05-27 — MF-11b: Mutual fund CSV import guidance (frontend)

### Added
- **Transactions** expandable “Supported CSV formats” panel — stock vs mutual fund column lists, import rules, inline MF example
- **Download sample MF CSV** — client-generated template (`csvImportGuidance.js`); no backend or NAV logic
- Frontend tests: `Transactions.test.jsx` (guidance, download button, import button unchanged), `csvImportGuidance.test.js`

### Changed
- Transactions import info banner — stock split/SWAP note retained; MF format details moved to expandable panel
- Docs: `current-state.md`, `frontend-design.md`, `page-layouts.md`

### Notes
- Backend MF CSV import unchanged (MF-11a)
- No stock sample CSV download in this phase

## 2026-05-27 — MF-11a: Mutual fund CSV import (backend)

### Added
- **Mutual fund CSV import** via existing `POST /api/v1/transactions/import-csv`
- Header detection: `Scheme Code` + `Folio Number` → MF format; stock CSV unchanged
- `parse_mutual_fund_transaction_csv`, `parse_import_csv` in `transactions/csv_import.py`
- MF rows routed to `create_mutual_fund_transaction()` (Asset, Profile, Folio, detail upsert)
- Cached DB NAV verification on import — no external AMFI/MFAPI calls
- `backend/tests/test_mutual_fund_csv_import.py` — 16 tests

### Changed
- `import_transactions_from_csv` branches on detected CSV format (stock vs MF)
- Docs: `api-design.md`, `mutual-funds.md`, `current-state.md`

### Notes
- Mixed stock + MF columns in one file → header validation error (not supported in MF-11a)
- Stock CSV import behavior and tests unchanged
- No frontend changes in this phase

## 2026-05-27 — Portfolio CRUD UI + bulk transaction assignment

### Added
- **Settings → Portfolios:** create, edit (name/description/base currency), deactivate non-default portfolios; max 5 active enforced in UI; backend validation errors displayed
- **`portfolioContext.reloadPortfolios()`** and **`selectPortfolio()`** — sidebar Portfolio View updates after portfolio changes; new portfolio auto-selected after create
- **Transactions bulk assign:** row checkboxes, select-all on page, toolbar to move selected transactions to a real portfolio via sequential full PUT (`buildTransactionUpdatePayload`)
- `frontend/src/utils/transactionPayload.js` — shared PUT payload builders for stock, MF, and STOCK_SPLIT reassignment
- Frontend tests: Settings portfolio CRUD, Layout selector refresh, Transactions bulk assign (including partial failure and split fields)

### Changed
- `Transactions.jsx` — selection state, bulk toolbar, assign flow
- `Settings.jsx` — Portfolios section with `PortfolioManagement` component
- Docs: `current-state.md`, `frontend-design.md`, `page-layouts.md`

### Notes
- **All Portfolios** remains virtual; cannot receive transactions directly
- Default Portfolio cannot be deactivated from UI
- No backend changes; no new bulk API endpoint

## 2026-05-27 — FX sync backfill for coverage gaps

### Fixed
- `sync_fx_rates` / `sync_fx_pair` backfill from earliest required valuation date when cached `FXRate` rows start later (GOOG USD prices from 2022-05-02 with USD→EUR FX from 2022-12-20 only → summary `portfolio_value: null`, `fx_status: fx_unavailable`)
- `earliest_required_fx_date` derives required start from transaction dates, cached stock price dates, and implied currency pairs (price→holding, price→display, holding→display)
- Incremental FX sync (latest cached date + 1) preserved when cache already covers from required inception

### Added
- `resolve_fx_sync_start_date`, `_earliest_fx_date`, `earliest_required_fx_date` in `fx/services.py`
- Backfill and summary integration tests in `test_fx_sync.py`

### Notes
- Read APIs unchanged (DB-only); 7-day FX fill on reads preserved; no live transaction data modified
- Backend: 393 pytest tests pass

## 2026-05-27 — Stock price sync backfill for coverage gaps

### Fixed
- `sync_prices` / `sync_one_stock_symbol` backfills from earliest transaction date when cached `HistoricalPrice` starts after first transaction (GOOG BUY 2022-05-02 with prices from 2022-12-23 only → summary `portfolio_value: 0` while `invested_amount > 0`)
- Incremental sync (latest cached date + 1) preserved when cache already covers from transaction inception

### Added
- `resolve_stock_sync_start_date` in `market_data/services/price_sync.py`
- Backfill regression tests in `test_market_data_sync.py`

### Notes
- Read APIs unchanged (DB-only); no live transaction data modified
- Backend: 385 pytest tests pass

## 2026-05-27 — Fix split-adjusted value history valuation

### Fixed
- Summary and performance value timeseries now consistently pair cached split-adjusted historical prices with split-adjusted transaction quantities (`build_split_adjusted_lot_snapshots` in `finance/fifo.py`)
- Prevents GOOG-style dashboards showing ~95% artificial loss on split dates when yfinance-adjusted prices were multiplied by unadjusted share counts
- Performance `value`, `cumulative_return`, and `twror` inherit the corrected value series; `STOCK_SPLIT` rows remain excluded from external cash-flow calculations

### Added
- `backend/tests/test_stock_split_valuation_api.py` — GOOG-like regression tests (summary, performance metrics, symbol/date isolation, missing price/FX, no yfinance on reads)
- Domain test for `build_split_adjusted_lot_snapshots` in `test_finance_domain.py`

### Changed
- `portfolios/summary_service.py` — uses shared finance timeline builder; holdings path relies on FIFO internal split adjustment (no double-apply)

### Notes
- No live transaction data modified; adjustment is in-memory at read time only
- No schema migrations; response shapes unchanged

## 2026-05-27 — Data safety guardrails

### Added
- `docs/data-safety.md` — incident summary, safe debugging, backup/restore, forbidden commands
- `make backup-db` — timestamped `pg_dump` to `backups/` via `kpulla6_postgres`
- `make db-safety-check` — DB name, transaction/portfolio/historical_price counts, last 5 transactions

### Changed
- `AGENTS.md` — mandatory data-safety rules for agents (no live DB deletes, backup before destructive ops, SQLite for ad-hoc work)
- `docs/workflows.md` — backup/safety-check bookends for data-sensitive phases; links to data-safety doc
- `.gitignore` — ignore `backups/` (local SQL dumps)

### Notes
- No application code, models, migrations, or API behavior changed
- Root cause of May 2026 transaction loss: ad-hoc script `Transaction.objects.filter(portfolio=…).delete()` on dev Postgres during split debugging

## 2026-05-26 — Phase MF-10: Live mutual fund NAV provider

### Added
- `market_data/providers/amfi_nav_parser.py` — MFAPI JSON/date/NAV parsing (Decimal, INR)
- Live `AmfiNavProvider` via MFAPI (`https://api.mfapi.in`) with injectable `http_get`
- `backend/tests/test_amfi_nav_provider.py` — 20 tests (parser, provider, sync, API; mocked HTTP)

### Changed
- `market_data/providers/mutual_fund_nav_provider.py` — live fetch for latest NAV and date-range history
- Docs: `api-design.md`, `database.md`, `current-state.md`, `decisions.md`, `mutual-funds.md`

### Notes
- External NAV calls only in sync paths; read APIs unchanged (DB-only)
- No new Python dependencies (stdlib `urllib`)
- All tests mock HTTP — no real network in CI
- Backend: 371 pytest tests pass

## 2026-05-26 — Phase MF-9: Mutual fund NAV refresh API and combined sync

### Added
- `POST /api/v1/nav/refresh` — manual MF NAV sync; optional `scheme_codes`; synced/skipped/failed response
- `market_data/nav_refresh.py` — refresh payload helpers
- `backend/tests/test_mutual_fund_nav_refresh_api.py` — 11 tests

### Changed
- `market_data/services/market_data_sync.py` — includes `sync_mutual_fund_navs` by default
- `POST /api/v1/portfolio/force-sync` — extended response with MF counts and warnings
- `sync_market_data` command — `--skip-mutual-funds`; output includes MF stats
- `Makefile` `refresh` / `sync-market-data` — uses combined `sync_market_data` command
- Settings page — Data & sync explainer (no new external calls from frontend)
- Docs: `api-design.md`, `database.md`, `current-state.md`, `decisions.md`, `mutual-funds.md`

### Notes
- Stock `POST /api/v1/prices/refresh` unchanged
- Read APIs still DB-only for NAV
- `AmfiNavProvider` placeholder unchanged
- Backend: 351 pytest tests pass

## 2026-05-26 — Phase MF-8: Frontend mutual fund transactions

### Added
- `TransactionModal` asset type selector — Stock (default) and Mutual fund modes
- MF form fields mapped to backend API (`scheme_code`, `folio_number`, `nav_date`, etc.)
- Transactions table: scheme/folio display, units/NAV columns, calm NAV verification badge
- `frontend/src/utils/transactionDisplay.js` — display helpers (no finance math)
- Frontend tests: MF create/edit/display in `TransactionModal.test.jsx`, `Transactions.test.jsx`, `transactionDisplay.test.js`

### Changed
- `frontend/src/pages/Assets.jsx` — safe MF holding labels (scheme name, folio, `holding_key`)
- `frontend/src/api.js` — field-level validation error messages from backend
- `StatusBadge` — `verified` / `nav_warning` variants for NAV status
- Docs: `frontend-design.md`, `current-state.md`, `mutual-funds.md`

### Notes
- Stock transaction form and CSV import unchanged
- No frontend external NAV/AMFI calls
- Backend contracts unchanged

## 2026-05-26 — Phase MF-7: Mutual fund classification

### Added
- `finance/mutual_fund_classification.py` — conservative metadata inference
- `market_data/mutual_fund_classification_bridge.py` — Asset/profile bridge + upsert helper
- MF holdings/asset detail fields: `primary_asset_class`, `classification_source`, `classification_notes`
- `PrimaryAssetClass.UNKNOWN` choice on `Asset`
- `backend/tests/test_mutual_fund_classification.py` — 16 tests

### Changed
- `portfolios/holdings_service.py`, `holdings_views.py` — MF classification on read
- `transactions/mutual_fund_services.py` — infer class on create/update when not explicit
- Docs: `api-design.md`, `database.md`, `current-state.md`, `decisions.md`

### Notes
- Hybrid → HYBRID, not EQUITY; stock rows unchanged
- No external API in classification
- Backend: 340 pytest tests pass

## 2026-05-26 — Phase MF-6: Mutual fund NAV validation

### Added
- `transactions/mf_nav_validation.py` — `verify_mutual_fund_nav_inputs` (cached NAV + market value tolerances)
- `NavVerificationStatus`: `VERIFIED`, `NAV_MISSING`, `NAV_MISMATCH`, `VALUE_MISMATCH`, `WARNING_ACCEPTED`
- `backend/tests/test_mutual_fund_nav_validation.py` — 11 tests

### Changed
- `transactions/mutual_fund_services.py` — MF-6 validation on create/update (replaces ratio-based MF-3 check)
- `backend/tests/test_mutual_fund_transactions_api.py` — `VERIFIED` expectation
- Docs: `api-design.md`, `database.md`, `current-state.md`, `decisions.md`

### Notes
- Mismatch saves with status/message; structural errors still 400
- No external NAV provider on transaction write/read
- Backend: 324 pytest tests pass

## 2026-05-26 — Phase MF-5: Mutual fund summary and performance

### Added
- Summary and performance include MF positions (cached NAV, forward-fill, INR FX conversion)
- `finance/mutual_fund_cashflows.py` — `merge_portfolio_xirr` with MF `investment_date` / `paid_value`
- `market_data/nav_repository.py` — `list_mutual_fund_navs_for_schemes`, `latest_mutual_fund_navs_by_scheme`
- `backend/tests/test_mutual_fund_summary_performance_api.py` — 14 tests

### Changed
- `portfolios/summary_service.py` — MF holdings, timeseries merge, combined XIRR
- `portfolios/performance_service.py` — MF external flows and timeseries via `transactions_by_mf_holding`
- Docs: `api-design.md`, `database.md`, `current-state.md`, `decisions.md`

### Notes
- Stock summary/performance unchanged when no MF transactions
- No external NAV provider on summary/performance reads
- Backend: 313 pytest tests pass; frontend: 79 vitest tests pass

## 2026-05-26 — Phase MF-4: Mutual fund holdings and asset detail

### Added
- `GET /api/v1/portfolio/holdings` — MF rows grouped by `scheme_code` + `folio_number`; `holding_key`, `latest_nav`, `nav_status`, `units`
- `GET /api/v1/portfolio/assets/{scheme_code}?folio_number=...` — folio-scoped MF asset detail with MF transaction fields
- `backend/tests/test_mutual_fund_holdings_api.py` — 14 tests

### Changed
- `portfolios/holdings_service.py` — separate stock vs MF paths; DB-only NAV via `latest_nav_for_asset`
- `portfolios/holdings_views.py` — `folio_number` query param; MF response fields on asset detail
- Docs: `api-design.md`, `database.md`, `current-state.md`, `decisions.md`

### Notes
- Stock holdings and asset detail behavior unchanged; existing holdings/summary/performance tests pass
- No external NAV provider on holdings/asset detail reads
- Summary/performance MF integration deferred to MF-5
- Backend: 299 pytest tests pass

## 2026-05-26 — Phase MF-3: Mutual fund transaction API

### Added
- `POST/PUT /api/v1/transactions` with `asset_type=MUTUAL_FUND` — BUY/SELL, scheme/folio/dual dates/NAV/units/values
- `transactions/mutual_fund_services.py` — validation, Asset/Profile/Folio upsert, atomic create/update
- `MutualFundTransactionWriteSerializer`; MF fields on `TransactionSerializer` read output
- `backend/tests/test_mutual_fund_transactions_api.py` — 16 tests

### Changed
- `transactions/views.py` — route MF vs stock create/update
- `transactions/services.py` — prefetch MF detail on list/get
- Docs: `api-design.md`, `database.md`, `current-state.md`, `decisions.md`

### Notes
- Stock transaction API unchanged for non-MF requests
- No external NAV provider on transaction read/write; optional cached NAV status only
- Holdings/summary/performance/frontend not wired
- Backend: 285 pytest tests pass; frontend: 79 vitest tests pass

## 2026-05-26 — Phase MF-2: Mutual fund NAV cache and sync foundation

### Added
- `market_data/providers/mutual_fund_nav_provider.py` — `NavPoint`, `MutualFundNavProvider`, `AmfiNavProvider` (placeholder)
- `market_data/services/mutual_fund_nav_sync.py` — incremental idempotent NAV upsert to `HistoricalPrice`
- `market_data/nav_lookup.py` — `latest_nav_for_asset`, `NavLookupResult` (DB only)
- `market_data/nav_repository.py` — `list_mutual_fund_navs_in_range` (DB only)
- Management command: `sync_mutual_fund_navs` with optional `--scheme-code`
- `backend/tests/test_mutual_fund_nav_sync.py` — 12 tests

### Notes
- No read API or holdings/summary/performance integration; no frontend changes
- `AmfiNavProvider` does not call live AMFI in MF-2; inject mock/real provider at sync time
- `POST /api/v1/nav/refresh` and `sync_market_data` MF wiring deferred
- Backend: 269 pytest tests pass; frontend: 79 vitest tests pass

## 2026-05-26 — Phase MF-1: Mutual fund schema foundation

### Added
- `market_data.models.Asset`, `MutualFundProfile`, `PrimaryAssetClass`; `AssetType.MUTUAL_FUND`
- `transactions.models.Folio`, `MutualFundTransactionDetail`, `NavVerificationStatus`
- Nullable `HistoricalPrice.asset` FK (non-breaking)
- Migrations: `market_data/0002_mutual_fund_schema`, `transactions/0002_mutual_fund_schema`
- `backend/tests/test_models_mutual_funds.py` — 12 model tests

### Changed
- `HistoricalPrice.asset_type` max_length 8 → 16 (supports `MUTUAL_FUND`)
- `docs/database.md`, `docs/current-state.md`, `docs/decisions.md`

### Notes
- Stock, FX, benchmark, holdings, summary, performance, and transaction APIs unchanged
- MF transaction detail not wired to CRUD APIs yet (MF-3)
- Backend: 257 pytest tests pass; frontend: 79 vitest tests pass

## 2026-05-26 — Phase MF-0: Indian Mutual Funds design documentation

### Added
- `docs/mutual-funds.md` — purpose, MVP scope, target data model (`Asset`, `MutualFundProfile`, folio strategy, transaction details), NAV cache/validation/sync, holdings grouping, summary/performance impact, classification, frontend impact, phased plan MF-1–MF-9, risks, open questions

### Changed
- `docs/database.md` — planned MF tables and `HistoricalPrice`/`AssetType` extensions (marked not implemented)
- `docs/api-design.md` — planned MF transaction, holdings, sync, and read-path contracts (marked not implemented)
- `docs/current-state.md` — Planned / MF-0 section

### Notes
- Documentation only; no backend runtime code, migrations, frontend, or test changes
- Preserves existing stock, FX, benchmark, holdings, summary, performance, and transaction behavior
- Read APIs must use cached DB NAV/prices only — no external AMFI calls on dashboard/holdings reads

## 2026-05-25 — Page layout governance documentation

### Added
- `docs/page-layouts.md` — source of truth for per-page layout; change process and ownership table
- Cross-reference from `docs/frontend-design.md`

### Notes
- Documentation only; no app code changes

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

## 2026-05-25 — Phase 4: Asset Detail Metric Sheet migration

### Changed
- **Asset Detail:** Metric Sheet layout with `PageHeader` (symbol title, Assets breadcrumb, portfolio/currency subtitle), hero KPI row (`MetricCard` + `CurrencyValue` / `PercentValue`), grouped `SectionCard` sections (position, market, data quality, transactions), `StatusBadge` for holding/price/FX status, `WarningBanner` for API warnings, `LoadingState` / `ErrorState` / `EmptyState`
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
