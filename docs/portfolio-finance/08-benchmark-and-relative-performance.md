# Benchmark and relative performance

Relative metrics compare your **subject** (portfolio or asset) to a **benchmark index** using **aligned daily returns**. They power the Metric Sheet **Benchmark** table and Compare benchmark rows.

Benchmark **chart overlay** on the performance page uses separate rebasing logic in `finance/benchmarks.py` (display only). Metric Sheet stats use **simple daily index price returns** from cached `HistoricalPrice` rows (`asset_type=INDEX`).

Alignment rules (implemented):

- **Exact calendar date intersection** only.  
- Skip days where either side has `null` return.  
- **No forward-fill** of missing benchmark prices.

---

## Paired count

### Simple meaning
Number of days where both subject and benchmark have valid returns.

### Formula intuition
Count of aligned dates after intersection.

### What it means to the user
“How much data backed these ratios?” Low count → noisy beta/alpha.

### Why professionals care
Statistical significance; regulators care about data quality.

### When it is useful
Read before trusting IR or beta.

### When it is misleading
High count over a calm period can still miss regime change out-of-sample.

### Example interpretation
Paired count 42 on 3Y range with warning → metrics may be `null` or unstable; heed warning.

### How KPulla6 should display it
- **Label:** Paired Count  
- **Format:** Integer  
- **Compare:** neutral (no better/worse highlight)

### Implementation notes
- **Implemented:** `benchmark.paired_count`  
- Warning when `paired_count < 2`

### Related metrics
All benchmark metrics below

---

## Correlation

### Simple meaning
How closely daily moves track the benchmark (−1 to +1).

### Formula intuition
Pearson correlation of aligned daily return series.

### What it means to the user
~1 → moving together; ~0 → unrelated daily noise; negative → opposite days.

### Why professionals care
Diversification analysis; risk model inputs.

### When it is useful
Checking if a stock **is** its benchmark (high corr, beta ~1).

### When it is misleading
Short windows; correlation of returns ≠ correlation of levels.

### Example interpretation
Correlation 0.3, beta 0.5 → somewhat related but not a clone of the index.

### How KPulla6 should display it
- **Label:** Correlation  
- **Format:** Ratio  
- **Compare:** neutral highlight

### Implementation notes
- **Implemented:** `benchmark.metrics.correlation` — `comparison.correlation`

### Related metrics
Beta, R² (R² not exposed — **Planned**)

---

## Beta

### Simple meaning
Sensitivity of subject daily returns to benchmark daily returns.

### Formula intuition
\[
\beta = \frac{\mathrm{Cov}(r_s, r_b)}{\mathrm{Var}(r_b)}
\]
(sample covariance / variance on aligned days).

### What it means to the user
β ≈ 1 → market-like swing; β > 1 → amplified; β < 1 → damped.

### Why professionals care
CAPM, hedging, risk budgeting (“beta exposure”).

### When it is useful
Interpreting whether alpha came from stock selection vs market tide.

### When it is misleading
Unstable for low vol benchmarks or few pairs. Different benchmark → different beta.

### Example interpretation
Beta 1.2, benchmark up year → subject tended to move 20% more than index daily.

### How KPulla6 should display it
- **Label:** Beta  
- **Format:** Ratio (2 decimals)  
- **Compare:** neutral

### Implementation notes
- **Implemented:** `benchmark.metrics.beta` — `comparison.beta`

### Related metrics
Alpha, Treynor, active return

---

## Alpha (CAPM, annualized)

### Simple meaning
Average annualized return **above** what CAPM expected given beta and risk-free rate.

### Formula intuition
\[
\alpha_{\text{ann}} = \bar r_{s,\text{ann}} - \big(r_f + \beta(\bar r_{b,\text{ann}} - r_f)\big)
\]
with \(r_f = 0\) in current API.

### What it means to the user
“Did I beat the index **after** adjusting for market sensitivity?” — not the same as raw outperformance.

### Why professionals care
Active manager skill metric (debated, but ubiquitous).

### When it is useful
Long overlap with sensible benchmark (e.g. stock vs S&P).

### When it is misleading
Wrong benchmark inflates alpha. Zero risk-free assumption vs real T-bills.

### Example interpretation
Alpha +3% with beta 1 → outperformed CAPM expectation; raw active return may differ slightly.

### How KPulla6 should display it
- **Label:** Alpha  
- **Format:** Percent with sign  
- **Compare:** higher is better

### Implementation notes
- **Implemented:** `benchmark.metrics.alpha` — `comparison.alpha`  
- Annualized means: `mean(daily) × 252`

### Related metrics
Active return, information ratio, beta

---

## Active return (annualized)

### Simple meaning
Average annualized **raw** outperformance vs benchmark (not beta-adjusted).

### Formula intuition
Annualized mean of \((r_s - r_b)\) on aligned days.

### What it means to the user
“How much did I beat the index per year on average?” — simpler story than alpha.

### Why professionals care
Tracks “excess return” in allocator reports.

### When it is useful
Low-beta portfolios where beta-adjustment matters less to intuition.

### When it is misleading
Ignores whether excess came from higher risk (use IR).

### Example interpretation
Active return +2%, tracking error 4% → IR ≈ 0.5.

### How KPulla6 should display it
- **Label:** Active Return  
- **Format:** Percent with sign

### Implementation notes
- **Implemented:** `benchmark.metrics.active_return` — `comparison.active_return`

### Related metrics
Tracking error, information ratio, alpha

---

## Tracking error (annualized)

### Simple meaning
Volatility of **daily active return** (subject − benchmark), annualized.

### Formula intuition
Std dev of \((r_s - r_b)\) × \(\sqrt{252}\).

### What it means to the user
“How different daily path was from the index” — closet index funds → low TE.

### Why professionals care
Defines risk of active management; denominator of IR.

### When it is useful
Evaluating “closet indexer” vs true active bets.

### When it is misleading
High TE with negative active return → expensive divergence.

### Example interpretation
TE 1% → tight tracker; TE 8% → very different path.

### How KPulla6 should display it
- **Label:** Tracking Error  
- **Format:** Percent  
- **Compare:** lower is better

### Implementation notes
- **Implemented:** `benchmark.metrics.tracking_error` — `comparison.tracking_error`

### Related metrics
Information ratio, active return

---

## Information ratio

See [06 — Risk-adjusted return metrics](./06-risk-adjusted-return-metrics.md) (full template). Implemented in `benchmark.metrics.information_ratio`.

---

## Treynor ratio

See [06](./06-risk-adjusted-return-metrics.md). Implemented in `benchmark.metrics.treynor_ratio`.

---

## Benchmark selection (product behavior)

### Simple meaning
User picks an enabled index symbol (e.g. `^GSPC`) synced via `make sync-benchmarks`.

### What it means to the user
Wrong benchmark → wrong story. Value investors may still use a broad index as a **hurdle**, not a style match.

### Implementation notes
- Unknown/disabled benchmark → **422** on performance API  
- Missing prices → warnings; benchmark metrics `null`  
- Chart overlay and Metric Sheet share symbol but **different math paths**

---

## Planned / not yet implemented (relative performance)

| Metric | Status |
|--------|--------|
| Up/down capture ratios | **Planned** |
| R-squared | **Planned** |
| Rolling beta / alpha | **Planned** |
| Multi-benchmark fit | **Planned** |
| Custom blended benchmark | **Planned** |
