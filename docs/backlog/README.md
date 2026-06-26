# KPulla6 — Background Agent Backlog

Structured task queue for **Cursor Background Agents** to implement KPulla6 work **one phase at a time**, with safety gates, git discipline, and reviewable diffs.

**Backlog owner / planner / reviewer:** ChatGPT Project  
**Implementation worker:** Cursor Background Agent  
**This file:** operating guide + task index

---

## How to run a task

1. **Pick exactly one** open task file from the index below (in order unless the planner directs otherwise).
2. **Create a branch** from current `main` (or the branch the planner specifies):
   ```bash
   git checkout -b agent/NNN-short-slug
   ```
   Example: `agent/001-cash-unify-0`
3. **Read the task file** end-to-end plus linked docs (`AGENTS.md`, `docs/data-safety.md`, domain specs).
4. **Implement only the task scope.** Do not pull in later phases or unrelated fixes.
5. **Run safety gates** (see [Safety gates](#safety-gates)) before and after data/model work.
6. **Run tests** per the task file and [Test discipline](#test-discipline).
7. **Commit** one logical commit (or the count the planner requests) with a message that names the task ID.
8. **Final response** must follow [Final response format](#final-response-format) so ChatGPT Project can review.

---

## Operating principles

| Rule | Detail |
|------|--------|
| **One task = one branch = one reviewable diff** | Do not batch unrelated tasks. Do not commit to `main` unless explicitly instructed. |
| **Do not expand scope** | If you discover extra work, list it under **Deferred** in the final response; do not implement it. |
| **Docs-only tasks** | Tests optional unless docs tooling or CI checks require them. Still run `git diff --stat`. |
| **Code tasks** | Targeted tests first, then broader gates (see below). |
| **No runtime behavior in AGENT-WORKFLOW-0** | Backlog setup is documentation only. |

---

## Safety gates

**Never** on the live dev Postgres database (see `AGENTS.md` § Data safety):

- `Transaction.objects.delete()` or filtered bulk deletes
- `manage.py flush`, `TRUNCATE`, or destructive SQL on user tables
- `make db-reset`, `docker compose down -v`, or volume deletion
- Ad-hoc mutating scripts without `DJANGO_TEST_USE_SQLITE=1` and user approval

**Before any migration, model change, or ledger mutation on dev Postgres:**

```bash
make backup-db
make db-safety-check
```

Record transaction/portfolio counts from the safety check output. Re-run `make db-safety-check` after the phase and compare.

**Unit tests** always use SQLite: `make test-backend` sets `DJANGO_TEST_USE_SQLITE=1`.

---

## Test discipline

| Change type | Minimum commands |
|-------------|------------------|
| Backend logic / API / migrations | Targeted `pytest` files from the task doc → `make test-backend` |
| Frontend UI / `api.js` | Targeted Vitest files → `cd frontend && npm test -- --run` |
| Full phase confidence | `make test` (backend + frontend) |
| Release-style confidence | `make test-all` (includes `npm run build`) |
| Fast finance/cash sanity | `make test-fast` or `make test-critical` when touching cash/returns |
| Docs-only | Optional; run tests only if CI or touched tooling requires it |

Always state **pass/fail** and the **exact command** in the final response.

---

## Final response format

Every Background Agent completion message **must** include:

1. **Task ID** and title (e.g. `001 — CASH-UNIFY-0`)
2. **Files changed** (created / updated / deleted)
3. **Tests run** (commands + pass/fail; or “skipped — docs-only”)
4. **Git diff summary** (`git diff --stat` against branch base)
5. **Commit hash** if committed (or “not committed — awaiting review”)
6. **Deferred items** — anything discovered but intentionally out of scope
7. **Safety** — whether `backup-db` / `db-safety-check` were run (N/A for docs-only with no DB touch)

---

## Branch and commit conventions

- **Branch:** `agent/NNN-short-slug` matching the task file prefix.
- **Commit subject:** `NNN: Short imperative summary` (e.g. `001: Document unified cash taxonomy`).
- **Do not** force-push, amend pushed commits, or rewrite `main` unless the planner explicitly requests it.

---

## Task index

Execute in order within each epic unless the planner reprioritizes.

| # | File | ID | Status | Depends on |
|---|------|-----|--------|------------|
| 1 | [001-cash-unify-0.md](./001-cash-unify-0.md) | CASH-UNIFY-0 | **Done** | — |
| 2 | [002-cash-unify-1.md](./002-cash-unify-1.md) | CASH-UNIFY-1 | **Done** | 001 |
| 3 | [003-cash-unify-2.md](./003-cash-unify-2.md) | CASH-UNIFY-2 | **Done** | 002 |
| 4 | [004-cash-unify-3.md](./004-cash-unify-3.md) | CASH-UNIFY-3 | **Done** | 003 |
| 4a | [004a-cash-unify-3a.md](./004a-cash-unify-3a.md) | CASH-UNIFY-3A | Done | 004 |
| 5 | [005-cash-unify-4.md](./005-cash-unify-4.md) | CASH-UNIFY-4 | **Done** | 004, 004a |
| 5a | *(in-repo — CASH-UNIFY-4A)* | CASH-UNIFY-4A | **Done** | 005 |
| 6 | [006-fx-1.md](./006-fx-1.md) | FX-1 | Open | 005 (recommended) |
| 7 | [007-fx-2.md](./007-fx-2.md) | FX-2 | Open | 006 |
| 8 | [008-fd-tax-1a.md](./008-fd-tax-1a.md) | FD-TAX-1a | **Done** | — |
| 9 | [009-fd-tax-2.md](./009-fd-tax-2.md) | FD-TAX-2 | **Done** | 008 |
| 10 | [010-fd-acc-10c.md](./010-fd-acc-10c.md) | FD-ACC-10C | Open | — |
| 11 | [011-fd-acc-10d.md](./011-fd-acc-10d.md) | FD-ACC-10D | Open | 010 |
| 12 | [012-cash-corr-1.md](./012-cash-corr-1.md) | CASH-CORR-1 | Open | 005, 004a |
| 13 | [013-fd-analytics-1.md](./013-fd-analytics-1.md) | FD-ANALYTICS-1 | Open | 005 |
| 14 | [014-fd-analytics-2.md](./014-fd-analytics-2.md) | FD-ANALYTICS-2 | Open | 013 |

**Legend:** Open = not started by Background Agent. Planner updates status after review/merge.

---

## Epic summaries

### CASH-UNIFY (001–005, 004a, 4A, 012)

Clarify and surface the **two-ledger cash model** (portfolio broker cash vs bank ledger) without merging storage. Portfolio `CashLedgerEntry` and bank `CashMovement` remain separate per `docs/decisions.md` and [cash-unification.md](../cash-unification.md).

**Refined model (CASH-MODEL-REFINE-0):** `BankAccount` is independent; `BankAccount.portfolio` is a **current portfolio link** (not ownership). Link/delink = inclusion only; transfer = CASH-UNIFY-5; correction = CASH-CORR-1.

| Phase | Backlog | Scope |
|-------|---------|--------|
| **0** | 001 | Design doc + ADR (**done**) |
| **1** | 002 | `BankAccount.portfolio` link FK + inference + `GET /cash/overview` (**done**) |
| **2** | 003 | FD create derives portfolio from linked bank account (**done**) |
| **3** | 004 | Unified Cash page UI (**done**) |
| **3A** | 004a | Cash page verification: attribution, broker actions, diagnostics (**done**) |
| **4** | 005 | Bank account link/delink UX + inclusion + display-currency stabilization (**done**) |
| **4A** | — | Final audit/stabilization; diagnostics; docs/tests (**done**) |
| **CORR-1A** | — | Safe broker cash reversal (**done**) |
| **CORR** | 012 | Reconciliation diagnostics + safe reclassification (mistaken broker ↔ bank entries) |

**Deferred (not in backlog index):** CASH-UNIFY-5 broker ↔ bank **transfer** workflow (actual movements); CASH-UNIFY-6 physical/offline cash account.

### FX (006–007)

Deferred cash FX features: same-portfolio FX conversion legs (Cash-8C) and display-currency normalization on cash surfaces.

### FD-TAX (008–009)

FD-TAX-1 report polish (1a), then CSV/export (2).

### FD-ACC reversal completion (010–011)

FD-ACC-10C: settlement/renewal/cancel-FD reversals. FD-ACC-10D: audit, classifier regression, docs.

### CASH-CORR (012)

Reconciliation diagnostics and **safe reclassification** for mistaken broker ↔ bank cash entries (audited; no silent rewrite). Distinct from link/delink (CASH-UNIFY-4) and transfer (CASH-UNIFY-5).

### FD-ANALYTICS (013–014)

Standalone FD performance metrics and dashboard/analytics surfacing (principal-only baseline; no accrued-interest daily valuation unless task explicitly adds it).

---

## References

- [AGENTS.md](../../AGENTS.md) — agent rules + Background Agent Operating Rules
- [docs/data-safety.md](../data-safety.md) — incident notes, backup/restore
- [docs/workflows.md](../workflows.md) — make targets, TDD workflow
- [docs/cash-ledger.md](../cash-ledger.md) — broker cash ledger
- [docs/cash-unification.md](../cash-unification.md) — unified domain model & roadmap
- [docs/fixed-deposits-accounting.md](../fixed-deposits-accounting.md) — bank ledger + FD accounting
- [docs/current-state.md](../current-state.md) — MVP status and deferred items
