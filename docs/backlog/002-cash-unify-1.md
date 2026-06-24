# 002 — CASH-UNIFY-1: Bank account portfolio ownership + unified cash read API

**ID:** CASH-UNIFY-1  
**Branch:** `agent/002-cash-unify-1`  
**Depends on:** 001 (design approved)  
**Status:** Implemented (2026-06-24)

## Goal

Establish **portfolio ownership** for investment-linked bank accounts and expose a **read-only aggregated cash overview** so clients can fetch broker cash and bank ledger balances in one response, with explicit `ledger_type` attribution per row.

Design: [cash-unification.md](../cash-unification.md) §4, §6, §8.2.

## Scope

### Schema & backfill

- Add nullable `BankAccount.portfolio` FK → `Portfolio` (migration).
- Management command (dry-run default): infer `portfolio` when all linked movements/FDs point to one portfolio; leave null when ambiguous (§6.1).
- **No automatic cash movements** during backfill; no destructive deletes.

### Read API

- New endpoint: `GET /api/v1/cash/overview`
  - Query: existing `portfolio_scope` / `portfolio_id`, optional `display_currency` (native balances required; display FX may defer partial fields to CASH-UNIFY-4)
  - Response sections: `broker_cash` (from `CashLedgerEntry` balances), `bank_cash` (from `CashMovement` / `BankAccount` ledger balances), `totals` where FX available
  - Each line item: `ledger_type` (`PORTFOLIO` | `BANK`), `currency`, `balance`, `portfolio_id` or `bank_account_id`, `include_in_portfolio_value` for bank rows, `portfolio_assignment_status` when unassigned/ambiguous
- Extend bank account GET/PUT to expose/set `portfolio_id` (user assignment for ambiguous accounts).
- Wire URL in `backend/cash/` following existing scope validation.
- Document contract in `docs/api-design.md` and `docs/api-contracts.md`.
- Frontend `api.js`: add `fetchCashOverview` (no page UI required in this phase).

## Do not implement

- No writes, transfers, or cross-ledger movements
- No merging ledger tables or changing balance calculation rules
- No FD create portfolio derivation (CASH-UNIFY-2)
- No Cash page UI redesign (CASH-UNIFY-3)
- Do not change summary/performance valuation logic

## Safety requirements

- Run `make backup-db` and `make db-safety-check` before migration on dev Postgres
- Backfill command: dry-run default; no ledger row creation
- Never run destructive DB commands

## Expected files / areas

| Area | Files |
|------|--------|
| Model + migration | `backend/debt/models.py`, `debt/migrations/` |
| Backfill command | `backend/debt/management/commands/infer_bank_account_portfolios.py` (or similar) |
| API view + service | `backend/cash/views.py`, `backend/cash/services.py` or `cash/overview_service.py` |
| URLs | `backend/cash/urls.py`, `backend/api/urls.py` |
| Bank balance read | `backend/debt/bank_ledger_services.py`, `finance/bank_cash.py` |
| Tests | `backend/tests/test_cash_overview_api.py`, `backend/tests/test_bank_accounts_api.py` |
| Docs | `docs/api-design.md`, `docs/api-contracts.md`, `docs/database.md`, `docs/changelog.md` |
| Frontend client | `frontend/src/api.js` |

## Tests / commands

```bash
make backup-db && make db-safety-check
cd backend && DJANGO_TEST_USE_SQLITE=1 .venv/bin/python -m pytest tests/test_cash_overview_api.py tests/test_bank_accounts_api.py -q
make test-backend
git diff --stat
```

## Final response format

1. Task ID: `002 — CASH-UNIFY-1`
2. Files changed
3. Tests run (commands + pass/fail)
4. `git diff --stat`
5. Commit hash
6. Deferred items
7. Safety: backup/safety-check results
