# Refresh market data

Fill the PostgreSQL cache so the dashboard and holdings show current values.

## Before you start

The app must be running (or at least Postgres + backend for API sync):

```bash
make dev
```

Dashboard **does not** fetch live prices on page load — it reads the cache.

## Recommended: sync everything

```bash
make refresh
```

**Expected:**

```text
==> Syncing valuation cache: stock prices, benchmark indices, FX rates, mutual fund NAVs
...
==> Refresh complete (stocks, benchmarks, FX, mutual fund NAVs)
```

**Then open:** http://127.0.0.1:5173 — holdings and dashboard should show updated values (where symbols have cache coverage).

## Sync one cache at a time

| Command | Cache |
|---------|--------|
| `make sync-prices` | Stock `HistoricalPrice` |
| `make sync-benchmarks` | Benchmark indices |
| `make sync-fx` | FX rate pairs |
| `make sync-mutual-fund-navs` | MF NAV rows |

## API alternative (logged in)

| Endpoint | Scope |
|----------|--------|
| `POST /api/v1/prices/refresh` | Stocks |
| `POST /api/v1/nav/refresh` | MF NAVs |
| `POST /api/v1/portfolio/force-sync` | Combined |

Base URL: http://127.0.0.1:8000/api/v1 — see [API reference](../reference/api-reference.md).

## If values still look wrong

- Check dashboard warnings (`price_status`, `fx_status`)
- [Missing prices or NAVs](../troubleshooting/missing-prices-navs.md)

## Next

- [Read the dashboard](read-the-dashboard.md)
- Why cache exists: [Cached market data](../concepts/cached-market-data.md)
- Granular how-to: [Refresh prices, FX, benchmarks, and NAVs](../how-to/refresh-market-cache.md)
