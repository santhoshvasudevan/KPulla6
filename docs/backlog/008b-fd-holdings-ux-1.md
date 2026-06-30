# FD-HOLDINGS-UX-1 — Fix maturity value display and improve FD holdings actions UX

**Branch:** `agent/009-fd-holdings-ux-1`  
**Status:** Done

## Problem

- Active FD holdings showed maturity value as `—` for legacy rows created before maturity fields were backfilled.
- Actions column was crowded with many vertical buttons.

## Solution

- API `resolve_maturity_display()` returns dynamic estimates when stored values are null.
- Management command `recalculate_fd_maturity_estimates` (`--dry-run` default, `--apply` to persist).
- Holdings table shows maturity value + source badge; action strip below each row.

## Out of scope

- Broker-funded FD, settlement automation from estimates, tax logic changes.
