# AGENTS.md — KPulla6

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
