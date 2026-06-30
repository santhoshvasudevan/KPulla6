# KPulla6 Docs

**Portfolio Insight** — local-first portfolio tracker. The API computes holdings and returns. The UI displays results.

## Start here

<div class="grid cards" markdown>

-   **[Quickstart](getting-started/quickstart.md)**

    ---

    Bootstrap Postgres, run the app, open the dashboard.

-   **[Login](getting-started/login-and-first-use.md)**

    ---

    Set a password and sign in for the first time.

-   **[Tutorials](tutorials/index.md)**

    ---

    Learn by doing: portfolio, CSV, refresh, dashboard.

-   **[API reference](reference/api-reference.md)**

    ---

    Copy-paste `curl` examples against local `:8000`.

</div>

## I want to…

| Goal | Page |
|------|------|
| Run locally | [Quickstart](getting-started/quickstart.md) |
| Daily commands | [Common commands](getting-started/common-commands.md) |
| Refresh prices / NAVs | [Refresh market data](tutorials/refresh-market-data.md) |
| Understand returns | [Portfolio performance](concepts/portfolio-performance.md) |
| Fix an error | [Troubleshooting](troubleshooting/index.md) |
| Contribute | [Cursor workflow](maintenance/cursor-maintenance-workflow.md) |

## Local URLs

```bash
make dev
```

| Service | URL |
|---------|-----|
| App | http://127.0.0.1:5173 |
| API | http://127.0.0.1:8000/api/v1/health |
| Docs | http://127.0.0.1:8002 |

Stop app + docs (Postgres keeps running): `make stop-dev`

## App screenshots

!!! info "Visual pass 1 — placeholders"
    Dashboard, Transactions filters, and Settings display screenshots are **pending**. Capture manually while logged in — see [How to capture screenshots](maintenance/docs-visual-backlog.md#how-to-capture-screenshots). Tutorial pages show labeled placeholder callouts until PNGs are saved under `docs/assets/images/`.

## How this site is organized

| Section | When to use it |
|---------|----------------|
| [Getting Started](getting-started/overview.md) | Install and run |
| [Tutorials](tutorials/index.md) | First-time tasks |
| [How-to Guides](how-to/index.md) | One specific problem |
| [Concepts](concepts/architecture-overview.md) | Why it works this way |
| [Reference](reference/index.md) | API, commands, schema |
| [Troubleshooting](troubleshooting/index.md) | Something broke |

Deep specs (`api-design.md`, `architecture.md`, …) live in the repo and are linked from reference pages.

## Next

- New user → [Quickstart](getting-started/quickstart.md)
- API integrator → [API reference](reference/api-reference.md)

## Related

- [Product rules](product-rules.md) · [Current state](current-state.md) · [Changelog](changelog/index.md)
