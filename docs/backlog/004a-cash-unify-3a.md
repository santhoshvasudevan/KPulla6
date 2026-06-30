# 004a — CASH-UNIFY-3A: Cash page verification & attribution fix

**ID:** CASH-UNIFY-3A  
**Branch:** `agent/004a-cash-unify-3a`  
**Depends on:** 004 (CASH-UNIFY-3)  
**Status:** Done (2026-06-25)

## Goal

Fix **manual verification issues** on the unified Cash / Liquid Holdings page without changing accounting rules or implementing broad correction workflows.

Design: [cash-unification.md](../cash-unification.md) §5 · [page-layouts.md](../page-layouts.md) §8.

## Reported issues (manual QA)

On portfolio **IndianInvestments** (example):

| Section | Expected | Observed (reported) |
|---------|----------|---------------------|
| Broker Cash | 0 INR | Value appeared under wrong section |
| Bank Cash | ~1,109,389 INR | Value appeared under wrong section |
| Broker actions | Deposit / Withdraw / Transfer visible | Not visible on Cash page |
| Bank Cash forms | None on Cash page | Correct — read-only |

Root cause: CASH-UNIFY-3 WIP used `/cash/balances` (broker-only) for KPI/rows while bank cash lived in overview — values appeared swapped. Fixed by filtering overview rows on `ledger_type` and using overview totals only.

## Resolution (2026-06-25)

- Broker/Bank sections and KPIs filter `ledger_type` (`BROKER_CASH` / `BANK_CASH`).
- Per-row source diagnostics (`cash_ledger_entries` vs `cash_movements`).
- Broker Cash actions visible in header; Bank Cash read-only.
- Always-on **Show unassigned / ambiguous bank accounts** toggle.
- IndianInvestments regression: broker 0 INR, bank ~1.1M INR (pytest + Vitest).
- Correction/reclassification deferred to CASH-CORR-1.

## Scope

- **Attribution:** Ensure `BROKER_CASH` and `BANK_CASH` overview rows render in the correct sections with correct native balances.
- **Broker actions:** Restore/confirm **Broker Cash actions** (deposit, withdrawal, transfer, bulk) visible and functional on all supported scopes.
- **Source diagnostics:** Per-row `source` field visible (`cash_ledger_entries` vs `cash_movements`) to aid debugging.
- **Unassigned toggle:** Confirm **Show unassigned bank accounts** works when exclusions exist.
- **Tests:** Vitest regression for correct section placement and broker action visibility.
- **Docs:** Update `page-layouts.md` / `current-state.md` when fixed.

## Do not implement

- Bank account link/delink UX (CASH-UNIFY-4)
- Broker ↔ bank transfer workflow (CASH-UNIFY-5)
- Broad correction/reclassification (CASH-CORR-1) unless a narrowly safe read-only diagnostic is needed
- Backend accounting or ledger rule changes unless a minimal read-only bug is proven

## Safety requirements

- Frontend-focused; no migrations unless a proven read-only API attribution bug requires a minimal fix
- Never run destructive DB commands
- `make backup-db` only if touching production-like Postgres schema

## Expected files / areas

| Area | Files |
|------|--------|
| Cash page | `frontend/src/pages/Cash.jsx`, `Cash.css` |
| Overview consumer | verify `fetchCashOverview` row mapping |
| Optional backend | `backend/cash/overview_service.py` if attribution bug confirmed |
| Tests | `frontend/src/pages/Cash.test.jsx` |
| Docs | `docs/page-layouts.md`, `docs/current-state.md`, `docs/changelog.md` |

## Tests / commands

```bash
cd frontend && npm test -- --run src/pages/Cash.test.jsx
cd frontend && npm test -- --run
make test
git diff --stat
```

## Final response format

1. Task ID: `004a — CASH-UNIFY-3A`
2. Root cause summary
3. Files changed
4. Tests run (commands + pass/fail)
5. `git diff --stat`
6. Commit hash
7. Deferred items
