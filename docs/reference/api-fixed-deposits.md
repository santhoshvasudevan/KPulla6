# API — fixed deposits

Fixed deposit CRUD, maturity estimates, and lifecycle actions. Deep spec: [api-design.md](../api-design.md) · [fixed-deposits.md](../fixed-deposits.md).

**Base URL:** `http://127.0.0.1:8000/api/v1` · **Auth:** Session + CSRF for writes — [API authentication](api-auth.md)

!!! note "Screenshot placeholder"
    **Shows:** FD holdings with maturity value badge and action strip.  
    **Backlog:** [fixed-deposits-holdings.png](../maintenance/docs-visual-backlog.md)

---

## `GET /fixed-deposits`

| | |
|---|---|
| **Auth** | Session |
| **Purpose** | List active FDs for portfolio scope |

### Query parameters

| Param | Notes |
|-------|-------|
| `portfolio_scope` | `all` (default) |
| `portfolio_id` | Single portfolio |

### Example request

```bash
curl -s -b cookies.txt \
  "http://127.0.0.1:8000/api/v1/fixed-deposits?portfolio_id=1"
```

### Example response shape (200)

```json
[
  {
    "id": 1,
    "principal_amount": "100000.00",
    "currency": "INR",
    "investment_date": "2024-01-01",
    "maturity_date": "2025-01-01",
    "expected_maturity_value": "108000.00",
    "maturity_value_source": "AUTO_ESTIMATE",
    "estimate_type": "COMPOUNDED_MATURITY"
  }
]
```

List responses include `resolve_maturity_display()` fields for legacy rows. See [fixed-deposits-accounting.md](../fixed-deposits-accounting.md).

---

## `GET /fixed-deposits/maturity-estimate`

| | |
|---|---|
| **Auth** | Session |
| **Purpose** | Read-only estimate preview (no DB write) |

### Query parameters

`principal_amount`, `interest_rate_percent`, `interest_payout_frequency`, `investment_date`, `maturity_date`

**Expected:** `estimate_type` of `COMPOUNDED_MATURITY` or `PAYOUT_INTEREST` with interest breakdown for payout FDs.

---

## `POST /fixed-deposits`

| | |
|---|---|
| **Auth** | Session + CSRF |
| **Purpose** | Create FD + `FD_OPENING` bank debit |

**Required:** `portfolio_id`, `bank_account_id`, principal, dates, rate.

**Expected:** `201` · `400` on insufficient bank balance at investment date.

---

## `PUT /fixed-deposits/{id}`

Updates metadata; after opening, principal/bank/currency/portfolio are locked. Investment date may sync the opening debit.

**Expected:** `200` · `400` if funding insufficient at new date.

---

## Related endpoints

| Method | Path | Notes |
|--------|------|-------|
| `DELETE` | `/fixed-deposits/{id}` | Soft deactivate (legacy / no-ledger) |
| `POST` | `/fixed-deposits/{id}/cancel` | Reverse opening debit |
| `POST` | `/fixed-deposits/{id}/interest-payments` | Record interest |
| `POST` | `/fixed-deposits/{id}/settle` | Maturity settlement |

## Next

- [Cash API](api-cash.md)

## Related

- [Fixed deposits / debt](../concepts/fixed-deposits-debt.md) · [API reference](api-reference.md)
