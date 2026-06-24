# 012 — CASH-CORR-1: Cash reconciliation diagnostics

**ID:** CASH-CORR-1  
**Branch:** `agent/012-cash-corr-1`  
**Depends on:** 005, 010 (recommended)

## Goal

Provide **read-only reconciliation diagnostics** across portfolio broker cash and bank ledger, helping users spot mismatches (unseeded opening balance, stale reference balance, scope attribution gaps) without auto-correcting accounting.

## Scope

- Management command or API: `GET /api/v1/cash/reconciliation` (or `python manage.py diagnose_cash_reconciliation`)
  - Per user: flagged issues list with `severity`, `code`, `message`, `entity_type`, `entity_id`, suggested human action (not auto-fix)
  - Checks (examples): bank account with `opening_balance` but no `OPENING_BALANCE` movement; portfolio cash negative; bank account `include_in_portfolio_value` with ambiguous portfolio scope
- Optional frontend: Diagnostics section on Cash page or Settings (read-only table)
- Document codes in `docs/cash-ledger.md` or new `docs/cash-reconciliation.md`
- Tests: deterministic fixtures for each issue code
- `docs/changelog.md`

## Do not implement

- Automatic ledger writes or “fix” buttons that mutate data without explicit user confirmation flow
- Cross-ledger transfer creation
- FD-ACC-10C reversals (use dedicated APIs)

## Safety requirements

- Read-only diagnostics — no backup required
- If adding dev-only debug scripts that mutate data, require `DJANGO_TEST_USE_SQLITE=1`
- Never run destructive DB commands

## Expected files / areas

| Area | Files |
|------|--------|
| Diagnostic service | `backend/cash/reconciliation.py` or `scripts/diagnose_cash_reconciliation.py` |
| API | `cash/views.py` (optional) |
| Tests | `backend/tests/test_cash_reconciliation.py` (new) |
| Frontend | optional Cash/Settings UI |
| Docs | `docs/cash-ledger.md`, `docs/workflows.md` (diagnostics index) |

## Tests / commands

```bash
cd backend && DJANGO_TEST_USE_SQLITE=1 .venv/bin/python -m pytest tests/test_cash_reconciliation.py -q
make test-backend
git diff --stat
```

## Final response format

1. Task ID: `012 — CASH-CORR-1`
2. Files changed
3. Tests run (commands + pass/fail)
4. `git diff --stat`
5. Commit hash
6. Deferred items (guided fix workflows, auto-repair)
7. Safety notes
