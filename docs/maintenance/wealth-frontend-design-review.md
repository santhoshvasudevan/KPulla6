# Wealth tracking frontend review

Reviewed on 27 November 2026 for the KPulla6 frontend prototype.

## Recommendation

Start the Dashboard with current portfolio value, its invested basis, and one full-width history chart. Someone opening the app can see their wealth and how it changed before choosing a question to investigate. On Assets, give the allocation chart and its holdings drill-down the full width. Give data-quality checks and reconciliation their own table-oriented view. These three tasks benefit from different layouts.

## Ghostfolio walkthrough

The local reference was reviewed at desktop size and the holdings layout at a 390-pixel phone width. The signed-in overview displayed onboarding for an empty account. The populated overview crosshair, fill, and mobile history chart are illustrated in the earlier local chart study in `design-explorations/ghostfolio-benchmark/chart-benchmark.md`. Administrative screens are covered by the earlier local inventory in the same folder. Writes, imports, admin operations and paid features were outside the walkthrough.

| Area | Interaction or layout observed | Implication for KPulla6 |
| --- | --- | --- |
| Public home, features, about and resources | The landing page repeats the getting-started action across a long page. Documentation and product discovery have their own destinations. | Use onboarding space for a first step when the scope is empty. A returning holder should immediately see their selected portfolio and value. |
| Signed-in navigation | Home groups Overview, Holdings, Summary, Watchlist and Markets. Portfolio groups Analysis, Activities, Allocations, FIRE and X-ray. | Keep KPulla6’s portfolio and currency controls visible across pages. Use local tabs for questions about the same data. |
| Overview and Summary | The empty overview walks the user through accounts, recording activities and analysis. Summary has a separate reading view. The earlier populated example gives one history series most of the visual space. | Start with a clear scope, value and dated history. Preserve the selected range, currency and metric when switching views. |
| Holdings | Desktop has seven columns including first activity, quantity, allocation and change. Phone prioritizes name, share and change. | Give the name room to wrap. Put codes and secondary identifiers in a second line or detail row. Keep exact values and folio numbers accessible on touch. |
| Watchlist and Markets | Both reuse last all-time high and change-from-high columns. | Reuse consistent headers and formatting across comparisons. Any comparison needs a clearly identified period and measure. |
| Analysis | Four chart canvases share the analysis view with top and bottom rankings. Earlier captures show a comparison selector and date-specific readout. | Keep benchmark context beside the return chart. Use separate views for currency value and percentage return, preserving the backend’s definitions. |
| Allocations | Ten canvases, including small rings and a larger chart. Platform, asset class, holding, sector, geography and account provide different cuts. Secondary views include a map and a name/value/share table. | Show one large allocation chart at a time. Pair it with exact values, a selectable text equivalent and a clear denominator. KPulla6’s meaningful drill-down is often AMC → scheme → folio. |
| Activities and import | Paginated table with type, date, quantity, price, fee, value, currency and account. Add and import are separate actions. | Keep transaction entry separate from exploration. Preserve the investment date, NAV date and settlement details when opening a row. |
| Accounts | Platform, activity count, balance and currency are visible together. | Give bank cash, broker cash and linked FDs explicitly named rows. A combined total alone is difficult to reconcile. |
| FIRE | A planning input is adjacent to the projected-income chart. | Use the same pairing on existing FD maturity estimates, with actual and estimated values visibly distinguished. |
| X-ray | Diagnostics are grouped into recognizable questions such as liquidity, emergency fund and fees. | Group NAV, FX and benchmark warnings by what the user can investigate. Keep valuation-affecting warnings near the value they qualify. |
| Settings and access | Locale, language, currency and theme sit with account preferences. Export and access management have dedicated areas. | Keep display settings persistent across routes and separate from per-chart controls. |
| Administration | The earlier project inventory documents jobs, users and market-data settings. | Operational controls belong away from account views. Show the investor the freshness or coverage that affects their numbers. |

## Other portfolio products

| Reference | Design choice | Application |
| --- | --- | --- |
| Sharesight | The Investments page can change chart type, time period and grouping or collapse the chart to focus on holdings. Its contribution report uses bars to compare positive and negative contributors. | Use a line for history, a composition chart for current weights and signed bars only when contribution data exists. The page should always name the question and units. [Investments page](https://help.sharesight.com/ca/show_portfolio/) · [Contribution analysis](https://help.sharesight.com/uk/contribution-analysis-report/) |
| Portfolio Performance | Taxonomies support nested allocation views and navigation through levels. Its performance dashboard allows separate widgets and reporting periods. | Preserve classification, category and scheme as distinct levels. Put portfolio metrics together only when their scope and time basis can be read independently. [Taxonomy views](https://help.portfolio-performance.info/en/reference/view/taxonomies/using-taxonomies/) · [Performance dashboard](https://help.portfolio-performance.info/en/reference/view/reports/performance/dashboard/) |

## Interactive review

Open the following links in a signed-in KPulla6 development session. If the backend is running and the frontend is stopped, use `npm --prefix frontend run dev -- --open '/dashboard?variant=A'` from the project root.

| Direction | Try this | Trade-off |
| --- | --- | --- |
| [A · Value history](http://localhost:5173/dashboard?variant=A) | Read current value and basis, then switch from Value to TWROR and change the period. Hover the chart for the dated reading. | Best for a quick daily check. Allocation and portfolio warnings appear farther down. |
| [B · Allocation explorer](http://localhost:5173/dashboard?variant=B) | Hover or tap a slice, then select another bucket from the adjacent list. Open Assets for named holdings and folios. | Best for concentration questions. History takes an extra click. The ring uses the Dashboard API’s allocation buckets and its percentage is of the displayed bucket total. The Assets link opens the existing Assets page. |
| [C · Portfolio review](http://localhost:5173/dashboard?variant=C) | Compare invested basis, realized and unrealized P/L, then read the adjacent portfolio checks. Use the links to inspect the ledger or holdings. | Best for investigation. More numbers compete for attention during a routine check. |

The bottom arrows and keyboard left/right arrows cycle the three layouts. The ordinary Dashboard URL retains the complete current Dashboard. The experiment uses existing summary, performance and status responses. It adds no endpoint, database write or valuation logic.

## Decision for implementation planning

The proposed combination is A for the Dashboard, B’s chart and selectable rows on Assets, and C’s review pattern for investigating warnings. Before writing tickets, review the same portfolio in all three and decide which question deserves the first screen. For the chosen layout, the implementation plan should define the mobile column priorities, scope-preserving drill-down, chart measure and denominator, and the treatment of missing or provisional data. Scheme and folio navigation should reuse the existing Assets breakdowns.
