# Missing prices or NAVs

## Symptom: holdings show stale or missing values

Run:

```bash
make refresh
```

Or targeted sync:

```bash
make sync-prices
make sync-mutual-fund-navs
```

## Symptom: warnings on dashboard

Check `price_status`, `fx_status`, and API `warnings` — often missing FX or price for a symbol/date.

Diagnostics:

```bash
cd backend && python scripts/diagnose_nav_coverage.py
cd backend && python scripts/diagnose_fx_coverage.py
```

Concept: [Cached market data](../concepts/cached-market-data.md)

How-to: [Refresh market cache](../how-to/refresh-market-cache.md)
