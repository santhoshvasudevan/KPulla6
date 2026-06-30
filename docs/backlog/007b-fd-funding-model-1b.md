# 007B — FD-FUNDING-MODEL-1B: Fix historical FD seed-and-create flow

**Status:** Done (2026-06-29)

**Depends on:** FD-FUNDING-MODEL-1 (007)

## Problem

After 007, unlinked bank accounts could fund FDs, but backdated FD create still showed insufficient balance after seeding when:
- A cancelled FD's `FD_OPENING` debit remained in historical as-of balance (reversal dated at cancellation, not investment date).
- Seed date defaulted to investment date (same-day ordering ambiguity).
- FD opening debit validation used raw ledger balance, not funding-aware balance.

## Implemented

- **Funding balance** (`bank_funding_balance`): as-of balance excluding reversed movements and reversal rows; used by FD validation, `balance?as_of=`, and seed response.
- **FD_OPENING** debit uses funding balance validation.
- **Suggested seed date:** investment date − 1 day (UTC-safe); same-day deposits still allowed.
- **Duplicate seed:** `409` when same bank/date/amount/reason seed exists.
- **Insufficient balance 400:** `suggested_seed_date`, `suggested_seed_amount`, `bank_account_id`.
- **FD create UI:** seed panel defaults, disable while seeding, success refresh without auto-submit.
- **Diagnostic:** `manage.py bank_balance_timeline`.

## Deferred

- Broker-funded FD
- Partial mixed funding
- Combined seed+create in one transaction
