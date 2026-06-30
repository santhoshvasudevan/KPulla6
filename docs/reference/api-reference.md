# API reference

Resource-oriented API docs with copy-paste `curl` examples. Full contract: [api-design.md](../api-design.md).

**Base URL:** `http://127.0.0.1:8000/api/v1`

## Before you call the API

1. `make dev`
2. Sign in at http://127.0.0.1:5173 (session cookie)
3. Read [API authentication](api-auth.md) for CSRF + cookies in `curl`

## Health (no auth)

```bash
curl -s http://127.0.0.1:8000/api/v1/health
```

**Expected (200):**

```json
{"status":"ok","service":"kpulla6","database":"ok"}
```

## Resource guides

<div class="grid cards" markdown>

-   **[Authentication](api-auth.md)**

    ---

    Login, CSRF, session cookies.

-   **[Transactions](api-transactions.md)**

    ---

    List, create, CSV import.

-   **[Fixed deposits](api-fixed-deposits.md)**

    ---

    FD list, create, maturity estimate.

-   **[Cash](api-cash.md)**

    ---

    Balances, overview, ledger, movements.

-   **[Analytics](api-analytics.md)**

    ---

    Summary, performance, Metric Sheet.

</div>

## Other endpoints

| Area | Examples |
|------|----------|
| Portfolios | `GET /portfolios`, `POST /portfolios` |
| Settings | `GET /settings`, `PUT /settings` |
| Market sync | `POST /prices/refresh`, `POST /nav/refresh`, `POST /portfolio/force-sync` |
| Bank accounts | `GET /bank-accounts`, `POST /cash-movements` |

Index: [api-contracts.md](../api-contracts.md)

## Next

- [API authentication](api-auth.md)
- [Transactions API](api-transactions.md)

## Related

- [Reference overview](index.md) · [Add backend endpoint](../how-to/add-backend-api-endpoint.md)
