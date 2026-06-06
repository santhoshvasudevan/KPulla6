# MVP Release Checklist — KPulla6

**Purpose:** Practical gate before releases, major merges to `main`, or resuming work against real dev portfolio data.

**Related:** [product-rules.md](./product-rules.md) · [workflows.md](./workflows.md) · [data-safety.md](./data-safety.md) · [api-contracts.md](./api-contracts.md)

**MVP status:** **Release-ready with accepted limitations** (sign-off **2026-06-06**, MVP-RELEASE-1). Not production-deployed.

---

## A. Pre-release safety

- [x] Confirm working branch and that changes match the intended release scope.
- [x] Review [changelog.md](./changelog.md) and [current-state.md](./current-state.md) for accuracy.
- [x] If the release includes **migrations** or **real-data operations**, run:
  ```bash
  make backup-db
  make db-safety-check
  ```
  Record transaction and portfolio counts before and after. *(STAB-6: db-safety-check OK — 67 transactions, 5 portfolios.)*
- [x] Confirm **no unintended migrations** are included (review `git diff` / migration files). *(STAB-6: `makemigrations --check` clean.)*
- [x] Confirm **no destructive DB commands** were used in preparation (`flush`, bulk delete, `make db-reset`, `docker compose down -v`).
- [ ] For data-sensitive releases, confirm an on-disk backup exists under `backups/`. *(Recommended before commit/tag; not required for docs-only sign-off.)*

---

## B. Automated checks

Run from project root unless noted.

| Check | Command |
|-------|---------|
| **Daily fast feedback** | `make test-fast` — finance unit + cash services |
| **Pre-merge golden flows** | `make test-critical` — curated backend APIs + key frontend pages |
| **Release confidence** | `make test-all` — full backend + frontend tests + production build |
| Backend tests (full) | `make test-backend` |
| Frontend tests (full) | `make test-frontend` |
| Graphify (structural changes) | `make graphify` |

**Fallback (raw commands):**

```bash
cd backend && DJANGO_TEST_USE_SQLITE=1 .venv/bin/python -m pytest -v
cd frontend && npm test -- --run
cd frontend && npm run build
```

- [x] Backend tests passed (STAB-6: **840 passed**).
- [x] Frontend tests passed (STAB-6: **384 passed**).
- [x] Frontend build passed (STAB-6: `npm run build` OK).
- [x] Graphify refreshed and `graphify-out/GRAPH_REPORT.md` committed (STAB-6).

---

## B2. Optional diagnostics (real dev data / pre-migration)

Run from `backend/` after `make backup-db` when investigating live Postgres data. All scripts are **read-only** (see [workflows.md § Diagnostics](./workflows.md)).

```bash
cd backend
.venv/bin/python scripts/diagnose_settlement_integrity.py --username YOUR_USER
.venv/bin/python scripts/diagnose_negative_cash.py
.venv/bin/python scripts/diagnose_summary_vs_performance.py --portfolio-scope=all --display-currency EUR
.venv/bin/python scripts/diagnose_fx_coverage.py --display-currency EUR
.venv/bin/python scripts/diagnose_nav_coverage.py --stale-days 5
```

| Check | When |
|-------|------|
| Settlement integrity | After bulk imports, enabling cash-aware, or settlement-related bugs |
| Negative cash | Unexpected cash balances or future-impact validation failures |
| Summary vs performance | Dashboard headline value vs value chart mismatch |
| FX coverage | `fx_unavailable` warnings; before relying on multi-currency display totals |
| NAV coverage | MF holdings at zero or stale NAV warnings |

- [x] Diagnostics run (STAB-6: all exit 0 for user `santhoshkgvasudevan`, all scope).
- [x] Any non-zero exit codes investigated; fixes applied or tracked as known data issues. *(N/A — all clean.)*

---

## B3. Optional performance baseline (Dashboard)

Run when Dashboard feels slow, after large imports, or before a major release. Read-only; compare to [performance/dashboard-read-baseline.md](./performance/dashboard-read-baseline.md).

```bash
cd backend
.venv/bin/python scripts/profile_dashboard_read_paths.py --username USERNAME --verbose \
  --json-out tmp/dashboard_read_baseline_postgres.json
```

Use Django **username** (not email). Check default Dashboard paths: summary, performance value 1Y, Metric Sheet 1Y — each ideally **< 1 s**; parallel max ideally **~< 1 s**.

- [x] Profiler run (STAB-6: no major regression vs STAB-5B).
- [x] Results compared to Postgres baseline; regressions documented or tracked in backlog.

---

## C. Manual golden-flow QA

Use a **cash-aware test portfolio** or enable cash-aware on a scratch portfolio. Check off flows exercised; note any failures in the release notes.

**MVP-RELEASE-1:** User completed manual browser QA (2026-06-06). No blocking failures recorded.

### Auth and cash-aware defaults

- [x] Login / register — new user default portfolio is **cash-aware** (`cash_aware_enabled=true`).

### Cash and transactions

- [x] Add **cash deposit** on `/cash`.
- [x] Add **stock BUY** with sufficient same-currency cash — succeeds.
- [x] Attempt **BUY without cash** — shortfall panel (`required`, `available`, `shortfall`, `currency`).
- [x] **Add missing cash and continue** from `TransactionModal` — deposit then retry BUY.
- [x] **SELL** asset — cash balance increases (cash-aware settlement).
- [x] **Same-currency transfer** between portfolios — balances and ledger update; protected rows.
- [x] **Cross-currency transfer** — user-entered source and target amounts; no suggested FX rate; implied rate informational only if shown.
- [x] **Bulk cash entries** — preview then apply on `/cash`.
- [x] **CSV import cash preview** — shortfall preview before import; confirmed deposits when applicable.

### Dashboard and performance

- [x] Dashboard **Current Value** and **Value History** chart load for selected scope/range.
- [x] **Cumulative Return**, **TWROR**, and **XIRR** look sane for a known portfolio (no obvious spikes from same-currency internal moves).
- [x] **Assets** allocation includes **cash** where ledger rows exist.

### Quantitative Statistics / Metric Sheet

- [x] Dashboard **Metric Sheet** section renders (metrics, warnings if any).
- [x] **Asset Detail** Metric Sheet section renders.
- [x] **Compare** page (`/compare`) renders two-asset comparison.

### Future-impact hardening

- [x] **Transaction edit/delete** that would break future cash — **409** panel with `affected_entries`.
- [x] **Cash ledger edit/delete** with future-impact — **409** panel (Cash page).

### Settings

- [x] **Display currency** change — dashboard/summary refresh without stale flicker; FX warnings when conversion incomplete.

---

## D. Known limitations / deferred items

Do not treat absence of these as release blockers unless the release explicitly claims them:

| Item | Status |
|------|--------|
| Transfer fees | **Deferred** (Cash-8C) — accepted for MVP |
| Same-portfolio FX conversion | **Deferred** — accepted for MVP |
| Display-currency cash totals on `/cash` page | Deferred |
| Dividends / interest / taxes ledger types | Deferred |
| Dashboard read-path performance optimization | **Deferred** (STAB-5B — baseline acceptable; see [performance/dashboard-read-paths.md](./performance/dashboard-read-paths.md)) |
| Read-only diagnostics scripts | **Done** (STAB-4) |
| `make test-critical` / golden pytest subset | **Done** (STAB-3) |
| Background sync scheduler (Celery/RQ) | **Not configured** — accepted for MVP |
| Full browser E2E suite (Playwright/Cypress) | **Not present** — accepted for MVP |

---

## E. Release decision

- [x] All automated checks **passed** or **failures documented** with owner and follow-up issue.
- [x] Manual golden flows **passed** or **gaps documented** (which flows skipped and why).
- [x] [changelog.md](./changelog.md) updated for user-visible or contract changes.
- [x] [current-state.md](./current-state.md) updated when MVP scope or deferred items change.
- [x] Graphify refreshed if the release included structural/architecture changes (`make graphify`).
- [ ] Backup exists for any release that touched migrations or live dev data. *(Recommended before tag; optional for stabilization commit.)*

**Sign-off:** **2026-06-06** · branch **`main`** · **MVP-RELEASE-1** · Manual golden-flow QA complete; STAB-6 automated gates passed; **MVP release-ready with accepted limitations** (not production-deployed). Stabilization commit pending.
