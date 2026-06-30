# Investigate dashboard performance

## Baseline

Read paths were profiled on real Postgres dev data (STAB-5A/5B). Critical parallel loads target **&lt; 1 s**.

## Diagnostics (read-only)

From `backend/` with venv active:

```bash
python scripts/diagnose_summary_vs_performance.py
python scripts/diagnose_fx_coverage.py
python scripts/diagnose_nav_coverage.py
```

## Docs

- [Dashboard read paths](../performance/dashboard-read-paths.md)
- [Read baseline](../performance/dashboard-read-baseline.md)

## When to optimize

Deferred until thresholds are exceeded or data volume grows materially. Do not add live provider calls to read paths as a “fix”.

Troubleshooting: [Dashboard is slow](../troubleshooting/dashboard-slow.md)
