# Development Workflow — KPulla6

## Prerequisites
- Python 3.11+
- Node.js 20+
- Docker (for PostgreSQL only)

## Quick start
```bash
cp .env.example .env
make dev
```
- Backend: http://127.0.0.1:8000
- Frontend: http://127.0.0.1:5173
- API health: http://127.0.0.1:8000/api/v1/health

## Start and stop

| Action | Command |
|--------|---------|
| Start full dev stack | `make dev` |
| Stop backend + frontend only | `make stop-dev` |
| Stop backend, frontend, and Postgres | `make stop-all` |
| Check occupied dev ports | `make ports` |
| Clean stop + port check | `make clean-dev` |

Override ports: `BACKEND_PORT=8001 FRONTEND_PORT=5174 make dev`

Do **not** use `docker compose down -v` unless you intend to delete local database volumes. Normal stop (`make stop-all` or `make db-stop`) preserves DB data.

## Make targets
| Target | Description |
|--------|-------------|
| `make db` | Start PostgreSQL container |
| `make db-stop` | Stop PostgreSQL |
| `make db-logs` | Follow Postgres logs |
| `make db-shell` | `psql` in container |
| `make migrate` | Django migrations (requires db) |
| `make backend` | Run Django dev server |
| `make frontend` | Run Vite dev server |
| `make test` | Backend pytest (SQLite, no Docker) |
| `make dev` | db + migrate + backend + frontend |
| `make ports` | Show processes on backend/frontend dev ports |
| `make stop-backend` | Stop process on `BACKEND_PORT` (default 8000) |
| `make stop-frontend` | Stop process on `FRONTEND_PORT` (default 5173) |
| `make stop-dev` | Stop backend and frontend only |
| `make stop-all` | Stop backend, frontend, and Postgres container |
| `make clean-dev` | `stop-all` then `ports` |

## Generic feature workflow
Same discipline as KPulla5 (`../KPulla5/docs/workflows.md`):

1. Read `AGENTS.md`, `docs/current-state.md`, `docs/architecture.md`, `docs/api-design.md`
2. Define behavior, API, DB, and test impact
3. Protect existing features / contracts
4. Add tests first where practical
5. Minimal implementation; finance logic in `backend/finance/`
6. Run `make test`, frontend tests, `make dev` smoke check
7. Update docs and `docs/changelog.md`

## KPulla6-specific rules
- Do not modify `../KPulla5/`
- Use Django migrations for all schema changes
- Port finance logic into `backend/finance/` without Django imports
- Frontend remains API-driven only
