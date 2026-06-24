# 008 — FD-TAX-1a: Interest & tax report polish

**ID:** FD-TAX-1a  
**Branch:** `agent/008-fd-tax-1a`  
**Depends on:** FD-TAX-1 (implemented)

## Goal

Polish the **FD interest & tax withheld report** (FD-TAX-1) for usability: empty states, loading/errors, filter persistence, and API edge-case clarity — **no new report sources**.

## Scope

- Frontend Fixed Deposits report section:
  - Empty state when no rows in date range
  - Clear loading and error states (reuse app patterns)
  - Filter UX: preserve `group_by`, date range, portfolio scope in URL or session
  - Accessibility: table headers, keyboard focus on filter apply
- Backend (minor): validate `group_by` enum errors return consistent `400` payload; document all query params
- Tests: API invalid `group_by`; frontend smoke for empty/filter states
- `docs/fixed-deposits.md`, `docs/api-design.md` — FD-TAX-1 section touch-up
- `docs/changelog.md`

## Do not implement

- CSV/export (FD-TAX-2)
- New ledger sources or accounting changes
- Tax advice copy beyond existing disclaimers
- Performance/summary side effects

## Safety requirements

- Read-only report — no `make backup-db` unless unexpected migrations
- Never run destructive DB commands

## Expected files / areas

| Area | Files |
|------|--------|
| Report API | `backend/debt/` or reports module serving `fixed-deposit-interest` |
| Frontend | Fixed Deposits page report section + tests |
| Docs | `docs/fixed-deposits.md`, `docs/api-design.md` |

## Tests / commands

```bash
cd backend && DJANGO_TEST_USE_SQLITE=1 .venv/bin/python -m pytest tests/test_fixed_deposit_interest_report_api.py -q
cd frontend && npm test -- --run src/pages/FixedDeposits.test.jsx
make test
git diff --stat
```

## Final response format

1. Task ID: `008 — FD-TAX-1a`
2. Files changed
3. Tests run (commands + pass/fail)
4. `git diff --stat`
5. Commit hash
6. Deferred items (FD-TAX-2)
7. Safety notes
