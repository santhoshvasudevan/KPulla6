# Overview

Portfolio Insight is a local-first portfolio tracker. You record transactions. The API computes holdings and returns. The UI shows the results.

## What you can do

| Area | Examples |
|------|----------|
| Portfolios | **All Portfolios** view + up to 5 real portfolios |
| Stocks & MFs | Entry, CSV import, cached valuation |
| Cash | Broker ledger, bank cash, cash-aware trades |
| Fixed deposits | FD lifecycle and interest reporting |
| Analytics | Dashboard, holdings, **Metric Sheet** |

## Stack

| Layer | Technology |
|-------|------------|
| API | Django 5 + DRF |
| UI | React 19 + Vite |
| Database | PostgreSQL 16 (Docker) |
| Docs | MkDocs Material (this site) |

## Run it locally

```bash
cp .env.example .env
make bootstrap
make dev
```

**You are done when:** http://127.0.0.1:5173 loads and health returns OK:

```bash
curl -s http://127.0.0.1:8000/api/v1/health
```

**Expected:** `"status":"ok"`

Full steps: [Quickstart](quickstart.md)

## Suggested path

<div class="grid cards" markdown>

-   **[Quickstart](quickstart.md)**

    ---

    Install, bootstrap, start dev stack.

-   **[Login](login-and-first-use.md)**

    ---

    Password + first-use checklist.

-   **[Tutorials](../tutorials/index.md)**

    ---

    Portfolio, import, refresh, dashboard.

</div>

## Status and scope

MVP is release-ready for local-first use. Limits: [Current state](../current-state.md) · Rules: [Product rules](../product-rules.md).

## Next

- [Quickstart](quickstart.md)

## Related

- [Architecture overview](../concepts/architecture-overview.md) · [Common commands](common-commands.md)
