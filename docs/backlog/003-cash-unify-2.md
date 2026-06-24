# 003 — CASH-UNIFY-2: FD portfolio derived from bank account

**ID:** CASH-UNIFY-2  
**Branch:** `agent/003-cash-unify-2`  
**Depends on:** 002 (bank account portfolio ownership)

## Goal

Ensure **FixedDeposit.portfolio** is derived from the linked **BankAccount.portfolio** on create, so FD and bank account cannot silently belong to different portfolios.

Design: [cash-unification.md](../cash-unification.md) §4.3, §6.2.

## Scope

- **FD create (`POST /fixed-deposits`):**
  - Require `bank_account.portfolio` to be set (reject **400** if unassigned — user must assign bank account first).
  - Set `FixedDeposit.portfolio` from `bank_account.portfolio`; ignore or reject mismatched client-supplied `portfolio_id`.
- **FD create UI:** portfolio field read-only or hidden when bank account selected; show bank account portfolio in create modal.
- **Existing FDs:** if `fd.portfolio_id ≠ bank_account.portfolio_id`, expose read-only warning in API detail/list (`portfolio_mismatch_warning` or similar); **do not auto-rewrite** existing rows.
- **Validation tests:** create with assigned bank account; reject unassigned bank account; reject explicit portfolio mismatch.
- Update `docs/fixed-deposits.md`, `docs/api-design.md`, `docs/changelog.md`.

## Do not implement

- No changes to FD opening debit / ledger accounting rules
- No cross-ledger transfers
- No Cash page UI (CASH-UNIFY-3)
- No automatic migration that changes existing FD.portfolio values without dry-run + user-visible report

## Safety requirements

- Prefer validation-only changes; if data migration needed for flags, dry-run command first
- Run `make backup-db` and `make db-safety-check` before any migration on dev Postgres
- Never run destructive DB commands

## Expected files / areas

| Area | Files |
|------|--------|
| FD services | `backend/debt/services.py`, `backend/debt/fixed_deposit_services.py` (if split) |
| Serializers | `backend/debt/serializers.py` |
| Tests | `backend/tests/test_fixed_deposits_api.py` |
| Frontend | `frontend/src/pages/FixedDeposits.jsx`, `FixedDeposits.test.jsx` |
| Docs | `docs/fixed-deposits.md`, `docs/api-design.md`, `docs/changelog.md` |

## Tests / commands

```bash
cd backend && DJANGO_TEST_USE_SQLITE=1 .venv/bin/python -m pytest tests/test_fixed_deposits_api.py -q
make test-backend
cd frontend && npm test -- --run src/pages/FixedDeposits.test.jsx
git diff --stat
```

## Final response format

1. Task ID: `003 — CASH-UNIFY-2`
2. Files changed
3. Tests run (commands + pass/fail)
4. `git diff --stat`
5. Commit hash
6. Deferred items
7. Safety notes
