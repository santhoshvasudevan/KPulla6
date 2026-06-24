# 011 — FD-ACC-10D: Reversal framework audit & stabilization

**ID:** FD-ACC-10D  
**Branch:** `agent/011-fd-acc-10d`  
**Depends on:** 010

## Goal

**Audit and stabilize** FD-ACC-10C reversals: classifier regression, portfolio value history alignment, docs/decisions closure, and E2E scenario coverage.

## Scope

- Extend `backend/tests/test_fixed_deposit_end_to_end_accounting.py` with reversal scenarios (settlement, renewal, cancel paths)
- Classifier regression: `test_fd_cash_flow_classification.py`, `test_cash_movement_reversals_api.py`
- Verify summary, holdings, `metric=value`, XIRR/TWROR after each reversal type
- Docs: `fixed-deposits-accounting.md` FD-ACC-10C implementation notes; remove “deferred to 10C” language
- `docs/decisions.md` ADR for 10C/10D
- `docs/changelog.md` — FD-ACC-10C + 10D entries
- Fix bugs found during audit (minimal scope only)

## Do not implement

- New reversal types beyond 10C scope
- Accrued interest valuation (FD-ANALYTICS)
- Via-bank renewal or bank transfer APIs

## Safety requirements

- Prefer test-only fixes
- If production fixes require dev-DB verification with writes: `make backup-db` + `make db-safety-check`
- Never destructive DB commands

## Expected files / areas

| Area | Files |
|------|--------|
| Tests | `backend/tests/test_fixed_deposit_end_to_end_accounting.py`, `test_fd_cash_flow_classification.py` |
| Value history | `debt/portfolio_value.py`, `portfolios/performance_service.py` (only if bugs found) |
| Docs | `docs/fixed-deposits-accounting.md`, `docs/fixed-deposits.md`, `docs/current-state.md` |

## Tests / commands

```bash
make test-critical
make test-backend
make test
git diff --stat
```

## Final response format

1. Task ID: `011 — FD-ACC-10D`
2. Files changed
3. Tests run (`make test-critical`, `make test` — pass/fail)
4. `git diff --stat`
5. Commit hash
6. Deferred items
7. Safety notes
