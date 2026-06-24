# 004 — CASH-UNIFY-3: Unified Cash page UI

**ID:** CASH-UNIFY-3  
**Branch:** `agent/004-cash-unify-3`  
**Depends on:** 002 (overview API); 003 recommended (consistent portfolio ownership in copy)

## Goal

Update the **Cash page** to present **Cash / Liquid Holdings** with Broker Cash, Bank Cash, and Total Cash sections, using the CASH-UNIFY-1 overview API.

Design: [cash-unification.md](../cash-unification.md) §5 · [page-layouts.md](../page-layouts.md) §8.

## Scope

- Cash page (`frontend/src/pages/Cash.jsx`):
  - Header KPI strip: **Total Cash**, **Broker Cash**, **Bank Cash** (native currency from overview API)
  - **Broker Cash** section: existing balances, ledger, deposit/withdrawal/transfer/bulk (unchanged write behavior)
  - **Bank Cash** section: read-only per bank account balances; link to Settings → Bank accounts
  - Helper copy: Broker cash funds **securities/MF**; bank cash funds **FD/bank products**
- Consume `fetchCashOverview`; keep existing broker ledger table and modals
- Vitest updates for Cash page
- `docs/page-layouts.md` and `docs/frontend-design.md` — mark CASH-UNIFY-3 sections implemented
- `docs/changelog.md` entry

## Do not implement

- No new write APIs or cross-ledger transfer workflows (CASH-UNIFY-5)
- Display-currency converted headline totals if FX gaps — defer edge-case polish to CASH-UNIFY-4
- Do not redesign Transactions or Bank Accounts pages beyond navigation links
- No bank movement CRUD on Cash page (Settings remains write surface for bank ledger)

## Safety requirements

- Frontend + read API only — no DB migrations expected
- Never run destructive DB commands

## Expected files / areas

| Area | Files |
|------|--------|
| Cash page | `frontend/src/pages/Cash.jsx`, related components |
| Tests | `frontend/src/pages/Cash.test.jsx` |
| API client | `frontend/src/api.js` (if not done in 002) |
| Styles | page-local CSS or design tokens per `frontend-design.md` |
| Docs | `docs/page-layouts.md`, `docs/frontend-design.md`, `docs/changelog.md` |

## Tests / commands

```bash
cd frontend && npm test -- --run src/pages/Cash.test.jsx
cd frontend && npm test -- --run
make test
git diff --stat
```

## Final response format

1. Task ID: `004 — CASH-UNIFY-3`
2. Files changed
3. Tests run (commands + pass/fail)
4. `git diff --stat`
5. Commit hash
6. Deferred items
7. Safety: N/A for typical frontend-only phase
