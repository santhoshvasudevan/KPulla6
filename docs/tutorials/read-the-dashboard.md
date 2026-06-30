# Read the dashboard

Goal: interpret headline metrics and the performance chart.

## Open the dashboard

http://127.0.0.1:5173/ (after `make dev` and login)

## Headline KPIs

From `GET /api/v1/portfolio/summary?include_timeseries=false`:

- **Total value**, **Invested**, **P/L**, **XIRR**

Values respect **portfolio scope** and **display currency** from the header.

## Performance chart

From `GET /api/v1/portfolio/performance`:

- Metrics: **Value**, **Cumulative return**, **TWROR**
- Range pills: 7D, 1M, 1Y, ALL, etc.
- Optional benchmark overlay (cached index prices)

## Metric Sheet preview

Lower on the dashboard — portfolio Quantitative Statistics for the selected range. Full detail: [Metric Sheet](../concepts/metric-sheet.md).

## Warnings

Watch for `price_status`, `fx_status`, and banner warnings when cache or FX is incomplete. Fix with `make refresh` or scope/currency adjustments.

## Next

- [Portfolio performance concepts](../concepts/portfolio-performance.md)
- [Investigate dashboard performance](../how-to/investigate-dashboard-performance.md)
