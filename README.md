# Portfolio Insight — KPulla6

Django + DRF backend and React (Vite) frontend. Reference implementation: `../KPulla5/`.

## Quick start

```bash
cp .env.example .env
make bootstrap   # db + migrate + seed
make dev         # Postgres + Django :8000 + Vite :5173
make stop-dev    # stop Django + Vite (keeps Postgres running)
make stop-all    # stop Django + Vite + Postgres container (preserves DB volume)
make ports       # show processes on dev ports
```

Do not use `docker compose down -v` unless you intend to delete local database data.

- API: http://127.0.0.1:8000/api/v1/health
- App: http://127.0.0.1:5173

## Tests

```bash
make test          # backend pytest + frontend vitest
make test-backend
make test-frontend
cd frontend && npm run build
```

## Market data sync

Historical prices, benchmarks, and FX are cached in PostgreSQL. Sync is **manual** (no background scheduler):

```bash
make refresh          # sync prices + benchmarks + FX
make sync-prices      # stocks only
make sync-benchmarks
make sync-fx
```

Or `POST /api/v1/prices/refresh` / `POST /api/v1/portfolio/force-sync` from the API.

## Frontend API base URL

Set `VITE_API_BASE_URL` in `.env` (optional). Empty uses Vite proxy to Django (`/api` → `:8000`).
