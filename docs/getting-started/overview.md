# Overview

Portfolio Insight tracks stocks, mutual funds, broker cash, bank cash, and fixed deposits across multiple portfolios. The backend owns all portfolio math; the React UI displays API results only.

## What you can do

- Multi-portfolio scope with a virtual **All Portfolios** view
- Stock and mutual fund transactions with CSV import
- Cash-aware BUY/SELL with broker and bank ledgers
- Fixed deposit lifecycle and interest reporting
- Dashboard, holdings, and **Metric Sheet** analytics

## Stack

| Layer | Technology |
|-------|------------|
| Backend | Django 5, Django REST Framework |
| Frontend | React 19, Vite |
| Database | PostgreSQL 16 (Docker Compose) |
| Docs | MkDocs Material (this site) |

## Status

MVP is release-ready for local-first development. See [Current state](../current-state.md) and [Product rules](../product-rules.md) for scope and limitations.

## Next steps

- [Quickstart: run locally](quickstart.md)
- [Common commands](common-commands.md)
- [Architecture overview](../concepts/architecture-overview.md)
