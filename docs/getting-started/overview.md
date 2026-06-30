# Overview

Portfolio Insight is a local-first portfolio tracker on your Mac. You record transactions. The API computes holdings and returns. The UI shows the results.

## What you can do

| Area | Examples |
|------|----------|
| Portfolios | Virtual **All Portfolios** view + up to 5 real portfolios |
| Stocks & MFs | Manual entry, CSV import, cached price/NAV valuation |
| Cash | Broker ledger, bank cash, cash-aware BUY/SELL |
| Fixed deposits | FD lifecycle, bank funding, interest reporting |
| Analytics | Dashboard, holdings, **Metric Sheet** |

## Stack

| Layer | Technology |
|-------|------------|
| API | Django 5 + DRF (`/api/v1`) |
| UI | React 19 + Vite |
| Database | PostgreSQL 16 (Docker Compose) |
| Docs | MkDocs Material (this site) |

## Run it locally

```bash
cp .env.example .env
make bootstrap
make dev
```

**Then open:** http://127.0.0.1:5173

Step-by-step: [Quickstart](quickstart.md)

## Status and scope

MVP is release-ready for local-first use. Limits and implemented features: [Current state](../current-state.md) · [Product rules](../product-rules.md).

## Next steps

| Goal | Page |
|------|------|
| First login | [Login and first use](login-and-first-use.md) |
| Daily commands | [Common commands](common-commands.md) |
| How it fits together | [Architecture overview](../concepts/architecture-overview.md) |
