# Legendary investor metrics

Buffett, Graham, Lynch, and other “legendary” frameworks mix **business analysis** with **portfolio results**. Most classic ratios (ROE, P/E, debt/equity) come from **financial statements**, not from your transaction ledger.

This chapter separates:

1. **What Portfolio Insight can compute today** from your holdings and cash flows.
2. **What belongs in a stock research workflow** (Planned / not yet implemented in KPulla6).

## What KPulla6 already supports (investor outcomes)

| Lens | Implemented metric | Where |
|------|-------------------|--------|
| “Did I make money on my cash?” | XIRR, cumulative return, realized/unrealized P/L | Summary, Metric Sheet, holdings |
| “How smooth was the path?” | Volatility, drawdown, Sharpe/Sortino | Metric Sheet |
| “Did I beat the index?” | Alpha, active return, information ratio | Metric Sheet benchmark block |
| “How concentrated am I?” | Allocation % by `current_value` | Assets page (display only) |
| “Holdings discipline” | FIFO cost basis, closed/oversold warnings | Holdings, asset detail |

## Graham — margin of safety & defensive investing

**Simple meaning:** Buy with a cushion between price and conservative intrinsic value.

**In KPulla6:** Not computed. You would need external fair-value estimates per holding.

**Status:** **Planned / not yet implemented** (no `margin_of_safety` or intrinsic value fields).

**What you can use today:** Unrealized P/L vs FIFO cost shows **accounting** gain/loss, not economic margin of safety. Drawdown metrics show **path risk** after you are already invested.

## Buffett — quality, moat, owner earnings

**Simple meaning:** Prefer durable businesses with high returns on incremental capital and honest accounting.

**Classic metrics (external data):** ROE, ROIC, free cash flow yield, debt levels, share count trends.

**Status in KPulla6:** **Planned / not yet implemented** — no fundamentals API.

**Portfolio-level proxy today:**

- Long **holding period** visible in transaction history.
- **XIRR** vs benchmark **alpha** answers “did my Berkshire-style hold work?” not “is the moat intact?”

## Lynch — PEG, “ten-baggers,” know what you own

**Simple meaning:** Growth at a reasonable price; invest in businesses you understand; let winners run.

**Status in KPulla6:** No PEG or earnings growth. **Asset-level Metric Sheet** helps compare two holdings’ risk/return paths ([Compare](../frontend-design.md)).

**Useful today:** Calendar-year and monthly return grids show **which years** dominated your record (Lynch’s “story” over time).

## Munger — mental models & concentration

**Simple meaning:** Few high-conviction ideas; avoid unforced errors.

**KPulla6 today:** Allocation chart shows **weight %**; no formal concentration score (HHI, top-N %).

**Status:** **Planned / not yet implemented** — concentration analytics in Metric Sheet.

**Risk link:** Large single-name weight + high beta → benchmark-relative drawdowns in [08](./08-benchmark-and-relative-performance.md).

## Dalio — diversification & risk parity

**Simple meaning:** Balance risk contributions across uncorrelated streams.

**KPulla6 today:** Multi-currency portfolios with FX conversion; MF classification (`primary_asset_class`) for display — **not** a full risk-parity engine.

**Status:** Correlation matrix across holdings — **Planned / not yet implemented**.

## Templeton — contrarian timing

**Simple meaning:** Buy pessimism, sell optimism.

**KPulla6 today:** **Worst drawdown episodes** and monthly heatmap show **when** pain occurred; they do not score “fear/greed.”

## Mapping “legendary” questions to live metrics

| Question | Metric to open | Chapter |
|----------|----------------|---------|
| Did my cash earn a decent annualized return? | XIRR, CAGR | [04](./04-return-metrics.md) |
| Did I disturb the path with bad timing of deposits? | TWROR vs cumulative return | [04](./04-return-metrics.md) |
| Did I take too much pain for the return? | Sharpe, Sortino, max drawdown | [06](./06-risk-adjusted-return-metrics.md), [07](./07-drawdown-and-downside-risk.md) |
| Was I just riding the market? | Beta, alpha, correlation | [08](./08-benchmark-and-relative-performance.md) |
| Is one bet too large? | Allocation chart | [10](./10-asset-allocation-and-diversification.md) |

## How KPulla6 should talk about this (product copy)

- Do not imply ROE, PEG, or moat scores exist.
- Frame Metric Sheet as **portfolio outcome analytics** grounded in **your** transactions.
- Link value investing to **external research**; link KPulla6 to **measurement and discipline**.

## Related docs

- [02 — Institutional metrics](./02-institutional-fund-metrics.md)
- [11 — Behavioral interpretation](./11-behavioral-interpretation-for-users.md)
- [glossary](./glossary.md)
