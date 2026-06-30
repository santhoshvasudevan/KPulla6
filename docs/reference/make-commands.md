# Make commands

Exhaustive index of Makefile targets. Daily copy-paste subset: [Common commands](../getting-started/common-commands.md). Contributor detail: [workflows.md](../workflows.md).

## Dev stack

| Command | Purpose | Typical result |
|---------|---------|----------------|
| `make dev` | Postgres + migrate + Django + Vite + MkDocs | App :5173, API :8000, docs :8002 |
| `make stop-dev` | Stop Django, Vite, docs | Postgres still running |
| `make stop-all` | `stop-dev` + stop Postgres container | Volume preserved |
| `make ports` | List listeners on 8000, 5173, 8002 | PIDs or `(none)` |
| `make clean-dev` | `stop-all` then `ports` | All dev ports free |

Override ports: `BACKEND_PORT=8001 FRONTEND_PORT=5174 DOCS_PORT=8003 make dev`

| Command | Purpose |
|---------|---------|
| `make backend` | Django only (`:8000`) |
| `make frontend` | Vite only (`:5173`) |
| `make setup-backend` | Create venv + `pip install -r requirements.txt` |
| `make setup-frontend` | `npm install` |

## Database

| Command | Purpose | Typical result |
|---------|---------|----------------|
| `make db` | Start Postgres container | `kpulla6_postgres` running |
| `make db-stop` | Stop Postgres container | Container stopped |
| `make db-logs` | Follow Postgres logs | Streaming log output |
| `make db-shell` | `psql` in container | Interactive SQL |
| `make migrate` | Apply Django migrations | `Applying … OK` |
| `make seed` | `seed_initial_data` | Default user/portfolios |
| `make bootstrap` | `db` + `migrate` + `seed` | Fresh dev DB ready |
| `make backup-db` | `pg_dump` to `backups/` | `Backup written: backups/kpulla6_….sql` |
| `make db-safety-check` | Counts + last 5 transactions | Printed safety snapshot |

**Dangerous (avoid on real dev data):** `make db-reset` — wipes Docker volume.

Safety: [Data safety](../concepts/data-safety.md)

## Market data sync

| Command | Purpose |
|---------|---------|
| `make refresh` | Stocks + benchmarks + FX + MF NAVs |
| `make sync-market-data` | Same combined sync (no banner) |
| `make sync-prices` | Stocks only |
| `make sync-benchmarks` | Benchmark indices only |
| `make sync-fx` | FX rates only |
| `make sync-mutual-fund-navs` | MF NAVs only |

## Tests

| Command | Purpose |
|---------|---------|
| `make test` | Backend pytest + frontend Vitest |
| `make test-backend` | pytest with SQLite |
| `make test-frontend` | `npm test -- --run` |
| `make test-fast` | Finance + cash unit subset (~1 min) |
| `make test-critical` | Golden-flow APIs + key UI tests |
| `make test-all` | Full test + `npm run build` |

## Documentation

| Command | Purpose | Typical result |
|---------|---------|----------------|
| `make setup-docs` | Install MkDocs into backend venv | `requirements-docs.txt` installed |
| `make docs-serve` | MkDocs on `127.0.0.1:8002` | http://127.0.0.1:8002 |
| `make docs-build` | Static site | Output in `site/` |
| `make docs-check` | Strict build + consistency script | `docs-check: OK` |

## Other

| Command | Purpose |
|---------|---------|
| `make graphify` | Regenerate code graph (`graphify update .`) |
