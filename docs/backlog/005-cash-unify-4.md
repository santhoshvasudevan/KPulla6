# 005 — CASH-UNIFY-4: Bank account link/delink UX + portfolio inclusion stabilization

**ID:** CASH-UNIFY-4  
**Branch:** `agent/005-cash-unify-4`  
**Depends on:** 004, 004a (recommended)  
**Status:** **Done** (2026-06-26); **4B hotfix** (link modal + display currency auto-select) same date.

## Goal

Productize **bank account portfolio link/delink** and stabilize how linked vs unlinked bank cash appears in portfolio Cash holdings, display-currency totals, and terminology.

**Model (CASH-MODEL-REFINE-0):** `BankAccount.portfolio` = **current portfolio link** / **default investment portfolio** — not ownership. Link/delink changes classification/inclusion only; **no cash movements**.

Design: [cash-unification.md](../cash-unification.md) §4 · [decisions.md](../decisions.md) CASH-MODEL-REFINE-0.

## Scope

### Bank account link/delink UX

- Settings → Bank Accounts: clear **Link to portfolio** / **Delink** actions (or equivalent explicit control).
- Copy explains: link = bank cash appears in portfolio **Bank Cash**; delink = external/unassigned bank cash.
- Link/delink via `PUT /bank-accounts/{id}` `portfolio_id` (set or null) — **no** new ledger writes.
- Confirm FD create still requires linked account; portfolio derives from link (CASH-UNIFY-2 unchanged).

### Portfolio inclusion behavior

- **Linked:** Bank cash balance appears in selected portfolio's Cash overview / summary inclusion when rules apply (`include_in_portfolio_value`, scope).
- **Delinked:** Bank cash excluded from single-portfolio Bank Cash section; visible as unassigned/external via `include_unassigned` on overview.
- Overview API and Cash page consistent after link change (refresh without balance change).

### Display-currency & terminology

- Stabilize display-currency KPI totals on Cash page and overview when FX partial (cached FX only).
- Clarify **Broker Cash** vs **Bank Cash** vs unassigned/external in summary allocation and holdings copy where ambiguous.
- Regression tests: overview scope after link/delink; `make test-critical` if cash paths touched.

### Documentation

- `docs/changelog.md`, `docs/cash-unification.md`, `docs/api-design.md`, `docs/frontend-design.md`
- Close MVP deferred item: display-currency cash totals on `/cash` where FX available

## Do not implement

- Actual broker ↔ bank **transfer** legs (CASH-UNIFY-5)
- Mistaken-entry **reclassification** workflow (CASH-CORR-1)
- Multi-portfolio bank sub-balances per account
- Live FX on read path
- Same-portfolio FX conversion legs (FX-1)

## Safety requirements

- Link/delink = FK update only — no automatic `CashMovement` or `CashLedgerEntry` creation
- `make backup-db` + `make db-safety-check` before any migration (unlikely)
- Never run destructive DB commands

## Expected files / areas

| Area | Files |
|------|--------|
| Bank account UI | `frontend/src/components/BankAccountManagement.jsx` |
| Overview / scope | `backend/cash/overview_service.py` (if inclusion rules need tightening) |
| Cash page | `frontend/src/pages/Cash.jsx` (terminology/copy) |
| Tests | `test_cash_overview_api.py`, `Cash.test.jsx`, `BankAccountManagement.test.jsx` |
| Docs | `docs/current-state.md`, `docs/cash-unification.md`, `docs/changelog.md` |

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
6. Deferred items (CASH-UNIFY-5, CASH-CORR-1, FX-1)
7. Safety notes
