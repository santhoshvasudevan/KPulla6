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

Query: `page` (default 1), `page_size` (default 20), `portfolio_scope=all`, `portfolio_id`, plus column filters:

| Param | Meaning |
| --- | --- |
| `asset_symbol` | Single symbol, case-insensitive exact match |
| `symbols` | Comma-separated symbols / AMFI scheme codes, case-insensitive (multi-select) |
| `date_from` | Include transactions with `date >= date_from` (YYYY-MM-DD) |
| `date_to` | Include transactions with `date <= date_to` (YYYY-MM-DD) |
| `date_after` | Alias for `date_from` (used by the "Later than" date mode) |
| `date_before` | Alias for `date_to` (used by the "Earlier than" date mode) |

`asset_symbol` and `symbols` are combined into one symbol set. Date filter modes map to: *Earlier than X* → `date_to=X`; *Later than X* → `date_from=X`; *Between A and B* → `date_from=A&date_to=B`. All filters are applied **before** pagination, so `total`/`pages` reflect the filtered set.

Default (no scope params): all active real portfolios. Cannot combine `portfolio_scope=all` with `portfolio_id` (`422`). Unknown/inactive `portfolio_id` → `404`. Malformed `portfolio_id` or date, or `date_from > date_to` → `400`.

`GET /api/v1/transactions/filter-options`

Distinct filter values for the current portfolio scope (same `portfolio_scope` / `portfolio_id` rules as the list endpoint). `portfolios` always lists active real portfolios so the dropdown can broaden the current scope; `symbols`, `types`, and the date bounds are scoped to the current selection.

```json
{
  "portfolios": [{ "id": 1, "name": "Default Portfolio" }],
  "symbols": ["AAPL", "120503"],
  "types": ["BUY", "SELL", "DIVIDEND", "STOCK_SPLIT"],
  "date_min": "2019-10-10",
  "date_max": "2026-05-29"
}
```

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

**CSV columns (stock):** `Action`, `Date`, `ASSET SYMBOL`, `Qty`, `Price/Share`, optional `FEES`.

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
| Format detection | Stock vs mutual fund CSV is chosen from headers — see MF CSV below; **mixed stock + MF columns in one file → row 1 header error** |

#### Mutual fund CSV import (MF-11a)

Detected when headers include **Scheme Code** and **Folio Number** and do **not** also include stock marker columns (`ASSET SYMBOL`, `Qty`, or `Price/Share`).

**Required columns:** `Action`, `Scheme Code`, `Scheme Name`, `Folio Number`, `Investment Date`, `NAV Date`, `NAV`, `Units Allotted`, `Paid Value`, `Market Value`

**Optional columns:** `Fees` (empty/omitted → `paid_value - market_value` per MF transaction rules), `Currency` (default `INR`)

| Column | Maps to |
|--------|---------|
| `Action` | `BUY` or `SELL` only |
| `Scheme Code` | `asset_symbol` / AMFI `scheme_code` |
| `Scheme Name` | `MutualFundProfile.scheme_name` |
| `Folio Number` | folio (required) |
| `Investment Date` | `MutualFundTransactionDetail.investment_date` |
| `NAV Date` | `Transaction.date` |
| `NAV` | `price_per_share` |
| `Units Allotted` | `quantity` |
| `Paid Value` | `MutualFundTransactionDetail.paid_value` |
| `Market Value` | `MutualFundTransactionDetail.market_value` |

| Rule | Detail |
|------|--------|
| Date format | Same as stock CSV: `MM/DD/YY` or `MM/DD/YYYY` |
| Creation path | `create_mutual_fund_transaction()` — upserts Asset, Profile, Folio, detail row |
| NAV validation | Cached `HistoricalPrice` (`MUTUAL_FUND`) only — no external AMFI/MFAPI on import |
| All-or-nothing | Same as stock CSV |
| Portfolio query | Same as stock CSV |
| Mixed formats | Stock + MF columns in one file → **validation error** (not supported in MF-11a) |

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

Full market-data sync: stock prices + benchmark indices + FX rates + mutual fund NAVs.

Response (202): KPulla5-compatible `message` plus sync detail:

```json
{
  "message": "Sync started in background",
  "prices_success": true,
  "benchmarks_success": true,
  "fx_success": true,
  "fx_partial": false,
  "mutual_funds": {
    "synced": 2,
    "skipped": 0,
    "failed": 0,
    "success": true
  },
  "warnings": []
}
```

Execution is synchronous in the request thread (no Celery/RQ). Mutual fund NAV failures do not fail stock/benchmark/FX success flags.

### `POST /api/v1/nav/refresh` — **202 Accepted** (MF-9)

Manual incremental mutual fund NAV sync. Optional JSON: `{ "scheme_codes": ["120503", "120504"] }`. Omit `scheme_codes` to sync all active `MutualFundProfile` rows in DB.

Response:

```json
{
  "message": "Mutual fund NAV sync completed",
  "synced": 2,
  "skipped": 0,
  "failed": 0,
  "warnings": []
}
```

**Sync mode:** synchronous in the request thread. Calls MFAPI via `AmfiNavProvider` (live in MF-10). Read APIs never call the provider.

Per-scheme provider failure increments `failed` and adds a warning; other schemes continue.

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
| `sync_benchmarks` | Incremental benchmark index sync (`asset_type=INDEX`); anchor = earliest transaction date; backfill/incremental same rules as stocks |
| `sync_fx_rates` | Incremental FX pair sync (yfinance provider; logs when data missing) |
| `sync_market_data` | Combined sync (`--symbols`, `--skip-fx`, `--skip-mutual-funds`) |

Make targets: `make sync-prices`, `make sync-benchmarks`, `make sync-fx`, `make sync-market-data`.

### Phase 8 read-path contracts (for summary/performance)

1. `POST /api/v1/prices/refresh` — stock price sync only.
2. `POST /api/v1/portfolio/force-sync` — stocks + benchmarks + FX + mutual fund NAVs.
3. `POST /api/v1/nav/refresh` — mutual fund NAV sync only (MF-9).
4. Summary and value-history endpoints use cached `HistoricalPrice` and `FXRate` only.
5. No yfinance or external NAV provider calls during read APIs.
6. `historical_prices` unique key is `(asset_symbol, date)` only; `STOCK` and `INDEX` must not share the same symbol+date.

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

**All Portfolios aggregation (`portfolio_scope=all`):** Headline monetary fields (`total_invested`, `current_value`, `realized_pl`, `unrealized_pl`, `total_pl`) are the **sum of each active real portfolio’s summary** after conversion to the requested `display_currency`. Inactive portfolios are excluded; Default Portfolio is included once. Response `base_currency` equals `display_currency` for this virtual scope. `fx_status` is the worst status across child portfolios (`fx_unavailable` > `filled` > `ok`). `warnings` are prefixed with portfolio name. `xirr` is still computed from merged cashflows across all active portfolios (not summed). When `include_timeseries=true`, daily series points are summed by date from child portfolio series in `display_currency`.

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

## Analytics performance metrics (Metric Sheet)

Read paths use **cached DB data only** (same as summary/performance). Metrics are computed **on query**; MVP does not store derived analytics rows. Return values are **fractions** (e.g. `0.10` = 10%); UI may multiply by 100.

**Currency field:** `currency` is the valuation/display currency context for the portfolio scope (same as summary/performance). Return and risk ratios (cumulative return, CAGR, TWROR, Sharpe, drawdowns, etc.) are dimensionless fractions computed from same-currency value and flow inputs — they are **not** currency amounts and are not converted like monetary fields.

**Range vs XIRR:** Most metrics are computed over the selected `range` window (daily returns sliced from `range.start`). **XIRR** is an exception: it is always **full-scope** (inception through today), matching `GET /portfolio/summary`. The response includes `metrics.return.xirr_scope: "full_scope"` so clients can distinguish range-based stats from money-weighted IRR.

**Stock splits:** Daily value series uses split-adjusted FIFO quantities (`build_split_adjusted_lot_snapshots`). Cached stock `HistoricalPrice` rows must be split-adjusted (yfinance **Adj Close** from `make sync-prices`). Raw nominal pre-split prices are **unsupported** for Metric Sheet analytics; responses include a `warnings` entry when split-date valuation drops match the split factor (likely raw prices).

### Implemented: `GET /api/v1/analytics/performance-metrics` (Phase 5)

Portfolio-level Quantitative Statistics. Wired in `analytics/services.py`, `analytics/views.py`.

### Proposed (not yet implemented)

### Common query parameters (all analytics endpoints)

| Param | Default | Notes |
|-------|---------|--------|
| `range` | `1Y` | Same codes as performance: `7D`, `30D`, `YTD`, `1Y`, `3Y`, `5Y`, `ALL` |
| `display_currency` | settings / EUR | `EUR`, `USD`, `INR`, `GBP`, `CHF` |
| `benchmark` | — | Optional index symbol for beta, alpha, correlation |
| `portfolio_scope` | `all` | Portfolio-level endpoints only |
| `portfolio_id` | — | Single active portfolio |

Validation mirrors performance/summary (400/404/422). Response includes `warnings: string[]` for data-quality issues, including: missing cached stock prices (`Cached prices are missing for one or more dates…`), missing MF NAVs (`Cached NAVs are missing…`; suggests NAV sync), FX gaps, benchmark coverage, split-adjusted price inconsistency, or insufficient history. Generic fallback when values are wholly unavailable remains.

### `GET /api/v1/analytics/performance-metrics` (implemented)

Portfolio-level performance metric sheet (Quantitative Statistics summary).

**Rough response (200 OK):**
```json
{
  "subject": { "type": "portfolio", "portfolio_scope": "all", "display_currency": "EUR" },
  "range": "1Y",
  "benchmark": "^GSPC",
  "as_of": "2026-05-30",
  "warnings": [],
  "summary": {
    "total_return_pct": 12.5,
    "cagr_pct": 11.2,
    "xirr": 0.105,
    "volatility_pct": 14.0,
    "sharpe": 0.85,
    "sortino": 1.1,
    "max_drawdown_pct": -8.2,
    "calmar": 1.36,
    "beta": 0.92,
    "alpha_pct": 1.5,
    "correlation": 0.88
  },
  "period_returns": {
    "monthly": [{ "period": "2026-04", "return_pct": 2.1 }],
    "yearly": [{ "period": "2025", "return_pct": 15.3 }]
  },
  "drawdowns": {
    "max": { "pct": -8.2, "start": "2026-02-01", "trough": "2026-02-15", "end": "2026-03-01" },
    "series": [{ "date": "2026-01-01", "drawdown_pct": 0 }]
  },
  "win_loss": { "win_rate_pct": 55.0, "best_day_pct": 3.2, "worst_day_pct": -2.8 }
}
```

Fields may be `null` when data quality or history is insufficient. `xirr` is money-weighted (separate from TWROR-derived risk metrics). `xirr_scope` is always `"full_scope"` (not sliced by `range`); other return/risk/drawdown metrics use the selected range window.

**Phase 9A — additional blocks (portfolio + asset):** Top-level siblings of `metrics` (existing `metrics.return` / `risk` / `drawdown` / `periods` unchanged):

```json
{
  "periodic_returns": {
    "monthly": [{ "period": "2026-01", "return": 0.021 }],
    "yearly": [{ "period": "2025", "return": 0.143 }]
  },
  "drawdown_periods": {
    "worst": [
      {
        "start_date": "2025-01-10",
        "trough_date": "2025-02-05",
        "recovery_date": "2025-03-20",
        "drawdown": -0.182,
        "days_to_trough": 26,
        "days_to_recovery": 69,
        "recovered": true
      }
    ]
  }
}
```

* `periodic_returns`: compounded fractional returns from daily series in the selected range (`resample_monthly_returns` / `resample_yearly_returns`); days with `null` daily return are skipped.
* `drawdown_periods.worst`: up to 10 episodes ranked by severity (`worst_drawdown_periods` in `finance/drawdowns.py`); `drawdown` is a fraction (not percent). Empty arrays when history is insufficient; no extra warnings beyond existing Metric Sheet warnings.

### Implemented: `GET /api/v1/analytics/assets/{asset_symbol}/performance-metrics` (Phase 6)

Single-asset Metric Sheet (stock symbol or MF scheme code). Wired in `analytics/services.py`, `analytics/views.py`.

| Param | Notes |
|-------|--------|
| `folio_number` | Required when multiple MF folios exist for the scheme (`400`) |
| `portfolio_scope` / `portfolio_id` | Limit transactions to scope (same rules as portfolio endpoint) |
| `range`, `display_currency`, `benchmark` | Same as portfolio Metric Sheet |

**404** when no matching transactions in scope. **422** when `portfolio_scope=all` combined with `portfolio_id`.

**Response (200 OK):** Same nested `metrics` / optional `benchmark` / `warnings` shape as portfolio Metric Sheet, plus `periodic_returns` and `drawdown_periods` (Phase 9A). Subject:

```json
{
  "type": "asset",
  "asset_symbol": "AAPL",
  "name": "AAPL",
  "portfolio_scope": "all",
  "portfolio_id": null,
  "folio_number": null
}
```

Asset value series is built from scoped asset transactions + cached prices/NAV/FX (not portfolio series filtered post-hoc). Stocks use split-adjusted FIFO qty with cached historical prices; MFs use cached NAV rows and `investment_date` / `paid_value` cash flows (portfolio MF rules). `xirr_scope` is `"full_scope"`.

### Implemented: `GET /api/v1/analytics/compare` (Phase 7)

Side-by-side comparison of **exactly two** asset subjects (MVP). Wired in `analytics/services.py`, `analytics/views.py`.

| Param | Notes |
|-------|--------|
| `subjects` | Required comma-separated list, e.g. `asset:AAPL,asset:MSFT` (MVP: `asset:<symbol>` only, exactly two) |
| `portfolio_scope` / `portfolio_id` | Limit transactions to scope (same rules as portfolio Metric Sheet) |
| `range`, `display_currency`, `benchmark` | Same as portfolio Metric Sheet |

**400** when `subjects` missing, invalid format, wrong count, or unsupported subject type. **404** when a subject has no transactions in scope (same as asset Metric Sheet). **422** for invalid benchmark config or conflicting scope params.

Compare API metrics are computed over **common overlapping dates only** (exact date intersection of non-`None` daily returns; no forward-fill). Each subject gets aligned-window Metric Sheet metrics plus optional per-subject benchmark block. `normalized_series` rebases cumulative fractional returns to `0` on the first common date.

**Response (200 OK):**
```json
{
  "range": { "code": "3Y", "start": "2026-01-02", "end": "2026-03-15" },
  "currency": "EUR",
  "subjects": [
    {
      "id": "asset:AAPL",
      "type": "asset",
      "asset_symbol": "AAPL",
      "name": "AAPL",
      "folio_number": null,
      "metrics": { "return": {}, "risk": {}, "drawdown": {}, "periods": {} },
      "periodic_returns": { "monthly": [], "yearly": [] },
      "drawdown_periods": { "worst": [] },
      "benchmark": { "symbol": "^GSPC", "paired_count": 10, "metrics": {} },
      "warnings": []
    }
  ],
  "normalized_series": [
    { "date": "2026-01-02", "values": { "asset:AAPL": 0.0, "asset:MSFT": 0.0 } }
  ],
  "common_start_date": "2026-01-02",
  "common_end_date": "2026-03-15",
  "common_point_count": 42,
  "warnings": ["Compare API metrics are computed over common overlapping dates only."]
}
```

When `common_point_count < 2`, subject metrics are null, `periodic_returns` / `drawdown_periods` are empty arrays, and a global insufficient-overlap warning is included. Per-subject periodic returns and drawdown periods use the **aligned common-window** daily returns (not each asset’s independent full history). MF compare reuses asset Metric Sheet rules (single folio auto-resolved; multiple folios → **400** on asset resolution, same as asset endpoint — no per-subject `folio_number` in compare query yet).

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

---

## Indian Mutual Funds

Full design: [mutual-funds.md](./mutual-funds.md).

**Preservation rule:** Stock transaction, holdings, summary, performance, benchmark, FX, and CSV import endpoints remain valid. MF support is additive.

### Implemented: Mutual fund transactions (MF-3)

`POST/PUT /api/v1/transactions` with `"asset_type": "MUTUAL_FUND"` creates/updates mutual fund BUY/SELL rows. Stock requests omit `asset_type` and use the existing payload unchanged.

**Request fields (MF BUY/SELL)**

| Field | Required | Notes |
|-------|----------|-------|
| `asset_type` | Yes | `"MUTUAL_FUND"` |
| `scheme_code` | Yes | AMFI canonical id → `Transaction.asset_symbol` |
| `scheme_name` | Yes | Display metadata; upserts `MutualFundProfile` |
| `folio_number` | Yes | Upserts `Folio` per portfolio + asset |
| `type` | Yes | `BUY` or `SELL` only |
| `investment_date` | Yes | Stored on `MutualFundTransactionDetail` |
| `nav_date` | Yes | Primary valuation date → `Transaction.date` |
| `nav` | Yes | Per-unit NAV → `Transaction.price_per_share` |
| `units_allotted` | Yes | → `Transaction.quantity` |
| `paid_value` | Yes | Actual cash amount |
| `market_value` | Yes | Reference amount |
| `portfolio_id` | No | Defaults to Default Portfolio |
| `currency` | No | Default `INR` |
| `fees` | No | Default `paid_value - market_value` when omitted; error if negative |
| `fund_house`, `scheme_type`, `scheme_category`, `isin_growth`, `isin_reinvestment`, `direct_or_regular`, `growth_or_idcw` | No | Profile metadata |

**Validation:**
- No external NAV provider calls on create/update/read
- Cached NAV compare on create/update (MF-6): `scheme_code` + `nav_date` vs `HistoricalPrice` (`MUTUAL_FUND`); no external provider; mismatch does not block save
- Atomic create/update: `Transaction` + `MutualFundTransactionDetail` in one transaction
- DELETE hard-deletes transaction; detail cascades; Asset/Profile/Folio retained

**List/create response extensions (MF rows only):** `asset_type`, `scheme_code`, `scheme_name`, `folio_number`, `investment_date`, `nav_date`, `nav`, `units_allotted`, `paid_value`, `market_value`, `nav_verification_status`, optional `nav_verification_message`. Stock rows unchanged (no `asset_type` field).

**`nav_verification_status` (MF-6):**

| Status | Meaning |
|--------|---------|
| `VERIFIED` | Cached NAV matches entered NAV (±0.01 INR) and `market_value` matches `nav×units` (±1 INR) |
| `NAV_MISSING` | No cached NAV row for scheme + `nav_date` — transaction still saved |
| `NAV_MISMATCH` | Cached NAV exists but entered NAV outside tolerance |
| `VALUE_MISMATCH` | NAV matches cache but `market_value` outside tolerance vs `nav×units` |
| `NOT_VERIFIED` | Default on manual DB rows only |
| `OK` / `WARNING` / `UNCHECKED` | Legacy MF-3 values on older rows |

Structural invalid input (missing fields, non-positive nav/units, negative values, negative computed fees) → **400**.

**PUT:** Existing MF transactions auto-route to MF handler (or send `asset_type=MUTUAL_FUND`).

### Planned: Scheme lookup (MF-4+)

`GET /api/v1/mutual-funds/schemes?q={search}` — search by scheme name, return `scheme_code` + metadata from DB profile table. DB only; no live AMFI on read.

### Holdings (`GET /api/v1/portfolio/holdings`) — MF-4 implemented

Mutual fund positions appear as additional holding rows (stock rows unchanged — no `asset_type` on stock rows):

| Field | Notes |
|-------|-------|
| `asset_type` | `MUTUAL_FUND` on MF rows only |
| `asset_symbol` / `scheme_code` | AMFI `scheme_code` for MF |
| `scheme_name` | From `MutualFundProfile` |
| `folio_number` | Folio for MF |
| `holding_key` | `{scheme_code}:{folio_number}` |
| `units` | Same as `quantity` (units) for MF |
| `latest_nav` | Cached NAV (MF); stocks keep `latest_price` |
| `latest_price` | Also set to latest NAV on MF rows (backward compatibility) |
| `nav_status` | `ok` \| `nav_missing` (MF); stocks keep `price_status` |
| `price_status` | `ok` \| `price_missing`; MF mirrors NAV (`nav_missing` → `price_missing`) |
| `primary_asset_class` | `EQUITY`, `DEBT`, `HYBRID`, `LIQUID`, `COMMODITY`, `OTHER`, `UNKNOWN` (MF-7) |
| `classification_source` | `EXPLICIT`, `INFERRED`, `UNKNOWN` (MF-7) |
| `classification_notes` | Optional inference note (MF-7) |

**Grouping (MVP):** one row per `(scheme_code, folio_number)` within resolved portfolio scope. FIFO and oversell per folio group. Valuation: `current_value = remaining units × latest cached NAV` (`HistoricalPrice`, `asset_type=MUTUAL_FUND`). No external NAV provider on read.

### Asset detail — MF-4 implemented

`GET /api/v1/portfolio/assets/{scheme_code}?folio_number={folio}` — MF Metric Sheet with folio-scoped FIFO and transactions (MF fields on transaction rows). Stock route `{asset_symbol}` unchanged for tickers.

- Single folio for scheme: `folio_number` optional.
- Multiple folios: omitting `folio_number` → **400** `folio_number is required when multiple folios exist for this scheme`.
- Unknown folio → **404**.

MF response extensions: `asset_type`, `scheme_code`, `scheme_name`, `folio_number`, `latest_nav`, `nav_status`, `units`, `primary_asset_class`, `classification_source`, optional `classification_notes`.

### Summary and performance — MF-5 implemented

No new endpoints. `GET /api/v1/portfolio/summary` and `GET /api/v1/portfolio/performance` include mutual fund positions when MF transactions exist:

| Area | Behavior |
|------|----------|
| Totals | MF `current_value` = units × latest cached NAV; FIFO invested/realized/unrealized merged into portfolio totals |
| Timeseries | Daily MF value from units × forward-filled historical NAV (`list_mutual_fund_navs_for_schemes`); merged with stock series |
| XIRR | Stock flows unchanged; MF BUY/SELL use `investment_date` and `paid_value` (`merge_portfolio_xirr`) |
| Performance flows | `cumulative_return` / `twror` external flows use MF `paid_value` on `investment_date` |
| FX | INR MF amounts converted to `portfolio_base` / `display_currency` via cached `FXRate` (7-day fill) |
| Warnings | `Latest cached NAV missing for mutual fund {scheme}` when NAV absent |

Stock-only portfolios: same calculations and response shape (warnings only when MF rows exist). No external NAV provider on read.

### NAV sync — management command + HTTP (MF-2 + MF-9)

| Command / endpoint | Purpose |
|--------------------|---------|
| `sync_mutual_fund_navs` | Incremental NAV sync for active `MutualFundProfile` rows; optional `--scheme-code` |
| `POST /api/v1/nav/refresh` | Manual NAV sync; optional `{ "scheme_codes": [...] }` |
| `sync_market_data` / `POST /api/v1/portfolio/force-sync` | Includes MF NAV sync by default (`--skip-mutual-funds` to opt out) |

Sync calls MFAPI via `AmfiNavProvider` (MF-10); inject mock `http_get` in tests. Holdings/summary/performance/dashboard reads may **not** call NAV providers.

### Planned: Settings (MF-10+)

`PUT /api/v1/settings` — optional `mutual_fund_grouping`: `scheme_and_folio` \| `scheme_only` (aggregates holdings by scheme).
