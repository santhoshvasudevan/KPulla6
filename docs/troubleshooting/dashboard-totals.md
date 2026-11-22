# Dashboard totals differ from transaction payments

## Symptom

Dashboard Current Value or Total Invested does not match a sum of transaction
amounts. Allocation amounts may also appear much larger than the headline value.

## Likely causes

- Dashboard uses the selected display currency; transaction amounts remain in
  their native currency. Compare INR with INR, not INR transactions with EUR KPIs.
- `total_invested` means remaining FIFO cost basis, not lifetime BUY payments,
  net deposits, or BUY payments minus SELL proceeds. Sold lots are removed at
  acquisition cost. Stock/MF FIFO basis excludes fees under the existing rule.
- `current_value` uses remaining units times latest cached prices/NAVs, plus
  included broker cash, fixed-deposit principal, and opt-in bank cash. It is not
  the sum of historical payments or a live provider quote.
- Missing purchase/switch history can produce oversell warnings. A NAV verified
  badge verifies price inputs; it does not prove holdings history is complete.
- **Confirmed allocation bug:** native stock/MF holding values were added to
  allocation buckets without conversion, then labelled as display currency.
  Headline totals could be correct while allocation values were wrong.
- **Confirmed FD valuation bugs (#36):** current FD conversion preloaded only
  same-day FX, so an eligible Friday rate was ignored on Sunday and FD principal
  disappeared with a missing-FX warning. Separately, FD amounts already in
  display currency could be merged with investment amounts still in portfolio
  valuation currency and converted again (for example INR 100,000 FD + INR 100
  stock at 0.01 → EUR 11 instead of EUR 1,001).

## Quick checks

1. Confirm the dashboard portfolio scope and display currency. Match the same
   portfolio and all transaction pages; filters and pagination affect visible rows.
2. Inspect `GET /api/v1/portfolio/summary?include_timeseries=false` with the same
   scope/currency. Review `fx_status`, `warnings`, `cash_summary`, and
   `allocation_buckets.currency` / `fx_status`.
3. Reconcile remaining lots per asset and, for mutual funds, per folio. Use cached
   NAVs/prices for current valuation. Do not treat SELL proceeds as cost removed.

**Example:** 100 units bought at NAV INR 42.50 have FIFO cost basis INR 4,250.
If the actual payment is INR 4,255 and current NAV is INR 50, the remaining basis
is still INR 4,250 and current value is INR 5,000. At cached INR-to-EUR 0.01, the
dashboard shows EUR 42.50 and EUR 50, not the INR payment total.

## Fix

1. Use the corrected backend: allocation now converts native stock/MF values
   using cached FX before adding them to display-currency buckets. Missing FX
   excludes unconvertible amounts and marks allocation partial; it never silently
   labels INR as EUR. No provider calls are made during rendering.
2. Reload the dashboard to discard any pre-fix in-memory summary response.
3. Hover the KPI labels for their definitions. To compare with INR transactions,
   select INR as display currency; do not change stored transactions for display.
4. Review source statements for oversells or incomplete switch/purchase history.
   Do not invent purchases, alter units, or delete transactions to force totals
   to agree. Data corrections require a separately verified source.

The headline arithmetic was independently reconciled against recorded MF lots
and cached NAVs during diagnosis. It was not changed to use gross BUY payments.
A separate lifetime-purchases metric would be a distinct product requirement.

## Verify

```bash
cd backend
DJANGO_TEST_USE_SQLITE=1 .venv/bin/python -m pytest \
  tests/test_mutual_fund_summary_performance_api.py \
  tests/test_fd_valuation_fx_consistency.py -q
```

**Expected:** tests pass, including INR-to-EUR allocation, missing-FX cases, and
the FD weekend lookback / single-conversion oracle (EUR 1,001 / native INR 100,100).
With complete positive-valued holdings and available FX, allocation values should
reconcile with headline value within rounding for the same scope and currency.
Headline and transaction values must remain unchanged by the allocation fix.

## Related

- [Troubleshooting overview](index.md)
- [API design: summary metrics](../api-design.md)
- [Cash ledger](../cash-ledger.md)
- [Missing prices or NAVs](missing-prices-navs.md)
