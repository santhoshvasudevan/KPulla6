# Risk-adjusted return metrics

These metrics divide **reward** by **risk** (or drawdown) to answer: “Was the return worth the ride?”

KPulla6 MVP uses:

- **Numerator:** annualized arithmetic mean of daily excess returns over risk-free rate.  
- **Risk-free rate:** **0%** (not exposed in API/settings).  
- **Denominator:** annualized volatility, downside deviation, or |max drawdown| depending on metric.

---

## Sharpe ratio

### Simple meaning
Excess return per unit of total volatility.

### Formula intuition
\[
\text{Sharpe} \approx \frac{\bar r - r_f}{\sigma_{\text{ann}}}
\]
where \(\bar r\) is mean daily return annualized (\(\times 252\)), \(r_f\) is 0 in production API.

### What it means to the user
Higher Sharpe → more return per unit of **overall** bumpiness.

### Why professionals care
Universal fund ranking metric; allocator screens often set minimum Sharpe.

### When it is useful
Comparing strategies on similar horizons with enough daily data.

### When it is misleading
Non-normal returns (options, crypto spikes). Near-zero vol → `null`. Ignores **drawdown depth** (use Sortino/Calmar too).

### Example interpretation
Sharpe 0.8 vs benchmark portfolio Sharpe 0.5 on Compare → better risk efficiency on overlap window (not proof of future edge).

### How KPulla6 should display it
- **Label:** Sharpe Ratio  
- **Format:** Ratio (2–3 decimals)  
- **Compare:** higher is better

### Implementation notes
- **Implemented:** `metrics.risk.sharpe_ratio` — `risk_metrics.sharpe_ratio`  
- `null` when vol is `null` or zero  
- **Planned:** user-configurable risk-free rate in settings/API

### Related metrics
Sortino, volatility, information ratio, Treynor

---

## Sortino ratio

### Simple meaning
Excess return per unit of **downside** volatility.

### Formula intuition
\[
\text{Sortino} \approx \frac{\bar r - r_f}{\text{downside deviation}_{\text{ann}}}
\]

### What it means to the user
Like Sharpe, but does not treat upside swings as “risk.”

### Why professionals care
Preferred when upside volatility is desirable (equity compounding).

### When it is useful
Strategies with positive skew; comparing to Sharpe on same series.

### When it is misleading
Few losing days → downside deviation `null` → Sortino `null`. Can look infinite-quality on short windows with one tiny down day.

### Example interpretation
Sharpe 0.6, Sortino 1.1 → drawdown days were mild relative to up days.

### How KPulla6 should display it
- **Label:** Sortino Ratio  
- **Format:** Ratio  
- **Compare:** higher is better

### Implementation notes
- **Implemented:** `metrics.risk.sortino_ratio` — `risk_metrics.sortino_ratio`  
- `null` when downside deviation is `null` or zero

### Related metrics
Sharpe, downside deviation, max drawdown

---

## Calmar ratio

### Simple meaning
Annualized growth rate divided by the depth of the worst peak-to-trough loss.

### Formula intuition
\[
\text{Calmar} = \frac{\text{CAGR}_{\text{daily}}}{|\text{max drawdown}|}
\]
where CAGR here is from **compounded daily returns** over the range (`performance_stats.cagr`), **not** the headline money-weighted CAGR on summary cards.

### What it means to the user
“Growth per unit of worst pain” — popular in hedge fund letters.

### Why professionals care
Highlights **path risk** allocators fear (deep drawdowns).

### When it is useful
Longer ranges where max drawdown is meaningful.

### When it is misleading
No drawdown → denominator 0 → `null`. Short range with tiny drawdown can inflate Calmar. **Differs from headline CAGR** — see implementation notes.

### Example interpretation
Calmar 1.5 with max drawdown −10% → daily-path CAGR roughly 15% annualized equivalent (check actual CAGR fields separately).

### How KPulla6 should display it
- **Label:** Calmar Ratio  
- **Format:** Ratio  
- **Compare:** higher is better

### Implementation notes
- **Implemented:** `metrics.drawdown.calmar_ratio` — `drawdowns.calmar_ratio`  
- Uses `cagr(daily_fracs, start, end)` internally, not `cagr_from_total_return`  
- Document this duality in [12](./12-metric-implementation-notes.md)

### Related metrics
Max drawdown, CAGR, Sharpe

---

## Information ratio (benchmark-relative)

### Simple meaning
Active return per unit of tracking error vs a benchmark.

### Formula intuition
\[
IR = \frac{\text{active return}_{\text{ann}}}{\text{tracking error}_{\text{ann}}}
\]
Active return = annualized mean of \((r_{\text{subject}} - r_{\text{bench}})\) on aligned days.

### What it means to the user
“Did I earn enough **extra** return for the volatility of being different from the index?”

### Why professionals care
Core metric for active equity and long-short managers.

### When it is useful
When a benchmark is selected and `paired_count` is adequate.

### When it is misleading
Wrong benchmark (bond fund vs S&P). Low TE can inflate IR on tiny active bets.

### Example interpretation
IR 0.4, alpha +2% → consistent small outperformance per unit of tracking risk.

### How KPulla6 should display it
- **Label:** Information Ratio  
- **Benchmark table** and Compare (higher is better)

### Implementation notes
- **Implemented:** `benchmark.metrics.information_ratio` — `comparison.information_ratio`  
- Requires benchmark prices in DB and ≥2 aligned days

### Related metrics
Active return, tracking error, alpha, Sharpe

---

## Treynor ratio (benchmark-relative)

### Simple meaning
Excess return per unit of **market risk** (beta).

### Formula intuition
\[
\text{Treynor} \approx \frac{\text{annualized excess return on subject}}{\beta}
\]

### What it means to the user
Reward per unit of systematic risk — useful when beta ≠ 1.

### Why professionals care
Compares diversified equity portfolios on a beta-adjusted basis.

### When it is useful
High-beta names vs low-beta names with similar raw returns.

### When it is misleading
Beta ≈ 0 or unstable → `null`. Negative beta breaks simple interpretation.

### Example interpretation
High return, beta 1.5, moderate Treynor → much return came from market exposure.

### How KPulla6 should display it
- **Label:** Treynor Ratio  
- **Benchmark table** (implemented; not in Compare highlight map as “higher is better” — treated neutral in compare ranking for beta-related context)

### Implementation notes
- **Implemented:** `benchmark.metrics.treynor_ratio` — `comparison.treynor_ratio`  
- Risk-free 0% in API

### Related metrics
Beta, alpha, Sharpe

---

## Planned / not yet implemented (risk-adjusted family)

| Metric | Status |
|--------|--------|
| Omega ratio | **Planned** |
| Sterling / Burke ratio | **Planned** |
| Modigliani–Modigliani (M²) | **Planned** |
| Sharpe with configurable \(r_f\) | **Planned** (function param exists) |
