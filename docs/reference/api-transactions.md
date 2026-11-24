# API — transactions

Transaction list, create, update, delete, and CSV import. Deep spec: [api-design.md](../api-design.md) § Transactions.

**Base URL:** `http://127.0.0.1:8000/api/v1` · **Auth:** Session + CSRF for writes — [API authentication](api-auth.md)

---

## `GET /transactions`

| | |
|---|---|
| **Auth** | Session |
| **Purpose** | Paginated transaction list |

Mutual-fund `nav_verification_status` and optional message reflect the current
exact-date NAV cache, not just the saved import-time snapshot. Reads do not call
providers or modify transactions. Missing dates and mismatches remain warnings.

### Query parameters

| Param | Default | Notes |
|-------|---------|-------|
| `page` | `1` | Page number |
| `page_size` | `20` | Rows per page |
| `portfolio_scope` | all portfolios | `all` or omit with `portfolio_id` |
| `portfolio_id` | — | Single active portfolio |
| `symbols` | — | Comma-separated symbols |
| `date_from` / `date_to` | — | `YYYY-MM-DD` filters |

### Example request

```bash
curl -s -b cookies.txt \
  "http://127.0.0.1:8000/api/v1/transactions?portfolio_id=1&page_size=5"
```

### Example response (200)

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
      "currency": "USD"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 5,
  "pages": 1
}
```

### Common errors

| Status | When |
|--------|------|
| `400` | Invalid dates or `date_from > date_to` |
| `401` | Not logged in |
| `404` | Unknown `portfolio_id` |
| `422` | `portfolio_scope=all` combined with `portfolio_id` |

---

## `POST /transactions`

| | |
|---|---|
| **Auth** | Session + CSRF |
| **Purpose** | Create BUY / SELL / DIVIDEND / STOCK_SPLIT (and MF fields when applicable) |

**Expected:** `201` with created row.

**Cash-aware portfolios:** `400` with `required`, `available`, `shortfall` when BUY exceeds cash.

### Mutual-fund writes (`POST` and `PUT /transactions/{id}`)

MF create, update, and CSV import require a **positive INR cached NAV for the
exact `scheme_code` + `nav_date`**, typed `MUTUAL_FUND`. The backend stores this
canonical NAV in both `nav` and `price_per_share`; a supplied `nav` cannot override
it. No exact cache means `400` for transaction `POST`/`PUT`; CSV row failures
retain HTTP `200` with `success: false` (see import below). Explicitly refresh
NAV history, then retry.
There is no adjacent-date fallback, date substitution, or provider read during
validation. A refresh does not guarantee that the provider has that date.

Keep statement `units_allotted`, `fees`, `market_value`, and `paid_value` unchanged
when correcting NAV. Do not recompute them to make `nav × units` agree;
`VALUE_MISMATCH` remains a warning when the difference exceeds 1 INR.
Existing history is not silently rewritten by reads or refreshes.

**Cash exception:** Only an existing BUY whose canonical NAV actually changes,
with no linked settlement/cash rows and **all** statement/cash fields unchanged,
skips historical settlement backfill. This includes unchanged portfolio, scheme,
folio, type, currency, both dates, units, fees, market/paid values,
`actual_cash_received`, and `settlement_note`. No-op updates, other edits, creates,
and SELLs retain normal cash validation and settlement handling. See
[cash settlement rules](../cash-ledger.md#8-cash-aware-buysell-settlements-cash-4a-implemented).

---

## `GET /nav/lookup`

**Auth:** Authenticated session. **Purpose:** Exact-date DB-only lookup; no writes
or provider calls. Full path: `/api/v1/nav/lookup`.

| Query parameter | Required | Format |
|-----------------|----------|--------|
| `scheme_code` | Yes | AMFI scheme code |
| `nav_date` | Yes | `YYYY-MM-DD` |

Example: `GET /api/v1/nav/lookup?scheme_code=120503&nav_date=2026-11-20`.

**200 (available; illustrative):**

```json
{"scheme_code":"120503","nav_date":"2026-11-20","nav":"123.456789","status":"available"}
```

**200 (missing, including non-positive or non-INR cache rows):**

```json
{"scheme_code":"120503","nav_date":"2026-11-20","nav":null,"status":"missing"}
```

`nav` is a decimal **string** or `null`, never a JSON number. Missing or invalid
query parameters return `400`; unauthenticated access is rejected.

---

## `POST /nav/fetch-missing`

**Auth:** Session + CSRF. **Purpose:** Explicitly fetch one exact-date NAV from
MFAPI after `GET /nav/lookup` reported `missing`. Never creates or edits
transactions or cash. Full path: `/api/v1/nav/fetch-missing`.

**Body:** `{"scheme_code":"120503","nav_date":"2026-11-20"}` (numeric AMFI code;
`YYYY-MM-DD`, not later than tomorrow UTC).

The backend rechecks the exact-date cache first; a usable cached NAV always wins,
even during cooldown. Otherwise it requests only that scheme/date and caches only
one positive exact-date INR observation. Adjacent dates are never cached.

**200 (illustrative):**

```json
{"scheme_code":"120503","nav_date":"2026-11-20","outcome":"fetched","nav":"123.456789",
 "status":"available","retry_after_seconds":null,"failure_category":null,"attempt_id":null}
```

| `outcome` | `status` | Meaning |
|-----------|----------|---------|
| `cache_hit` | `available` | Already cached; no provider call |
| `fetched` | `available` | Fetched and cached the exact date |
| `date_unavailable` | `missing` | Provider has no NAV for that exact date |
| `timeout` | `missing` | Provider timed out |
| `provider_failure` | `missing` | Provider error, wrong scheme, or invalid/zero/non-INR row |
| `in_flight` | `missing` | Another request is fetching this scheme/date |
| `cooldown` | `missing` | A recent attempt failed; wait `retry_after_seconds` |

For unsuccessful outcomes `failure_category` equals `outcome`. Failed attempts
start a 60-second cooldown and return an opaque `attempt_id` bound to the
requesting user, scheme, and date (`cooldown` returns it only to that user).
In-flight claims expire after 30 seconds. **400:** invalid body. **409:** a
non-mutual-fund price row already occupies that symbol/date. Database errors are
server errors, never a cache miss.

---

## `POST /transactions/import-csv`

| | |
|---|---|
| **Auth** | Session + CSRF |
| **Body** | `multipart/form-data` field `file` |
| **Query** | Optional `portfolio_id` |

**Expected:** HTTP `200` with `success: true` on success, or HTTP `200` with
`success: false`, `imported_count: 0`, and `errors: [{row, field, message}]`
for row validation failures (all-or-nothing), including missing exact-date MF NAV
cache. Request-level errors retain their existing HTTP statuses.

MF imports use the same strict cached-NAV write rule above. Missing exact-date
cache blocks import; cash-funding confirmation does not bypass NAV validation.

Formats: [CSV formats](csv-formats.md) · Tutorial: [Import stock transactions](../tutorials/import-stock-transactions.md)

---

## Related endpoints

| Method | Path | Notes |
|--------|------|-------|
| `GET` | `/transactions/filter-options` | Distinct symbols, types, date bounds |
| `PUT` | `/transactions/{id}` | Full update |
| `DELETE` | `/transactions/{id}` | Hard delete (`204`) |
| `POST` | `/transactions/import-csv/preview-cash` | Cash shortfall preview (no writes) |

## Next

- [Fixed deposits API](api-fixed-deposits.md)

## Related

- [Transactions source of truth](../concepts/transactions-source-of-truth.md) · [API reference](api-reference.md)
