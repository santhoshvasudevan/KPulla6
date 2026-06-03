# Glossary

Short definitions for Portfolio Insight analytics. Fractions in API are decimal (0.10 = 10%) unless noted.

| Term | Definition | Implemented in KPulla6 |
|------|------------|------------------------|
| **Active return** | Annualized average daily outperformance vs benchmark | Yes — `benchmark.metrics.active_return` |
| **Adj Close** | Split/dividend-adjusted price used for stock valuation | Yes — price sync invariant |
| **Alpha (CAPM)** | Annualized return above CAPM expectation given beta; rf=0 in API | Yes — `benchmark.metrics.alpha` |
| **All Portfolios** | Virtual scope aggregating active real portfolios | Yes |
| **Average daily return** | Arithmetic mean of daily return fractions | Yes — `metrics.periods.average_daily_return` |
| **Benchmark** | Cached index (`HistoricalPrice` INDEX) for relative metrics | Yes — user-selected symbol |
| **Beta** | Covariance(subject, benchmark) / variance(benchmark) on daily returns | Yes |
| **CAGR** | Annualized growth rate from range money-weighted cumulative return | Yes — `metrics.return.cagr` |
| **Calendar-Year Return** | Yearly compounded daily TWROR-style returns | Yes — `periodic_returns.yearly` |
| **Calmar ratio** | CAGR from daily returns / \|max drawdown\| | Yes — note dual CAGR definitions in [12](./12-metric-implementation-notes.md) |
| **Cash-flow-adjusted return** | Daily return removing external flow impact on value change | Yes — `period_return` / TWROR chain |
| **Compare (API)** | Two assets on common overlapping dates | Yes — MVP |
| **Correlation** | Pearson correlation of aligned daily returns | Yes |
| **Cumulative return (range)** | Money-weighted total return for selected range | Yes — `metrics.return.cumulative_return` |
| **Display currency** | User setting for converted monetary display | Yes — settings |
| **Downside deviation** | Annualized volatility of returns below 0% | Yes |
| **Drawdown** | Wealth / running peak − 1 (≤ 0) | Yes — series and max |
| **FIFO** | First-in-first-out cost basis for holdings | Yes — not Metric Sheet |
| **Information ratio** | Active return / tracking error | Yes |
| **Max drawdown** | Most negative drawdown in range | Yes |
| **Metric Sheet** | Analytics block from `/analytics/*` | Yes |
| **Money-weighted return (MWR)** | Return affected by cash flow timing | Yes — cumulative return, XIRR |
| **Paired count** | Aligned subject/benchmark days | Yes |
| **Periodic return** | Compounded return over month/year bucket | Yes — monthly/yearly |
| **Realized P/L** | Profit/loss from closed lots (FIFO) | Yes — summary/holdings |
| **Risk-free rate** | Benchmark for excess return; **0% in API today** | Partial — code param, not exposed |
| **Sharpe ratio** | Annualized excess return / volatility | Yes |
| **Sortino ratio** | Annualized excess return / downside deviation | Yes |
| **Split-adjusted** | Quantities and prices scaled for stock splits | Yes — required for stocks |
| **Terminal value** | Ending market value in XIRR flows | Yes |
| **Tracking error** | Annualized vol of daily active return | Yes |
| **Treynor ratio** | Annualized excess return / beta | Yes |
| **TWROR** | Time-weighted return on residual (chain-linked) | Yes — chart + `metrics.return.twror` |
| **Unrealized P/L** | Mark-to-market vs remaining cost | Yes |
| **Volatility (annualized)** | Sample daily stdev × √252 | Yes |
| **Win rate** | Fraction of days with return > 0 | Yes |
| **Worst drawdown period** | Peak→trough episode with recovery metadata | Yes — `drawdown_periods.worst` |
| **XIRR** | IRR on transaction cash flows + terminal value | Yes — full scope |
| **Allocation %** | Holding weight by current value | Display only on Assets |
| **Capture ratio** | Upside/downside vs benchmark | **Planned** |
| **Concentration (HHI)** | Sum of squared weights | **Planned** |
| **Factor exposure** | Regression on style factors | **Planned** |
| **GIPS** | Global investment performance standards | **Planned** (reporting framework) |
| **Margin of safety** | Price vs intrinsic value cushion | **Planned** (fundamentals) |
| **Omega ratio** | Probability-weighted gains/losses | **Planned** |
| **ROE / ROIC** | Return on equity/capital | **Planned** (fundamentals) |
| **Turnover** | Trading volume / average assets | **Planned** |
| **VaR / CVaR** | Value at risk / expected shortfall | **Planned** |

## Acronyms

| Acronym | Expansion |
|---------|-----------|
| CAPM | Capital Asset Pricing Model |
| CAGR | Compound annual growth rate |
| FIFO | First in, first out |
| GIPS | Global Investment Performance Standards |
| IR | Information ratio |
| MF | Mutual fund |
| MWR | Money-weighted return |
| NAV | Net asset value |
| TWR | Time-weighted return |
| TWROR | Time-weighted return on residual |
| XIRR | Extended internal rate of return |

## See also

- [README](./README.md) — document index
- Chapters [04](./04-return-metrics.md)–[08](./08-benchmark-and-relative-performance.md) — full metric templates
