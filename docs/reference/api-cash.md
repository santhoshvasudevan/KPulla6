# API — cash

Broker cash ledger, unified overview, and bank cash movements. Deep spec: [api-design.md](../api-design.md) · [cash-ledger.md](../cash-ledger.md).

**Base URL:** `http://127.0.0.1:8000/api/v1` · **Auth:** Session + CSRF for writes — [API authentication](api-auth.md)

---

## `GET /cash/overview`

| | |
|---|---|
| **Auth** | Session |
| **Purpose** | Broker + bank cash rows with `ledger_type` (preferred for Cash page) |

### Query parameters

| Param | Default | Notes |
|-------|---------|-------|
| `portfolio_scope` / `portfolio_id` | scope rules | Same as other portfolio APIs |
| `display_currency` | settings | Optional FX display |
| `include_unassigned` | `false` | Show ambiguous bank accounts |

### Example request

```bash
curl -s -b cookies.txt \
  "http://127.0.0.1:8000/api/v1/cash/overview?portfolio_scope=all"
```

### Example response shape (200)

```json
{
  "rows": [
    {
      "ledger_type": "BROKER_CASH",
      "portfolio_id": 1,
      "currency": "EUR",
      "native_balance": "1200.00"
    }
  ],
  "totals": {
    "broker_cash_display_value": 1200.0,
    "bank_cash_display_value": 0.0
  }
}
```

---

## `GET /cash/balances`

Native-currency broker balances (no display FX in read path). Used for broker-specific views.

---

## `GET /cash/ledger`

Paginated broker cash ledger entries.

| Param | Notes |
|-------|-------|
| `page`, `page_size` | Pagination |
| `portfolio_id` | Filter |

---

## `POST /cash/deposits` · `POST /cash/withdrawals`

Manual broker cash entries. **Expected:** `201` · `400` on withdrawal shortfall.

---

## Bank movements (`/cash-movements`)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/cash-movements` | List bank ledger movements |
| `POST` | `/cash-movements` | Create manual movement |
| `POST` | `/cash-movements/{id}/reverse` | Reverse movement |

Bank seed: `POST /bank-accounts/{id}/seed-balance` — see [api-design.md](../api-design.md).

---

## Common errors

| Status | When |
|--------|------|
| `400` | Insufficient cash, validation failure |
| `401` | Not logged in |
| `409` | Edit/delete would break linked or future balances |

## Next

- [Analytics API](api-analytics.md)

## Related

- [Cash ledger](../concepts/cash-ledger.md) · [Cash unification](../cash-unification.md)
