# 006 — CASH-MODEL-REFINE-1: Decouple bank accounts from FD portfolio linking

**Status:** Done (2026-06-29)

**Depends on:** CASH-UNIFY-2 (superseded for FD create)

## Goal

Bank accounts are external funding sources. FD portfolio is explicitly selected at create time; `BankAccount.portfolio` controls cash visibility only.

## Implemented

- FD create API requires `portfolio_id` + `bank_account_id`
- Unlinked bank accounts may fund FDs
- FD create UI: portfolio selector + funding-source copy
- Docs updated across cash/FD/API/frontend

## Deferred

- Broker-funded FD
- Partial mixed funding
- Removing `BankAccount.portfolio` field
