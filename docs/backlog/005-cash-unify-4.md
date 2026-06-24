# 005 — CASH-UNIFY-4: Terminology, display-currency totals, stabilization

**ID:** CASH-UNIFY-4  
**Branch:** `agent/005-cash-unify-4`  
**Depends on:** 004

## Goal

**Stabilize and audit** the CASH-UNIFY epic: display-currency cash totals, allocation/summary terminology cleanup, regression tests, docs consistency, changelog/decisions closure.

Design: [cash-unification.md](../cash-unification.md) §3.3, §8.2.

## Scope

### Display-currency totals

- Extend cash overview to return `display_currency`, `total_broker_cash_display`, `total_bank_cash_display`, `total_combined_display` using cached FX only (`fx/lookup.convert_amount_with_fill`)
- Null/warning when FX unavailable — do not silently omit
- Cash page KPI strip shows converted totals when display currency from app settings is set
- Resolves MVP deferred item: “Display-currency cash totals on `/cash`”

### Terminology cleanup

- Summary allocation / holdings labels: clarify **Broker Cash** vs **Cash / Bank Cash** bucket where user-facing copy is ambiguous
- Docs audit: `cash-ledger.md`, `product-rules.md`, `api-contracts.md`, `fixed-deposits-accounting.md`, `cash-unification.md` — remove contradictions from 001–004

### Stabilization

- Regression tests: overview API + Cash page + `GET /cash/balances` consistency; scope rules for bank cash attribution; FX fill vs warning
- Run `make test-critical` and fix failures **only if caused by CASH-UNIFY work**
- `docs/changelog.md` — CASH-UNIFY epic summary entry
- Optional: `make graphify` if module boundaries changed significantly

## Do not implement

- Same-portfolio FX conversion legs (FX-1)
- Live FX fetch on read path
- Broker ↔ bank transfer workflow (CASH-UNIFY-5)
- Changes to investment valuation formulas beyond display-layer totals

## Safety requirements

- Read-path FX conversion only — no backup required unless migrations added
- Never run destructive DB commands

## Expected files / areas

| Area | Files |
|------|--------|
| Overview service | `backend/cash/` overview service |
| FX conversion | `backend/fx/lookup.py` (reuse) |
| Tests | `backend/tests/test_cash_overview_api.py`, `frontend/src/pages/Cash.test.jsx` |
| Frontend | `frontend/src/pages/Cash.jsx`, summary/allocation copy if needed |
| Docs | `docs/current-state.md`, `docs/cash-ledger.md`, `docs/changelog.md`, `docs/decisions.md` |

## Tests / commands

```bash
make test-critical
make test
git diff --stat
```

## Final response format

1. Task ID: `005 — CASH-UNIFY-4`
2. Files changed
3. Tests run (`make test-critical`, `make test` — pass/fail)
4. `git diff --stat`
5. Commit hash
6. Deferred items (hand off to CASH-UNIFY-5, CASH-CORR-1, FX-1)
7. Safety notes
