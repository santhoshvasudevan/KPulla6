# 012 — CASH-CORR-1: Cash reconciliation & safe reclassification

**ID:** CASH-CORR-1  
**Branch:** `agent/012-cash-corr-1`  
**Depends on:** 005, 004a (recommended); 010 (recommended for reversal patterns)

**Status:** Partial — **CASH-CORR-1A** broker reversal shipped 2026-06-26; read-only reconciliation + cross-ledger reclassification still open.

## Goal

Provide **read-only reconciliation diagnostics** and a **safe correction/reclassification workflow** for mistaken cash entries across portfolio broker cash and bank ledger — without silent rewrites or auto-fixing accounting.

**Distinction (CASH-MODEL-REFINE-0):**

| Operation | Purpose |
|-----------|---------|
| **Link/delink** | Change portfolio inclusion (`BankAccount.portfolio`) — no movements (CASH-UNIFY-4) |
| **Transfer** | Actual cash between broker and bank ledgers (CASH-UNIFY-5) |
| **Reclassification** | Fix mistaken historical entry (this phase) — audited, preserves trail |

Example: User recorded a **broker cash deposit** that should have been a **bank cash deposit** → guided reclassification with reversal + correct entry, not link toggling.

## Scope

### Read-only diagnostics

- Management command or API: `GET /api/v1/cash/reconciliation` (or `python manage.py diagnose_cash_reconciliation`)
  - Per user: flagged issues with `severity`, `code`, `message`, `entity_type`, `entity_id`, suggested human action (not auto-fix)
  - Checks (examples): bank account with `opening_balance` but no `OPENING_BALANCE` movement; portfolio cash negative; bank account `include_in_portfolio_value` with ambiguous portfolio scope; **possible broker/bank misclassification** (heuristic flags only)
- Optional frontend: Diagnostics section on Cash page or Settings (read-only table)
- Document codes in `docs/cash-ledger.md` or `docs/cash-reconciliation.md`

### Safe reclassification workflow

- User-initiated correction for **mistaken ledger classification**:
  - Broker deposit ↔ bank deposit (manual types only where safe)
  - Must use existing reversal patterns (broker: delete/reverse manual row; bank: `POST /cash-movements/{id}/reverse` + new row) or explicit paired API
  - **Audit trail:** `reverses_id`, reason/note, no silent UPDATE of amounts across ledgers
- UI: guided flow with preview of before/after balances; confirm step
- Tests: deterministic fixtures; no cross-ledger auto-balance without user confirm

### Docs & changelog

- `docs/cash-unification.md` §4.2 (correction vs link vs transfer)
- `docs/changelog.md`

## Do not implement

- Automatic ledger writes or “fix” buttons without explicit user confirmation
- Cross-ledger **transfer** product (CASH-UNIFY-5)
- FD-ACC-10C settlement/renewal reversals (use dedicated APIs)
- Silent rewrite of historical rows
- Fixing attribution bugs that belong in CASH-UNIFY-3A (overview mapping)

## Safety requirements

- Reclassification requires user confirmation; preserve audit trail
- `make backup-db` + `make db-safety-check` before any bulk correction tooling on dev Postgres
- Dev-only mutating scripts: `DJANGO_TEST_USE_SQLITE=1` unless user approves
- Never run destructive DB commands

## Expected files / areas

| Area | Files |
|------|--------|
| Diagnostic service | `backend/cash/reconciliation.py` or management command |
| Reclassification service | `backend/cash/reclassification.py` (new, if needed) |
| API | `cash/views.py` |
| Tests | `backend/tests/test_cash_reconciliation.py`, `test_cash_reclassification.py` |
| Frontend | optional Cash/Settings guided correction UI |
| Docs | `docs/cash-ledger.md`, `docs/workflows.md` |

## Tests / commands

```bash
cd backend && DJANGO_TEST_USE_SQLITE=1 .venv/bin/python -m pytest tests/test_cash_reconciliation.py -q
make test-backend
make test
git diff --stat
```

## Final response format

1. Task ID: `012 — CASH-CORR-1`
2. Files changed
3. Tests run (commands + pass/fail)
4. `git diff --stat`
5. Commit hash
6. Deferred items (auto-repair, transfer workflow)
7. Safety notes
