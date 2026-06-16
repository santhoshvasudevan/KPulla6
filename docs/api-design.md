# Portfolio Insight — API Design (KPulla6)

**Stack:** Django REST Framework · Base URL: `/api/v1`

This document describes the **target** REST API (carried forward from KPulla5). KPulla6 implements endpoints incrementally; only implemented routes are live in the running app.

## Implemented Endpoint Index

Quick reference for MVP endpoints. Detail sections below. Product rules: [product-rules.md](./product-rules.md). **Contract index (frontend + tests + error shapes):** [api-contracts.md](./api-contracts.md).

| Method | Path | Purpose | Frontend (`api.js`) | Backend tests |
|--------|------|---------|----------------------|---------------|
| GET | `/api/v1/portfolio/summary` | FIFO headline metrics, optional timeseries, cash-inclusive `current_value` | `fetchDashboardSummary` | `test_portfolio_summary_api.py` |
| GET | `/api/v1/portfolio/performance` | Value / cumulative return / TWROR series; benchmark overlay | `fetchPortfolioPerformance` | `test_portfolio_performance_api.py` |
| GET | `/api/v1/portfolio/holdings` | Holdings table + allocation (includes cash) | `fetchHoldings` | `test_holdings_api.py` |
| GET | `/api/v1/portfolio/assets/{asset_symbol}` | Asset detail + FIFO metrics | `fetchAssetDetails` | `test_holdings_api.py` |
| GET | `/api/v1/analytics/performance-metrics` | Portfolio Metric Sheet | `getPortfolioMetricSheet` | `test_analytics_performance_metrics_api.py` |
| GET | `/api/v1/analytics/assets/{asset_symbol}/performance-metrics` | Asset Metric Sheet | `getAssetMetricSheet` | `test_analytics_asset_metrics_api.py` |
| GET | `/api/v1/analytics/compare` | Two-asset Metric Sheet compare | `getCompareMetricSheet` | `test_analytics_compare_api.py` |
| GET | `/api/v1/cash/balances` | Native-currency balances (no display FX in read path) | `fetchCashBalances` | `test_cash_api.py` |
| GET | `/api/v1/cash/ledger` | Paginated cash ledger | `fetchCashLedger` | `test_cash_api.py` |
| POST | `/api/v1/cash/deposits` | Manual `CASH_DEPOSIT` | `createCashDeposit` | `test_cash_api.py` |
| POST | `/api/v1/cash/withdrawals` | Manual `CASH_WITHDRAWAL` | `createCashWithdrawal` | `test_cash_api.py` |
| PUT | `/api/v1/cash/ledger/{id}` | Edit manual deposit/withdrawal | `updateCashLedgerEntry` | `test_cash_api.py` |
| DELETE | `/api/v1/cash/ledger/{id}` | Delete manual deposit/withdrawal | `deleteCashLedgerEntry` | `test_cash_api.py` |
| POST | `/api/v1/cash/transfers` | Same- or cross-currency portfolio transfer | `createCashTransfer` | `test_cash_api.py` |
| POST | `/api/v1/cash/bulk-entries/preview` | Bulk schedule preview | `previewCashBulkEntries` | `test_cash_bulk_entries_api.py` |
| POST | `/api/v1/cash/bulk-entries/apply` | Confirmed bulk manual entries | `applyCashBulkEntries` | `test_cash_bulk_entries_api.py` |
| GET | `/api/v1/bank-accounts` | List active user bank accounts | `fetchBankAccounts` | `test_bank_accounts_api.py` |
| POST | `/api/v1/bank-accounts` | Create bank account | `createBankAccount` | `test_bank_accounts_api.py` |
| PUT | `/api/v1/bank-accounts/{id}` | Update bank account | `updateBankAccount` | `test_bank_accounts_api.py` |
| DELETE | `/api/v1/bank-accounts/{id}` | Soft deactivate bank account | `deleteBankAccount` | `test_bank_accounts_api.py` |
| POST | `/api/v1/bank-accounts/{id}/seed-opening-balance` | Seed `OPENING_BALANCE` from `opening_balance` | `seedBankAccountOpeningBalance` | `test_cash_movements_api.py` |
| GET | `/api/v1/cash-movements` | List bank cash movements (paginated) | `fetchCashMovements` | `test_cash_movements_api.py` |
| POST | `/api/v1/cash-movements` | Create manual movement | `createCashMovement` | `test_cash_movements_api.py` |
| GET | `/api/v1/cash-movements/{id}` | Movement detail | — | `test_cash_movements_api.py` |
| GET | `/api/v1/fixed-deposits` | List active fixed deposits (portfolio scope) | `fetchFixedDeposits` | `test_fixed_deposits_api.py` |
| POST | `/api/v1/fixed-deposits` | Create fixed deposit | `createFixedDeposit` | `test_fixed_deposits_api.py` |
| PUT | `/api/v1/fixed-deposits/{id}` | Update fixed deposit | `updateFixedDeposit` | `test_fixed_deposits_api.py` |
| DELETE | `/api/v1/fixed-deposits/{id}` | Soft deactivate fixed deposit | `deleteFixedDeposit` | `test_fixed_deposits_api.py` |
| GET | `/api/v1/transactions` | Paginated asset transactions | `fetchTransactions` | `test_transactions_api.py` |
| POST | `/api/v1/transactions` | Create stock/MF transaction | `createTransaction` | `test_transactions_api.py`, `test_cash_aware_transactions_api.py` |
| PUT | `/api/v1/transactions/{id}` | Update transaction | `updateTransaction` | `test_transactions_api.py`, `test_cash_aware_transactions_api.py` |
| DELETE | `/api/v1/transactions/{id}` | Delete transaction | `deleteTransaction` | `test_transactions_api.py` |
| POST | `/api/v1/transactions/import-csv` | CSV import (stock or MF) | `importTransactionsCsv` | `test_csv_import_api.py`, `test_mutual_fund_csv_import.py` |
| POST | `/api/v1/transactions/import-csv/preview-cash` | CSV cash shortfall preview (no writes) | `previewCsvImportCash` | `test_csv_import_cash_preview.py` |

**Removed (not active):** `POST /api/v1/cash/backfill-preview`, `POST /api/v1/cash/backfill-apply` — use deposits/withdrawals or bulk entries instead.

## Implemented in KPulla6

### Health
`GET /api/v1/health`

Public; no authentication required.

### Authentication (implemented)

Session-based auth for the React SPA. See `docs/auth.md` for setup.

| Method | Path | Auth |
|--------|------|------|
| GET | `/api/v1/auth/csrf` | Public |
| GET | `/api/v1/auth/me` | Session |
| POST | `/api/v1/auth/login` | Public |
| POST | `/api/v1/auth/logout` | Session |
| POST | `/api/v1/auth/register` | Public |
| POST | `/api/v1/auth/password-reset` | Public |

Google OAuth: `GET /accounts/google/login/` (django-allauth; redirects to `FRONTEND_URL` after success).

All other `/api/v1/*` endpoints require an authenticated session (`401`/`403` when missing).

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

**Cash-aware write errors (stock + MF when `portfolio.cash_aware_enabled`):**

| Condition | Status | Response |
|-----------|--------|----------|
| Insufficient same-currency cash for BUY (create/update) | **400** | `detail`, `required`, `available`, `shortfall`, `currency` |
| Settlement change would make future balance negative (edit/delete/type morph) | **409** | `detail`, `currency`, `earliest_negative_date`, `lowest_balance`, `affected_entries[]` |

Future-impact `detail`: `"This transaction change would make future cash balance negative."` Applies when deleting a `SELL` whose proceeds funded later activity, morphing `SELL` → `BUY`/`STOCK_SPLIT`, or other settlement sync that removes positive cash before a later negative balance.

**Legacy → cash-aware:** editing a transaction created while `cash_aware_enabled=false` after enable may attempt settlement creation on first `PUT`; fails with **400** shortfall if ledger funding is missing.

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
| Cash-aware (Cash-5) | Without `create_cash_deposits=true` + `cash_preview_confirmed=true`, import with cash shortfalls → **409** + preview body; legacy `cash_aware_enabled=false` unchanged |
| Confirmed import | Backend **recomputes** preview from CSV; creates `CASH_DEPOSIT` rows then transactions atomically; same-currency only; no FX |

#### CSV cash preview (Cash-5)

`POST /api/v1/transactions/import-csv/preview-cash`

- Same multipart `file` and optional `portfolio_id` as import.
- **200:** simulation only (no writes). Parse errors → `success`-style `row_errors` in preview response (HTTP 200).

```json
{
  "cash_aware": true,
  "can_import_without_deposits": false,
  "shortfalls": [
    {
      "portfolio_id": 5,
      "portfolio_name": "Default Portfolio",
      "date": "2026-06-04",
      "currency": "EUR",
      "required": 1005.0,
      "available_before": 0.0,
      "shortfall": 1005.0,
      "reason": "BUY AAPL"
    }
  ],
  "proposed_deposits": [
    {
      "portfolio_id": 5,
      "portfolio_name": "Default Portfolio",
      "date": "2026-06-04",
      "currency": "EUR",
      "amount": 1005.0,
      "source_of_funds": "CSV import cash deposit",
      "note": "Auto-proposed before CSV import"
    }
  ],
  "row_errors": [],
  "summary": {
    "rows": 10,
    "cash_aware_rows": 10,
    "proposed_deposit_count": 1,
    "total_shortfall_by_currency": [{ "currency": "EUR", "amount": 1005.0 }]
  }
}
```

Simulation: rows in chronological order; existing ledger + simulated deposits/settlements; BUY uses transaction currency only; MF BUY uses `paid_value` / `investment_date`; SELL credits proceeds; `STOCK_SPLIT` / `DIVIDEND` no cash effect.

**Import with confirmation:** `POST /api/v1/transactions/import-csv?create_cash_deposits=true&cash_preview_confirmed=true` — deposits from fresh preview, then import (all-or-nothing).

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

**Metrics:** FIFO remaining cost basis (`total_invested`), latest cached prices for `current_value`, `realized_pl` / `unrealized_pl` / `total_pl`, optional portfolio `xirr` (full-scope). **`current_value` includes cash** (Cash-6A). **Performance `value` / `twror` / `cumulative_return`** use cash-inclusive daily values and cash-aware external flows when `cash_aware_enabled=true` (Cash-6C.2); legacy portfolios keep investment-only TWROR/cumulative return.

**Portfolio `xirr` (Cash-6C.1):**

| Mode | External flows | Terminal value |
|------|----------------|----------------|
| `cash_aware_enabled=false` (legacy) | Stock/MF BUY/SELL (unchanged) | Holdings only (no cash in terminal) |
| `cash_aware_enabled=true` | `CASH_DEPOSIT`, `CASH_WITHDRAWAL`, unlinked `ADJUSTMENT`; settlements/transfers excluded | Holdings + cash in calculation currency |

Sign convention: deposits **negative**, withdrawals and terminal **positive** (investor perspective). Missing FX for a required cash-flow conversion → `xirr: null` and a warning (same pattern as cash in `current_value`).

**All Portfolios aggregation (`portfolio_scope=all`):** Headline monetary fields are summed per portfolio in `display_currency`. **`xirr`:** per-portfolio rules above; external flows converted to `display_currency` and **merged by date** (not summed); terminal = combined holdings + cash in `display_currency`. **Mixed mode:** cash-aware portfolios use ledger deposits/withdrawals; legacy portfolios use transaction BUY/SELL flows in the same merged series. `warnings` may include XIRR FX unavailability. When `include_timeseries=true`, daily series points are summed by date from child portfolio series in `display_currency`.

**Response (200 OK)** — see KPulla5 shape: `total_invested`, `current_value`, `realized_pl`, `unrealized_pl`, `total_pl`, `xirr`, `base_currency`, `display_currency`, `fx_status`, `timeseries[]`; optional `warnings` (e.g. oversell, cash FX partial); optional **`cash_summary`** (Cash-6A):

```json
"cash_summary": {
  "display_currency": "EUR",
  "total_display_value": 1200.0,
  "balances": [
    {
      "portfolio_id": 1,
      "portfolio_name": "Scalablefolio",
      "currency": "EUR",
      "native_balance": 1200.0,
      "display_value": 1200.0
    }
  ]
}
```

Cash balances are included in `current_value` regardless of `cash_aware_enabled` when ledger rows exist. Missing FX for a cash currency excludes that balance from the converted total and adds: `FX unavailable for one or more cash balances; portfolio value may be partial.`

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
- `value` — daily portfolio value in `display_currency` (investment + cash, Cash-6B).
- `twror` / `cumulative_return` — cash-inclusive daily values and cash-aware external flows when `cash_aware_enabled=true` (Cash-6C.2); legacy mode unchanged. Optional `warnings` (e.g. missing FX on external flows) may wrap `points` in `{"points", "warnings"}` like `metric=value`.
- `cumulative_return` — `((value + withdrawals - contributions) / contributions - 1) * 100`; `null` when contributions ≤ 0 or flows/FX unknown.
- `twror` — chain-linked period returns from Phase 6 `compute_twror_series`; `null` on first day or zero prior value. For `range != ALL`, TWROR is recomputed on the sliced window only (not rebased from full history).

**Benchmark:** Supported for `cumulative_return` and `twror` only. Returns `{ "metric", "series": [{ "name", "type", "data": [{ "date", "value" }] }], "warnings" }` with portfolio rebased to 0% at common anchor. `metric=value` ignores `benchmark` / `benchmarks` (list response). Missing benchmark prices → portfolio-only series + warning (not a hard failure).

**Range:** Never starts before first transaction date; clamped to inception when the requested window is earlier.

**Response (no benchmark):** JSON array of `{ "date", "value", "metric", "currency", "label": null }`.

---

## Analytics performance metrics (Metric Sheet)

Read paths use **cached DB data only** (same as summary/performance). Metrics are computed **on query**; MVP does not store derived analytics rows. Return values are **fractions** (e.g. `0.10` = 10%); UI may multiply by 100.

**Currency field:** `currency` is the valuation/display currency context for the portfolio scope (same as summary/performance). Return and risk ratios are dimensionless fractions — they are **not** currency amounts and are not converted like monetary fields.

**Return metrics (`metrics.return`):**
- `cumulative_return` — terminal money-weighted return for the selected `range`, same formula as `GET /portfolio/performance?metric=cumulative_return` (fraction; UI × 100).
- `cagr` — compound annual growth rate from that terminal cumulative return and calendar span (`range.start` → `range.end`); not TWROR.
- `twror` — terminal chain-linked TWROR for the range (matches `GET /portfolio/performance?metric=twror`).
- `xirr` — full-scope money-weighted IRR from `portfolios/xirr_service` (same as summary; `xirr_scope: "full_scope"`).

Risk/drawdown/period stats still use TWROR-style daily returns from values and external flows.

**All Portfolios value series:** `GET /portfolio/performance` with `portfolio_scope=all` and `metric=value` builds per-portfolio daily value series (each in its own portfolio base), converts each to `display_currency`, adds scope cash converted per day, then aggregates — matching `GET /portfolio/summary` all-scope aggregation. The last valid `metric=value` point should equal `current_value` when display currency is set.

When cash FX is partial, `metric=value` may return `{"points": [...], "warnings": ["FX unavailable for one or more cash balances; value history may be partial."]}` instead of a bare array.

**All Portfolios return metrics:** For `portfolio_scope=all`, `metric=cumulative_return` and `metric=twror` use the same aggregated display-currency value series. External cash flows are built per portfolio in portfolio base, converted to `display_currency` on each flow date (7-day FX fill), then aggregated by date. **All-scope TWROR** is computed from this aggregated display-currency value and external cash-flow series. Single-portfolio scopes still use portfolio-base value/flow series.

**Cash-only + display currency:** When there are no investments, returns are ~0 only if native cash currencies match `display_currency` (or FX to display is flat). Multi-currency cash with `display_currency` different from a cash currency shows non-zero TWROR/cumulative return/XIRR from cached FX movement on the cash leg — expected; see `docs/cash-ledger.md` § Cash-aware TWROR.

**Range vs XIRR:** Most metrics are computed over the selected `range` window (daily returns sliced from `range.start`). **XIRR** is an exception: it is always **full-scope** (inception through today), matching `GET /portfolio/summary`. The response includes `metrics.return.xirr_scope: "full_scope"` so clients can distinguish range-based stats from money-weighted IRR.

**Stock splits:** Daily value series uses split-adjusted FIFO quantities (`build_split_adjusted_lot_snapshots`). Cached stock `HistoricalPrice` rows must be split-adjusted (yfinance **Adj Close** from `make sync-prices`). Raw nominal pre-split prices are **unsupported** for Metric Sheet analytics; responses include a `warnings` entry when split-date valuation drops match the split factor (likely raw prices).

### Implemented: `GET /api/v1/analytics/performance-metrics` (Phase 5)

Portfolio-level Quantitative Statistics. Wired in `analytics/services.py`, `analytics/views.py`.

### Common query parameters (all analytics endpoints)

| Param | Default | Notes |
|-------|---------|--------|
| `range` | `1Y` | Same codes as performance: `7D`, `30D`, `YTD`, `1Y`, `3Y`, `5Y`, `ALL` |
| `display_currency` | settings / EUR | `EUR`, `USD`, `INR`, `GBP`, `CHF` |
| `benchmark` | — | Optional index symbol for beta, alpha, correlation |
| `portfolio_scope` | `all` | Portfolio-level endpoints only |
| `portfolio_id` | — | Single active portfolio |

Validation mirrors performance/summary (400/404/422). Response includes `warnings: string[]` for data-quality issues, including: missing cached stock prices (`Cached prices are missing for one or more dates…`), missing MF NAVs (`No cached NAV is available…`; suggests NAV sync), stale MF NAVs (`Latest cached NAV is older than 5 days…`; warns only when latest cached NAV is more than 5 calendar days older than the valuation end date — weekend/holiday gaps without forward-fill from a recent NAV do not trigger this), FX gaps, benchmark coverage, split-adjusted price inconsistency, or insufficient history. Generic fallback when values are wholly unavailable remains.

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
  "drawdown_series": [
    { "date": "2026-01-02", "drawdown": 0.0 },
    { "date": "2026-01-03", "drawdown": -0.012 }
  ],
  "drawdown_periods": {
    "worst": [
      {
        "rank": 1,
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

* `periodic_returns.monthly`: compounded fractional returns from daily series in the selected range (`resample_monthly_returns`); days with `null` daily return are skipped.
* `periodic_returns.yearly`: **Calendar-Year Return** — cash-flow-adjusted daily returns (TWROR-style `period_return` from values and external flows) compounded within each calendar year (`resample_yearly_returns`). **Not** simple start-vs-end portfolio value change. Frontend label: **Calendar-Year Return**; helper copy: *Cash-flow adjusted return using daily TWROR.*
* `drawdown_series` (Phase 13B): running drawdown fractions from the same daily return series (`drawdown_series` in `finance/drawdowns.py`); `drawdown` is 0 or negative (fraction, not percent). One point per date with a computed drawdown; empty array when history is insufficient.
* `drawdown_periods.worst`: up to 10 episodes ranked by severity (`worst_drawdown_periods` in `finance/drawdowns.py`); `rank` 1 = deepest drawdown; `drawdown` is a fraction (not percent). Empty arrays when history is insufficient; no extra warnings beyond existing Metric Sheet warnings.

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

Compare API metrics are computed over **common overlapping dates only** (exact date intersection of non-`None` daily returns; no forward-fill). Each subject gets aligned-window Metric Sheet metrics (economic cumulative return, CAGR, TWROR, risk) plus optional per-subject benchmark block. **XIRR** remains full-scope per subject (`xirr_scope: "full_scope"`). `normalized_series` rebases cumulative fractional returns to `0` on the first common date.

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
      "drawdown_series": [],
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

When `common_point_count < 2`, subject metrics are null, `periodic_returns` / `drawdown_periods` / `drawdown_series` are empty arrays, and a global insufficient-overlap warning is included. Per-subject periodic returns, drawdown series, and drawdown periods use the **aligned common-window** daily returns (not each asset’s independent full history). MF compare reuses asset Metric Sheet rules (single folio auto-resolved; multiple folios → **400** on asset resolution, same as asset endpoint — no per-subject `folio_number` in compare query yet).

---

## Cash Ledger

Full design: [cash-ledger.md](./cash-ledger.md) · agent rules: [.cursor/rules/320-cash-ledger.mdc](../.cursor/rules/320-cash-ledger.mdc). **Auth:** authenticated session; data limited to the current user’s active portfolios. Scope rules match holdings/summary (`portfolio_scope=all` default; cannot combine with `portfolio_id` → **422**; unknown/inactive/not-owned `portfolio_id` → **404**).

### Cash API surface (implemented vs planned)

| Method | Path | Notes |
|--------|------|--------|
| GET | `/api/v1/cash/balances` | Native currency balances; no display-currency conversion in read path |
| GET | `/api/v1/cash/ledger` | Paginated ledger items |
| POST | `/api/v1/cash/deposits` | Manual `CASH_DEPOSIT` |
| POST | `/api/v1/cash/withdrawals` | Manual `CASH_WITHDRAWAL`; 400 shortfall if insufficient |
| PUT | `/api/v1/cash/ledger/{id}` | Manual rows only; 409 if linked/system or future-impact violation |
| DELETE | `/api/v1/cash/ledger/{id}` | Manual rows only; same protections as PUT |
| POST | `/api/v1/cash/transfers` | **Done** (Cash-8A/8B) — same- or cross-currency portfolio transfer |
| POST | `/api/v1/cash/bulk-entries/preview` | **Done** (Cash-7D) — schedule preview |
| POST | `/api/v1/cash/bulk-entries/apply` | **Done** (Cash-7D) — confirmed bulk manual entries |
| POST | `/api/v1/transactions/import-csv/preview-cash` | **Done** (Cash-5) — CSV cash simulation; no writes |

**Settlement rows** (`BUY_SETTLEMENT`, `SELL_SETTLEMENT`, `TAX_WITHHELD`, transfer legs, FX legs) are **system-protected** — created/updated/deleted only via `/api/v1/transactions` or `/api/v1/cash/transfers`, not via manual cash ledger edit.

**No implicit FX:** BUY sufficiency and withdrawal checks use **same-currency** ledger cash only. No `FX_CONVERSION_*` write endpoint in current phase.

**Cash-aware transactions:** When `portfolio.cash_aware_enabled=true`, stock/MF `POST`/`PUT`/`DELETE` on `/api/v1/transactions` maintain linked settlements atomically (see Cash-4A below).

### Implemented (Cash-2) — read APIs

#### `GET /api/v1/cash/balances`

Query: `portfolio_scope`, `portfolio_id`, optional `as_of_date` (YYYY-MM-DD; default today), optional `currency` (native filter; unsupported → **400**).

**All scope (200):**
```json
{
  "portfolio_scope": "all",
  "as_of_date": "2026-06-04",
  "balances": [
    {
      "portfolio_id": 1,
      "portfolio_name": "Scalablefolio",
      "currency": "EUR",
      "balance": 12500.0
    }
  ],
  "totals_by_currency": [{ "currency": "EUR", "balance": 12500.0 }]
}
```

**Single portfolio (200):**
```json
{
  "portfolio_id": 1,
  "portfolio_name": "Scalablefolio",
  "as_of_date": "2026-06-04",
  "balances": [{ "currency": "EUR", "balance": 12500.0 }]
}
```

- Native currency only (no display-currency conversion in Cash-2).
- Omits `(portfolio, currency)` pairs with **no ledger rows** in scope; zero balance included when rows exist.
- No ledger rows → empty `balances` / `totals_by_currency` (not an error).
- `as_of_date` includes entries with `date <= as_of_date`.

#### `GET /api/v1/cash/ledger`

Query: `portfolio_scope`, `portfolio_id`, `currency`, `entry_type`, `date_from`, `date_to`, `page` (default 1), `page_size` (default 20).

- Ordered by `date` desc, `id` desc.
- `date_from > date_to` → **400**; unsupported `currency` / `entry_type` → **400**.
- Response: `{ "items", "total", "page", "page_size", "pages" }` — each item includes `portfolio_id`, `portfolio_name`, `amount` (signed float), `linked_transaction_id`, `transfer_group_id`, timestamps.

#### Portfolios — `cash_aware_enabled` (Cash-2, Cash-4A.1)

`GET/POST/PUT/DELETE /api/v1/portfolios` responses include `cash_aware_enabled` (boolean).

| Context | Default / behavior |
|---------|------------------|
| **Existing DB rows** | Unchanged (`false` unless previously set `true`) |
| **`POST` omitted field** | **`true`** (Cash-4A.1) |
| **`POST` explicit `false`** | Allowed — legacy-mode portfolio |
| **Registration default portfolio** | Created with `true` |
| **`PUT`** | May set `cash_aware_enabled` (e.g. enable tester portfolio without bulk migration) |

When `true`, Cash-4A BUY/SELL settlement rules apply. Portfolio-level XIRR uses cash ledger external flows (Cash-6C.1). TWROR/cumulative_return cash integration is Cash-6C.2+.

**Portfolio `id`:** globally unique internal primary key (FK target for transactions, cash ledger, etc.). Not per-user sequential `id=1`. Optional future UI: user-facing `portfolio_number` / `display_order` — not in Cash-4A.1.

### Implemented (Cash-3A) — manual deposit / withdrawal

#### `POST /api/v1/cash/deposits` — **201 Created**

**Request (JSON):**
```json
{
  "portfolio_id": 1,
  "date": "2026-06-04",
  "currency": "EUR",
  "amount": 1000.00,
  "source_of_funds": "Bank transfer",
  "note": "Monthly contribution"
}
```

| Field | Required | Notes |
|-------|----------|--------|
| `portfolio_id` | Yes | Active portfolio owned by current user |
| `date` | Yes | `YYYY-MM-DD` |
| `currency` | Yes | Must be in `SUPPORTED_CASH_CURRENCIES` (20 codes) |
| `amount` | Yes | Strictly positive in request; stored signed **positive** |
| `source_of_funds` | No | Optional string |
| `note` | No | Optional string |

- `entry_type = CASH_DEPOSIT`; no `linked_transaction` / `transfer_group`.
- Allowed when `cash_aware_enabled` is `false`.
- Native currency only (no display-currency conversion).

**Response:** single ledger item (same shape as `GET /cash/ledger` items).

**Errors:** `400` validation (zero/negative amount, unsupported currency, invalid date); `404` unknown/inactive/not-owned portfolio; `401`/`403` unauthenticated.

#### `POST /api/v1/cash/withdrawals` — **201 Created**

**Request (JSON):**
```json
{
  "portfolio_id": 1,
  "date": "2026-06-04",
  "currency": "EUR",
  "amount": 500.00,
  "note": "Withdrawal to bank"
}
```

- Request `amount` strictly positive; stored signed **negative** (`CASH_WITHDRAWAL`).
- **Insufficient cash (400):** balance for `(portfolio, currency)` as of `date` (entries with `date <= withdrawal date`) must cover withdrawal. Response:
```json
{
  "detail": "Insufficient cash balance for withdrawal.",
  "required": 500.0,
  "available": 100.0,
  "shortfall": 400.0,
  "currency": "EUR"
}
```
- No FX conversion for sufficiency checks (same currency only).

#### `POST /api/v1/cash/transfers` — **201 Created** (Cash-8A / Cash-8B)

Portfolio-to-portfolio transfer. **No automatic FX lookup** — the user enters what was sent and what was received.

**Same-currency request (legacy, Cash-8A):**
```json
{
  "source_portfolio_id": 1,
  "target_portfolio_id": 2,
  "date": "2026-06-06",
  "currency": "EUR",
  "amount": 1000.0,
  "note": "Move cash"
}
```

**Cross-currency request (Cash-8B):**
```json
{
  "source_portfolio_id": 1,
  "target_portfolio_id": 2,
  "date": "2026-06-06",
  "source_currency": "USD",
  "source_amount": 1000.0,
  "target_currency": "EUR",
  "target_amount": 920.0,
  "note": "Broker conversion"
}
```

Use **either** `currency` + `amount` **or** the four explicit fields — not both.

| Field | Required | Notes |
|-------|----------|--------|
| `source_portfolio_id` | Yes | Active; must differ from target |
| `target_portfolio_id` | Yes | Active; same user |
| `date` | Yes | `YYYY-MM-DD` |
| `currency` + `amount` | Legacy | Same-currency only; normalized to source/target fields |
| `source_currency` / `source_amount` | Cross-currency | Supported code; strictly positive |
| `target_currency` / `target_amount` | Cross-currency | Supported code; strictly positive; user-entered received amount |
| `note` | No | Copied to group and both ledger rows |

When `source_currency == target_currency`, `source_amount` must equal `target_amount`.

**Response (201):**
```json
{
  "transfer_group_id": 10,
  "date": "2026-06-06",
  "source_portfolio_id": 1,
  "target_portfolio_id": 2,
  "source_currency": "USD",
  "source_amount": 1000.0,
  "target_currency": "EUR",
  "target_amount": 920.0,
  "implied_rate": 0.92,
  "currency": "EUR",
  "amount": 1000.0,
  "entries": []
}
```

`implied_rate` = `target_amount / source_amount` (informational only; not used for valuation). Legacy `currency` / `amount` included when both legs share one currency.

`entries`: `TRANSFER_OUT` in source currency (−`source_amount`), `TRANSFER_IN` in target currency (+`target_amount`).

**Errors:** `400` validation; insufficient **source-currency** cash (shortfall payload); `404` portfolio; `409` future-impact on source; `401`/`403` unauthenticated.

**Performance:** single-portfolio external flows per leg; same-currency all-scope nets to zero; cross-currency all-scope reflects user-entered amounts in display currency (not forced neutral).

### Implemented (Cash-3D / Cash-4D) — edit / delete manual ledger entries

#### `PUT /api/v1/cash/ledger/{id}` — **200 OK**

**Allowed only** for manual entries: `CASH_DEPOSIT` or `CASH_WITHDRAWAL` with `linked_transaction_id` and `transfer_group_id` both null. Portfolio cannot change in this phase.

**Request (JSON):** same editable fields as deposit/withdrawal writes (no `portfolio_id`):

| Field | Required | Notes |
|-------|----------|--------|
| `date` | Yes | `YYYY-MM-DD` |
| `currency` | Yes | Supported cash currency |
| `amount` | Yes | Strictly positive in request; stored signed by `entry_type` |
| `source_of_funds` | No | Optional |
| `note` | No | Optional |

- `entry_type` is immutable.
- Withdrawal updates validate sufficiency excluding the row being edited.
- **Future impact (Cash-4D):** simulates running balance from the earliest affected date; rejects if any later day would be negative in the affected currency stream(s). Currency change validates **both** old and new currency ledgers.

**Response:** updated ledger item (ledger item shape).

**Errors:** `400` validation / insufficient cash on withdrawal edit; `404` not found or not owned; `409` linked/system entry **or** future negative balance (see below); `401`/`403` unauthenticated.

#### `DELETE /api/v1/cash/ledger/{id}` — **204 No Content**

Same manual-entry rules as `PUT`. Blocked when any later ledger date would have negative balance in that portfolio/currency. **No cascade delete** of linked asset transactions or settlements.

**Errors:** `404` not found; `409` protected entry or future negative balance.

#### Future impact error (Cash-4D) — **409 Conflict**

When edit/delete would make a later running balance negative:

```json
{
  "detail": "This cash change would make future cash balance negative.",
  "currency": "EUR",
  "earliest_negative_date": "2026-06-05",
  "lowest_balance": -500.0,
  "affected_entries": [
    {
      "id": 123,
      "date": "2026-06-05",
      "entry_type": "BUY_SETTLEMENT",
      "amount": -1000.0,
      "linked_transaction_id": 456,
      "asset_symbol": "AAPL"
    }
  ]
}
```

Up to **10** `affected_entries` from `earliest_negative_date` onward. Client must not recompute balances; user resolves manually (add deposit, edit/delete later transactions). Cascade delete deferred.

**Protected entry detail:** `"Linked or system-generated cash entries cannot be edited directly."`

### Removed — Cash-7A/7B shortfall backfill APIs

`POST /api/v1/cash/backfill-preview` and `POST /api/v1/cash/backfill-apply` were **removed**. Historical funding uses manual `POST /cash/deposits` / `withdrawals` or **Bulk Cash Entries** (`bulk-entries/preview` + `apply`).

### Implemented (Cash-7D) — bulk cash entries schedule

User-defined manual `CASH_DEPOSIT` / `CASH_WITHDRAWAL` schedules (opening balance, monthly contributions, periodic withdrawals). Use actual amounts and dates.

#### `POST /api/v1/cash/bulk-entries/preview`

**Request:**
```json
{
  "portfolio_id": 1,
  "entry_type": "CASH_DEPOSIT",
  "currency": "EUR",
  "amount": 900,
  "start_date": "2022-06-01",
  "end_date": "2022-12-01",
  "frequency": "monthly",
  "source_of_funds": "Monthly contribution",
  "note": "Historical contribution"
}
```

| Field | Rules |
|-------|--------|
| `entry_type` | `CASH_DEPOSIT` or `CASH_WITHDRAWAL` |
| `frequency` | `once` (uses `start_date` only; `end_date` optional) or `monthly` (`end_date` required, ≥ `start_date`) |
| `amount` | Positive decimal |
| `currency` | Supported native currency |

**Response (200):** `portfolio_id`, `entry_count`, `entries[]` (`date`, `currency`, `entry_type`, `amount`, `source_of_funds`, `note`), `total_by_currency[]`, `warnings[]` (duplicate skip hints; withdrawal negative-balance preview).

**Errors:** **400** invalid range/frequency/currency; **404** portfolio not owned.

#### `POST /api/v1/cash/bulk-entries/apply`

Same body as preview plus **`confirmed`: true** (required).

**Rules:**
1. Backend **recomputes** schedule from request — does not trust client preview rows.
2. Creates manual ledger rows inside `transaction.atomic()`.
3. Skips duplicate identical manual rows (same portfolio/date/currency/amount/source/note/type); reports `skipped_existing_count`.
4. **Withdrawals:** reject **400** if schedule would make running balance negative on any date.
5. No `BUY_SETTLEMENT` / `SELL_SETTLEMENT`; no transaction mutation; no auto `cash_aware_enabled`.
6. Max **500** entries per schedule.

**Response (200):** `created_count`, `skipped_existing_count`, `created_entries[]`, `summary.total_created_by_currency`, `warnings[]`.

### Implemented (Cash-4A) — cash-aware BUY/SELL settlements

When `portfolio.cash_aware_enabled` is **true**, `POST` / `PUT` / `DELETE` `/api/v1/transactions` (stock and mutual fund) enforce cash and maintain linked ledger rows. Legacy portfolios (`cash_aware_enabled=false`) are unchanged.

**Stock / ETF**

| Type | Settlement | Cash check |
|------|------------|------------|
| `BUY` | `BUY_SETTLEMENT` (negative) = `quantity × price_per_share + fees` on `transaction.date` | Required cash in `transaction.currency` as of transaction date |
| `SELL` | `SELL_SETTLEMENT` (positive) = calculated proceeds; optional `TAX_WITHHELD` (negative) when `actual_cash_received` &lt; calculated | Reject if proceeds ≤ 0; reject if actual &gt; calculated |
| `STOCK_SPLIT` | None | None |
| `DIVIDEND` | None (deferred) | None |

**Mutual fund**

| Type | Settlement amount | Ledger `date` |
|------|-------------------|---------------|
| `BUY` | `paid_value` (not qty × NAV) | `investment_date` |
| `SELL` | `paid_value` when &gt; 0; else `units_allotted × nav − fees` | `investment_date` |

**Insufficient cash on BUY (400):**

```json
{
  "detail": "Insufficient cash balance for purchase.",
  "required": 1005.0,
  "available": 500.0,
  "shortfall": 505.0,
  "currency": "EUR"
}
```

- Atomic: transaction and settlement succeed or fail together.
- `DELETE` removes linked settlement rows first (then transaction). Deleting SELL settlements (`SELL_SETTLEMENT` + `TAX_WITHHELD`) is blocked if net removal would make later balances negative.
- SELL write body (optional): `actual_cash_received` (positive), `settlement_note` (text). Response includes both fields.
- Linked settlements are not editable via `PUT/DELETE /cash/ledger/{id}` (**409**).

**Same-currency funding (Cash-4E):** `available` and `shortfall` reflect **only** ledger cash in `currency` (the transaction currency). Other currencies are ignored for sufficiency — e.g. USD deposits do not fund a EUR BUY. No implicit FX conversion; no `FX_CONVERSION_*` APIs in this phase.

**Not in Cash-4A:** CSV cash preview, summary/performance/allocation, transfers, bulk auto-enable of existing portfolios.

**Cash-4A.1:** New portfolios and registration defaults use `cash_aware_enabled=true`; existing rows are not migrated.

**Summary/performance/allocation (Cash-6):** Cash-6A implemented on summary `current_value` and holdings `allocation`; performance/value history/TWROR/XIRR deferred to Cash-6B/6C. No breaking changes to stock/MF fields.

---

## Fixed Deposits — Bank cash ledger (implemented — FD-ACC-1)

Full design: [fixed-deposits-accounting.md](./fixed-deposits-accounting.md).

| Method | Path | Notes |
|--------|------|--------|
| GET | `/api/v1/cash-movements` | **Done** — paginated; filter `bank_account_id` |
| POST | `/api/v1/cash-movements` | **Done** — `MANUAL_DEPOSIT`, `MANUAL_WITHDRAWAL`, `ADJUSTMENT` only |
| GET | `/api/v1/cash-movements/{id}` | **Done** |
| PUT/PATCH/DELETE | `/api/v1/cash-movements/{id}` | **405** — immutable ledger in FD-ACC-1 |
| POST | `/api/v1/bank-accounts/{id}/seed-opening-balance` | **Done** — opt-in opening balance seed |

**Bank account response extensions:** `has_ledger_entries`, `opening_balance_seeded`, `balance_source` (`manual` \| `ledger`).

**PUT `/bank-accounts/{id}`:** rejects `current_balance` when ledger exists (**400**).

**Deferred (FD-ACC-9+):** reversal endpoint, `TRANSFER_IN`/`OUT` manual API, via-bank renewal path. **FD-ACC-7/8 done:** opt-in bank cash in portfolio summary/holdings/allocation/performance/returns.

### FD interest payments (FD-ACC-4)

| Method | Path | Notes |
|--------|------|--------|
| GET | `/api/v1/fixed-deposits/{id}/interest-payments` | **Done** — list payments for FD (user-scoped) |
| POST | `/api/v1/fixed-deposits/{id}/interest-payments` | **Done** — `{ payment_date, gross_interest, tax_withheld?, comment? }`; atomically creates `FixedDepositInterestPayment` + `FD_INTEREST` CREDIT for **net**; optional `warning` for COMPOUNDED FD |
| GET | `/api/v1/fixed-deposit-interest-payments/{payment_id}` | **Done** |
| PUT/PATCH/DELETE | `/api/v1/fixed-deposit-interest-payments/{payment_id}` | **405** — immutable; corrections via future ADJUSTMENT/reversal |

**Rejected:** interest payment on `CLOSED` FD (**400**). `ACTIVE` and `MATURED` allowed. Bank account taken from FD (not client-supplied).

**Portfolio:** FD principal summary unchanged; bank ledger credit does not increase portfolio `current_value`.

### FD maturity / closure settlement (FD-ACC-5)

| Method | Path | Notes |
|--------|------|--------|
| POST | `/api/v1/fixed-deposits/{id}/mark-matured` | **Done** — `ACTIVE` → `MATURED`; no cash movements; idempotent if already `MATURED` |
| POST | `/api/v1/fixed-deposits/{id}/settle` | **Done** — `{ settlement_type, settlement_date, principal_returned?, gross_interest?, tax_withheld?, comment? }` |
| GET | `/api/v1/fixed-deposits/{id}/settlements` | **Done** |
| GET | `/api/v1/fixed-deposit-settlements/{settlement_id}` | **Done** |
| PUT/PATCH/DELETE | `/api/v1/fixed-deposit-settlements/{settlement_id}` | **405** — immutable |

**Outcomes:** `MATURITY` → `MATURED_SETTLED`; `CLOSURE` → `CLOSED`. Zero net interest → no interest movement. Portfolio summary excludes settled principal; included bank cash rises when `include_in_portfolio_value=true` (FD-ACC-7).

### FD renewal (FD-ACC-6)

| Method | Path | Notes |
|--------|------|--------|
| POST | `/api/v1/fixed-deposits/{id}/renew` | **Done** — settle old FD + create renewed FD atomically |

**Request:** `renewal_date`, `new_deposit_account_number`, `new_principal_amount`, `new_interest_rate_percent`, `new_interest_payout_frequency`, `new_maturity_date`, optional `new_institution_name`, `new_investment_date` (defaults `renewal_date`), `nominee_name`, `comment`, `gross_interest`, `tax_withheld`, `cash_payout_amount`, optional `direct_reinvest_amount` (defaults `new_principal_amount`).

**Response (201):** `renewal_id`, `old_fixed_deposit`, `new_fixed_deposit`, `settlement_id`, `direct_reinvest_amount`, `cash_payout_amount`, `gross_interest`, `tax_withheld`, `net_interest`, `cash_movement_ids`, `currency`.

**Accounting:** Direct rollover — no bank movement for reinvested principal; renewed FD has no `FD_OPENING` debit. `cash_payout_amount` → `FD_MATURITY_PRINCIPAL` CREDIT; net final interest → `FD_MATURITY_INTEREST` CREDIT. Normal `POST /fixed-deposits` still creates `FD_OPENING` debit.

**Rejected:** `CLOSED`/`MATURED_SETTLED` FD; already renewed FD; foreign FD (**404**); invalid dates/amounts (**400**).

### FD create — mandatory opening debit (FD-ACC-3)

| Method | Path | Notes |
|--------|------|--------|
| POST | `/api/v1/fixed-deposits` | **Done** — atomically creates `FD_OPENING` `CashMovement` (SYSTEM DEBIT); **400** on insufficient bank balance with `required`, `available`, `shortfall`, `currency` |

**FD response extensions:** `has_opening_cash_movement`, `opening_cash_movement_id`.

**PUT `/fixed-deposits/{id}`:** rejects changes to `principal_amount`, `bank_account_id`, `currency`, `investment_date`, `portfolio_id` when opening movement exists (**400**). Legacy FDs without opening movement remain fully editable.

**Lifecycle:** `ACTIVE` → `MATURED` (mark-matured) → `MATURED_SETTLED` or `CLOSED` (settle) — **implemented FD-ACC-5**.

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

Response includes **`holdings`** (investment rows only — stocks/MF) and **`allocation`** (Cash-6A: active investment slices plus cash rows). Optional **`warnings`** when cash FX conversion is partial.

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

**Cash allocation rows (Cash-6A)** — in `allocation` only, not in `holdings`:

| Field | Notes |
|-------|-------|
| `asset_type` | `CASH` |
| `asset_symbol` | `Cash EUR`, `Cash INR`, etc. |
| `primary_asset_class` | `CASH` |
| `is_cash` | `true` |
| `native_currency` | Ledger currency |
| `native_balance` | Sum in native currency for scope |
| `current_value` | Display-currency value (backend-computed) |
| `currency` | Requested `display_currency` |

Compare and Asset Metric Sheet must exclude cash rows (`is_cash` / `asset_type=CASH`).

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
| XIRR | Portfolio: `compute_scope_xirr` (legacy BUY/SELL or cash-aware ledger per `cash_aware_enabled`). Asset-level: stock/MF BUY/SELL unchanged (`calculate_xirr` / `merge_portfolio_xirr`) |
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
