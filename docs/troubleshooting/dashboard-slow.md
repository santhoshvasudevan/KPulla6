# Dashboard is slow

## First checks

1. Run `make refresh` if sync is stale (unrelated but often confused with slowness)
2. Confirm Postgres is running (`make db`)
3. Check parallel API calls in browser network tab

## Diagnostics

```bash
cd backend && python scripts/diagnose_summary_vs_performance.py
```

## Baseline

Read paths target **&lt; 1 s** on dev hardware — see [dashboard read baseline](../performance/dashboard-read-baseline.md).

How-to: [Investigate dashboard performance](../how-to/investigate-dashboard-performance.md)

**Do not** add live yfinance/AMFI calls to GET handlers as a workaround.
