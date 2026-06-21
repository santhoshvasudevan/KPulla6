# KPulla6 Frontend Redesign PRD — Executive Portfolio OS

## 1. Purpose

This document is the product and design requirement document for a future KPulla6 frontend redesign named **KPulla6 Executive Portfolio OS**.

The redesign exists to turn the current MVP frontend into a calmer, more executive, chart-first portfolio analytics experience while preserving KPulla6's existing product strengths: cash ledger, fixed deposits, mutual funds, Metric Sheet analytics, Compare, portfolio scope, display currency, cached data status, and backend-owned calculations.

This document is **documentation only**. It does not authorize implementation by itself. Any frontend code changes require explicit approval after this PRD is reviewed.

## 2. Product Vision

KPulla6 should feel like a private portfolio analytics and wealth operating system: modern, calm, executive, data-rich, trustworthy, and serious.

The target experience should:

- Help the user understand total wealth, portfolio performance, data health, allocation, activity, cash, and fixed deposit status quickly.
- Make deeper analytics available without crowding the top fold.
- Feel premium and analytical, not decorative.
- Stay light-first with dark mode compatibility.

The redesigned UI should **not** feel like:

- A crypto app.
- A broker trading terminal.
- A generic admin panel.
- A neon dashboard.
- A casual budgeting app.

## 3. Current Baseline

The existing frontend remains the production baseline until the redesign is implemented and validated phase by phase.

Rules:

- Do not delete or replace the current frontend in one large step.
- Do not create a separate `frontend-v2` app unless explicitly approved later.
- Do not remove current routes, auth flows, API wrappers, contexts, or tests during design work.
- Redesign should be implemented incrementally inside the existing React app.
- Every phase must leave the production app usable.

## 4. Recommended Implementation Architecture

Recommended approach:

- Keep the current `frontend/` folder.
- Preserve existing `api.js`, contexts, routes, protected-route behavior, and app bootstrap.
- Add or refactor shared design primitives gradually.
- Build shared card, table, badge, navigation, filter, and chart components before migrating pages.
- Migrate page by page, starting with shell foundations and chart primitives, then Dashboard.
- Keep the redesign API-driven and compatible with existing backend contracts.

Tradeoff:

- A parallel `frontend-v2` app is possible but higher risk because auth, routing, contexts, API wrappers, tests, CSS tokens, protected routes, and app shell behavior can drift.
- Incremental replacement is safer for KPulla6 because the app already has meaningful route behavior, session auth, portfolio context, display currency state, and test coverage.

## 5. Non-Negotiable Constraints

- React remains API-driven.
- No finance, FX, FIFO, valuation, XIRR, TWROR, benchmark, Sharpe, Sortino, drawdown, or performance calculations in React.
- Preserve `frontend/src/api.js` contracts unless separately approved.
- Preserve session auth, CSRF handling, protected routes, public auth routes, redirects, logout, and 401 behavior.
- Preserve `portfolio_scope` and `display_currency` propagation.
- Preserve current `PortfolioProvider` settings gate behavior where pages wait for `settingsLoaded && apiQuery`.
- Preserve cached price, NAV, benchmark, and FX status visibility.
- Preserve the no-live-provider-call-on-read rule.
- Preserve KPulla5 untouched.
- Preserve backend-owned analytics and warnings.
- Do not redesign backend APIs, formulas, database schema, or migrations as part of this frontend redesign.

## 6. Benchmark Synthesis

The Ghostfolio benchmark produced these useful patterns for KPulla6:

- **Two-level navigation:** a calm top-level navigation plus contextual local navigation reduces page clutter.
- **Large hero charts:** the chart becomes the visual center of the experience instead of one card among many.
- **Spacious top fold:** fewer competing widgets above the fold makes the dashboard feel more premium.
- **Allocation composition pages:** dashboard allocation can be a preview; deeper allocation belongs lower in the scroll or on Assets.
- **Mature holdings/activity tables:** scan-friendly table columns are more useful than decorative widgets.
- **X-ray health checks:** grouped portfolio review rules are a strong model for KPulla6 data quality and portfolio health.
- **Calm empty states:** optional features and missing data should be explained quietly.
- **Clutter control:** separate overview, holdings, activities, allocation, and review concepts instead of forcing all content into one viewport.
- **Filter/settings menu:** complex filters can live in a compact panel rather than always occupying page space.

Ghostfolio is a reference pattern only. KPulla6 must not copy Ghostfolio branding, logos, source code, exact layouts, or product identity.

## 7. Chart Benchmark Synthesis

The chart benchmark produced these requirements:

- Dashboard chart should be large, sparse, and calm.
- Dashboard chart should be less technical than Metric Sheet charts.
- Hover crosshair is required for time-series charts.
- Active point marker is required when hovering.
- Tooltip should be compact and focused.
- Benchmark overlay should be available on return-oriented charts.
- Dashboard metric controls should include `Value`, `Cumulative Return`, and `TWROR`.
- Axis/grid density should depend on context: sparse on Dashboard, richer in analytics pages.
- Loading, empty, error, stale, and partial-data states must be designed.
- Recharts improvement is recommended first.
- Apache ECharts should be considered later only if Recharts becomes limiting for dense Compare or Metric Sheet interactions.

Recommended chart approach:

- Keep Recharts in the near term.
- Build a shared chart system around existing backend data contracts.
- Add consistent chart cards, tooltips, crosshair styling, legends, benchmark overlays, responsive heights, and state handling.

## 8. Target Experience

**KPulla6 Executive Portfolio OS** is the target experience:

- Light-first.
- Premium but not flashy.
- Spacious and chart-first.
- Top-level navigation plus contextual page navigation.
- Dashboard as a calm whole-wealth overview.
- Analytics pages as deeper quantitative surfaces.
- Scroll is allowed and preferred over crowding.
- Tables are serious, slightly colorful, and restrained.
- Health/status review is visible but not alarmist.

Direction 5 is the preferred visual reference direction. It blends Ghostfolio-inspired navigation and chart hierarchy with KPulla6-specific assets, cash, fixed deposits, Metric Sheet, Compare, portfolio scope, and cached-data status.

## 9. App Shell Requirements

The redesigned shell must include:

- Global top navigation for primary product areas.
- Contextual side navigation or page-local navigation for dense sections.
- Portfolio selector.
- Display currency selector.
- Theme selector: System / Light / Dark.
- Signed-in user identity.
- Logout.
- Cached data status or concise data freshness note.
- Protected route behavior identical to the current app.
- Public-only behavior for Login, Register, and Forgot Password.
- Responsive/mobile behavior with no inaccessible controls.

Recommended top-level navigation:

- Dashboard
- Transactions
- Cash
- Assets
- Fixed Deposits
- Compare
- Settings

Possible contextual navigation examples:

- Dashboard: Overview, Holdings, Allocation, Metric Sheet, Review Queue.
- Assets: Holdings, Allocation, Asset Detail context.
- Settings: Display, Portfolios, Bank Accounts, Cash Movements.

## 10. Dashboard Requirements

The Dashboard should be a calm whole-wealth overview.

Above the fold:

- Hero area with page title and current value.
- Compact KPI strip.
- Large Performance Center chart.
- Minimal chart controls.
- Allocation preview.
- Portfolio Health / Review Queue preview.
- Concise cached data / NAV / FX status.

Below the fold:

- Top Holdings.
- Recent Transactions.
- Allocation deep dive.
- Metric Sheet summary.
- Benchmark snapshot.
- Monthly returns heatmap.
- Fixed deposit maturity insight.
- Recent alerts or warnings.

Dashboard layout requirements:

- Current Value remains the hero metric.
- KPI strip should be compact, not a field of equal-weight cards.
- Performance chart is the primary visual anchor.
- Allocation is visible but not dominant.
- Health/status widgets support the chart; they do not compete with it.
- Detailed tables and secondary analytics should move lower in the scroll.
- The existing Invested vs Current behavior remains preserved unless separately approved for movement or removal in `docs/page-layouts.md`.

## 11. Chart Requirements

Shared chart system requirements:

- Shared chart card shell with title, subtitle, controls, legend, status, and footer.
- Responsive chart height rules by page type.
- Sparse Dashboard chart.
- Richer analysis charts for Metric Sheet, Compare, and Asset Detail.
- Crosshair on hover.
- Active point marker.
- Compact tooltip.
- Benchmark overlay.
- Legend chips for portfolio, benchmark, drawdown, and compared assets.
- Loading skeleton with reserved height.
- Empty state with clear reason and next action.
- Error state with retry where appropriate.
- Partial-data state for missing price/NAV/FX/benchmark data.
- Display currency formatting from API context.
- No frontend calculations beyond formatting and display-only percentages explicitly allowed by existing docs.

Recommended chart defaults:

- Dashboard default: `Value`, unless user review later prefers `TWROR`.
- Return metrics: enable benchmark overlay.
- Metric Sheet: yearly returns bar chart, drawdown area chart, monthly returns heatmap.
- Compare: normalized multi-series chart with shared hover date.
- Asset Detail: focused performance/price chart with optional transaction markers later.

## 12. Page-By-Page Requirements

| Page | Redesign Intent | Must Preserve | Ghostfolio-Inspired Idea | Risk | Phase |
| --- | --- | --- | --- | --- | --- |
| Login | Premium, simple auth entry. | Session login, CSRF, error handling, Google auth link if present. | Calm minimal card, clear trust tone. | Breaking auth flow. | P9 |
| Register | Same auth family as Login. | User creation, default portfolio/settings behavior. | Calm onboarding copy. | Accidentally changing backend expectations. | P9 |
| Forgot Password | Low-friction recovery. | Password reset API behavior and fallback copy. | Understated empty/success states. | Overpromising email behavior. | P9 |
| Dashboard | Whole-wealth command center. | Summary, performance, benchmark, Metric Sheet, warnings, Invested vs Current unless approved otherwise. | Large sparse hero chart, KPI strip, health preview. | Crowding the top fold again. | P4 |
| Transactions | Mature activity workflow. | Filters, pagination, CSV import, MF fields, cash preview, CRUD, bulk assign, future-impact errors. | Activity table density and compact import/actions. | Losing filter/API parameter semantics. | P5 |
| Cash | Serious cash ledger surface. | Native balances, ledger, deposits/withdrawals, transfers, bulk entries, future-impact errors. | Clean account/ledger split with practical filters. | Creating client-side running balances. | P5 |
| Assets | Holdings and allocation hub. | Holdings, allocation, cash/FD rows from API, closed holdings, warnings. | Holdings table + deeper composition modules. | Making cash rows clickable as investment rows. | P6 |
| Asset Detail | Focused asset analytics. | FIFO/API metrics, warnings, MF folio behavior, transaction history, Metric Sheet. | One focused chart plus supporting detail. | Frontend FIFO/performance drift. | P6 |
| Fixed Deposits | Lifecycle operations with cash impact clarity. | Bank account dependency, ledger balance, lifecycle actions, warnings, renewal/settlement rules. | Planning-style status cards, maturity review. | Accrued interest or FD math in React. | P7 |
| Compare | Quantitative comparison surface. | Two subjects, no cash subjects, backend common window, benchmark, warnings. | Analysis-page chart hierarchy and shared hover. | Client-side ranking/calculation creep. | P8 |
| Settings | Administrative but calm. | Display currency sync, portfolios, bank accounts, cash movements, theme/auth controls. | Contextual settings sections. | Breaking context synchronization. | P9 |

## 13. Data Table Requirements

Tables should be slightly colorful but restrained:

- Soft tinted headers.
- Asset-class pills: Stock, Mutual Fund, Fixed Deposit, Cash.
- Status badges for stale NAV, missing price, FX unavailable, oversold, closed, cash-aware, included cash, maturity state.
- Right-aligned numeric columns.
- Tabular numerals.
- Practical scan-friendly columns.
- Hover states.
- Clear empty states.
- No rainbow rows.
- Do not color entire rows except for subtle hover or selected states.
- Do not rely on color alone; status text must be present.

Priority tables:

- Holdings.
- Recent Transactions.
- Transactions full table.
- Cash ledger.
- Fixed Deposits.
- Metric Sheet tables.
- Compare metrics.

## 14. Portfolio Health / X-Ray Requirements

KPulla6 should include a grouped Portfolio Health or Review Queue concept inspired by Ghostfolio's X-ray pattern.

Review checks may include:

- Price cache current/stale/missing.
- NAV freshness.
- FX availability.
- Benchmark overlap.
- Cash-aware mode.
- Fixed deposit maturity.
- Concentration/allocation review.
- Metric Sheet warnings.
- Oversold/closed/price-missing holdings.
- Cash ledger future-impact warnings when returned by APIs.

Rules:

- Use backend-provided data, existing warnings, or existing API status fields only.
- Do not create new frontend finance logic.
- Keep copy concise and calm.
- Group checks by topic.
- Use statuses such as Good, Review, Current, Stale, Missing, Blocked, or Action Needed.

## 15. Implementation Phases

Recommended phases:

- **P0: Protective tests** — add/update route, auth, shell, selector, API parameter, chart contract, and state tests before visual migration.
- **P1: Design tokens and shell foundation** — evolve tokens, top nav, contextual nav strategy, layout constraints.
- **P2: Shared cards/tables/badges** — mature reusable surfaces before page migration.
- **P3: Shared chart system** — tooltip, crosshair, benchmark overlay, responsive heights, chart states.
- **P4: Dashboard redesign** — implement Executive Portfolio OS dashboard structure.
- **P5: Transactions and Cash** — migrate dense operational tables and filters.
- **P6: Assets and Asset Detail** — holdings, allocation, asset analytics.
- **P7: Fixed Deposits** — FD lifecycle and maturity review polish.
- **P8: Compare and Metric Sheet charts** — deeper analytics chart refinement.
- **P9: Auth and Settings polish** — auth screens, settings sections, theme/user controls.
- **P10: Cleanup and audit** — remove dead CSS only after parity is proven; run full test/audit pass.

## 16. Protective Tests Before Implementation

Before implementation starts, add or confirm protective coverage for:

- Route inventory test.
- Login direct test.
- Forgot Password direct test.
- Register direct test.
- Shell navigation tests.
- Protected route redirect tests.
- Portfolio selector tests.
- Display currency selector tests.
- Theme selector tests.
- Transaction filter/API parameter tests.
- Cash page ledger/balance state tests.
- Chart data contract tests for Dashboard, Compare, Asset Detail, and Metric Sheet.
- Dashboard loading/empty/error/warning states.
- Benchmark selector behavior.
- `portfolio_scope=all` vs `portfolio_id` propagation.
- `display_currency` propagation.
- No frontend finance calculation guard if feasible through lint/static tests or focused unit tests.

## 17. Acceptance Criteria

The redesign is acceptable only when:

- Visual direction matches KPulla6 Executive Portfolio OS.
- Existing frontend remains usable after every phase.
- All current routes are preserved.
- All current API behavior is preserved.
- All protected route/auth behavior is preserved.
- Session auth and CSRF behavior are preserved.
- Portfolio scope and display currency behavior are preserved.
- Dashboard sections are preserved or explicitly approved for movement/removal.
- Cash ledger, fixed deposits, mutual funds, Metric Sheet, Compare, cached data status, and warnings remain first-class.
- No frontend finance calculations are introduced.
- Tests pass for each implementation phase.
- Dark mode remains readable even though the design is light-first.

## 18. Out Of Scope

- Backend redesign.
- API redesign.
- Formula changes.
- Database changes.
- Migrations.
- Ghostfolio copying.
- Ghostfolio source inspection for implementation.
- New product features unless separately approved.
- `frontend-v2` app unless separately approved.
- Removing current frontend.
- Replacing `api.js` unless separately approved.
- Live market/NAV/FX provider calls during frontend reads.

## 19. Decision Log / Open Questions

Open questions:

- What is the final top navigation structure?
- Is contextual side navigation global, or only inside Dashboard/Portfolio-style pages?
- Does the dashboard chart default to `Value` or `TWROR`?
- Is Apache ECharts needed later, or can Recharts handle the full roadmap?
- Does Allocation Deep Dive live on Dashboard, Assets, or both?
- Should Direction 5's top navigation fully replace the current sidebar, or should the first implementation keep the current sidebar and evolve it?
- Which Portfolio Health checks require new backend support versus reuse of existing warnings?

Current decision log:

- Direction 5 is the preferred reference direction.
- Incremental migration inside the existing React app is preferred over a separate frontend-v2.
- Recharts improvement is preferred before considering ECharts.
- Dashboard should be scrollable rather than compressed into one viewport.
- Existing frontend remains the production baseline until phased implementation is approved and validated.

## 20. Relationship To Design Explorations

These files are exploratory artifacts, not production code:

- `design-explorations/dashboard-direction-5.html`
- `design-explorations/dashboard-direction-5.css`
- `design-explorations/ghostfolio-benchmark/ghostfolio-benchmark.md`
- `design-explorations/ghostfolio-benchmark/chart-benchmark.md`

Direction 5 should guide future implementation discussions, but production implementation must still happen through approved, incremental changes in the real React app.
