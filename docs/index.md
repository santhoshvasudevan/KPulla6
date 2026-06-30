# KPulla6 Documentation

**Portfolio Insight** is a local-first portfolio tracker: Django API, React UI, PostgreSQL. Transactions and cash ledgers are the source of truth; prices, FX, and NAVs are cached in the database.

## Start here

| I want to… | Go to |
|------------|--------|
| Run the app locally | [Quickstart](getting-started/quickstart.md) |
| Sign in and explore | [Login and first use](getting-started/login-and-first-use.md) |
| Add holdings or import CSV | [Tutorials](tutorials/add-first-portfolio.md) |
| Refresh stock prices / NAVs | [Refresh market data](tutorials/refresh-market-data.md) |
| Understand how returns work | [Portfolio performance](concepts/portfolio-performance.md) |
| Look up an API endpoint | [API reference](reference/api-reference.md) |
| Fix a dev problem | [Troubleshooting](troubleshooting/dev-server-ports.md) |

## Local URLs (`make dev`)

| Service | URL |
|---------|-----|
| App | http://127.0.0.1:5173 |
| API health | http://127.0.0.1:8000/api/v1/health |
| Docs (this site) | http://127.0.0.1:8002 |
| Docs (local domain) | http://docs.kpulla6.com:8002 — see [Local docs domain](how-to/local-docs-domain.md) |

## How this site is organized

This documentation follows [Diátaxis](https://diataxis.fr/):

- **Tutorials** — guided first-time tasks
- **How-to guides** — solve a specific problem
- **Concepts** — understand the model and “why”
- **Reference** — facts, commands, schemas, routes
- **Maintenance** — contributors, audits, release
- **Troubleshooting** — common errors

Detailed historical specs remain in the repository under `docs/` and are linked from summary pages.
