# API — transactions

Transaction list, create, update, delete, and CSV import. Deep spec: [api-design.md](../api-design.md) § Transactions.

**Base URL:** `http://127.0.0.1:8000/api/v1` · **Auth:** Session + CSRF for writes — [API authentication](api-auth.md)

---

## `GET /transactions`

| | |
|---|---|
| **Auth** | Session |
| **Purpose** | Paginated transaction list |

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

---

## `POST /transactions/import-csv`

| | |
|---|---|
| **Auth** | Session + CSRF |
| **Body** | `multipart/form-data` field `file` |
| **Query** | Optional `portfolio_id` |

**Expected:** `200` with `success: true` or `400` with row errors (all-or-nothing).

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
