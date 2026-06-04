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
| `assets` | `Asset` | `market_data` (MF-1) |
| `mutual_fund_profiles` | `MutualFundProfile` | `market_data` (MF-1) |
| `folios` | `Folio` | `transactions` (MF-1) |
| `mutual_fund_transaction_details` | `MutualFundTransactionDetail` | `transactions` (MF-1) |

### Portfolio
- Real portfolios only; **`All Portfolios` is virtual** and must not be stored (`Portfolio.clean()` rejects that name).
- **`user` FK** (`auth.User`): each portfolio belongs to one user; transactions scope through portfolio ownership.
- Default portfolio constraint: at most one `is_default=True` **per user** (partial unique constraint).
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
- `asset_type`: `STOCK`, `INDEX`, `ETF`, `FX`, `MUTUAL_FUND` (MF-1).
- **Unique:** `(asset_symbol, date)` — unchanged in MF-1.
- Optional nullable `asset` FK → `assets` (MF-1); existing rows remain null; stock sync unchanged.
- **Stock sync coverage:** `sync_prices` / `POST /api/v1/prices/refresh` sync symbols from stock/ETF transactions only (excludes mutual fund rows and AMFI scheme codes). MF NAVs use `sync_mutual_fund_navs` / `sync_market_data` MF path. Fetch from earliest transaction date when no rows exist, or when the earliest cached price date is after the earliest transaction date (backfill gap). When cached prices already start at or before the first transaction, sync continues incrementally from latest cached date + 1. Read APIs never trigger sync.
- **Benchmark sync coverage:** `sync_benchmarks` / combined `sync_market_data` use `asset_type=INDEX` rows. Anchor = earliest transaction date (stocks and mutual funds). Same incremental/backfill rules as stocks (latest cached + 1 when continuous; backfill from anchor when cache starts later). Read APIs never trigger sync.

### Asset (MF-1)
- Canonical instrument registry.
- `asset_type`, `symbol` (AMFI `scheme_code` for MFs), `display_name`, `currency`, `provider`, `provider_symbol`, `primary_asset_class`, `region`, `is_active`.
- **Unique:** `(asset_type, symbol)`.

### MutualFundProfile (MF-1)
- One-to-one with `Asset` where `asset_type=MUTUAL_FUND`.
- `scheme_code` (unique), `scheme_name`, optional AMC metadata (`fund_house`, `scheme_type`, `scheme_category`, ISINs, `direct_or_regular`, `growth_or_idcw`).

### Folio (MF-1)
- Scoped to `(portfolio, asset, folio_number)`.
- **Unique:** `(portfolio, asset, folio_number)`.
- Required for `MutualFundTransactionDetail` (folio-level MF tracking).

### MutualFundTransactionDetail (MF-1; wired MF-3)
- One-to-one with `Transaction`; links to `Folio`.
- `investment_date`, `nav_date`, `nav`, `units_allotted`, `paid_value`, `market_value`.
- `nav_verification_status`: `NOT_VERIFIED` (default), `VERIFIED`, `NAV_MISSING`, `NAV_MISMATCH`, `VALUE_MISMATCH`, `WARNING_ACCEPTED`; legacy `OK`, `WARNING`, `UNCHECKED`.
- `nav_verification_message`: human-readable detail when status is not `VERIFIED`.
- MF-6 validation on write compares entered `nav` and `market_value` to cached `historical_prices` (`MUTUAL_FUND`, same `scheme_code` + `nav_date`); DB only, no external provider.

## MF-7 — Classification (implemented)

| Field | Usage |
|-------|--------|
| `Asset.primary_asset_class` | Canonical MVP class; explicit value wins over inference |
| `MutualFundProfile.scheme_category`, `scheme_type`, `scheme_name` | Inputs for conservative inference when class unset/`UNKNOWN` |
| Inference helper | `finance/mutual_fund_classification.py` (pure); bridge `market_data/mutual_fund_classification_bridge.py` |
| On MF txn create/update | `maybe_apply_inferred_asset_class` sets `Asset.primary_asset_class` only when not already explicit |
| Holdings/asset detail | Expose `primary_asset_class`, `classification_source`, optional `classification_notes` on MF rows only |

**Deferred:** exposure breakdown (equity/debt %), tax classification, allocation chart wiring.
- Created/updated via `POST/PUT /api/v1/transactions` with `asset_type=MUTUAL_FUND` (`transactions/mutual_fund_services.py`).
- **Mapping:** `Transaction.date=nav_date`, `quantity=units_allotted`, `price_per_share=nav`, `asset_symbol=scheme_code`, `currency` default `INR`.
- **Fees:** when omitted on MF create/update, `fees = paid_value - market_value` (error if negative).

### PrimaryAssetClass (MF-1 enum)
- `EQUITY`, `DEBT`, `HYBRID`, `LIQUID`, `COMMODITY`, `OTHER` — on `Asset.primary_asset_class`; hybrid not auto-mapped to equity.

### FXRate
- Cached FX for date-based conversion.
- **Unique:** `(from_currency, to_currency, date)`.
- **Sync coverage:** `sync_fx_rates` fetches from `earliest_required_fx_date` (transactions + stock price currencies) when no rows exist or when required date precedes earliest cached row; otherwise incremental from latest cached date + 1. Read APIs use same-date lookup with up to 7-day prior fill — never trigger sync.

### BenchmarkIndexConfig
- **Unique:** `symbol`.
- Seeded defaults: `^GSPC`, `^IXIC`, `^DJI`, `^STOXX50E`, `^GDAXI`, `^NSEI` (Nifty 50), `^BSESN` (BSE Sensex).

### AppSettings
- **One row per user** (`OneToOneField` to `auth.User`): `tax_rate_percentage`, `display_currency` (`EUR` default).
- Supported display currencies: `EUR`, `USD`, `INR`, `GBP`, `CHF`.
- Legacy singleton row migrated to initial owner `santhoshkgvasudevan@gmail.com`.
- `last_sync_timestamp` updated after successful full `sync_market_data` / stock sync.

## Caching strategy (unchanged intent)
- Historical closes and FX in DB; incremental sync via `sync_prices`, `sync_benchmarks`, `sync_fx_rates`, or `POST /api/v1/prices/refresh`.
- Mutual fund NAVs: incremental sync via `sync_mutual_fund_navs` (MF-2); cached as `historical_prices` rows with `asset_type=MUTUAL_FUND`.
- Unique keys: `(asset_symbol, date)` on `historical_prices`; `(from_currency, to_currency, date)` on `fx_rates`.
- Benchmark rows use `asset_type=INDEX`; stock rows use `STOCK`; MF NAV rows use `MUTUAL_FUND`.
- No live external API calls during summary/performance/holdings read APIs; benchmark overlay uses `historical_prices` with `asset_type=INDEX` only.
- NAV lookup helpers (`latest_nav_for_asset`, `list_mutual_fund_navs_in_range`) read DB only — never call AMFI on read.

## MF-2 — NAV cache and sync (implemented)

| Component | Location |
|-----------|----------|
| Provider abstraction | `mutual_fund_nav_provider.py` — live `AmfiNavProvider` (MFAPI); `amfi_nav_parser.py` — JSON parsing |
| External fetch | MFAPI `GET /mf/{scheme_code}/latest` and `GET /mf/{scheme_code}?startDate=&endDate=` — sync paths only |
| Sync service | `market_data/services/mutual_fund_nav_sync.py` — `sync_mutual_fund_navs`, `sync_one_mutual_fund`, `upsert_mutual_fund_nav` |
| Latest NAV lookup | `market_data/nav_lookup.py` — `latest_nav_for_asset`, `NavLookupResult` |
| Range lookup | `market_data/nav_repository.py` — `list_mutual_fund_navs_in_range` |
| Management command | `python manage.py sync_mutual_fund_navs` — optional `--scheme-code` filter |

**Sync rules (MF-2):**
- Syncs only active `MutualFundProfile` rows present in DB.
- Incremental: latest cached NAV date + 1 day, else earliest `MutualFundTransactionDetail.nav_date` / matching `Transaction.date`.
- Skips profiles with no anchor date and no cached NAV.
- Upserts `HistoricalPrice`: `asset_symbol=scheme_code`, `asset_type=MUTUAL_FUND`, `close_price=NAV`, `currency=INR`, `source=amfi`, optional `asset` FK.
- Provider failure per scheme does not abort batch; stock/FX/benchmark sync unchanged.
- External provider used **only** in sync path (management command / injected provider), not in read APIs.

**Later phases:** `POST /api/v1/nav/refresh`, `sync_market_data` MF inclusion (MF-9), summary/performance MF metrics — see `docs/current-state.md`.

## MF-4 — Holdings and asset detail read path (implemented)

| Step | Behavior |
|------|----------|
| Source transactions | `Transaction` rows with `MutualFundTransactionDetail` (BUY/SELL only for FIFO) |
| Grouping key | `(scheme_code, folio_number)` via `MutualFundTransactionDetail.folio` |
| Display metadata | `MutualFundProfile.scheme_name` via `Folio.asset` |
| Latest valuation | `latest_nav_for_asset(scheme_code)` → latest `HistoricalPrice` where `asset_type=MUTUAL_FUND` |
| Missing NAV | `nav_status=nav_missing`, `price_status=price_missing`, `current_value=0` when units remain |
| Currency | INR on MF holding rows; `fx_status` follows display vs holding currency (same rules as stocks) |

Stock holdings continue to use `Transaction.asset_symbol` grouping and `latest_historical_price` (`asset_type=STOCK`).

## MF-5 — Summary and performance read path (implemented)

| Step | Behavior |
|------|----------|
| Grouping | MF positions per `(scheme_code, folio_number)` in summary/performance builders |
| Latest value | `latest_mutual_fund_navs_by_scheme` → `HistoricalPrice` (`MUTUAL_FUND`) |
| Range NAV | `list_mutual_fund_navs_for_schemes` for timeseries; forward-fill last known NAV per calendar day |
| Valuation date | `Transaction.date` = `nav_date`; cash-flow date = `MutualFundTransactionDetail.investment_date` |
| Cash flows | BUY `−paid_value`, SELL `+paid_value` on `investment_date` (INR, converted via cached FX) |
| FIFO P/L | NAV × units cost basis (same as holdings); fees excluded from FIFO per existing finance rules |

## Testing
- `make test` uses in-memory SQLite (`DJANGO_TEST_USE_SQLITE=1`).
- Phase 2 tests: `backend/tests/test_models_phase2.py`.
- MF-2 tests: `backend/tests/test_mutual_fund_nav_sync.py`.

---

## Planned — Indian Mutual Funds (MF-3+; not yet implemented)

Full design: [mutual-funds.md](./mutual-funds.md). MF-1 schema and MF-2 NAV cache/sync are in place; items below are deferred.

### Deferred: `HistoricalPrice` unique constraint

MF-1 kept `(asset_symbol, date)` unchanged. A future phase may add `asset_type` to the unique key if symbol collision across types becomes a problem. Stock/index price tests and sync remain on `(asset_symbol, date)` with type-filtered lookups.

### Deferred: `transactions.asset_id`

Nullable FK from `Transaction` → `Asset` for MF rows — not added in MF-1. Stock flows continue via `asset_symbol` only.

### Mutual fund NAV sync path (MF-2 + MF-9)

| Path | External calls | Notes |
|------|----------------|-------|
| `sync_mutual_fund_navs` command | Provider in sync only | Incremental upsert to `historical_prices` (`asset_type=MUTUAL_FUND`) |
| `POST /api/v1/nav/refresh` | Provider in sync only | Optional `scheme_codes` filter |
| `sync_market_data` / `force-sync` | Provider in sync only | MF NAV included by default; `--skip-mutual-funds` opts out |
| Holdings / summary / performance / transactions reads | **None** | `latest_nav_for_asset`, `list_mutual_fund_navs_*` — DB only |

### Planned settings (MF-10+)

| Column | Notes |
|--------|-------|
| `mutual_fund_grouping` | `SCHEME_AND_FOLIO` (default) \| `SCHEME_ONLY` on `AppSettings` or portfolio settings |

### Planned future tables (not MVP)

| Table | Purpose |
|-------|---------|
| `mutual_fund_exposure` | Optional equity/debt/other % breakdown per scheme |
| Tax classification fields | Separate from `primary_asset_class`; MF tax phase TBD |
