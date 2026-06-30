# AGENTS.md — KPulla6

**Documentation index:** [docs/README.md](./docs/README.md)

- Inspect existing code before editing.
- Make the smallest safe change.
- Do not rewrite unrelated files.
- Do not reset, wipe, or recreate user data.
- Add or update tests for logic, API, DB, or calculation changes.
- State test results clearly in every implementation summary (pass/fail and command used).
- KPulla5 (`../KPulla5/`) is the reference implementation — do not modify it.
- Backend: Django + Django REST Framework; schema changes via Django migrations only (no runtime `ALTER TABLE`).
- Database: PostgreSQL via Docker Compose (`make db`); do not install PostgreSQL globally.
- Finance logic lives in `backend/finance/` and must stay framework-independent.
- React frontend is API-driven; no finance calculations in the frontend.
- Preserve `/api/v1` contracts where practical when porting from KPulla5.
- Transactions remain source of truth; historical prices and FX rates are cached in DB.
- No live yfinance or external market-data calls during dashboard rendering.

## Product rules

Read **`docs/product-rules.md`** for the canonical index of MVP product rules (cash, returns, Metric Sheet, transfers, frontend, data safety). Deep specs: `docs/cash-ledger.md`, `docs/architecture.md`, `docs/api-design.md`.

**Release / contracts:** [mvp-release-checklist.md](./docs/mvp-release-checklist.md) · [api-contracts.md](./docs/api-contracts.md) (thin index; detail in `api-design.md`).

## Cash Ledger

For cash-related work, follow `docs/cash-ledger.md` and `.cursor/rules/320-cash-ledger.mdc` (mental model, native currency, cash-aware mode, settlements, frontend/API guardrails, data safety).

## Testing (TDD expectations)

| Change type | Expected tests |
|-------------|----------------|
| Backend logic, API, calculations | Add or update **pytest** in `backend/tests/`; run `make test-backend` or targeted file |
| Frontend UI or `api.js` client | Add or update **Vitest**; run `cd frontend && npm test -- --run` |
| Finance formula changes | Deterministic regression tests in `test_finance_*.py` or API golden tests |
| Data-sensitive work | SQLite only (`DJANGO_TEST_USE_SQLITE=1`); follow data-safety workflow for live DB |

Add tests **first where practical**; at minimum in the **same phase** as production changes. See `docs/workflows.md` § TDD / test workflow.

## Graphify

Optional navigation aid — code, tests, migrations, and docs are source of truth. Regenerate only after significant architecture/module/API/routing changes: `graphify update .` or `make graphify`. Policy: `docs/workflows.md` § Graphify Usage.

## Documentation site

Browse project docs locally with MkDocs Material: `make docs-serve` or `make dev` (http://127.0.0.1:8002 · http://docs.kpulla6.com:8002 with local hosts). After doc or API contract edits, run `make docs-check`.

## Data safety (mandatory)

Local Postgres (`portfolio_insight_kpulla6`) holds real dev portfolio data. Treat it as production-like.

### Never on the live dev database

- `Transaction.objects.delete()` or `Transaction.objects.filter(...).delete()`
- `manage.py flush`
- SQL `TRUNCATE` or bulk `DELETE` on user tables
- `make db-reset`, `docker compose down -v`, or Docker volume deletion
- Ad-hoc `python -c` / shell scripts that mutate transactions unless the user explicitly approves and a backup exists

### Before any destructive DB operation

1. Run `make backup-db` and confirm the backup file was written.
2. Run `make db-safety-check` and record DB name + transaction count.
3. Obtain **explicit user approval** for the destructive action.

### Safe debugging workflow

- **Unit tests:** always use `make test` / `make test-backend` (`DJANGO_TEST_USE_SQLITE=1`, in-memory SQLite).
- **Ad-hoc Django scripts:** set `DJANGO_TEST_USE_SQLITE=1` or point `DATABASE_URL` at a scratch database — never the default dev Postgres unless the user asks.
- **Schema / migration work:** run `make backup-db` and `make db-safety-check` before and after (see `docs/workflows.md`, `docs/data-safety.md`).

### Reference

- Full incident notes, backup/restore, and forbidden commands: `docs/data-safety.md`

## Background Agent Operating Rules

For phased work queued in **`docs/backlog/`**, Cursor Background Agents act as the **implementation worker**. ChatGPT Project owns backlog priority, scope approval, and review.

### Workflow

1. **One task = one branch = one reviewable diff.** Branch name: `agent/NNN-short-slug` (see task file). Do not implement multiple backlog items in one branch unless the planner explicitly combines them.
2. **Do not expand scope.** Out-of-scope discoveries go in the final response under **Deferred**; do not implement them in the same phase.
3. Read the task file, `AGENTS.md`, and linked domain docs before editing.

### Safety

4. **Never run destructive DB commands** on live dev Postgres (see § Data safety above).
5. Before **migrations, model changes, or ledger mutations** on dev Postgres: run `make backup-db` and `make db-safety-check`; record counts; re-check after the phase.

### Testing

6. **Code changes:** run targeted tests from the task file, then `make test-backend` and/or `cd frontend && npm test -- --run` as appropriate; use `make test` for full backend + frontend confidence; `make test-all` when the task touches build-critical paths.
7. **Docs-only tasks:** tests optional unless docs tooling or CI requires them.

### Final response (required)

Every Background Agent completion must report:

- **Files changed** (created / updated / deleted)
- **Tests run** (commands + pass/fail, or “skipped — docs-only”)
- **`git diff --stat`** summary against the branch base
- **Commit hash** if committed (or state not committed)
- **Deferred items** intentionally left out of scope

Backlog index and operating guide: [docs/backlog/README.md](./docs/backlog/README.md).
