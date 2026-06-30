# Refresh prices, FX, benchmarks, and NAVs

## Combined sync

```bash
make refresh
# or
make sync-market-data
```

## Individual caches

| Command | Cache |
|---------|--------|
| `make sync-prices` | Stock `HistoricalPrice` |
| `make sync-benchmarks` | Index benchmarks |
| `make sync-fx` | FX rate pairs |
| `make sync-mutual-fund-navs` | MF NAV rows |

## API

| Endpoint | Scope |
|----------|--------|
| `POST /api/v1/prices/refresh` | Stocks |
| `POST /api/v1/nav/refresh` | MF NAVs |
| `POST /api/v1/portfolio/force-sync` | Combined |

## Read-path rule

Dashboard, holdings, summary, and performance **never** call external providers during GET requests.

Tutorial: [Refresh market data](../tutorials/refresh-market-data.md) · Concept: [Cached market data](../concepts/cached-market-data.md)
