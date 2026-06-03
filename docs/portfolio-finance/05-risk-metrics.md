# Risk metrics

Risk metrics describe **how variable** returns are, especially on the downside. KPulla6 derives them from **daily cash-flow-adjusted return fractions** over the selected Metric Sheet range (same series as drawdown and Sharpe).

Convention: **annualized** outputs are fractions (`0.14` = 14% vol). Sample standard deviation uses \(n-1\) when \(n \ge 2\). Annualization assumes **252** periods per year.

---

## Volatility (annualized)

### Simple meaning
Typical size of day-to-day swings, scaled to a one-year equivalent.

### Formula intuition
1. Compute sample std dev of daily returns \(s_d\).  
2. Annualize: \(\sigma_{\text{ann}} = s_d \times \sqrt{252}\).

### What it means to the user
“How bumpy was this portfolio/asset?” Higher → more nerve-wracking day-to-day.

### Why professionals care
Risk budgets, position sizing, Sharpe denominator, regulatory risk reports.

### When it is useful
Comparing two assets on Compare (lower is better highlight). Pairing with return to judge efficiency.

### When it is misleading
Assumes past volatility predicts future. Few trading days → unstable estimate. Ignores **liquidity** and **gap risk** on illiquid MFs with stale NAV.

### Example interpretation
Volatility 18% with CAGR 10% → moderate equity-like ride. Volatility 5% with CAGR 2% → calm but low payoff (see Sharpe).

### How KPulla6 should display it
- **Label:** Volatility (annualized)  
- **Format:** Percent  
- **Compare:** lower is better (subtle highlight)

### Implementation notes
- **Implemented:** `metrics.risk.volatility_annualized` — `risk_metrics.annualized_volatility`  
- Returns `null` if fewer than two valid daily returns  
- Returns `0` if all valid days identical

### Related metrics
Sharpe ratio, downside deviation, beta, tracking error

---

## Downside deviation (annualized)

### Simple meaning
Volatility computed only on days **below** a target return (default 0%) — “bad” volatility.

### Formula intuition
1. Take daily returns with \(r_t < 0\).  
2. Sample std dev of those values.  
3. Annualize with \(\sqrt{252}\).

### What it means to the user
“How violent were the **losing** days?” Sortino uses this in the denominator.

### Why professionals care
Penalizes harmful volatility without punishing upside variability (unlike standard deviation).

### When it is useful
Asymmetric return profiles (positive skew strategies). Comparing strategies with similar vol but different crash days.

### When it is misleading
Few down days → `null` (needs ≥2 downside observations). A strategy with almost no losing days can look artificially calm.

### Example interpretation
Volatility 20%, downside deviation 12% → losses were clustered but upswings were wide.

### How KPulla6 should display it
- **Label:** Downside Deviation  
- **Format:** Percent  
- **Table:** Risk group on Metric Sheet

### Implementation notes
- **Implemented:** `metrics.risk.downside_deviation` — `risk_metrics.downside_deviation`  
- Target return fixed at `0` (not user-configurable)

### Related metrics
Sortino ratio, max drawdown, volatility

---

## Planned / not yet implemented (risk family)

| Metric | Status |
|--------|--------|
| Semi-deviation vs benchmark | **Planned** |
| VaR / CVaR (95%, 99%) | **Planned** |
| Skewness / kurtosis | **Planned** |
| Rolling volatility | **Planned** |
| Configurable `periods_per_year` (365 vs 252) | **Planned** — code default 252 |

See [06 — Risk-adjusted returns](./06-risk-adjusted-return-metrics.md) and [07 — Drawdown](./07-drawdown-and-downside-risk.md).
