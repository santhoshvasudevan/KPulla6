# Refresh market data

Goal: populate the PostgreSQL cache so dashboard and holdings show current values.

## One command (recommended)

```bash
make refresh
```

Syncs stock prices, benchmark indices, FX rates, and mutual fund NAVs.

## Granular commands

```bash
make sync-prices
make sync-benchmarks
make sync-fx
make sync-mutual-fund-navs
```

## HTTP alternatives

- `POST /api/v1/prices/refresh` — stocks
- `POST /api/v1/nav/refresh` — MF NAVs
- `POST /api/v1/portfolio/force-sync` — combined

## Important

Read APIs (dashboard, holdings, summary) use **cached DB data only** — they do not call Yahoo or AMFI during page load.

## Next

- [Read the dashboard](read-the-dashboard.md)
- [Cached market data](../concepts/cached-market-data.md)

How-to detail: [Refresh prices, FX, benchmarks, and NAVs](../how-to/refresh-market-cache.md)
