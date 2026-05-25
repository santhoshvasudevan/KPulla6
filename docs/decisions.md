# Architecture Decisions — KPulla6

## 2026-05-19 — Greenfield stack
- **Django + DRF** replace FastAPI for HTTP and ORM
- **PostgreSQL** (Docker Compose) replaces SQLite file persistence
- **React + Vite** retained for frontend
- **KPulla5** remains the behavioral and API contract reference

## Data strategy (inherited)
- Transactions are source of truth
- Historical prices and FX rates cached in DB
- No live external market-data calls during dashboard rendering

## Schema strategy
- Django migrations only; no runtime `ALTER TABLE`

## Finance modules
- Pure Python in `backend/finance/`; no Django/ORM imports in calculation code

## UI strategy (inherited)
- No manual price input
- Prices derived from DB only

## Finance rules (inherited)
- BUY negative cash flow; SELL positive cash flow
- XIRR includes current valuation
