# Institutional and hedge-fund metrics

Professional allocators, fund-of-funds, and hedge funds use a shared vocabulary for **return**, **risk**, **relative performance**, and **operational quality**. This chapter maps that world to what Portfolio Insight implements today.

## How institutions organize analytics

| Layer | Question | Typical metrics |
|-------|----------|-----------------|
| **Return** | Did capital grow? | TWR (path), MWR/IRR (client), CAGR |
| **Risk** | How bumpy was the ride? | Volatility, downside deviation, beta |
| **Risk-adjusted** | Return per unit of risk? | Sharpe, Sortino, information ratio, Calmar |
| **Relative** | vs policy benchmark? | Active return, tracking error, alpha, beta |
| **Tail / path** | Worst episodes? | Max drawdown, drawdown duration, recovery |
| **Operations** | Can I trust the numbers? | Audit, GIPS, capacity, liquidity — mostly outside this app |

KPulla6’s **Metric Sheet** covers the middle four rows for portfolio, asset, and pairwise compare subjects, using **daily cash-flow-adjusted returns** derived from cached valuations.

## Metrics KPulla6 implements (Metric Sheet)

These align with standard institutional dashboards (often under “Quantitative Statistics” or “risk/return attribution”):

| Metric | API path (fraction unless noted) | Module |
|--------|----------------------------------|--------|
| Cumulative return | `metrics.return.cumulative_return` | `performance_stats` + economic formula in `analytics/services` |
| CAGR | `metrics.return.cagr` | `cagr_from_total_return` |
| TWROR (terminal) | `metrics.return.twror` | `finance/twror.py` |
| XIRR | `metrics.return.xirr` | `finance/xirr.py` |
| Volatility (annualized) | `metrics.risk.volatility_annualized` | `risk_metrics.py` |
| Downside deviation | `metrics.risk.downside_deviation` | `risk_metrics.py` |
| Sharpe ratio | `metrics.risk.sharpe_ratio` | `risk_metrics.py` |
| Sortino ratio | `metrics.risk.sortino_ratio` | `risk_metrics.py` |
| Max drawdown | `metrics.drawdown.max_drawdown` | `drawdowns.py` |
| Longest drawdown | `metrics.drawdown.longest_drawdown_days` | `drawdowns.py` |
| Calmar ratio | `metrics.drawdown.calmar_ratio` | `drawdowns.py` |
| Best/worst day, win rate, avg daily | `metrics.periods.*` | `performance_stats.period_summary` |
| Beta, alpha, correlation, TE, IR, Treynor | `benchmark.metrics.*` | `comparison.py` |
| Monthly / yearly periodic | `periodic_returns` | `returns.py` |
| Drawdown series & worst episodes | `drawdown_series`, `drawdown_periods` | `drawdowns.py` |

Summary/holdings (not Metric Sheet but institutional-adjacent):

| Metric | API | Status |
|--------|-----|--------|
| FIFO cost basis, realized/unrealized P/L | `GET /portfolio/summary`, holdings | **Implemented** |
| Holdings `xirr` | summary | **Implemented** |

## Common institutional metrics — not yet in KPulla6

Mark these **Planned / not yet implemented** unless noted otherwise:

| Metric | Why allocators use it |
|--------|------------------------|
| **VaR / CVaR** | Regulatory and risk-limit reporting |
| **Skewness / kurtosis** | Tail risk shape |
| **Omega / Sterling / Burke ratios** | Alternative risk-adjusted rankings |
| **Up/down capture vs benchmark** | Simple relative path story |
| **Rolling 12m return & volatility** | Point-in-time dashboards |
| **Portfolio turnover** | Tax and capacity |
| **Factor exposures (Fama-French, etc.)** | Style attribution |
| **GIPS composite reporting** | Official track record |
| **Liquidity gates, gates, high-water marks** | Hedge fund terms (legal/ops) |
| **Configurable risk-free rate** | Sharpe/alpha vs T-bills — code supports parameter; API/UI fixed at 0% |

Documenting them here sets expectations: the Metric Sheet is **MVP institutional-lite**, not a full risk platform.

## Hedge-fund lens (what pros emphasize)

1. **Drawdown culture** — max drawdown and **time underwater** matter as much as CAGR; Calmar (CAGR / |max DD|) is a popular shorthand.
2. **Benchmark choice** — equity long-short may use S&P 500; market-neutral may use cash + beta overlay. KPulla6 uses **user-selected index symbols** from cached `BenchmarkIndexConfig` rows.
3. **Information ratio** — active return per unit of tracking error; core for “did active management earn its tracking risk?”
4. **Capacity and flows** — institutions separate **manager return** (TWR) from **investor return** (MWR). KPulla6 exposes both via TWROR path stats vs money-weighted cumulative return / XIRR.

## Fund-of-funds / allocator checklist (mapped to app)

| Allocator question | KPulla6 today |
|--------------------|---------------|
| Track record length | `range=ALL`, calendar-year chart |
| Consistency | Monthly heatmap, win rate, periodic returns |
| Crisis behavior | Drawdown chart, worst episodes table |
| Style drift vs benchmark | Beta, correlation, active return |
| Operational trust | Warnings (prices, NAV, FX, splits); manual `make refresh` for cache |

## Value-investor contrast (same chapter, different tools)

Institutions optimizing **relative rank** within a peer group often overweight Sharpe and IR. **Value investors** (see [03](./03-legendary-investor-metrics.md)) may ignore short-term volatility if business quality and margin of safety are strong — but they still care about **permanent capital loss** (drawdown, concentration), which KPulla6 surfaces.

## Further reading in this knowledge base

- Per-metric detail: [04](./04-return-metrics.md)–[08](./08-benchmark-and-relative-performance.md)
- Construction: [09](./09-portfolio-construction.md)
- User-facing explanations: [11](./11-behavioral-interpretation-for-users.md)
