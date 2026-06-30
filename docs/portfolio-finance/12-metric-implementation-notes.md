# Metric implementation notes

Technical reference for developers and doc maintainers. **Do not document formulas here that are not in code.**

## Module map (`backend/finance/`)

| Module | Responsibility |
|--------|----------------|
| `returns.py` | Daily/monthly/yearly fractional returns; `period_return`, `compound_return` |
| `twror.py` | TWROR percent-point series for performance chart |
| `performance_stats.py` | Cumulative from daily chain, economic cumulative, CAGR, period summary |
| `performance_range.py` | Range codes → start dates |
| `risk_metrics.py` | Volatility, downside deviation, Sharpe, Sortino |
| `drawdowns.py` | Drawdown series, max DD, episodes, Calmar |
| `comparison.py` | Benchmark alignment, beta, alpha, IR, normalized compare series |
| `benchmarks.py` | Chart overlay rebasing only — **not** Metric Sheet betas |
| `xirr.py` | XIRR cash flows |
| `fifo.py` / `splits.py` | Lots, split-adjusted quantities |
| `mutual_fund_cashflows.py` | MF XIRR merge rules |

Orchestration: `backend/analytics/services.py` (Django allowed).  
Tests: `test_finance_*.py`, `test_analytics_*_api.py`.

## API endpoints

| Endpoint | Subject |
|----------|---------|
| `GET /api/v1/analytics/performance-metrics` | Portfolio |
| `GET /api/v1/analytics/assets/{symbol}/performance-metrics` | Asset (optional `folio_number`) |
| `GET /api/v1/analytics/compare` | Two `asset:` subjects |

Shared query params: `range`, `display_currency`, `portfolio_scope`, `portfolio_id`, `benchmark`.

## Response shape (metrics block)

```json
{
  "metrics": {
    "return": {
      "cumulative_return": 0.12,
      "cagr": 0.11,
      "xirr": 0.105,
      "xirr_scope": "full_scope",
      "twror": 0.14
    },
    "risk": {
      "volatility_annualized": 0.18,
      "downside_deviation": 0.12,
      "sharpe_ratio": 0.85,
      "sortino_ratio": 1.1
    },
    "drawdown": {
      "max_drawdown": -0.082,
      "longest_drawdown_days": 45,
      "calmar_ratio": 1.36
    },
    "periods": {
      "best_day": 0.032,
      "worst_day": -0.028,
      "win_rate": 0.55,
      "average_daily_return": 0.0004
    }
  },
  "benchmark": {
    "symbol": "^GSPC",
    "paired_count": 252,
    "metrics": { "beta": 0.92, "alpha": 0.015, "...": null }
  },
  "periodic_returns": { "monthly": [], "yearly": [] },
  "drawdown_series": [],
  "drawdown_periods": { "worst": [] },
  "warnings": []
}
```

All fractional metrics: **JSON float fractions**, not percents.

## Critical conventions

### Daily return input

Built via `daily_returns_from_values(ValuePoint[], flows_by_date)`:

\[
r_t = \frac{V_t - F_t - V_{t-1}}{V_{t-1}}
\]

First day return is `null`. Used for risk, drawdown, periodic resampling, benchmark alignment.

### Two CAGR / cumulative paths (do not conflate)

| Use case | Cumulative / CAGR source |
|----------|-------------------------|
| `metrics.return.cumulative_return`, `metrics.return.cagr` | **Money-weighted** `economic_cumulative_return_fraction` + `cagr_from_total_return` |
| `metrics.return.twror` | Terminal `compute_twror_series` / 100 |
| `metrics.drawdown.calmar_ratio` | `cagr(daily_fracs, start, end)` from **compounded daily returns** |
| Risk / Sharpe / max DD | Daily fractional returns from values/flows |

Documenting this prevents “why doesn’t Calmar match CAGR?” bugs filed as errors.

### XIRR scope

Always full-scope cash flows; **not** range-sliced. Response flag: `xirr_scope: "full_scope"`.

### Annualization

- `periods_per_year = 252` default in `risk_metrics.py` and `comparison.py`.  
- Sharpe/Sortino numerator: `mean(r - rf_daily) * 252` with `rf = 0` in production API.  
- Volatility: sample stdev × `sqrt(252)`.

### Benchmark alignment

`align_return_series` — intersection of dates with non-null subject and benchmark returns; no fill.

Compare subjects: `align_multi_subject_returns` + metrics on sliced window; XIRR still full-scope per subject.

### Stock splits

- Quantities: split-adjusted snapshots.  
- Prices: must be **Adj Close** (yfinance) — invariant documented in `analytics/services.py`.  
- Warning when post-split value drop ≈ split factor.

### Mutual funds

- NAV from `HistoricalPrice` (`MUTUAL_FUND`).  
- Stale if latest NAV > 5 calendar days before valuation end.  
- XIRR: `merge_portfolio_xirr` / MF cashflow dates.

### All Portfolios

Aggregated display-currency value and flows per date; then same pipeline as single portfolio.

## Frontend display (`frontend/src`)

| Piece | Role |
|-------|------|
| `utils/metricFormatters.js` | Fraction → %, ratios, days, em dash |
| `components/metricSheet/*` | Tables, charts, compare ranking |
| `compareMetricRanking.js` | Display-only better/worse; no math |

**No finance calculations in React** (AGENTS.md).

## Holdings / summary metrics (separate APIs)

| Field | API | Finance |
|-------|-----|---------|
| `total_invested`, `realized_pl`, `unrealized_pl` | `/portfolio/summary`, holdings | FIFO |
| `xirr` | summary | `compute_scope_xirr` |
| Performance series | `/portfolio/performance` | summary timeseries + twror |

Not duplicated inside `metrics` block unless also on Metric Sheet.

## Planned / not yet implemented (engineering)

| Item | Notes |
|------|-------|
| Persist derived metrics | MVP on-query only |
| Configurable `risk_free_rate` | Params exist in `risk_metrics` / `comparison`; API hardcodes 0 |
| Celery auto-sync | Manual `make refresh` today |
| Golden files for all metrics | Partial (`test_finance_domain` TWROR only) |
| Compare >2 subjects | MVP = 2 |
| `folio_number` on compare query | **Planned** |

## Maintenance checklist

When changing a formula:

1. Update `backend/finance/*.py` + unit test.  
2. Update this knowledge base metric section.  
3. If API shape changes, update `docs/api-design.md` and frontend formatters.  
4. Do not change frontend to “fix” display mismatch — fix backend.

## Related docs

- [api-design.md](../api-design.md) — Analytics section  
- [architecture.md](../architecture.md) — Metric Sheet architecture  
- [AGENTS.md](../agents.md)
