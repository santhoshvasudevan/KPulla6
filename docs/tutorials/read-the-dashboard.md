# Read the dashboard

Interpret headline KPIs, the performance chart, and Metric Sheet preview.

## Prerequisites

```bash
make dev
make refresh
```

Sign in: [Login and first use](../getting-started/login-and-first-use.md)

## Steps

### 1. Open the dashboard

http://127.0.0.1:5173/

<div class="screenshot-placeholder" markdown="1">
!!! warning "Screenshot pending — dashboard overview"
    **Save as:** `docs/assets/images/dashboard-overview.png`  
    **Capture when:** logged in at `/` with KPI cards, allocation, and performance chart visible.  
    **Notice:** Portfolio scope and display currency in the sticky header.  
    **Workflow:** [How to capture screenshots](../maintenance/docs-visual-backlog.md#how-to-capture-screenshots)  
    **Troubleshooting:** [Missing prices or NAVs](../troubleshooting/missing-prices-navs.md) if KPIs look empty.
</div>

### 2. Set scope and currency

Use the header **Portfolio view** and **Display currency** selectors.

**Expected:** KPIs and chart update for the selected scope.

### 3. Read headline KPIs

Powered by `GET /api/v1/portfolio/summary?include_timeseries=false`:

| KPI | Meaning (short) |
|-----|-----------------|
| Total value | Holdings + cash in display currency |
| Invested | FIFO cost basis |
| P/L | Realized + unrealized |
| XIRR | Money-weighted return (when computable) |

API detail: [Analytics API](../reference/api-analytics.md)

### 4. Use the performance chart

Powered by `GET /api/v1/portfolio/performance`:

- **Metrics:** Value, Cumulative return, TWROR
- **Range:** 7D, 1M, 1Y, ALL, etc.
- **Benchmark:** optional overlay (cached index prices)

### 5. Scroll to Metric Sheet

Portfolio quantitative statistics for the selected range.

!!! note "Screenshot pending — Metric Sheet"
    **File:** `metric-sheet-preview.png` — out of scope for this pass. See [visual backlog](../maintenance/docs-visual-backlog.md).

Concept: [Metric Sheet](../concepts/metric-sheet.md)

## You are done when…

- [ ] KPIs show numbers (not all zeros) after `make refresh`
- [ ] Performance chart renders for at least one range
- [ ] No blocking warning banner (or you know why it appears)

## Troubleshooting

| Issue | Page |
|-------|------|
| Missing/stale values | [Missing prices or NAVs](../troubleshooting/missing-prices-navs.md) |
| Slow load | [Dashboard is slow](../troubleshooting/dashboard-slow.md) |

## Next

- [Portfolio performance](../concepts/portfolio-performance.md)

## Related

- [Analytics API](../reference/api-analytics.md) · [Investigate dashboard performance](../how-to/investigate-dashboard-performance.md)
