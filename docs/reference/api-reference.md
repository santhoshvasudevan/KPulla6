# API reference

Quick smoke tests and pointers to the full contract.

## Base URL

```text
http://127.0.0.1:8000/api/v1
```

Start the API:

```bash
make dev
```

## Health check

```bash
curl -s http://127.0.0.1:8000/api/v1/health
```

**Expected:** HTTP 200, JSON with `"status":"ok"`.

## Auth

Session auth via django-allauth. Use the app at http://127.0.0.1:5173 — not raw `:8000` for UI workflows.

Setup: [Configure Google OAuth](../how-to/configure-google-oauth.md) · [auth.md](../auth.md)

## Common read endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /portfolio/summary` | Dashboard KPIs |
| `GET /portfolio/performance` | Performance chart |
| `GET /holdings` | Holdings table |
| `GET /fixed-deposits` | FD list |

All require login. Pass `portfolio_scope` or `portfolio_id` as documented in the full spec.

## Full documentation

| Doc | Contents |
|-----|----------|
| [api-design.md](../api-design.md) | Every endpoint, payloads, errors |
| [api-contracts.md](../api-contracts.md) | Thin contract index |

## Adding endpoints

Contributor checklist: [Add a backend API endpoint](../how-to/add-backend-api-endpoint.md)
