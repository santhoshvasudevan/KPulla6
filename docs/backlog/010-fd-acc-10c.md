# 010 — FD-ACC-10C: Settlement / renewal / cancel-FD reversals

**ID:** FD-ACC-10C  
**Branch:** `agent/010-fd-acc-10c`  
**Depends on:** FD-ACC-10B (implemented)

## Goal

Extend the **reversal framework** to cover FD lifecycle events deferred from FD-ACC-10B: settlement reversal, renewal reversal, and cancel-FD reversal (where distinct from existing cancel workflow).

## Scope

- Design alignment with `docs/fixed-deposits-accounting.md` § FD-ACC-10B deferred list
- New POST endpoints (proposed):
  - `POST /api/v1/fixed-deposits/{id}/reverse-settlement`
  - `POST /api/v1/fixed-deposits/{id}/reverse-renewal`
  - Extend or document cancel reversal if separate from `POST .../cancel` + `FD_OPENING_REVERSAL`
- Linked `CashMovement` reversal rows; FD status rollback rules; eligibility guards (no double reverse)
- Classifier updates in `debt/cash_ledger_flows.py` for new reversal movement types
- Frontend: Reverse actions on eligible settlement/renewal rows with confirmation + `reversal_reason`
- Migration only if new movement types or FK fields required
- Tests: E2E scenarios in `test_fixed_deposit_end_to_end_accounting.py` style

## Do not implement

- FD-ACC-10D audit pass (next task)
- Via-bank renewal path
- Manual `TRANSFER_IN`/`OUT` bank API
- Destructive deletes on ledger or FD rows

## Safety requirements

**Mandatory before migrations:**

```bash
make backup-db
make db-safety-check
```

Re-run safety check after migrate. Never `DELETE`/`TRUNCATE` on `cash_movements` or `transactions` for corrections — reversal rows only.

## Expected files / areas

| Area | Files |
|------|--------|
| Services | `backend/debt/` FD settlement/renewal/cancel services |
| Models | `debt/models.py`, migrations |
| Classifier | `debt/cash_ledger_flows.py` |
| API | `debt/views.py` or FD views |
| Frontend | `frontend/src/pages/FixedDeposits.jsx`, Bank/cash movement UI |
| Tests | `backend/tests/test_fd_*_reversal*.py` |
| Docs | `docs/fixed-deposits-accounting.md`, `docs/api-design.md`, `docs/decisions.md` |

## Tests / commands

```bash
make backup-db
make db-safety-check
cd backend && DJANGO_TEST_USE_SQLITE=1 .venv/bin/python -m pytest tests/test_fd_settlement_reversal_api.py tests/test_fixed_deposit_end_to_end_accounting.py -q
make test-backend
make test-critical
git diff --stat
```

## Final response format

1. Task ID: `010 — FD-ACC-10C`
2. Files changed
3. Tests run (commands + pass/fail)
4. `git diff --stat`
5. Commit hash
6. Deferred items (10D, via-bank renewal, etc.)
7. Safety: pre/post safety-check counts
