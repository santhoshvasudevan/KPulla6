# 008 — FD-MATURITY-VALUE-1: Estimated and user-confirmed maturity value

**Status:** Done (2026-06-29)

## Goal

FD create/edit shows app-calculated maturity estimate; user can override with bank-confirmed value; holdings table displays expected maturity value and source. Does not change settlement accounting.

## Implemented

- Model fields + migration `0011_fixed_deposit_maturity_value`
- `estimate_maturity_value` helper (Actual/365; compounded + simple interest)
- `GET /fixed-deposits/maturity-estimate` preview
- Create/update persistence with `AUTO_ESTIMATE` / `USER_CONFIRMED`
- FD form estimate section + override UX
- Holdings table maturity value column

## Deferred

- Broker-funded FD
- Tax calculation changes
- Auto-applying estimate to settlement proceeds
