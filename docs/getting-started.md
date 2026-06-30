# Getting Started

Quick start for local development. The app is **local-first**: PostgreSQL via Docker, Django API on port 8000, React on port 5173.

## Prerequisites

- Python 3.11+
- Node.js 20+
- Docker (PostgreSQL only)

## Bootstrap

```bash
cp .env.example .env
make bootstrap   # db + migrate + seed
make dev         # Postgres + Django :8000 + Vite :5173
```

- API health: <http://127.0.0.1:8000/api/v1/health>
- App: <http://127.0.0.1:5173>

Stop dev servers with `make stop-dev`. Postgres keeps running. Use `make stop-all` to stop Postgres too (data volume preserved).

## Tests

```bash
make test              # backend pytest + frontend vitest
make test-backend
make test-frontend
make test-critical     # golden-flow subset before merges
```

Backend tests use SQLite (`DJANGO_TEST_USE_SQLITE=1`); Docker is not required for pytest.

## Market data sync

Prices, benchmarks, FX, and mutual fund NAVs are cached in PostgreSQL. Refresh manually:

```bash
make refresh
```

## Documentation site

Browse project docs locally (MkDocs Material):

```bash
make docs-serve    # http://127.0.0.1:8001
make docs-build
make docs-check    # strict build + consistency script
```

## Data safety

Treat the local Postgres database as production-like personal data. Before destructive operations:

```bash
make backup-db
make db-safety-check
```

See [Data Safety](data-safety.md) and [Development Workflow](workflows.md).

## Next steps

| Topic | Doc |
|-------|-----|
| Current implementation status | [Current State](current-state.md) |
| API contracts | [API Design](api-design.md) |
| Architecture | [Architecture](architecture.md) |
| Agent / contributor rules | `AGENTS.md` (repository root) |
