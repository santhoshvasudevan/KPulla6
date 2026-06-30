# Quickstart: run locally

## Prerequisites

- Python 3.11+
- Node.js 20+
- Docker (PostgreSQL only)

## Bootstrap

```bash
cp .env.example .env
make bootstrap   # Postgres + migrate + seed
make dev         # Postgres + Django :8000 + Vite :5173 + Docs :8002
```

| URL | Service |
|-----|---------|
| http://127.0.0.1:5173 | React app |
| http://127.0.0.1:8000/api/v1/health | API health |
| http://127.0.0.1:8002 | Documentation (this site) |

Stop dev servers (Postgres keeps running):

```bash
make stop-dev
```

## First login

After bootstrap, set a password for the seeded owner — see [Login and first use](login-and-first-use.md).

## Refresh market data

Cached prices and NAVs are not fetched automatically on dashboard load:

```bash
make refresh
```

See [Refresh market data](../tutorials/refresh-market-data.md).

## More

- [Common commands](common-commands.md)
- [Local docs domain](../how-to/local-docs-domain.md)
- [Development workflow](../workflows.md) (detailed contributor guide)
