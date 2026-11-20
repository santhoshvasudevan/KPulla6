# Count pending mutual fund purchases in portfolio value

## Problem Statement
Cash-aware portfolio history drops when a mutual fund purchase is funded before its units appear. The deposit is adjusted out of performance, but the pending investment is absent from value, creating false losses, rebounds, and drawdowns.

## Solution
Carry linked mutual fund purchase funding in daily portfolio value from cash settlement through the day before NAV recognition. Replace the pending amount with units on the recognition date.

## User Stories
1. As an investor, I want paid purchases counted during allotment so that my value history stays complete.
2. As an investor, I want deposits separated from performance so that funding does not look like a loss.
3. As an investor, I want weekend gaps handled so that Monday allotment does not cause an artificial rebound.
4. As an investor, I want same-day purchases counted once so that value is accurate.
5. As an investor, I want overlapping purchases included so that each payment is reflected.
6. As an investor, I want filtered history to include purchases already pending at the start.
7. As an investor, I want combined portfolios to reflect the same valuations as their individual portfolios.
8. As an investor, I want the ledger and NAV dates preserved so that I can reconcile statements.
9. As an investor, I want genuine NAV movements reflected when units appear.

## Implementation Decisions
- Derive pending value from linked mutual fund BUY settlements in cash-aware scopes and use cached FX for display currency.
- Apply the adjustment at the shared historical valuation boundary. Keep cash balances, external flows and API shape intact.
- Use a half-open settlement-to-recognition interval. Preserve existing missing-value handling.
- No migration or data backfill.

## Testing Decisions
- Exercise the existing portfolio performance seam with a funded Friday purchase, flat NAV and Monday allotment. Assert the value and return remain economically continuous.
- Cover the all-portfolio path through the shared valuation boundary. Use SQLite and synthetic records.

## Out of Scope
Scheme corrections, redemption timing, cash ledger edits and frontend redesign.

## Further Notes
Pending value is part of portfolio valuation and is unavailable for spending.
