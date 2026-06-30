# KPulla6 Docs

**Portfolio Insight** tracks stocks, mutual funds, cash, and fixed deposits on your Mac. The API owns all math. The UI displays results.

## I want to…

| Goal | Start here |
|------|------------|
| Run the app | [Quickstart](getting-started/quickstart.md) |
| Sign in | [Login and first use](getting-started/login-and-first-use.md) |
| Add a portfolio or import CSV | [Tutorials](tutorials/add-first-portfolio.md) |
| Refresh prices or NAVs | [Refresh market data](tutorials/refresh-market-data.md) |
| Understand returns | [Portfolio performance](concepts/portfolio-performance.md) |
| Look up an API | [API reference](reference/api-reference.md) |
| Fix something broken | [Troubleshooting](troubleshooting/index.md) |

## Local URLs

Start everything:

```bash
make dev
```

| What | URL |
|------|-----|
| App | http://127.0.0.1:5173 |
| API health | http://127.0.0.1:8000/api/v1/health |
| Docs (this site) | http://127.0.0.1:8002 |
| Docs with local hostname | http://docs.kpulla6.com:8002 — [setup](how-to/local-docs-domain.md) |

Stop app + docs (Postgres keeps running):

```bash
make stop-dev
```

## How this site is organized

| Section | Use when you want to… |
|---------|------------------------|
| [Getting Started](getting-started/overview.md) | Install and run locally |
| [Tutorials](tutorials/add-first-portfolio.md) | Learn by doing a first task |
| [How-to Guides](how-to/local-docs-domain.md) | Solve one specific problem |
| [Concepts](concepts/architecture-overview.md) | Understand why it works this way |
| [Reference](reference/make-commands.md) | Look up commands, API, schema |
| [Troubleshooting](troubleshooting/index.md) | Fix errors |
| [Maintenance](maintenance/cursor-maintenance-workflow.md) | Contribute or review |

Long-form specs (`api-design.md`, `architecture.md`, etc.) stay in the repo and are linked from summary pages — not duplicated here.
