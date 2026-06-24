# 001 — CASH-UNIFY-0: Unified cash model (design)

**ID:** CASH-UNIFY-0  
**Branch:** `agent/001-cash-unify-0`  
**Type:** Docs-only (no runtime changes)  
**Status:** Design complete (2026-06-24)

## Goal

Document a **unified cash domain model** and implementation roadmap so users and agents consistently distinguish portfolio broker cash (`CashLedgerEntry`) from bank ledger cash (`CashMovement`), without merging the two ledgers.

## Delivered

- **Dedicated design doc:** [cash-unification.md](../cash-unification.md)
- Portfolio composition taxonomy (securities, MF, FD, cash holdings: broker + bank; physical deferred)
- Two-ledger separation rules; read-path no cross-ledger auto-writes
- Future `BankAccount.portfolio` ownership; FD portfolio derived from bank account
- Future Cash tab layout (Broker / Bank / Total sections)
- Backfill strategy (infer when unambiguous; manual assignment when not)
- Safety & accounting rules; phases CASH-UNIFY-1..6 mapped to backlog 002–005
- ADR in [decisions.md](../decisions.md) · cross-links in architecture, current-state, FD docs, api-design, frontend-design, page-layouts, product-rules, cash-ledger appendix
- Backlog tasks [002](../backlog/002-cash-unify-1.md)–[005](../backlog/005-cash-unify-4.md) aligned to roadmap

## Do not implement (confirmed)

- No API endpoints, models, migrations, or frontend changes in this phase
- Do not merge `cash_ledger_entries` and `cash_movements` tables
- Do not implement CASH-UNIFY-1..4 runtime features in this task

## Safety requirements

- Docs-only — `make backup-db` / `make db-safety-check` not required
- Do not run destructive DB commands

## Tests / commands

```bash
git diff --stat
git status --short
```

Tests skipped — docs-only.

## Final response format

1. Task ID: `001 — CASH-UNIFY-0`
2. Files changed
3. Tests run: `skipped — docs-only`
4. `git diff --stat` output
5. Commit hash or “not committed”
6. Deferred items (CASH-UNIFY-5 broker-bank transfer; CASH-UNIFY-6 physical cash)
7. Confirmation: no runtime behavior changed
