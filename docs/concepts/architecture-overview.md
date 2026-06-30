# Architecture overview

**One sentence:** Transactions in Postgres are the source of truth; the API computes holdings and returns; the React app displays API results.

## Stack

| Layer | Technology |
|-------|------------|
| API | Django 5 + DRF at `/api/v1` |
| UI | React 19 + Vite |
| Database | PostgreSQL 16 (Docker Compose) |
| Finance math | Pure Python in `backend/finance/` |

## Data flow

```text
Transactions (source of truth)
    → finance layer (FIFO, XIRR, TWROR, cash)
    → read APIs (holdings, summary, performance)
    → React UI (display only — no portfolio math in the browser)
```

## Cached market data

Stock prices, FX rates, and MF NAVs live in database tables.

- **Populate:** `make refresh` or sync management commands
- **Read APIs:** use cache only — no live Yahoo/AMFI calls during page load

Concept: [Cached market data](cached-market-data.md)

## Portfolio scope

- **All Portfolios** is a virtual view (`portfolio_scope=all`) — not a real DB portfolio
- Real portfolios are DB rows (max 5 active)

## What belongs where

| Question | Read |
|----------|------|
| Endpoint payloads and errors | [API design](../api-design.md) |
| Tables and migrations | [Database](../database.md) |
| Product rules and cash | [Product rules](../product-rules.md) |
| Why we chose X | [Decisions](../decisions.md) |
| Module layout | [Backend module map](../reference/backend-module-map.md) |

Full architecture spec: [architecture.md](../architecture.md)
