# Project Summary — KPulla6 (Portfolio Insight)

## Overview
**Portfolio Insight** tracks transactions and portfolio performance using cached market data. **KPulla6** is a greenfield rewrite of the KPulla5 application on a production-friendly stack while preserving domain rules and API contracts.

## Stack
| Layer | Technology |
|-------|------------|
| Backend | Django 5, Django REST Framework |
| Database | PostgreSQL 16 (Docker Compose) |
| Frontend | React 19, Vite 6 |
| Reference | KPulla5 — FastAPI, SQLite (unchanged) |

## Repository layout
```
KPulla6/
├── AGENTS.md
├── Makefile
├── docker-compose.yml
├── .env.example
├── backend/
│   ├── config/           # Django settings, root URLs
│   ├── api/              # Versioned API (health, future routers)
│   ├── finance/          # Framework-independent calculations
│   ├── portfolios/
│   ├── transactions/
│   ├── market_data/
│   ├── fx/
│   ├── analytics/
│   ├── settings_app/
│   ├── tests/
│   └── manage.py
├── frontend/
│   └── src/              # React + Vite
└── docs/
```

## Current scope
- Health, settings, portfolios, transactions CRUD, CSV import
- Holdings + asset detail APIs (FIFO from finance layer, cached prices)
- Market data: incremental price/benchmark/FX sync (API + management commands)
- Portfolio summary API with optional value-history timeseries (cached prices/FX only)
- Portfolio performance API (`value`, cumulative return, TWROR, range, benchmark comparison)
- `backend/finance/` — FIFO, stock splits, XIRR, TWROR, performance range, benchmark helpers (pure Python)
- Docker PostgreSQL + `make dev`
- React app: dashboard, holdings, transactions, settings (API-driven; no client-side valuation math)

## Planned (from KPulla5)
Automatic background scheduler — see `docs/current-state.md`.

## Running locally
```bash
cp .env.example .env
make dev
```
