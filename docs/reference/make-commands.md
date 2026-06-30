# Make commands

Quick index — full list in root `Makefile` and [workflows.md](../workflows.md).

## Dev stack

| Command | Purpose |
|---------|---------|
| `make dev` | Postgres + Django + Vite + MkDocs |
| `make stop-dev` | Stop dev processes |
| `make ports` | Show listening ports |

## Docs

| Command | Purpose |
|---------|---------|
| `make docs-serve` | MkDocs on `127.0.0.1:8002` |
| `make docs-build` | Static site → `site/` |
| `make docs-check` | Strict build + consistency script |

## Data & sync

| Command | Purpose |
|---------|---------|
| `make db` | Start Postgres |
| `make migrate` | Apply migrations |
| `make refresh` | Sync prices, FX, benchmarks, NAVs |
| `make backup-db` | SQL backup |
| `make test` | Backend + frontend tests |

Getting started: [Common commands](../getting-started/common-commands.md)
