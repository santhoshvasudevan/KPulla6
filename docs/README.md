# Portfolio Insight Documentation

Developer entry point for **KPulla6** — a local-first portfolio tracker with Django + DRF backend, React frontend, and PostgreSQL. Use this page to navigate; detailed specs stay in linked docs.

---

## A. Product overview

Portfolio Insight tracks stocks and mutual funds across multiple portfolios with cash-aware valuation, performance analytics, and CSV import. Transactions and the cash ledger are the source of truth; prices, FX, and NAVs are cached in the database.

**MVP status:** Release-ready with accepted limitations (local-first dev; not production-deployed). Stabilization phases STAB-1 through STAB-6 and MVP-RELEASE-1 are complete.

**Main capabilities:**

| Area | Summary |
|------|---------|
| Portfolio tracking | Multi-portfolio scope, virtual All Portfolios aggregate, display currency |
| Stocks and mutual funds | FIFO holdings, splits, MF folio-scoped transactions, CSV import |
| Cash-aware portfolios | Ledger balances, BUY/SELL settlements, deposits/withdrawals/transfers |
| Metric Sheet | Portfolio, asset, and Compare Quantitative Statistics |
| Compare | Side-by-side two-asset analytics |
| CSV import | Stock and mutual fund formats with cash shortfall preview |
| Transfers | Same- and cross-currency portfolio transfers |
| Diagnostics | Read-only integrity scripts for local troubleshooting |

**Read next:** [current-state.md](./current-state.md) · [mvp-release-checklist.md](./mvp-release-checklist.md)

---

## B. Architecture

Django domain apps (`portfolios`, `cash`, `transactions`, `analytics`, `market_data`, `fx`) orchestrate reads and writes. Pure finance math lives in `backend/finance/` with no Django imports. React is API-driven — no client-side valuation or return calculations.

**Read next:**

| Doc | Contents |
|-----|----------|
| [architecture.md](./architecture.md) | Module boundaries, data flow, Metric Sheet architecture |
| [database.md](./database.md) | PostgreSQL schema, caching, migrations |
| [decisions.md](./decisions.md) | Architecture decision record |
| [GRAPH_REPORT.md](../graphify-out/GRAPH_REPORT.md) | Optional code graph navigation (regenerate with `make graphify`) |

---

## C. Product rules

**[product-rules.md](./product-rules.md)** is the canonical index of MVP product rules — cash, returns, Metric Sheet, transfers, frontend guardrails, and data safety. Do not duplicate rules here; follow the index and linked deep specs.

**Also:** [cash-ledger.md](./cash-ledger.md) · Cursor rule [320-cash-ledger](cursor-rules/320-cash-ledger.md)

---

## D. API contracts

Two layers:

| Doc | Use when |
|-----|----------|
| [api-contracts.md](./api-contracts.md) | Quick lookup — endpoint → frontend client → tests → key error shapes |
| [api-design.md](./api-design.md) | Full request/response specs, phase history, closed assumptions |

Base URL: `/api/v1` · Session auth required except health and auth endpoints.

---

## E. Cash ledger

Cash is a **portfolio balance component**, not an investment asset. When `cash_aware_enabled=true`, BUY must be funded from ledger cash in the **transaction currency** only (no implicit cross-currency funding). Cash-aware portfolios include cash in current value, allocation, value history, XIRR, TWROR, and cumulative return. Deposits, withdrawals, manual edit/delete, transfers, and bulk entries are supported via `/cash` APIs and UI.

**Read next:** [cash-ledger.md](./cash-ledger.md) · [product-rules.md](./product-rules.md) § Cash Ledger rules

---

## F. Portfolio analytics / Metric Sheet

Quantitative Statistics at three scopes: **portfolio** (Dashboard), **asset** (Asset Detail), and **Compare** (two subjects). Metrics include return and risk ratios, drawdown periods and series, benchmark-relative stats (beta, alpha, correlation), and monthly/yearly return tables — all computed on the backend from cash-flow-adjusted daily return series.

**Read next:** [architecture.md](./architecture.md) § Quantitative Statistics · [api-contracts.md](./api-contracts.md) § Analytics · [frontend-design.md](./frontend-design.md)

---

## G. Frontend design

Institutional Slate design system — analytics-first layout, CSS tokens, shared UI primitives, Light/Dark/System theme. React displays and formats API values only.

**Read next:** [frontend-design.md](./frontend-design.md) · [page-layouts.md](./page-layouts.md)

---

## H. Development workflow

Local stack: Docker Postgres, `make dev`, session auth. Data-sensitive work requires backup and safety checks before any destructive operation.

**Documentation portal:** `make docs-serve` or `make dev` (MkDocs Material at http://127.0.0.1:8002) · `make docs-check` after doc/API edits · Diátaxis nav in `mkdocs.yml`.

**Read next:** [workflows.md](./workflows.md) · [data-safety.md](./data-safety.md) · [AGENTS.md](agents.md)

---

## I. Testing strategy

| Target | Purpose |
|--------|---------|
| `make test-fast` | Finance unit + cash service subset (~1 min) |
| `make test-critical` | Golden-flow backend APIs + key frontend page tests |
| `make test-all` | Full backend + frontend suite + production build |

Backend tests use SQLite (`DJANGO_TEST_USE_SQLITE=1`); no Docker required for pytest/Vitest.

**Read next:** [workflows.md](./workflows.md) § Make targets · [mvp-release-checklist.md](./mvp-release-checklist.md) § A Automated tests

---

## J. Diagnostics and troubleshooting

Read-only scripts under `backend/scripts/` — no mutations, no external market-data calls. Run from `backend/` with the project venv.

| Script | Checks |
|--------|--------|
| `diagnose_settlement_integrity.py` | Cash-aware BUY/SELL settlement links, orphans, mismatches |
| `diagnose_negative_cash.py` | Chronological negative running cash balances |
| `diagnose_summary_vs_performance.py` | Summary `current_value` vs performance `metric=value` |
| `diagnose_fx_coverage.py` | Cached FX gaps for display-currency conversion |
| `diagnose_nav_coverage.py` | Held MF scheme NAV missing or stale rows |
| `diagnose_cash_aware_returns.py` | Cash-aware summary, performance, XIRR, external flows |

**Read next:** [workflows.md](./workflows.md) § Diagnostics · [mvp-release-checklist.md](./mvp-release-checklist.md) § B2 Optional diagnostics

---

## K. Performance

Dashboard read paths were profiled on real Postgres dev data (STAB-5A/5B). Critical parallel load stays under ~1 s; optimization is **deferred** unless thresholds are exceeded or data volume grows materially.

**Read next:** [performance/dashboard-read-paths.md](./performance/dashboard-read-paths.md) · [performance/dashboard-read-baseline.md](./performance/dashboard-read-baseline.md)

---

## L. Release readiness

MVP release QA (STAB-6) and manual golden-flow sign-off (MVP-RELEASE-1) passed with accepted limitations. Commit stabilization work before tagging.

**Read next:** [mvp-release-checklist.md](./mvp-release-checklist.md) · [current-state.md](./current-state.md)

---

## M. Changelog

Implementation history and stabilization phase notes: **[changelog.md](./changelog.md)**

---

## N. Deferred roadmap

Post-MVP items tracked in [current-state.md](./current-state.md) § Deferred / Not Yet Implemented:

| Topic | Status |
|-------|--------|
| Transfer fees | Deferred (Cash-8C) |
| Same-portfolio FX conversion | Deferred |
| Display-currency cash totals on `/cash` | Deferred |
| Dividends / interest / taxes ledger types | Deferred |
| Full browser E2E suite (Playwright/Cypress) | Not present |
| Background sync scheduler (Celery/RQ) | Not configured |
| Dashboard read-path optimization | Deferred — revisit when targets exceeded (STAB-5C+) |
