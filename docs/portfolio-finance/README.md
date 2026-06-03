# Portfolio Finance Knowledge Base — KPulla6 (Portfolio Insight)

This section is the **finance reference** for Portfolio Insight: what each metric means, how professionals use it, and how KPulla6 computes and displays it today.

It is written for a **serious personal investor** who wants institutional-quality analytics without hedge-fund jargon overload. Where useful, we also note how **value investors** and **fund allocators** think about the same numbers.

## How to use these docs

| Audience | Start here |
|----------|------------|
| New to portfolio analytics | [01 — Portfolio analytics overview](./01-portfolio-analytics-overview.md) |
| Understanding a Metric Sheet number | Metric chapters [04](./04-return-metrics.md)–[08](./08-benchmark-and-relative-performance.md), then [glossary](./glossary.md) |
| Why two return numbers disagree | [04 — Return metrics](./04-return-metrics.md) (money-weighted vs TWROR) |
| Building or reviewing formulas | [12 — Metric implementation notes](./12-metric-implementation-notes.md) |
| Explaining metrics to end users | [11 — Behavioral interpretation](./11-behavioral-interpretation-for-users.md) |

## Implementation status (summary)

KPulla6 computes analytics in **`backend/finance/`** (pure Python) and exposes them via **`GET /api/v1/analytics/*`**. The React app **displays only** — no Sharpe, drawdown, or return math in the browser.

| Area | Status |
|------|--------|
| Metric Sheet (portfolio, asset, compare) | **Implemented** |
| Summary / holdings FIFO & P/L | **Implemented** (`GET /portfolio/summary`, holdings APIs) |
| Performance chart series | **Implemented** (`GET /portfolio/performance`) |
| Configurable risk-free rate | **Planned / not yet implemented** (Sharpe, Sortino, alpha use 0%) |
| Portfolio allocation analytics (concentration, factor exposure) | **Planned / not yet implemented** (Assets page shows simple % weights only) |
| Tax-adjusted returns, turnover, VaR | **Planned / not yet implemented** |

Always treat **“Planned / not yet implemented”** entries as design targets, not live API fields.

## Document map

| # | File | Contents |
|---|------|----------|
| 01 | [portfolio-analytics-overview](./01-portfolio-analytics-overview.md) | Subjects, ranges, data flow, Metric Sheet vs summary |
| 02 | [institutional-fund-metrics](./02-institutional-fund-metrics.md) | Allocator / hedge-fund vocabulary; what KPulla6 covers |
| 03 | [legendary-investor-metrics](./03-legendary-investor-metrics.md) | Buffett, Lynch, Graham-style lenses (mostly conceptual) |
| 04 | [return-metrics](./04-return-metrics.md) | Cumulative return, CAGR, TWROR, XIRR, periodic returns |
| 05 | [risk-metrics](./05-risk-metrics.md) | Volatility, downside deviation |
| 06 | [risk-adjusted-return-metrics](./06-risk-adjusted-return-metrics.md) | Sharpe, Sortino, Calmar |
| 07 | [drawdown-and-downside-risk](./07-drawdown-and-downside-risk.md) | Max drawdown, episodes, series |
| 08 | [benchmark-and-relative-performance](./08-benchmark-and-relative-performance.md) | Beta, alpha, tracking error, IR, Treynor |
| 09 | [portfolio-construction](./09-portfolio-construction.md) | How holdings and cash flows feed analytics |
| 10 | [asset-allocation-and-diversification](./10-asset-allocation-and-diversification.md) | Allocation display vs future analytics |
| 11 | [behavioral-interpretation-for-users](./11-behavioral-interpretation-for-users.md) | Plain-language guidance and pitfalls |
| 12 | [metric-implementation-notes](./12-metric-implementation-notes.md) | Code modules, API keys, conventions |
| — | [glossary](./glossary.md) | Short definitions and cross-links |

## Metric article template

Detailed metric pages in chapters 04–08 follow this structure:

1. **Simple meaning**
2. **Formula intuition**
3. **What it means to the user**
4. **Why professionals care**
5. **When it is useful**
6. **When it is misleading**
7. **Example interpretation**
8. **How KPulla6 should display it**
9. **Implementation notes**
10. **Related metrics**

## Related project docs

- [Project summary](../project-summary.md)
- [Current state](../current-state.md)
- [API design](../api-design.md) — analytics endpoints and response shapes
- [Frontend design](../frontend-design.md) — Metric Sheet UI
- [Architecture](../architecture.md) — Quantitative Statistics / Metric Sheet architecture
- [AGENTS.md](../../AGENTS.md) — finance code must stay in `backend/finance/`
