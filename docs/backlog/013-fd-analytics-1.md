# 013 — FD-ANALYTICS-1: Standalone FD performance API (design + MVP)

**ID:** FD-ANALYTICS-1  
**Branch:** `agent/013-fd-analytics-1`  
**Depends on:** 005 (cash/FD value history stable)

## Goal

Introduce **standalone Fixed Deposit performance metrics** (deferred from FD-ACC-8): principal-only IRR/yield-style metrics per FD, separate from stock/MF Metric Sheet.

## Scope

- Design section in `docs/fixed-deposits-accounting.md` or `docs/fixed-deposits.md`: define FD performance meaning (principal flows, recorded interest only, no daily accrual)
- New read endpoint: `GET /api/v1/fixed-deposits/{id}/performance` (or `/analytics/fixed-deposits/{id}`)
  - Returns: `xirr` or money-weighted return on FD principal + recorded interest payouts, `status`, date range, warnings
  - Uses cached data only; no accrued interest simulation
- Pure finance helper in `backend/finance/` if needed (framework-independent)
- Backend tests with known FD lifecycle fixtures
- Document in `docs/api-design.md`
- **No dashboard UI required** in this phase (API + docs only acceptable)

## Do not implement

- Daily accrued interest in portfolio value history (FD-ANALYTICS-2)
- Metric Sheet integration for FD as asset subject
- Changes to existing portfolio XIRR/TWROR formulas unless required for consistency bugs

## Safety requirements

- Read-only analytics — no backup unless migrations
- Never run destructive DB commands

## Expected files / areas

| Area | Files |
|------|--------|
| Finance | `backend/finance/fixed_deposit_returns.py` (new, optional) |
| Service | `backend/debt/fd_performance_service.py` (new) |
| API | debt or analytics URLs |
| Tests | `backend/tests/test_fd_performance_api.py` (new) |
| Docs | `docs/fixed-deposits.md`, `docs/api-design.md` |

## Tests / commands

```bash
cd backend && DJANGO_TEST_USE_SQLITE=1 .venv/bin/python -m pytest tests/test_fd_performance_api.py -q
make test-backend
git diff --stat
```

## Final response format

1. Task ID: `013 — FD-ANALYTICS-1`
2. Files changed
3. Tests run (commands + pass/fail)
4. `git diff --stat`
5. Commit hash
6. Deferred items (FD-ANALYTICS-2 UI, accrual)
7. Safety notes
