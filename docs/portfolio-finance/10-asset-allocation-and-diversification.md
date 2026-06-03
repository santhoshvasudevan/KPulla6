# Asset allocation and diversification

**Allocation** is how capital is split across holdings. **Diversification** is whether those pieces move independently enough to reduce portfolio risk.

KPulla6 today shows **simple allocation**; advanced diversification analytics are **planned**.

## Implemented: holdings allocation (display)

### Simple meaning
Each holding’s share of total `current_value` in the scoped portfolio view.

### Formula intuition
\[
\text{weight}_i = \frac{\text{current\_value}_i}{\sum_j \text{current\_value}_j}
\]

Computed in the frontend for chart labels/tooltips (sum of backend values) — **display only**, not persisted analytics.

### What it means to the user
“How concentrated is my book?” — one glance at the Assets allocation chart.

### Why professionals care
Policy ranges (“max 5% per name”), risk concentration limits.

### When it is useful
Spotting single-name or single-MF dominance.

### When it is misleading
Ignores **correlation** (two stocks can both be 10% but move together). Ignores cash not modeled as a holding if fully invested.

### Example interpretation
Top holding 45% → concentration risk; read with beta and drawdown, not weight alone.

### How KPulla6 should display it
- **Assets page** allocation chart (Recharts)  
- Tooltip may show percent from summed `current_value`  
- MF: scheme name / folio labels

### Implementation notes
- **Implemented:** holdings API `current_value`; chart is display math in React  
- MF `primary_asset_class` on rows — **not** yet rolled into allocation-by-asset-class chart (**Planned**)

### Related metrics
Beta, correlation (vs benchmark — not across holdings)

---

## Mutual fund asset class (metadata)

### Simple meaning
Coarse bucket: equity, debt, hybrid, etc., inferred from scheme metadata.

### Status
- **Implemented** on holdings/detail: `primary_asset_class`, `classification_source`  
- **Planned / not yet implemented:** allocation pie by asset class, hybrid breakdown, tax category

See [mutual-funds.md](../mutual-funds.md) MF-7.

---

## Diversification concepts (mostly planned)

| Concept | Institution view | KPulla6 status |
|---------|------------------|----------------|
| Correlation across holdings | Risk model | **Planned** — only benchmark correlation implemented |
| Effective number of bets | \(1/\sum w_i^2\) | **Planned** |
| Sector / geography weights | Factor exposure | **Planned** |
| Currency diversification | FX series | Partial — multi-currency with conversion warnings |
| Alternatives / low correlation | Allocator mix | User-defined via symbols only |

### How to approximate today

1. **Benchmark correlation / beta** on portfolio Metric Sheet — market diversification proxy, not internal.  
2. **Compare** two holdings on common dates — pairwise path similarity.  
3. **Allocation chart** — concentration, not covariance.

---

## Institutional allocation policy (reference)

Typical policy portfolio might target 60/40 equity/bond with ±5% bands. KPulla6 does **not** store policy targets — document externally and compare manually to allocation chart.

**Rebalancing** appears only when you trade; no drift alerts (**Planned**).

---

## Value-investor allocation lens

Concentration in **best ideas** is a feature, not a bug — but size should match **conviction and liquidity**. Use:

- Allocation % for size discipline  
- Max drawdown and longest drawdown for **emotional** and **permanent capital** risk  
- Full-scope XIRR for long-hold outcomes

Avoid inferring “diversification score” from the app until correlation matrix exists.

---

## Planned / not yet implemented (allocation module)

| Feature | Status |
|---------|--------|
| Asset-class allocation chart | **Planned** |
| Top-N concentration % (HHI) | **Planned** |
| Holdings correlation matrix | **Planned** |
| Geographic / sector breakdown | **Planned** |
| Policy band vs actual | **Planned** |

## Related docs

- [09 — Portfolio construction](./09-portfolio-construction.md)
- [08 — Benchmark metrics](./08-benchmark-and-relative-performance.md)
- [11 — Behavioral interpretation](./11-behavioral-interpretation-for-users.md)
