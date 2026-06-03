# Drawdown and downside risk

**Drawdown** measures pain from a **peak**: how far wealth fell before recovering. It is the metric many investors feel most acutely — institutions monitor it for risk limits and client retention.

KPulla6 builds drawdowns from the same **daily return series** as volatility (wealth index starts at 1, compounds \((1+r_t)\)).

---

## Max drawdown

### Simple meaning
The largest peak-to-trough **percentage** decline in the range.

### Formula intuition
Track running peak wealth \(P_t\). Drawdown at \(t\) is \(W_t/P_t - 1\). Max drawdown is the minimum (most negative) value.

### What it means to the user
“Worst loss from a prior high” during the window — e.g. −18% means you were 18% below a prior peak.

### Why professionals care
Risk limits (“max 10% drawdown”), fund redemption triggers, psychological breaking points.

### When it is useful
Crisis periods, leverage strategies, single-stock holdings.

### When it is misleading
Unrecovered drawdown at range end may grow if you extend the window. Split/price errors create **fake** drawdowns (warnings).

### Example interpretation
Max drawdown −25%, cumulative return +5% → you recovered and finished up, but the path was painful.

### How KPulla6 should display it
- **Label:** Max Drawdown  
- **Format:** Percent (negative)  
- **Tone:** less negative is better on Compare  
- **Chart:** drawdown area series

### Implementation notes
- **Implemented:** `metrics.drawdown.max_drawdown` — `drawdowns.max_drawdown`  
- Fraction (UI × 100)

### Related metrics
Calmar, longest drawdown, worst episodes

---

## Longest drawdown (days)

### Simple meaning
Longest time spent below a prior peak before making a **new** high.

### Formula intuition
When drawdown < 0, count inclusive **calendar days** from first day below peak through last day still below that peak before recovery. Without dates, counts consecutive return periods.

### What it means to the user
“How long was I underwater?” — duration risk, not depth.

### Why professionals care
Allocator patience; hedge funds report “time to recover.”

### When it is useful
Recovery-heavy narratives; MF with stale NAV may distort calendar length.

### When it is misleading
Still underwater at range end → episode counts through end but recovery incomplete (see worst periods table).

### Example interpretation
Longest drawdown 90 days, max drawdown −8% → shallow but long grind vs sharp crash.

### How KPulla6 should display it
- **Label:** Longest Drawdown  
- **Format:** Integer days + “days” suffix

### Implementation notes
- **Implemented:** `metrics.drawdown.longest_drawdown_days` — `drawdowns.longest_drawdown_days`

### Related metrics
Worst drawdown periods (`days_to_recovery`), max drawdown

---

## Drawdown series

### Simple meaning
Daily running drawdown fraction for charting.

### Formula intuition
Same as max drawdown logic, emitted per date with valid return.

### What it means to the user
Visual **underwater** curve; shaded regions for worst episodes.

### Why professionals care
Risk committees review paths, not scalars.

### When it is useful
Dashboard / Asset Detail drawdown chart (Phase 13C).

### When it is misleading
Sparse dates → jagged series. `null` return days emit `null` drawdown points.

### Example interpretation
Shaded rank-1 region matches deepest table row.

### How KPulla6 should display it
- **Chart:** `MetricSheetDrawdownChart` from `drawdown_series[]` (`date`, `drawdown` ≤ 0)  
- Unrecovered episodes shade to series end

### Implementation notes
- **Implemented:** top-level `drawdown_series` on portfolio/asset/compare APIs  
- `drawdowns.drawdown_series`

### Related metrics
`drawdown_periods.worst`, max drawdown

---

## Worst drawdown periods (episodes)

### Simple meaning
Ranked list of distinct drawdown episodes: peak date, trough date, optional recovery, depth, durations.

### Formula intuition
Walk wealth path; on new peak close prior episode; track trough; recovery when wealth ≥ episode peak.

### What it means to the user
“Show me the three worst crashes and whether I recovered.”

### Why professionals care
Explains **narrative** risk beyond a single max number.

### When it is useful
Table below drawdown chart; Compare shows per-subject tables (no cross-subject ranking).

### When it is misleading
Requires dated returns; <2 valid points → empty list. Rank 1 = deepest `drawdown` fraction.

### Example interpretation
Episode rank 1: −18%, recovered in 69 days → V-shaped. Rank 2 unrecovered → still below peak.

### How KPulla6 should display it
- **Table columns:** rank, start (peak), trough, recovery, drawdown %, days to trough/recovery, status  
- **Compare:** `CompareDrawdownPeriodsSection` per subject

### Implementation notes
- **Implemented:** `drawdown_periods.worst` (up to 10) — `worst_drawdown_periods`  
- Fields: `rank`, `start_date`, `trough_date`, `recovery_date`, `drawdown`, `days_to_trough`, `days_to_recovery`, `recovered`

### Related metrics
Max drawdown, drawdown series, Calmar

---

## Downside deviation (cross-reference)

Treated as a **risk** metric but conceptually “downside risk.” See [05 — Risk metrics](./05-risk-metrics.md).

---

## Planned / not yet implemented (drawdown family)

| Metric | Status |
|--------|--------|
| Average drawdown | **Planned** |
| Ulcer index | **Planned** |
| Pain index | **Planned** |
| Drawdown at risk (95%) | **Planned** |
| Underwater chart vs benchmark | **Planned** |
