# Database & Caching Strategy — KPulla6

## Overview
KPulla6 uses **PostgreSQL 16** (Docker Compose). Schema is defined by **Django models and migrations** only (no runtime `ALTER TABLE`).

## PostgreSQL (Docker Compose)
- Service: `postgres` in `docker-compose.yml`
- Default database: `portfolio_insight_kpulla6`
- Connection: `DATABASE_URL` or `POSTGRES_*` in `.env`
- **pgAdmin:** optional inspection UI only

## Migrations & bootstrap
```bash
make migrate    # apply migrations
make seed       # idempotent seed (Default Portfolio, AppSettings, benchmarks)
make bootstrap  # db + migrate + seed
```

## Tables (Phase 2 — implemented)

| Table | Django model | App |
|-------|----------------|-----|
| `portfolios` | `Portfolio` | `portfolios` |
| `transactions` | `Transaction` | `transactions` |
| `historical_prices` | `HistoricalPrice` | `market_data` |
| `benchmark_index_config` | `BenchmarkIndexConfig` | `market_data` |
| `fx_rates` | `FXRate` | `fx` |
| `settings` | `AppSettings` | `settings_app` |

### Portfolio
- Real portfolios only; **`All Portfolios` is virtual** and must not be stored (`Portfolio.clean()` rejects that name).
- At most one row with `is_default=True` (partial unique constraint).
- Seed: `python manage.py seed_initial_data` creates **Default Portfolio** (`EUR` base currency).

### Transaction
- Required `portfolio` FK (`PROTECT`); source of truth for holdings.
- Types: `BUY`, `SELL`, `DIVIDEND`, `STOCK_SPLIT`.
- Monetary fields use `DecimalField`; dates use `DateField`.
- **Stock splits:** `split_from` and `split_to` are the canonical persisted fields (KPulla5 `conversion_ratio` / `needs_review` are **not** modeled in KPulla6). CSV `SWAP` pairs and direct `STOCK_SPLIT` rows populate these fields; `quantity`/`price_per_share` default to `0` for split rows. On CSV direct `STOCK_SPLIT`, `currency` is set to `EUR` for schema consistency only (not valuation input).
- API DELETE removes the transaction row (hard delete). Portfolio DELETE only sets `portfolios.is_active=false`.
- **FIFO calculations** (Phase 6–7): fees are not included in lot cost basis (KPulla5 parity). Holdings APIs consume `backend/finance/` via `transactions/finance_adapter.py`.
- **Valuation input** (Phase 7–9): holdings and summary read latest or date-range `historical_prices` (`asset_type=STOCK`); summary timeseries forward-fills missing calendar days from prior cached rows; FX from `fx_rates` with same-date lookup and up to 7-day backfill for gaps.

### HistoricalPrice
- Cached market closes (not user-entered valuation).
- `asset_type`: `STOCK`, `INDEX`, `ETF`, `FX`.
- **Unique:** `(asset_symbol, date)`.

### FXRate
- Cached FX for date-based conversion.
- **Unique:** `(from_currency, to_currency, date)`.

### BenchmarkIndexConfig
- **Unique:** `symbol`.
- Seeded defaults: `^GSPC`, `^IXIC`, `^DJI`, `^STOXX50E`, `^GDAXI`.

### AppSettings
- Singleton row (`pk=1` from seed): `tax_rate_percentage`, `display_currency` (`EUR` default).
- Supported display currencies: `EUR`, `USD`, `INR`, `GBP`, `CHF`.
- `last_sync_timestamp` updated after successful full `sync_market_data` / stock sync.

## Caching strategy (unchanged intent)
- Historical closes and FX in DB; incremental sync via `sync_prices`, `sync_benchmarks`, `sync_fx_rates`, or `POST /api/v1/prices/refresh`.
- Unique keys: `(asset_symbol, date)` on `historical_prices`; `(from_currency, to_currency, date)` on `fx_rates`.
- Benchmark rows use `asset_type=INDEX`; stock rows use `STOCK`.
- No live external API calls during summary/performance read APIs; benchmark overlay uses `historical_prices` with `asset_type=INDEX` only.

## Testing
- `make test` uses in-memory SQLite (`DJANGO_TEST_USE_SQLITE=1`).
- Phase 2 tests: `backend/tests/test_models_phase2.py`.
