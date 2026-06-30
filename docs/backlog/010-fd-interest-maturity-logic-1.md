# FD-INTEREST-MATURITY-LOGIC-1 — Compounded vs payout FD estimate behavior

**Branch:** `agent/010-fd-interest-maturity-logic-1`  
**Status:** Done

## Problem

Payout FDs (monthly/quarterly/half-yearly/annual) incorrectly showed maturity value above principal using simple interest added to principal.

## Solution

- **COMPOUNDED:** maturity value = principal + compounded interest.
- **Payout:** maturity value = principal; estimate total + periodic interest separately.
- API `estimate_type`: `COMPOUNDED_MATURITY` | `PAYOUT_INTEREST`.
- `maturity_value_source`: `AUTO_PRINCIPAL` for payout auto estimates.
