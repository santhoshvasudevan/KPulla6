# Quickstart: run locally

Get the app, API, and docs running on your Mac in a few minutes.

## Prerequisites

- Python 3.11+
- Node.js 20+
- Docker (for PostgreSQL only)

## 1. Configure environment

```bash
cp .env.example .env
```

Edit `.env` only if you need Google OAuth or custom ports.

## 2. Bootstrap database

```bash
make bootstrap
```

**What it does:** starts Postgres, runs migrations, seeds initial data.

**Expected:** ends without errors; `docker ps` shows `kpulla6_postgres`.

## 3. Start dev stack

```bash
make dev
```

**What it starts:** Postgres, Django `:8000`, Vite `:5173`, MkDocs `:8002`.

**Check the API:**

```bash
curl -s http://127.0.0.1:8000/api/v1/health
```

**Expected:**

```json
{"status":"ok","service":"portfolio-insight"}
```

(Exact payload may vary slightly — look for HTTP 200 and `"status":"ok"`.)

| Service | Open in browser |
|---------|-----------------|
| App | http://127.0.0.1:5173 |
| Docs | http://127.0.0.1:8002 |

## 4. Set a password and sign in

Bootstrap creates an owner account. Set a local password before login — see [Login and first use](login-and-first-use.md).

## 5. Refresh market cache (optional)

Dashboard valuations use cached DB prices — not live market calls.

```bash
make refresh
```

**Expected:** sync commands run for stocks, benchmarks, FX, and MF NAVs; ends with `Refresh complete`.

Details: [Refresh market data](../tutorials/refresh-market-data.md).

## Stop

```bash
make stop-dev
```

Stops Django, Vite, and docs. Postgres keeps running.

```bash
make stop-all
```

Also stops the Postgres container (data volume preserved).

## Next

- [Common commands](common-commands.md)
- [Local docs domain](../how-to/local-docs-domain.md)
- Full contributor workflow: [workflows.md](../workflows.md)
