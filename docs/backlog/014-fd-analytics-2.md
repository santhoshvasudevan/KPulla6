# 014 — FD-ANALYTICS-2: FD analytics dashboard surfacing

**ID:** FD-ANALYTICS-2  
**Branch:** `agent/014-fd-analytics-2`  
**Depends on:** 013

## Goal

Surface **FD performance and yield context** on Fixed Deposits UI and Dashboard allocation/Debt sections, consuming FD-ANALYTICS-1 API.

## Scope

- Fixed Deposits page: per-FD performance column or detail drawer (XIRR/yield, principal, recorded interest, status)
- Dashboard: optional FD summary KPI or tooltip on Debt bucket when `has_fixed_deposits`
- Warnings when performance cannot be computed (cancelled FD, missing dates)
- Frontend tests: Fixed Deposits + Dashboard smoke
- `docs/page-layouts.md`, `docs/frontend-design.md`, `docs/changelog.md`
- Explicit copy: principal-only; no daily accrual unless product rules updated

## Do not implement

- Daily accrued interest valuation in `metric=value` timeseries
- FD as Compare / Metric Sheet asset subject
- Tax reporting changes (FD-TAX)

## Safety requirements

- Read-only UI — no backup required
- Never run destructive DB commands

## Expected files / areas

| Area | Files |
|------|--------|
| Frontend | `frontend/src/pages/FixedDeposits.jsx`, `Dashboard.jsx`, components |
| API client | `frontend/src/api.js` |
| Tests | `FixedDeposits.test.jsx`, `Dashboard.test.jsx` |
| Docs | `docs/page-layouts.md`, `docs/fixed-deposits.md` |

## Tests / commands

```bash
cd frontend && npm test -- --run src/pages/FixedDeposits.test.jsx src/pages/Dashboard.test.jsx
make test
make test-critical
git diff --stat
```

## Final response format

1. Task ID: `014 — FD-ANALYTICS-2`
2. Files changed
3. Tests run (commands + pass/fail)
4. `git diff --stat`
5. Commit hash
6. Deferred items (accrual, Metric Sheet FD subject)
7. Safety notes
