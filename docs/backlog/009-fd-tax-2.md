# 009 — FD-TAX-2: Interest & tax report CSV export

**ID:** FD-TAX-2  
**Branch:** `agent/009-fd-tax-2`  
**Depends on:** 008

## Goal

Add **CSV export** for the FD interest and tax withheld report (deferred from FD-TAX-1).

## Scope

- New endpoint: `GET /api/v1/reports/fixed-deposit-interest/export` (or `?format=csv` on existing report)
  - Same filters as JSON report: scope, dates, `display_currency`, `group_by`
  - CSV columns: stable header row documented in API spec
  - Content-Type `text/csv`; filename includes date range
- Frontend: Export CSV button on Fixed Deposits report section
- Read-only — no ledger mutations
- Disclaimer: not tax advice
- Tests: CSV shape, filter parity with JSON, cancelled/reversed exclusions
- `docs/api-design.md`, `docs/fixed-deposits.md`, `docs/changelog.md`

## Do not implement

- PDF export, email, or scheduled reports
- New report metrics or accounting changes
- FD-TAX-1a UI polish unless required for export button placement

## Safety requirements

- Read-only export — no backup required
- Never run destructive DB commands

## Expected files / areas

| Area | Files |
|------|--------|
| Report service | backend report module |
| Views | report export view |
| Frontend | Fixed Deposits page, `api.js` |
| Tests | `backend/tests/test_fixed_deposit_interest_report_api.py` |

## Tests / commands

```bash
cd backend && DJANGO_TEST_USE_SQLITE=1 .venv/bin/python -m pytest tests/test_fixed_deposit_interest_report_api.py -q
make test-backend
cd frontend && npm test -- --run src/pages/FixedDeposits.test.jsx
git diff --stat
```

## Final response format

1. Task ID: `009 — FD-TAX-2`
2. Files changed
3. Tests run (commands + pass/fail)
4. `git diff --stat`
5. Commit hash
6. Deferred items
7. Safety notes
