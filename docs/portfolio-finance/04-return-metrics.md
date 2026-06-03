# Return metrics

Return metrics answer: **how much did value grow?** The answer depends on whether you measure **your cash experience**, **the path of the portfolio independent of deposit size**, or **calendar buckets**.

All Metric Sheet return fields are API **fractions**; the UI shows percents.

---

## Cumulative return (range, money-weighted)

### Simple meaning
Total growth of capital over the selected range, treating deposits and withdrawals as part of the economics — “if I put money in and took money out on these dates, what was my overall gain on contributed capital?”

### Formula intuition
At the window end:

\[
\text{cumulative} = \frac{V_{\text{end}} + W - C}{C} - 1
\]

where \(V\) is portfolio value, \(C\) cumulative contributions (buys), \(W\) cumulative withdrawals (sells), in display currency with known flows.

### What it means to the user
“This is how my **account** did over 1Y / 3Y / ALL, in line with the performance chart’s cumulative return line.”

### Why professionals care
Client reporting and “money-weighted” performance (MWR) reflect **investor timing** of flows.

### When it is useful
Single headline for a range; comparing to your own contribution history.

### When it is misleading
Heavy deposits late in the range can **dilute** the percentage vs an early lump sum. Not comparable to fund factsheets that quote **time-weighted** returns.

### Example interpretation
Cumulative return +12% on 1Y with steady contributions → account grew 12% on net contributed capital over that year (not necessarily 12% on Jan 1 balance).

### How KPulla6 should display it
- **Label:** Cumulative Return  
- **Format:** Percent with sign; green/red tone on tables where applicable  
- **Location:** Metric Sheet summary cards; Compare table (higher is better highlight)

### Implementation notes
- **Implemented:** `metrics.return.cumulative_return`  
- `analytics/services._economic_cumulative_return_fraction` — same as `GET /portfolio/performance?metric=cumulative_return` terminal point  
- `null` when contributions ≤ 0 or flows unknown on terminal date  

### Related metrics
CAGR, TWROR, XIRR, Calendar-Year Return

---

## CAGR (compound annual growth rate)

### Simple meaning
The constant yearly rate that would grow contributed capital into the same terminal outcome over the **calendar span** of the range.

### Formula intuition
If total money-weighted return over \(d\) calendar days is \(R\):

\[
\text{CAGR} = (1 + R)^{365/d} - 1
\]

Uses `(end_date - start_date).days`, not count of trading days.

### What it means to the user
“Annualized version of my range cumulative return” — handy for comparing 7D vs 5Y windows.

### Why professionals care
Standardizes different horizons for allocator review.

### When it is useful
Comparing ranges of different lengths; talking to advisors who think in “% per year.”

### When it is misleading
Very short ranges (7D annualized) explode or look noisy. Not the same as **fund CAGR on TWR** if flows are large.

### Example interpretation
+8% cumulative over exactly 365 days → CAGR ≈ +8%. Same cumulative over 180 days → CAGR much higher.

### How KPulla6 should display it
- **Label:** CAGR  
- **Format:** Percent  
- **Summary cards** and risk/return tables

### Implementation notes
- **Implemented:** `metrics.return.cagr` via `cagr_from_total_return` on economic cumulative return  
- **Not** compounded from TWROR daily returns (unlike Calmar’s internal CAGR helper — see [06](./06-risk-adjusted-return-metrics.md))

### Related metrics
Cumulative return, TWROR, Calmar

---

## TWROR (time-weighted return on residual, terminal)

### Simple meaning
Chain-linked daily returns that remove the impact of **when** you added or withdrew cash — closer to “how did the **portfolio mix** perform day by day?”

### Formula intuition
Each day with known prior value \(V_{t-1}\) and external flow \(F_t\):

\[
r_t = \frac{V_t - F_t - V_{t-1}}{V_{t-1}}
\]

Compound \((1+r_t)\) across the range; Metric Sheet shows **terminal** cumulative TWROR as a fraction (chart uses percent points).

### What it means to the user
“If I had not timed my deposits, how would the path have looked?” Closer to **manager skill** than XIRR.

### Why professionals care
GIPS and fund reporting use time-weighted returns for comparability across investors with different cash flows.

### When it is useful
Judging strategy vs luck in **timing contributions**; aligning with index path metrics (also flow-adjusted on subject side).

### When it is misleading
Sparse or missing daily values break the chain (`null` days). Asset-level series with few price points can be choppy.

### Example interpretation
TWROR +15% but cumulative return +5% → large deposits before a rally may have hurt **your** dollar-weighted outcome while the **path** was strong.

### How KPulla6 should display it
- **Label:** TWROR  
- **Helper (optional):** “Cash-flow-adjusted chain-linked return for the selected range.”  
- Performance chart metric toggle **TWROR** for full series

### Implementation notes
- **Implemented:** `metrics.return.twror`, `finance/twror.compute_twror_series`  
- Daily inputs for risk/drawdown also come from `daily_returns_from_values` (same flow logic)

### Related metrics
Cumulative return, XIRR, daily returns (internal)

---

## XIRR (extended internal rate of return)

### Simple meaning
Annualized IRR that makes the NPV of all **cash flows** (buys negative, sells positive, terminal value positive) equal to zero.

### Formula intuition
Find rate \(r\) such that \(\sum CF_i / (1+r)^{t_i} = 0\) with actual transaction dates (fees included in stock flows; MF uses investment/paid value rules).

### What it means to the user
“Since I started, what discount rate explains my deposits, withdrawals, and today’s value?” — classic **personal portfolio** metric.

### Why professionals care
Private wealth and PE/VC use IRR for irregular flows; differs from public-fund TWR factsheets.

### When it is useful
Full-life performance with irregular contributions; comparing to a hurdle rate you care about.

### When it is misleading
Short history or tiny early flows → unstable IRR. **Not sliced by Metric Sheet range** — always full scope.

### Example interpretation
XIRR 11% with `xirr_scope: full_scope` while 1Y CAGR is −3% → long-term record is good but the selected year was weak.

### How KPulla6 should display it
- **Label:** XIRR  
- **Note:** “XIRR is full-scope; other Metric Sheet values follow the selected range.” (implemented Phase 8E)  
- **Format:** Percent

### Implementation notes
- **Implemented:** `metrics.return.xirr`, `xirr_scope: "full_scope"`  
- `finance/xirr.calculate_xirr` / `compute_scope_xirr`  
- Summary card also shows portfolio XIRR

### Related metrics
Cumulative return (range), CAGR

---

## Average daily return

### Simple meaning
Arithmetic mean of valid daily **fractional** returns in the range.

### Formula intuition
\(\bar r = \frac{1}{n}\sum r_t\) — not compounded.

### What it means to the user
Typical **day** in the window (can be tiny, e.g. 0.04%).

### Why professionals care
Building block for volatility and Sharpe numerators.

### When it is useful
Quick sense of drift; diagnosing win rate vs average size of wins.

### When it is misleading
Not annualized; not investable as a forecast.

### Example interpretation
Win rate 55% but average daily return near 0 → many small wins/losses.

### How KPulla6 should display it
- **Label:** Average Daily Return  
- **Table:** Period group; percent with sign

### Implementation notes
- **Implemented:** `metrics.periods.average_daily_return` — `performance_stats.average_return`

### Related metrics
Win rate, volatility, Sharpe

---

## Best day / Worst day

### Simple meaning
Largest single-day gain and loss in the range (fractional).

### Formula intuition
\(\max r_t\), \(\min r_t\) over valid daily returns.

### What it means to the user
Tail **day** moves — stress-test emotions and liquidity.

### Why professionals care
Fat-tail diagnostics; risk committees watch worst-day vs VaR (VaR not in app).

### When it is useful
Volatile assets (single stock compare); crisis windows.

### When it is misleading
Corporate actions with **wrong** (non split-adjusted) prices create fake “worst days” — heed split warnings.

### Example interpretation
Worst day −8% with max drawdown −12% → most pain was one gap day, not a long slide.

### How KPulla6 should display it
- **Labels:** Best Day, Worst Day  
- **Tone:** gain/loss coloring

### Implementation notes
- **Implemented:** `metrics.periods.best_day`, `worst_day`

### Related metrics
Max drawdown, volatility

---

## Win rate

### Simple meaning
Share of days with **positive** return (zero counts as not a win).

### Formula intuition
\(\#\{r_t > 0\} / n\)

### What it means to the user
“How often am I green day-to-day?” — not the same as being profitable over the range.

### Why professionals care
Hit ratio in trading; less central for long-only investors.

### When it is useful
Compare two assets in Compare view alongside average daily return.

### When it is misleading
Many small up days, one huge down day → high win rate, bad cumulative return.

### Example interpretation
Win rate 60% but negative CAGR → losses were larger than wins.

### How KPulla6 should display it
- **Label:** Win Rate  
- **Format:** Percent (fraction × 100)

### Implementation notes
- **Implemented:** `metrics.periods.win_rate`

### Related metrics
Average daily return, volatility

---

## Monthly periodic return

### Simple meaning
Compounded daily returns within each calendar month in the selected range.

### Formula intuition
\(\prod_{t \in \text{month}} (1+r_t) - 1\)

### What it means to the user
Building blocks for the **monthly heatmap** — seasonality and streaks.

### Why professionals care
Risk reporting by month; investor letters.

### When it is useful
Spotting consistent vs lumpy performance.

### When it is misleading
Partial months at range edges only include days inside the range.

### Example interpretation
March +4%, April −2% → two-month story inside 1Y range.

### How KPulla6 should display it
- **Monthly returns grid** (year × month) with five-band heatmap  
- Fallback table if monthly empty

### Implementation notes
- **Implemented:** `periodic_returns.monthly` — `resample_monthly_returns`  
- Skips `null` daily returns

### Related metrics
Calendar-Year Return, TWROR daily chain

---

## Calendar-Year Return (yearly periodic)

### Simple meaning
Cash-flow-adjusted return for each **calendar year** in the range, compounded from the same daily TWROR-style returns used for risk metrics.

### Formula intuition
Compound daily \(r_t\) for all dates in Jan 1–Dec 31 of that year (within range).

### What it means to the user
“How did each calendar year finish?” — **not** simple Jan 1 vs Dec 31 account balance change.

### Why professionals care
Tax years, annual reviews, allocator “vintage” thinking.

### When it is useful
Bar chart **Calendar-Year Return** on Dashboard / Asset Detail.

### When it is misleading
First/last year may be partial if range clips them. Differs from headline **money-weighted** cumulative return for the same year if flows were large.

### Example interpretation
2024 Calendar-Year Return +10% but cumulative 1Y +6% → flow timing vs calendar bucket definitions differ.

### How KPulla6 should display it
- **Title:** Calendar-Year Return  
- **Helper:** “Cash-flow adjusted return using daily TWROR.”  
- Compare yearly table column: **Year Return**

### Implementation notes
- **Implemented:** `periodic_returns.yearly` — `resample_yearly_returns`  
- Chart: `MetricSheetYearlyReturnChart`

### Related metrics
Cumulative return, monthly periodic, TWROR

---

## Normalized cumulative return (Compare)

### Simple meaning
Each subject’s compounded return on the **common date window**, rebased to 0% on the first shared date.

### Formula intuition
Start at 0 on first overlap date; compound daily returns from second date forward (per subject).

### What it means to the user
Apples-to-apples **path** chart for two holdings.

### Why professionals care
Security selection comparisons in research notes.

### When it is useful
Compare page line chart only.

### When it is misleading
Short overlap → unstable lines; global warning when `common_point_count < 2`.

### Example interpretation
Two lines diverge after shared start → relative path difference, not position sizing.

### How KPulla6 should display it
- **CompareNormalizedChart** — percent axis from API `normalized_series`

### Implementation notes
- **Implemented:** `comparison.normalized_cumulative_return_series` on compare API  
- **Not** a Metric Sheet scalar

### Related metrics
TWROR, cumulative return (per subject on same window)

---

## Planned / not yet implemented (return family)

| Metric | Note |
|--------|------|
| Rolling 12-month return | Would need rolling window API |
| Money-weighted monthly return | Calendar-year uses TWROR daily, not MWR |
| Tax-adjusted return | No tax lot engine in analytics |
| Dividend-adjusted total return index | Stock prices use cached Adj Close; dividends not modeled separately |

See [12 — Implementation notes](./12-metric-implementation-notes.md).
