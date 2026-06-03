# Behavioral interpretation for users

Metric Sheet numbers are precise; **human reactions** are not. This chapter helps you explain outcomes to yourself (or to a user of Portfolio Insight) without overconfidence or panic.

## Golden rules

1. **Two return numbers can both be right** — cumulative return (money-weighted) vs TWROR (path) answer different questions. See [04](./04-return-metrics.md).
2. **XIRR is always “since the beginning”** — do not compare XIRR to a 1Y CAGR without saying so (`xirr_scope: full_scope`).
3. **Range changes the story** — switching `7D` → `ALL` changes volatility, drawdown, and CAGR; not a bug.
4. **Null is honest** — `—` means insufficient data (flows, prices, overlap), not zero performance.
5. **Read warnings first** — missing prices, stale NAV, FX gaps, and split suspicions invalidate calm conclusions.

## Metric-by-metric user stories

### “Am I winning?”

| If they care about… | Show | Avoid saying |
|---------------------|------|--------------|
| Total account growth in a period | Cumulative return, CAGR | “XIRR for this year” without scope note |
| Lifetime cash yield | XIRR (full scope) | Equating XIRR to fund factsheet TWR |
| Skill vs deposit timing | TWROR vs cumulative return | “TWROR is how much money I made” |

**Value investor angle:** Business quality does not change daily; short CAGR noise is normal for concentrated portfolios.

### “Is it too risky?”

| Signal | Plain language |
|--------|----------------|
| Volatility | “Typical daily bumpiness, annualized.” |
| Max drawdown | “Worst drop from a previous high in this period.” |
| Longest drawdown | “How long you stayed below a past peak.” |
| Sharpe / Sortino | “Return per unit of pain; higher is better if data is long enough.” |

**Behavioral trap:** Low volatility in a **rising** market feels safe right before a drawdown. Pair with max drawdown history.

### “Am I beating the market?”

| Metric | Plain language |
|--------|----------------|
| Active return | “Average yearly beat vs index on days we could compare.” |
| Alpha | “Beat after accounting for how market-sensitive the portfolio is (beta).” |
| Beta | “How much you move with the index.” |
| Information ratio | “Beat per unit of ‘being different’ from the index.” |

**Trap:** Picking a mismatched benchmark (small-cap portfolio vs S&P 500) makes alpha meaningless.

### “What happened in year X?”

Use **Calendar-Year Return** bar chart — cash-flow-adjusted yearly compounding, not bank statement YoY unless flows were trivial.

### “Stock A vs Stock B”

Use **Compare** with the common-dates note. Say: “We only compare days when both had prices.” Do not rank drawdown episodes across subjects (not implemented).

## Emotional mapping (drawdowns)

| Drawdown depth | Typical feeling | Constructive response |
|----------------|-----------------|------------------------|
| −5% to −10% | Unease | Check if thesis changed; review allocation % |
| −10% to −25% | Stress | Re-read warnings; confirm prices/NAV correct |
| > −25% | Panic risk | Separate **permanent loss** (thesis break) vs **quotation loss** (metric path) |

Institutions pre-commit to limits; individuals benefit from the same **pre-written rules** (max add per name, rebalance bands).

## When to refresh data before interpreting

If warnings mention missing prices or NAV:

```bash
make refresh
```

Stale MF NAV (>5 calendar days behind valuation date) triggers a warning — weekend gaps with recent NAV do not.

## Copy patterns for UI (KPulla6)

Already implemented or recommended:

| Element | Copy |
|---------|------|
| XIRR note | “XIRR is full-scope; other Metric Sheet values follow the selected range.” |
| Calendar-year chart | “Cash-flow adjusted return using daily TWROR.” |
| Compare | “Compared over common dates: {start} – {end}” |
| Warnings | Calm `warning` severity — explain fix (sync, check splits), not blame |

Avoid:

- “Guaranteed future Sharpe”  
- “Alpha proves skill” on short windows  
- Implying fundamentals (ROE, moat) exist in Metric Sheet

## FAQ-style misconceptions

**“Sharpe is 2, I’m a genius.”**  
Short sample, zero risk-free rate, or lucky window. Check paired count and range length.

**“Beta below 1 means safe.”**  
Lower market sensitivity ≠ no drawdown; bonds and stocks both can fall.

**“Win rate 70% means profitable.”**  
Average loss size matters; see worst day and max drawdown.

**“Metric Sheet disagrees with my broker.”**  
Different return definitions (TWR vs MWR), FX display currency, fees inclusion, split-adjusted prices.

## Related docs

- [01 — Overview](./01-portfolio-analytics-overview.md)
- [04](./04-return-metrics.md)–[08](./08-benchmark-and-relative-performance.md)
- [frontend-design.md](../frontend-design.md) — Metric Sheet UX
