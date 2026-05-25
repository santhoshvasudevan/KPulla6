# Graph Report - KPulla6  (2026-05-20)

## Corpus Check
- 150 files · ~36,700 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 994 nodes · 1879 edges · 86 communities (80 shown, 6 thin omitted)
- Extraction: 76% EXTRACTED · 24% INFERRED · 0% AMBIGUOUS · INFERRED: 445 edges (avg confidence: 0.69)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]
- [[_COMMUNITY_Community 45|Community 45]]
- [[_COMMUNITY_Community 46|Community 46]]
- [[_COMMUNITY_Community 47|Community 47]]
- [[_COMMUNITY_Community 48|Community 48]]
- [[_COMMUNITY_Community 49|Community 49]]
- [[_COMMUNITY_Community 51|Community 51]]
- [[_COMMUNITY_Community 52|Community 52]]
- [[_COMMUNITY_Community 54|Community 54]]

## God Nodes (most connected - your core abstractions)
1. `ensure_default_portfolio()` - 58 edges
2. `_price()` - 31 edges
3. `_buy()` - 30 edges
4. `_buy()` - 26 edges
5. `_import()` - 25 edges
6. `_payload()` - 25 edges
7. `Transaction` - 25 edges
8. `_buy()` - 23 edges
9. `_buy()` - 23 edges
10. `_price()` - 23 edges

## Surprising Connections (you probably didn't know these)
- `test_sync_fx_rates_command_calls_service()` --calls--> `type`  [INFERRED]
  backend/tests/test_fx_sync.py → frontend/package.json
- `sync_benchmark_prices()` --calls--> `earliest_transaction_date()`  [INFERRED]
  backend/market_data/services/benchmark_sync.py → backend/market_data/services/symbols.py
- `test_performance_scope_all_and_portfolio_id_422()` --calls--> `ensure_default_portfolio()`  [INFERRED]
  backend/tests/test_portfolio_performance_api.py → backend/portfolios/seed.py
- `test_summary_scope_all_and_portfolio_id_422()` --calls--> `ensure_default_portfolio()`  [INFERRED]
  backend/tests/test_portfolio_summary_api.py → backend/portfolios/seed.py
- `test_fx_upsert_idempotent()` --calls--> `upsert_fx_rate()`  [INFERRED]
  backend/tests/test_fx_sync.py → backend/fx/services.py

## Communities (86 total, 6 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.05
Nodes (60): Layout(), { container }, sel, TransactionModal(), AssetDetail(), Assets(), mockSummary, rows (+52 more)

### Community 1 - "Community 1"
Cohesion: 0.06
Nodes (45): Command, ensure_benchmark_indices(), assert_no_virtual_portfolio_rows(), ensure_default_portfolio(), ensure_app_settings(), seeded(), _buy(), _fx() (+37 more)

### Community 2 - "Community 2"
Cohesion: 0.10
Nodes (43): HealthView, GET /api/v1/health — service and database connectivity check., APIView, Exception, AssetNotFoundError, HoldingsValidationError, PortfolioAssetDetailView, PortfolioHoldingsView (+35 more)

### Community 3 - "Community 3"
Cohesion: 0.06
Nodes (42): Enum, align_single_benchmark_to_portfolio_calendar(), build_benchmark_comparison_data(), first_portfolio_metric_index(), merge_performance_and_benchmarks(), _normalize_series_index_to_naive_dates(), PerformancePoint, Benchmark index helpers for performance comparison (framework-independent).  Ben (+34 more)

### Community 4 - "Community 4"
Cohesion: 0.07
Nodes (38): convert_amount_on_date(), convert_amount_with_fill(), fx_lookup_from_maps(), get_fx_rate_on_date(), load_fx_rate_maps(), _norm_ccy(), Same-date FX only (no latest-rate fallback for historical dates).     Returns di, Convert using same-date FX only. Status is ok or fx_unavailable. (+30 more)

### Community 5 - "Community 5"
Cohesion: 0.11
Nodes (41): calculate_fifo_cost_basis_metrics(), FifoCostBasisMetrics, _Lot, FIFO cost basis metrics for a single asset.      Fees are intentionally ignored, _zero_metrics(), detect_oversell(), True when a SELL quantity exceeds available lots at that point in time     (afte, apply_stock_split_adjustments() (+33 more)

### Community 6 - "Community 6"
Cohesion: 0.12
Nodes (35): _buy(), _index_price(), _price(), _sell(), test_benchmark_cumulative_return_comparison(), test_benchmark_missing_prices_warning(), test_benchmark_no_yfinance(), test_benchmark_twror_comparison() (+27 more)

### Community 7 - "Community 7"
Cohesion: 0.09
Nodes (38): _count_txns(), _import(), test_direct_stock_split_rejects_currency_in_price_share(), test_import_all_or_nothing(), test_import_assigns_provided_portfolio_id(), test_import_buy_rows(), test_import_defaults_fees_to_zero(), test_import_defaults_portfolio_to_default() (+30 more)

### Community 8 - "Community 8"
Cohesion: 0.06
Nodes (34): Asset detail, code:json ({), code:json ({), code:json ({), code:json ({), code:json ({), code:json ({), code:json ({) (+26 more)

### Community 9 - "Community 9"
Cohesion: 0.10
Nodes (29): _payload(), _split_payload(), test_delete_does_not_remove_other_transactions(), test_delete_removes_transaction(), test_list_asset_symbol_filter_case_insensitive(), test_list_default_is_portfolio_scope_all(), test_list_portfolio_id_filter(), test_list_portfolio_scope_all_active_portfolios() (+21 more)

### Community 10 - "Community 10"
Cohesion: 0.12
Nodes (23): AssetDetailResult, build_asset_detail(), _build_holding_item(), build_holdings(), _fifo_eligible_queryset(), _float_or_none(), _holding_status(), HoldingsResult (+15 more)

### Community 11 - "Community 11"
Cohesion: 0.16
Nodes (26): _buy(), _price(), _sell(), test_buy_only_summary_metrics(), test_buy_sell_fifo_remaining_invested(), test_display_currency_converted_with_fx(), test_display_currency_missing_fx_unavailable(), test_display_currency_same_fx_ok() (+18 more)

### Community 12 - "Community 12"
Cohesion: 0.14
Nodes (19): Meta, Portfolio, Meta, PortfolioCreateSerializer, PortfolioSerializer, PortfolioUpdateSerializer, _active_count(), _active_name_exists() (+11 more)

### Community 13 - "Community 13"
Cohesion: 0.14
Nodes (23): calculate_portfolio_xirr(), Portfolio-level XIRR from BUY/SELL cash flows plus a terminal valuation.     Spl, latest_stock_prices_by_symbol(), list_index_prices_in_range(), list_stock_prices_in_range(), Benchmark index rows (asset_type INDEX), ascending by date., _stock_filter(), build_portfolio_summary() (+15 more)

### Community 14 - "Community 14"
Cohesion: 0.20
Nodes (17): DailyPrice, _buy(), MockPriceProvider, test_benchmark_symbol_caret_preserved(), test_benchmark_sync_incremental_idempotent(), test_benchmark_sync_stores_index_rows(), test_holdings_price_status_uses_latest_helper(), test_prices_refresh_without_symbols() (+9 more)

### Community 15 - "Community 15"
Cohesion: 0.08
Nodes (23): dependencies, lucide-react, react, react-dom, react-router-dom, recharts, devDependencies, jsdom (+15 more)

### Community 16 - "Community 16"
Cohesion: 0.12
Nodes (15): Backend Status, Constraints, Current State — KPulla6 (Portfolio Insight), Frontend (Phase 11), Last Updated, Not Yet Implemented, Phase 10 contracts (verified in tests), Phase 4 contracts (verified in tests) (+7 more)

### Community 17 - "Community 17"
Cohesion: 0.13
Nodes (5): BaseCommand, Command, Command, Command, Command

### Community 18 - "Community 18"
Cohesion: 0.13
Nodes (14): AppSettings, BenchmarkIndexConfig, Caching strategy (unchanged intent), code:bash (make migrate    # apply migrations), Database & Caching Strategy — KPulla6, FXRate, HistoricalPrice, Migrations & bootstrap (+6 more)

### Community 19 - "Community 19"
Cohesion: 0.13
Nodes (8): AnalyticsConfig, ApiConfig, AppConfig, FxConfig, MarketDataConfig, PortfoliosConfig, SettingsAppConfig, TransactionsConfig

### Community 20 - "Community 20"
Cohesion: 0.22
Nodes (12): _latest_stock_price_date(), Incrementally sync STOCK historical prices for transaction symbols.     When onl, Incremental sync for one stock symbol. Returns False on provider failure., _stock_price_filter(), StockSyncResult, _symbol_base_currency(), sync_one_stock_symbol(), sync_stock_prices() (+4 more)

### Community 21 - "Community 21"
Cohesion: 0.17
Nodes (11): API, Architecture — KPulla6 (Portfolio Insight), Backend, Constraints, Data flow (target), Database, Development, Finance domain (Phase 6) (+3 more)

### Community 22 - "Community 22"
Cohesion: 0.20
Nodes (6): PriceProvider, Return daily closes and optional quote currency for the symbol., MarketDataSyncResult, Run stock prices, benchmarks, and optional FX sync., sync_all_market_data(), AppSettings

### Community 23 - "Community 23"
Cohesion: 0.20
Nodes (9): code:block1 (KPulla6/), code:bash (cp .env.example .env), Current scope, Overview, Planned (from KPulla5), Project Summary — KPulla6 (Portfolio Insight), Repository layout, Running locally (+1 more)

### Community 24 - "Community 24"
Cohesion: 0.22
Nodes (6): BenchmarkIndicesView, PortfolioForceSyncView, PricesRefreshView, Manual historical price refresh (synchronous).     May call external market-data, Alias for full market-data sync (stocks + benchmarks + FX).     Runs synchronous, list_enabled_benchmark_indices()

### Community 25 - "Community 25"
Cohesion: 0.22
Nodes (8): code:bash (cp .env.example .env), code:bash (make test          # backend pytest + frontend vitest), code:bash (make refresh          # sync prices + benchmarks + FX), Frontend API base URL, Market data sync, Portfolio Insight — KPulla6, Quick start, Tests

### Community 26 - "Community 26"
Cohesion: 0.31
Nodes (7): _adj_close_or_close_series(), default_price_provider(), _norm_ccy(), normalize_provider_symbol(), yfinance-backed price history (used by sync commands and manual refresh only)., Uppercase stock tickers; preserve benchmark caret symbols., YFinancePriceProvider

### Community 27 - "Community 27"
Cohesion: 0.25
Nodes (7): 2026-05-19 — Phase 4 contracts documented and tested, 2026-05-19 — Phase 5 assumptions closed (pre–Phase 6), Added, Changelog — KPulla6, Docs, Docs updated, Tests

### Community 28 - "Community 28"
Cohesion: 0.25
Nodes (7): 2026-05-19 — Greenfield stack, Architecture Decisions — KPulla6, Data strategy (inherited), Finance modules, Finance rules (inherited), Schema strategy, UI strategy (inherited)

### Community 29 - "Community 29"
Cohesion: 0.25
Nodes (7): Completed (foundation), Layer mapping, Migration Readiness — KPulla5 → KPulla6, Next phases, Reference, Risks, Status

### Community 30 - "Community 30"
Cohesion: 0.25
Nodes (7): code:bash (cp .env.example .env), Development Workflow — KPulla6, Generic feature workflow, KPulla6-specific rules, Make targets, Prerequisites, Quick start

### Community 33 - "Community 33"
Cohesion: 0.60
Nodes (5): _latest_index_price_date(), _norm_ccy(), Incrementally sync enabled benchmark indices (asset_type=INDEX).     Requires at, sync_benchmark_prices(), upsert_index_price()

### Community 34 - "Community 34"
Cohesion: 0.40
Nodes (5): latest_historical_price(), normalize_asset_symbol(), Latest STOCK (or legacy null asset_type) close for symbol, case-insensitive., test_latest_price_returns_newest_by_date(), test_missing_latest_price_returns_none()

### Community 35 - "Community 35"
Cohesion: 0.40
Nodes (5): 2026-05-19 — Initial foundation (Django + DRF + React + Docker PostgreSQL), Added, Docs updated, Not included (by design), Tests

### Community 36 - "Community 36"
Cohesion: 0.40
Nodes (5): 2026-05-19 — Phase 2: Django models, migrations, seed, Added, Docs updated, Not included, Tests

### Community 37 - "Community 37"
Cohesion: 0.40
Nodes (5): 2026-05-19 — Phase 3: Settings and Portfolios APIs, Added, Docs updated, Not included, Tests

### Community 38 - "Community 38"
Cohesion: 0.40
Nodes (5): 2026-05-19 — Phase 4: Transaction CRUD APIs, Added, Docs updated, Not included, Tests

### Community 39 - "Community 39"
Cohesion: 0.40
Nodes (5): 2026-05-19 — Phase 5: CSV import and stock splits, Added, Docs updated, Not included, Tests

### Community 40 - "Community 40"
Cohesion: 0.40
Nodes (3): AssetType, HistoricalPrice, Meta

### Community 42 - "Community 42"
Cohesion: 0.50
Nodes (4): 2026-05-19 — Phase 10: Portfolio performance API, Added, Not included, Tests

### Community 43 - "Community 43"
Cohesion: 0.50
Nodes (4): 2026-05-19 — Phase 8: Historical prices, FX cache, benchmark sync, Added, Notes, Tests

### Community 44 - "Community 44"
Cohesion: 0.50
Nodes (4): 2026-05-19 — Phase 9: Portfolio summary API, Added, Not included, Tests

### Community 45 - "Community 45"
Cohesion: 0.50
Nodes (4): 2026-05-19 — Phase 7: Holdings and asset detail APIs, Added, Not included, Tests

### Community 46 - "Community 46"
Cohesion: 0.50
Nodes (4): 2026-05-19 — Phase 6: Finance domain layer, Added, Not included, Tests

### Community 48 - "Community 48"
Cohesion: 0.67
Nodes (3): 2026-05-19 — Phase 11: React frontend integration, Added, Notes

### Community 49 - "Community 49"
Cohesion: 0.67
Nodes (3): 2026-05-19 — Assets page fixes (post Phase 11), Fixed, Tests

## Knowledge Gaps
- **173 isolated node(s):** `name`, `private`, `version`, `dev`, `build` (+168 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **6 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ensure_default_portfolio()` connect `Community 1` to `Community 2`, `Community 4`, `Community 6`, `Community 7`, `Community 9`, `Community 11`, `Community 12`, `Community 13`, `Community 14`?**
  _High betweenness centrality (0.202) - this node is a cross-community bridge._
- **Why does `resolve_portfolio_scope()` connect `Community 2` to `Community 1`, `Community 3`, `Community 12`?**
  _High betweenness centrality (0.071) - this node is a cross-community bridge._
- **Why does `Transaction` connect `Community 2` to `Community 3`, `Community 4`, `Community 10`, `Community 13`, `Community 14`, `Community 20`?**
  _High betweenness centrality (0.048) - this node is a cross-community bridge._
- **Are the 57 inferred relationships involving `ensure_default_portfolio()` (e.g. with `list_active_portfolios()` and `get_portfolio()`) actually correct?**
  _`ensure_default_portfolio()` has 57 INFERRED edges - model-reasoned connections that need verification._
- **Are the 27 inferred relationships involving `str` (e.g. with `convert_amount_on_date()` and `resolve_fx_rate()`) actually correct?**
  _`str` has 27 INFERRED edges - model-reasoned connections that need verification._
- **What connects `name`, `private`, `version` to the rest of the system?**
  _209 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.052659716653301256 - nodes in this community are weakly interconnected._