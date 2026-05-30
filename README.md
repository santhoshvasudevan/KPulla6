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

### iPad / home LAN (full app, frontend only)

On the Mac: `make dev`, then `ipconfig getifaddr en0` for your LAN IP.

On iPad (same Wi‑Fi): open `http://<mac-lan-ip>:5173`. Do not use `:8000` on the iPad.

Keep `VITE_API_BASE_URL` empty in `.env` so API calls use the Vite proxy. See `docs/workflows.md` for details.

## Tests

```bash
make test          # backend pytest + frontend vitest
make test-backend
make test-frontend
cd frontend && npm run build
```

## Market data sync

Stock prices, benchmark indices, FX rates, and mutual fund NAVs are cached in PostgreSQL. Sync is **manual** (no background scheduler):

```bash
make refresh                 # stocks + benchmarks + FX + mutual fund NAVs
make sync-market-data        # same combined sync (no completion banner)
make sync-prices             # stocks only
make sync-benchmarks
make sync-fx
make sync-mutual-fund-navs   # mutual fund NAVs only
```

Or `POST /api/v1/prices/refresh`, `POST /api/v1/nav/refresh`, or `POST /api/v1/portfolio/force-sync` from the API.

## Frontend API base URL

Set `VITE_API_BASE_URL` in `.env` (optional). Empty uses Vite proxy to Django (`/api` → `:8000`). For iPad/LAN access, leave it empty and use `http://<mac-lan-ip>:5173` only — do not point it at `:8000`.
