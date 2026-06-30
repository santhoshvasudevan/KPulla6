# 004 — CASH-UNIFY-3: Unified Cash page UI

**ID:** CASH-UNIFY-3  
**Branch:** `agent/004-cash-unify-3`  
**Depends on:** 002 (overview API); 003 recommended (consistent portfolio ownership in copy)  
**Status:** **Done** (2026-06-24)

## Goal

Update the **Cash page** to present **Cash / Liquid Holdings** with Broker Cash, Bank Cash, and Total Cash sections, using the CASH-UNIFY-1 overview API.

Design: [cash-unification.md](../cash-unification.md) §5 · [page-layouts.md](../page-layouts.md) §8.

## Delivered

- Cash page (`frontend/src/pages/Cash.jsx`):
  - Title **Cash / Liquid Holdings**; KPI strip: Total / Broker / Bank Cash from `fetchCashOverview`
  - **Broker Cash** section: overview rows + existing ledger, deposit/withdrawal/transfer/bulk (unchanged write behavior)
  - **Bank Cash** section: read-only per bank account balances; link to Settings → Bank accounts; `include_unassigned` toggle when exclusions exist
  - Warnings: FX partial, API `warnings`, excluded unassigned/ambiguous counts
- Vitest updates for Cash page (`Cash.test.jsx`)
- Docs: `page-layouts.md`, `frontend-design.md`, `cash-unification.md`, `current-state.md`, `changelog.md`

## Follow-up

- **CASH-UNIFY-3A** ([004a-cash-unify-3a.md](./004a-cash-unify-3a.md)): manual verification — Broker/Bank attribution, broker actions visibility, source diagnostics.
- **CASH-MODEL-REFINE-0:** bank account portfolio **link** semantics documented; link/delink UX → CASH-UNIFY-4.

## Do not implement (deferred)

- No new write APIs or cross-ledger transfer workflows (CASH-UNIFY-5)
- Display-currency converted headline totals when FX gaps — CASH-UNIFY-4
- Bank movement CRUD on Cash page (Settings remains write surface)

## Tests / commands

```bash
cd frontend && npm test -- --run src/pages/Cash.test.jsx
cd frontend && npm test -- --run
make test
```
