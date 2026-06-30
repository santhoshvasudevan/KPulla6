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
- **Cash ledger** (broker cash): deposits, withdrawals, transfers, bulk entries, cash-aware BUY/SELL, broker reversal (CASH-CORR-1A)
- **Cash unification (CASH-UNIFY-0..4B, 4A):** two-ledger model; `GET /cash/overview`; Cash / Liquid Holdings page; bank account portfolio link/delink; display-currency auto-select on portfolio switch
- **Bank ledger + Fixed Deposits:** bank accounts, FD lifecycle, principal-only portfolio integration, opt-in bank cash in portfolio value
- **FD interest/tax report (FD-TAX-1/1A/2):** read-only JSON + CSV export; not tax advice
- `backend/finance/` — FIFO, stock splits, XIRR, TWROR, performance range, benchmark helpers (pure Python)
- Docker PostgreSQL + `make dev`
- React app: dashboard, holdings, transactions, cash, fixed deposits, settings (API-driven; no client-side valuation math)

## Deferred (post-milestone)
- CASH-UNIFY-5 broker ↔ bank transfer; FD-FUND-BROKER; broader CASH-CORR-1 reclassification; FX-1/FX-2; FD-ACC-10C/10D; FD-ANALYTICS — see [backlog/README.md](./backlog/README.md) and [current-state.md](./current-state.md).

## Planned (from KPulla5)
Automatic background scheduler — see `docs/current-state.md`.

## Running locally
```bash
cp .env.example .env
make dev
```
