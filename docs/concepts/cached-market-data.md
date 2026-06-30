# Cached market data

Read APIs use **database caches** only.

| Cache | Populated by |
|-------|----------------|
| `HistoricalPrice` | `make sync-prices`, `POST .../prices/refresh` |
| `FXRate` | `make sync-fx` |
| Benchmark indices | `make sync-benchmarks` |
| MF NAV | `make sync-mutual-fund-navs`, `POST .../nav/refresh` |

## Why

- Predictable dashboard latency
- No rate limits or network failures during page loads
- Reproducible tests with SQLite fixtures

## User action

Run `make refresh` after adding symbols or when prices look stale.

How-to: [Refresh market cache](../how-to/refresh-market-cache.md)
