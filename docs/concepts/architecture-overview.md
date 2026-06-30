# Architecture overview

KPulla6 is a local-first portfolio tracker:

- **Backend:** Django 5 + DRF (`/api/v1`)
- **Frontend:** React 19 + Vite
- **Database:** PostgreSQL 16 (Docker Compose)
- **Finance:** Pure Python in `backend/finance/` — no Django imports

## Data flow

```text
Transactions (source of truth)
    → finance layer (FIFO, XIRR, TWROR, cash)
    → read APIs (holdings, summary, performance)
    → React UI (display only)
```

Cached **HistoricalPrice**, **FXRate**, and MF NAV tables feed valuation — sync commands populate them; GET handlers do not call Yahoo/AMFI live.

## Scope

- **All Portfolios** is virtual (`portfolio_scope=all`)
- Real portfolios are DB rows (max 5 active)

Deep dive: [architecture.md](../architecture.md) · [decisions.md](../decisions.md)
