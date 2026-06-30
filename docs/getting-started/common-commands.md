# Common commands

Quick reference. Exhaustive list: [Make commands](../reference/make-commands.md).

## Daily dev

| Command | Purpose |
|---------|---------|
| `make dev` | Postgres + migrate + Django + Vite + docs |
| `make stop-dev` | Stop Django, Vite, and docs (keeps Postgres) |
| `make stop-all` | Stop dev processes + Postgres container |
| `make ports` | Show listeners on 8000, 5173, 8002 |

## Database

| Command | Purpose |
|---------|---------|
| `make db` | Start Postgres container |
| `make migrate` | Apply Django migrations |
| `make seed` | Seed initial data |
| `make backup-db` | `pg_dump` to `backups/` |
| `make db-safety-check` | Row counts + recent transactions |

## Market data

| Command | Purpose |
|---------|---------|
| `make refresh` | Stocks + benchmarks + FX + MF NAVs |
| `make sync-prices` | Stocks only |
| `make sync-mutual-fund-navs` | MF NAVs only |

## Tests

| Command | Purpose |
|---------|---------|
| `make test` | Backend pytest + frontend Vitest |
| `make test-critical` | Golden-flow subset before merges |

## Documentation

| Command | Purpose |
|---------|---------|
| `make docs-serve` | Docs only on :8002 |
| `make docs-build` | Static site → `site/` |
| `make docs-check` | Strict build + consistency script |
