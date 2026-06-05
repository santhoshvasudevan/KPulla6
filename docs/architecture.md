# Architecture — KPulla6 (Portfolio Insight)

## Overview
Local-first portfolio tracker. **KPulla6** uses Django + DRF + PostgreSQL + React, preserving KPulla5 domain rules and `/api/v1` contracts where practical.

## Backend
- **Framework:** Django 5 + Django REST Framework
- **Auth:** Django session auth + django-allauth (Google OAuth); see `docs/auth.md`
- **Domain apps (Phase 2 models in place):**
  - `portfolios` — `Portfolio` (`cash_aware_enabled`, default false)
  - `cash` — `CashLedgerEntry`, `CashTransferGroup` (Cash-1 schema; APIs Cash-2+)
  - `transactions` — `Transaction` (FK to real portfolio only)
  - `market_data` — `HistoricalPrice`, `BenchmarkIndexConfig`
  - `fx` — `FXRate`
  - `settings_app` — `AppSettings`
  - `analytics` — Metric Sheet orchestration (`analytics/services.py`); `GET /api/v1/analytics/performance-metrics` (Phase 5)
  - `api` — HTTP routing (`/api/v1/health` today)
- **Finance logic:** `backend/finance/` — framework-independent (Phase 6)
  - `types.py`, `splits.py`, `fifo.py`, `xirr.py`, `twror.py`, `performance_range.py`, `benchmarks.py`
  - Analytics: `returns.py` (Phase 2); `performance_stats.py`, `risk_metrics.py`, `drawdowns.py` (Phase 3); `comparison.py` (Phase 4); `benchmarks.py` (chart overlay only)
  - Django adapter: `transactions/finance_adapter.py` (DTO mapping only)

## Database
- PostgreSQL 16 via Docker Compose
- Django migrations only
- Seed: `manage.py seed_initial_data` / `make seed`

## Virtual vs real portfolios
- **All Portfolios** is a virtual aggregate (API `portfolio_scope=all`); never stored in `portfolios`.
- Only real portfolios exist as rows; **Default Portfolio** is seeded with `is_default=True`.

## Finance domain (Phase 6)
- Pure Python; no Django ORM in `backend/finance/`.
- **FIFO** (`calculate_fifo_cost_basis_metrics`): cumulative qty/invested, avg cost, realized/unrealized P/L; fees ignored in FIFO (KPulla5 parity).
- **Splits** (`apply_stock_split_adjustments`): `split_to/split_from` on prior same-symbol BUY/SELL before split date.
- **Value history** (`build_split_adjusted_lot_snapshots`): daily portfolio valuation pairs cached split-adjusted prices with split-adjusted quantities; `STOCK_SPLIT` rows are not cash flows.
- **XIRR** (`calculate_xirr`): BUY negative, SELL positive, terminal holding value; uses `pyxirr`.
- **TWROR** (`compute_twror_series`): chain-linked daily return series; exposed via `GET /portfolio/performance?metric=twror` (Phase 10).

## Data flow (target)
1. **Transactions** → holdings, cost basis, realized P/L (finance layer ready; APIs next).
2. **HistoricalPrice** + **FXRate** → cached valuation inputs.
3. **AppSettings.display_currency** → API display layer (future).
4. Manual sync (`POST /prices/refresh`, management commands) writes prices/FX/benchmarks; holdings and future dashboard reads DB only.

## Frontend
- React + Vite; API-driven; no finance calculations in the client.

## API
- Base: `/api/v1`
- Implemented: health, settings, portfolios CRUD, transactions CRUD, CSV import, holdings, asset detail
- Services: `portfolios/services.py`, `portfolios/holdings_service.py`, `portfolios/scope.py`, `settings_app/services.py`, `transactions/services.py`, `transactions/csv_import.py`, `market_data/price_lookup.py`
- Phase 8: `market_data/services/`, `market_data/providers/`, `fx/services/`, `fx/lookup.py`
- Phase 9: `portfolios/summary_service.py` — summary + timeseries from cached prices/FX
- `GET /api/v1/portfolio/performance` — value / cumulative return / TWROR time series; optional benchmark comparison (`portfolios/performance_service.py`, `finance/benchmarks.py`, `finance/performance_range.py`)
- **Frontend** (`frontend/src/`): API-driven pages; `portfolioContext` builds `portfolio_scope=all` or `portfolio_id` query params; charts render backend series only

## Development
- `make bootstrap` — db, migrate, seed
- `make dev` — full stack (migrate; seed manually or via bootstrap first)

## Quantitative Statistics / Metric Sheet architecture

**Purpose:** Provide **Quantitative Statistics** — professional **performance metrics and charts** in a **Metric Sheet** layout (risk/return ratios, drawdowns, periodic returns, benchmark-relative stats) at portfolio, single-asset, and (later) multi-asset comparison scope — without live market-data calls on read paths.

### Subject levels

| Level | Scope | Primary user surface (future) |
|-------|--------|--------------------------------|
| **Portfolio** | `portfolio_scope=all` or `portfolio_id` | Dashboard — Performance Quality section |
| **Asset** | One stock/ETF symbol or MF scheme+folio | Asset Detail — Metric Sheet tab/section |
| **Comparison** | Two or more assets, same range/benchmark | Future Compare page (side-by-side table + charts) |

### Data sources (persisted; no live provider on read)

1. **Transactions** — BUY/SELL (and splits for quantity/price adjustment); MF uses `investment_date` / `paid_value` for external cash flows where applicable.
2. **HistoricalPrice** — split-adjusted stock/ETF closes (`yfinance` **Adj Close** via `make sync-prices`); benchmark `asset_type=INDEX`. **Invariant:** `build_split_adjusted_lot_snapshots` scales pre-split transaction quantities, so cached stock closes must be split-adjusted too. Raw nominal pre-split prices × split-adjusted qty produce false valuation spikes (see `test_stock_split_valuation_api.py`, `test_analytics_split_metrics_api.py`). Metric Sheet endpoints warn when a split date shows a value drop ratio matching the split factor (likely raw prices).
3. **FXRate** — same-date conversion into portfolio/holding/display currency (7-day fill where summary/performance already allows).
4. **Mutual fund NAVs** — `HistoricalPrice` rows with `asset_type=MUTUAL_FUND`.
5. **Benchmark index prices** — cached index levels for beta, alpha, correlation, and overlay charts.

Transactions remain the **source of truth**. Prices, FX, NAVs, and benchmarks are **cache inputs** refreshed only via manual sync (`make refresh`, refresh HTTP endpoints, management commands).

### Primary calculation input

Most technical metrics (Sharpe, Sortino, annualized volatility, max drawdown, beta, alpha, correlation, monthly/yearly return tables, win/loss rates, best/worst period) are computed from a **daily cash-flow-adjusted return series**:

- Build daily **portfolio value** (or asset value) series from cached prices/NAV + split-adjusted holdings — same foundation as Phase 9/10 (`build_portfolio_value_timeseries` / asset-level analogue).
- Derive **external flows** per day (BUY/SELL cash, MF `paid_value` on `investment_date`) — same rules as `portfolios/performance_service._build_external_flows`.
- Convert to **period returns** via TWROR logic: \(r_d = (PV_d - F_d - PV_{d-1}) / PV_{d-1}\), then chain-link for cumulative TWROR or export **daily \(r_d\)** as the analytics input series.

**Do not** use XIRR or raw price-only returns as the base input for these daily technical metrics.

### Separate metrics (unchanged roles)

| Metric family | Role | Module / API today |
|---------------|------|---------------------|
| **XIRR** | Money-weighted IRR on BUY/SELL (+ terminal value) | `finance/xirr.py`, `finance/mutual_fund_cashflows.py`; summary + holdings; **`compute_scope_xirr`** in `summary_service` for cross-module reuse |
| **FIFO** | Cost basis, realized/unrealized P/L | `finance/fifo.py`; holdings, summary |
| **TWROR time series** | Cumulative chain-linked % for charts | `finance/twror.py`; `GET /portfolio/performance?metric=twror` |
| **cumulative_return** | Contribution-adjusted headline % | performance API |

Analytics performance-metrics endpoints **compose** these where appropriate (e.g. show XIRR alongside Sharpe) but **derive** risk/return stats from TWROR-style daily returns. XIRR in the Metric Sheet response is **full-scope** (`xirr_scope: "full_scope"`), not sliced by the selected performance range.

### Backend module plan (`backend/finance/` — framework-independent)

| Module | Responsibility |
|--------|----------------|
| `returns.py` | **Implemented (Phase 2):** `period_return`, `daily_returns_from_values`, `daily_returns_from_twror_series`, `compound_return` / `chain_returns`, `resample_monthly_returns` / `resample_yearly_returns` — fractional outputs; TWROR inputs in percent points |
| `performance_stats.py` | **Phase 3:** cumulative return, CAGR, best/worst, win rate, `period_summary`; monthly/yearly tables via `returns.py` |
| `risk_metrics.py` | **Phase 3:** annualized volatility, downside deviation, Sharpe, Sortino (252-day annualization; beta/alpha in Phase 4) |
| `drawdowns.py` | **Phase 3:** drawdown series, max drawdown, longest drawdown days, Calmar; **Phase 9A:** `worst_drawdown_periods` (ranked peak/trough/recovery episodes) |
| `comparison.py` | **Phase 4 + 7:** align daily returns by date; correlation, beta, alpha, tracking error, active return, information ratio, Treynor, `benchmark_summary`; **Phase 7:** `align_multi_subject_returns`, `normalized_cumulative_return_series` for compare API |
| `benchmarks.py` | Chart overlay: rebased portfolio vs index **price** series (pandas); not daily-return stats |

**Django orchestration** (`backend/analytics/` — may import ORM, scope, repositories):

| Module | Responsibility |
|--------|----------------|
| `services.py` | Resolve scope/range/display currency/benchmark; load transactions + cached prices/FX/NAV; build value + flow series; call `finance/*`; assemble warnings via `build_metric_sheet_from_daily_returns`; **Phase 9A:** `periodic_returns` + `drawdown_periods` blocks; **Phase 7:** `build_analytics_compare` aligns multi-subject daily returns on exact common dates before metrics |
| `views.py` / serializers (later) | `GET /api/v1/analytics/...` — no finance math in views |

Existing **`portfolios/performance_service.py`** remains the source of portfolio-level value/TWROR **time series** for charts; analytics services **reuse** its timeseries/flow builders (or shared helpers extracted later) to avoid duplicating valuation rules.

### API direction

- `GET /api/v1/analytics/performance-metrics` — **implemented** (Phase 5): portfolio performance metric sheet (query: `portfolio_scope`, `portfolio_id`, `range`, `display_currency`, optional `benchmark`)
- `GET /api/v1/analytics/assets/{asset_symbol}/performance-metrics` — **implemented** (Phase 6): asset performance metric sheet (MF: `folio_number` when required)
- `GET /api/v1/analytics/compare` — **implemented** (Phase 7): two-asset side-by-side Metric Sheet comparison with `normalized_series` (query: `subjects=asset:A,asset:B`, scope, `range`, `display_currency`, optional `benchmark`)

See `docs/api-design.md` for response shapes.

### Compare API data flow (Phase 7)

```
subjects=asset:AAPL,asset:MSFT
  → per subject: reuse asset Metric Sheet pipeline (_prepare_asset_daily_metrics_inputs)
  → range-sliced daily return points per subject
  → align_multi_subject_returns (exact date intersection; skip None; no forward-fill)
  → normalized_cumulative_return_series (first common date = 0; compound from second date)
  → build_metric_sheet_from_daily_returns on aligned window per subject
  → optional benchmark_summary per subject vs cached INDEX prices on aligned window
```

Compare metrics (return, risk, drawdown, periods) use the **aligned common window only**, not each asset’s independent full history. XIRR remains full-scope per subject when computable.

### Frontend direction (proposed — not implemented in Phase 1)

- **Dashboard:** Performance Quality cards + drawdown / monthly return charts fed only by analytics APIs.
- **Asset Detail:** Metric Sheet section (metrics table, drawdown table, periodic returns).
- **Compare (future):** Side-by-side metrics table; all values from backend — **no** Sharpe/beta/volatility math in React.

### Warnings and partial availability

Responses should expose a `warnings` array (and per-metric `null` where needed), consistent with performance benchmark behavior:

- Missing **stock price** → skip or null days; warn per symbol.
- Missing **FX** → `flows_unknown_from` / `fx_unavailable` style gating (reuse performance patterns).
- Missing **MF NAV** → null asset/portfolio value on affected days; warn when no cached NAV exists, or when the latest cached NAV is older than 5 calendar days (weekend/holiday gaps are acceptable when forward-fill from a recent NAV is available).
- Missing **benchmark** prices → portfolio-only metrics; beta/alpha/correlation null with warning.
- **Insufficient history** (e.g. &lt; 2 return observations) → ratio metrics null, not zero.
- **Stock split + price history:** when cached prices appear to be raw nominal (not split-adjusted) around a `STOCK_SPLIT`, Metric Sheet responses include a warning; metrics may still be returned but returns around the split are unreliable. Use `make sync-prices` (Adj Close) for supported symbols.

Never call yfinance, MFAPI, or other external providers during analytics **read** paths.

### Storage and caching (MVP decision)

**MVP does not persist** TWROR daily series, derived daily returns, or computed analytics metrics.

- Metrics are **calculated on query** from persisted source data (transactions, prices, FX, NAVs, benchmark prices).
- **Optional future cache/snapshot table** may be added only after formulas and API contracts stabilize.
- If caching is introduced later, invalidation must run on changes to transactions, prices, FX, NAVs, or benchmark rows affecting the subject; cache keys must include **subject** (portfolio/asset), **range**, **display_currency**, **benchmark**, and an **input hash** (e.g. latest transaction id + max price date per symbol).

## Cash Ledger (Cash-1 foundation)

Schema and pure balance helpers are in place; read APIs and cash-aware performance logic are **Cash-2+**. Full specification: [cash-ledger.md](./cash-ledger.md).

- **App:** `cash` — `CashLedgerEntry`, `CashTransferGroup`; `Portfolio.cash_aware_enabled` (default `false`).

- **Cash** = portfolio balance component (per portfolio, per currency); included in current value, value history, allocation, and buying-power checks.
- **Stocks / MFs** = investment assets; cash excluded from Asset Metric Sheet, Compare, and investment-style performance analytics.
- **Ledger:** proposed `CashLedgerEntry` (+ later `CashTransferGroup`) — settlements link to `Transaction`; deposits/withdrawals are external flows for TWROR/XIRR in cash-aware mode; BUY/SELL become internal after backfill.
- **Legacy mode:** existing BUY/SELL external-flow behavior until portfolio cash-aware mode is enabled and backfilled.
- **Finance:** balance and flow rules in `backend/finance/` (framework-independent); Django services orchestrate ORM + existing summary/performance builders.
- **APIs:** additive `/api/v1/cash/*` (planned); preserve existing contracts.

## Constraints
- Do not modify KPulla5
- No runtime schema patching
- Transactions = source of truth
