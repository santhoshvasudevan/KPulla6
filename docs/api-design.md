# Portfolio Insight — API Design (KPulla6)

**Stack:** Django REST Framework · Base URL: `/api/v1`

This document describes the **target** REST API (carried forward from KPulla5). KPulla6 implements endpoints incrementally; only implemented routes are live in the running app.

## Implemented in KPulla6

### Health
`GET /api/v1/health`

**Response (200 OK)** — database reachable:
```json
{
  "status": "ok",
  "service": "kpulla6",
  "database": "ok"
}
```

**Response (503)** — database unreachable:
```json
{
  "status": "degraded",
  "service": "kpulla6",
  "database": "unavailable"
}
```

### Settings

`GET /api/v1/settings`

**Response (200 OK)**
```json
{
  "tax_rate_percentage": 15.0,
  "display_currency": "EUR"
}
```

`PUT /api/v1/settings` — partial update supported (at least one field required).

**Request**
```json
{
  "tax_rate_percentage": 20.0,
  "display_currency": "USD"
}
```

**Response (200 OK)** — same shape as GET.

**Errors (400):** unsupported `display_currency` (allowed: `EUR`, `USD`, `INR`, `GBP`, `CHF`); `tax_rate_percentage` outside `0`–`100`.

### Portfolios

`GET /api/v1/portfolios` — active real portfolios only (no virtual **All Portfolios** row).

**Response (200 OK)** — array of:
```json
{
  "id": 1,
  "name": "Default Portfolio",
  "description": null,
  "base_currency": "EUR",
  "is_default": true,
  "is_active": true,
  "created_at": "...",
  "updated_at": "..."
}
```

`POST /api/v1/portfolios` — create non-default portfolio (`201`). Validates non-empty name, unique active name (case-insensitive), max **5** active portfolios (including Default).

`PUT /api/v1/portfolios/{portfolio_id}` — update `name`, `description`, `base_currency`, `is_active`. Cannot deactivate Default Portfolio.

`DELETE /api/v1/portfolios/{portfolio_id}` — soft deactivate (`is_active=false`). Cannot delete Default Portfolio. Row and transactions are retained.

**Errors:** `400` validation; `404` unknown portfolio.

### Transactions

`GET /api/v1/transactions`

Query: `page` (default 1), `page_size` (default 20), `asset_symbol` (case-insensitive), `portfolio_scope=all`, `portfolio_id`.

Default (no scope params): all active real portfolios. Cannot combine `portfolio_scope=all` with `portfolio_id` (`422`).

**Response (200 OK)**
```json
{
  "items": [
    {
      "id": 1,
      "asset_symbol": "AAPL",
      "date": "2026-05-01",
      "type": "BUY",
      "quantity": 10.5,
      "price_per_share": 150.0,
      "portfolio_id": 1,
      "portfolio_name": "Default Portfolio",
      "currency": "USD",
      "fees": 2.5,
      "split_from": null,
      "split_to": null
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20,
  "pages": 1
}
```

`POST /api/v1/transactions` (`201`) — assigns `portfolio_id` or Default Portfolio. Uppercases `asset_symbol`. Types: `BUY`, `SELL`, `DIVIDEND`, `STOCK_SPLIT`.

`PUT /api/v1/transactions/{id}` — full update; omit `portfolio_id` to keep existing portfolio.

`DELETE /api/v1/transactions/{id}` — hard delete (`204`).

**Validation:** quantity > 0 for non-split types; `price_per_share` ≥ 0; `split_from`/`split_to` > 0 for splits; inactive/unknown portfolio `404`.

#### CSV import

`POST /api/v1/transactions/import-csv`

- **Content-Type:** `multipart/form-data`
- **Body:** `file` (CSV upload)
- **Query:** optional `portfolio_id` — assigns all rows to that active real portfolio; omitted → Default Portfolio
- **Response (200):** always HTTP 200; use `success` to distinguish outcome

**Success**
```json
{
  "success": true,
  "imported_count": 10,
  "errors": []
}
```

**Validation failure (all-or-nothing — zero rows inserted)**
```json
{
  "success": false,
  "imported_count": 0,
  "errors": [
    { "row": 3, "field": "Qty", "message": "Quantity must be positive" }
  ]
}
```

**CSV columns:** `Action`, `Date`, `ASSET SYMBOL`, `Qty`, `Price/Share`, optional `FEES`.

| Rule | Detail |
|------|--------|
| Date format | `MM/DD/YY` (also `MM/DD/YYYY`) |
| Actions | `BUY`, `SELL`, `DIVIDEND`, `SWAP`, `STOCK_SPLIT` |
| SWAP | Two rows (same date + symbol, opposite-sign whole-number qty) → one `STOCK_SPLIT` with `split_from`/`split_to` |
| STOCK_SPLIT (direct) | `Qty` = `split_from`, `Price/Share` = `split_to` |
| FEES | Omitted/empty → `0` |
| Symbols | Uppercased on import |
| Portfolio | Unknown/inactive `portfolio_id` query param → request-level **404** (`{"detail": "..."}`), not CSV row errors |
| Encoding | UTF-8 required (`utf-8-sig`); invalid bytes → row-level `file` error in import response |
| File type | MIME type and file extension are **not** validated yet |

#### Phase 5 closed assumptions (verified in tests)

| # | Assumption | Contract |
|---|------------|----------|
| 1 | Direct `STOCK_SPLIT` CSV | `Action=STOCK_SPLIT`; `Qty` → `split_from`; `Price/Share` → `split_to`. Both columns are **plain ratio numbers** (`parse_plain_decimal`), not currency-parsed. Currency symbols in `Price/Share` are rejected. |
| 2 | `SWAP` conversion | Exactly **two** rows per `(date, symbol)`; opposite-sign **whole-number** quantities; ratio derived via **GCD** → one `STOCK_SPLIT` with `split_from` / `split_to`. Incomplete or ambiguous pairs → row-level errors; import fails. |
| 3 | Split currency | Direct `STOCK_SPLIT` rows store `currency=EUR` for schema consistency only; not used as monetary valuation. `quantity` and `price_per_share` persist as `0`. |
| 4 | Portfolio query errors | Invalid or inactive `portfolio_id` on the import URL → **404** before CSV row processing; response is DRF `detail`, not `{success, errors}`. |
| 5 | File validation scope | UTF-8 decode + required columns/rows only; no MIME or extension check. |

#### Phase 4 behavioral contracts

| Topic | Contract |
|-------|----------|
| List scope | `portfolio_scope=all` **and** `portfolio_id` together → **422** |
| Portfolio lookup | Unknown or inactive `portfolio_id` on list/create/update → **404** |
| Transaction DELETE | **Hard delete** row; response **204 No Content** |
| Portfolio DELETE | **Soft deactivate** (`is_active=false`); response **200** with portfolio body; row retained |
| Transaction PUT | **Full body** required (all write fields for the transaction type). If `portfolio_id` is **omitted**, the existing portfolio assignment is **unchanged** |
| Stock splits | Canonical fields: `split_from`, `split_to` only. No `conversion_ratio` or `needs_review` in KPulla6 |
| Out of scope (Phase 4) | Daily high/low price validation, yfinance, background sync |

#### Holdings

`GET /api/v1/portfolio/holdings`

Query: `portfolio_scope=all`, `portfolio_id`, `display_currency` (`EUR` default; allowed: `EUR`, `USD`, `INR`, `GBP`, `CHF`).

Default: `portfolio_scope=all` when neither scope param is provided. Cannot combine `portfolio_scope=all` with `portfolio_id` (**422**). Unknown/inactive `portfolio_id` → **404**.

**Response (200 OK)**
```json
{
  "fx_status": "ok",
  "display_currency": "EUR",
  "holdings": [
    {
      "asset_symbol": "AAPL",
      "quantity": 10.0,
      "avg_cost_per_share": 140.0,
      "latest_price": 175.5,
      "current_value": 1755.0,
      "invested_amount": 1400.0,
      "realized_gain_loss": 200.0,
      "unrealized_gain_loss": 355.0,
      "currency": "EUR",
      "price_status": "ok",
      "holding_status": "ok",
      "warnings": [],
      "xirr": 0.125
    }
  ]
}
```

| Field | Notes |
|-------|--------|
| `holding_status` | `ok` \| `closed` (qty 0) \| `oversold` (SELL exceeded FIFO lots) |
| `price_status` | `ok` \| `price_missing` (no `HistoricalPrice` row, or price→holding FX unavailable) |
| `fx_status` (response + per holding) | `ok` when `display_currency` matches holding currency; `fx_unavailable` when display conversion is requested but not implemented |
| `current_value` | `0` when price missing or qty 0 |
| Fully sold | Included with `holding_status=closed` (KPulla5 parity) |

Prices: latest `HistoricalPrice` row (`STOCK` type), case-insensitive symbol match. When the stored price currency differs from the asset's transaction currency, the close is converted using cached FX (same-date with up to 7-day backfill). No yfinance/sync on read.

#### Asset detail

`GET /api/v1/portfolio/assets/{asset_symbol}`

Same scope and `display_currency` rules as holdings. Symbol match is case-insensitive; response `asset_symbol` is uppercase. No transactions in scope → **404**.

**Response (200 OK)** — includes FIFO metrics, `transactions` ordered by date, `holding_status`, `price_status`, `fx_status`, `warnings`, optional `xirr`.

---

## Phase 8 — Market data sync (implemented)

### `POST /api/v1/prices/refresh` — **202 Accepted**

Optional JSON: `{ "symbols": ["AAPL", "MSFT"] }`. Omit `symbols` to sync all distinct transaction asset symbols. Requested symbols are normalized to uppercase and **intersected** with transaction symbols (arbitrary symbols not in the portfolio are ignored).

Response: `{ "message": "Price sync scheduled" }`.

**Sync mode:** runs **synchronously** in the request thread (no Celery/RQ). External APIs may be called during this manual refresh only.

### `POST /api/v1/portfolio/force-sync` — **202 Accepted**

Alias for full market-data sync: stock prices + benchmark indices + FX rates.

Response: `{ "message": "Sync started in background" }` (KPulla5-compatible message; execution is synchronous in KPulla6).

### `GET /api/v1/benchmarks/indices`

Returns enabled rows from `benchmark_index_config` (seeded on `make seed`):

```json
{
  "indices": [
    { "symbol": "^GSPC", "name": "S&P 500" }
  ]
}
```

### Management commands

| Command | Purpose |
|---------|---------|
| `sync_prices` | Incremental stock `HistoricalPrice` sync (`--symbols` optional) |
| `sync_benchmarks` | Incremental benchmark index sync (`asset_type=INDEX`) |
| `sync_fx_rates` | Incremental FX pair sync (yfinance provider; logs when data missing) |
| `sync_market_data` | Combined sync (`--symbols`, `--skip-fx`) |

Make targets: `make sync-prices`, `make sync-benchmarks`, `make sync-fx`, `make sync-market-data`.

### Phase 8 read-path contracts (for summary/performance)

1. `POST /api/v1/prices/refresh` — stock price sync only.
2. `POST /api/v1/portfolio/force-sync` — stocks + benchmarks + FX.
3. Summary and value-history endpoints use cached `HistoricalPrice` and `FXRate` only.
4. No yfinance or external calls during read APIs.
5. `historical_prices` unique key is `(asset_symbol, date)` only; `STOCK` and `INDEX` must not share the same symbol+date.

---

## Phase 9 — Portfolio summary (implemented)

### `GET /api/v1/portfolio/summary`

Query params:

| Param | Default | Notes |
|-------|---------|--------|
| `include_timeseries` | `true` | `false` → `timeseries: []`, skips series build |
| `portfolio_scope` | — | `all` when neither scope nor id given |
| `portfolio_id` | — | Single active portfolio |
| `display_currency` | settings / EUR | `EUR`, `USD`, `INR`, `GBP`, `CHF` |

Validation: `portfolio_scope=all` + `portfolio_id` → **422**; unknown/inactive `portfolio_id` → **404**; invalid `display_currency` → **400**.

**Data sources:** DB-cached prices and FX only (no sync on read).

**Metrics:** FIFO remaining cost basis (`total_invested`), latest cached prices for `current_value`, `realized_pl` / `unrealized_pl` / `total_pl`, optional portfolio `xirr` (Phase 6 helper, fees in cashflows). Timeseries: daily holdings from transactions, forward-filled stock prices, same-date FX with up to 7-day backfill for gaps (`fx_status`: `ok` / `filled` / `fx_unavailable`). Missing FX → `portfolio_value: null` on affected points.

**Response (200 OK)** — see KPulla5 shape: `total_invested`, `current_value`, `realized_pl`, `unrealized_pl`, `total_pl`, `xirr`, `base_currency`, `display_currency`, `fx_status`, `timeseries[]`; optional `warnings` (e.g. oversell).

---

## Phase 10 — Portfolio performance (implemented)

### `GET /api/v1/portfolio/performance`

Query params:

| Param | Default | Notes |
|-------|---------|--------|
| `metric` | `value` | `value`, `cumulative_return`, `twror` |
| `range` | `1Y` | `7D`, `30D`, `YTD`, `1Y`, `3Y`, `5Y`, `ALL` |
| `benchmark` | — | Single index symbol (e.g. `^GSPC`); comparison for return metrics only |
| `benchmarks` | — | Legacy comma-separated list; **first symbol only** |
| `portfolio_scope` | `all` | When neither scope nor `portfolio_id` is sent |
| `portfolio_id` | — | Single active portfolio |
| `display_currency` | settings / EUR | `EUR`, `USD`, `INR`, `GBP`, `CHF` |

Validation: invalid `metric` / `range` / `display_currency` → **400**; `portfolio_scope=all` + `portfolio_id` → **422**; unknown/inactive portfolio → **404**; unknown/disabled `benchmark` with return metric → **422**.

**Data sources:** Reuses Phase 9 value timeseries (`portfolios/summary_service.build_portfolio_value_timeseries`). Cached `HistoricalPrice` (stocks + `asset_type=INDEX` for benchmarks) and `FXRate` only — **no external calls on read**.

**Metrics:**
- `value` — daily portfolio value in `display_currency` (same-date FX + 7-day fill, matching summary).
- `cumulative_return` — `((value + withdrawals - contributions) / contributions - 1) * 100`; `null` when contributions ≤ 0 or flows/FX unknown.
- `twror` — chain-linked period returns from Phase 6 `compute_twror_series`; `null` on first day or zero prior value. For `range != ALL`, TWROR is recomputed on the sliced window only (not rebased from full history).

**Benchmark:** Supported for `cumulative_return` and `twror` only. Returns `{ "metric", "series": [{ "name", "type", "data": [{ "date", "value" }] }], "warnings" }` with portfolio rebased to 0% at common anchor. `metric=value` ignores `benchmark` / `benchmarks` (list response). Missing benchmark prices → portfolio-only series + warning (not a hard failure).

**Range:** Never starts before first transaction date; clamped to inception when the requested window is earlier.

**Response (no benchmark):** JSON array of `{ "date", "value", "metric", "currency", "label": null }`.

---

## Planned (KPulla5 contract — not yet implemented in KPulla6)

### Common error response (target)
```json
{
  "error": "ErrorType",
  "message": "Human readable error message",
  "details": {},
  "timestamp": "2026-05-03T10:00:00Z",
  "path": "/api/v1/resource"
}
```

Query parameters (`portfolio_scope`, `portfolio_id`, `display_currency`, `range`, etc.) remain as documented in KPulla5 until ported.
