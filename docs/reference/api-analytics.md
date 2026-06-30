# API — analytics

Portfolio summary, performance series, and Metric Sheet endpoints. Deep spec: [api-design.md](../api-design.md) § Phase 9–10 and analytics.

**Base URL:** `http://127.0.0.1:8000/api/v1` · **Auth:** Session — [API authentication](api-auth.md)

!!! note "Screenshot placeholder"
    **Shows:** Dashboard KPIs + performance chart.  
    **Backlog:** [dashboard-overview.png](../maintenance/docs-visual-backlog.md)

!!! note "Screenshot placeholder"
    **Shows:** Metric Sheet quantitative statistics panel.  
    **Backlog:** [metric-sheet-preview.png](../maintenance/docs-visual-backlog.md)

---

## `GET /portfolio/summary`

| | |
|---|---|
| **Auth** | Session |
| **Purpose** | Dashboard headline KPIs |

### Query parameters

| Param | Default | Notes |
|-------|---------|-------|
| `include_timeseries` | `true` | `false` skips series build |
| `portfolio_scope` / `portfolio_id` | all | Scope rules |
| `display_currency` | settings | `EUR`, `USD`, `INR`, … |

### Example request

```bash
curl -s -b cookies.txt \
  "http://127.0.0.1:8000/api/v1/portfolio/summary?include_timeseries=false&portfolio_scope=all"
```

### Example response shape (200)

```json
{
  "total_invested": 50000.0,
  "current_value": 52000.0,
  "realized_pl": 1000.0,
  "unrealized_pl": 1000.0,
  "total_pl": 2000.0,
  "xirr": 0.12,
  "display_currency": "EUR",
  "warnings": []
}
```

Uses **cached** prices and FX only — no live market calls on GET.

---

## `GET /portfolio/performance`

| | |
|---|---|
| **Auth** | Session |
| **Purpose** | Performance chart series |

### Query parameters

| Param | Default | Options |
|-------|---------|---------|
| `metric` | `value` | `value`, `cumulative_return`, `twror` |
| `range` | `1Y` | `7D`, `30D`, `YTD`, `1Y`, `3Y`, `5Y`, `ALL` |
| `benchmark` | — | Index symbol (return metrics only) |
| `portfolio_scope` / `portfolio_id` | all | Scope |
| `display_currency` | settings | FX display |

### Example request

```bash
curl -s -b cookies.txt \
  "http://127.0.0.1:8000/api/v1/portfolio/performance?metric=twror&range=1Y"
```

**Expected:** JSON array of `{ "date", "value", "metric", "currency" }` points (or wrapped object with `warnings`).

---

## `GET /analytics/performance-metrics`

Portfolio **Metric Sheet** — quantitative statistics for the selected range.

### Common query parameters

`portfolio_scope`, `portfolio_id`, `range`, `display_currency` — see [api-design.md](../api-design.md).

---

## Related analytics endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/analytics/assets/{asset_symbol}/performance-metrics` | Asset Metric Sheet |
| `GET` | `/analytics/compare` | Two-asset compare |
| `GET` | `/portfolio/holdings` | Holdings + allocation |

## Common errors

| Status | When |
|--------|------|
| `400` | Invalid `metric`, `range`, or currency |
| `404` | Unknown portfolio |
| `422` | Invalid benchmark or scope combination |

Tutorial: [Read the dashboard](../tutorials/read-the-dashboard.md) · Concept: [Metric Sheet](../concepts/metric-sheet.md)

## Next

- [Reference overview](index.md)

## Related

- [Portfolio performance](../concepts/portfolio-performance.md) · [Cached market data](../concepts/cached-market-data.md)
