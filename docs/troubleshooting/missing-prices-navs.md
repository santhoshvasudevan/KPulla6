# Missing prices or NAVs

## Symptom: Transactions shows NAV Not In Cache after refresh

### Likely causes

- The transaction was imported before NAV history was cached. Older versions
  displayed the saved verification snapshot even after a successful refresh.
- A newer NAV is cached, but the transaction's exact `nav_date` is missing.
  Older incremental refreshes started after the latest cached date and could miss
  older imported transactions or gaps within existing history.
- The provider has no NAV for that exact date, or its request failed.

### Quick checks

Check `scheme_code`, `nav_date`, and `nav_verification_message` in the transactions
response. Compare against an exact-date `HistoricalPrice` row with
`asset_type=MUTUAL_FUND`; having a recent NAV alone is insufficient.

The project uses MFAPI (`https://api.mfapi.in/mf/{scheme_code}`) through
`AmfiNavProvider`. The full-history URL can return thousands of rows while an
incremental `?startDate=YYYY-MM-DD&endDate=YYYY-MM-DD` request returns none.
That is expected when no NAV has been published in the requested range.

### Fix

1. Run `make sync-mutual-fund-navs` (or use `POST /api/v1/nav/refresh` with
   `scheme_codes` for selective refresh).
2. Reload Transactions. API responses now recheck the exact-date cache, without
   changing saved transaction values or making provider calls during reads.
3. Refresh now includes missing historical transaction NAV dates, not just dates
   after the newest cached NAV. If the provider still has no exact-date row, the
   warning correctly remains. Check the source statement's NAV date; do not
   replace it with investment date or a nearby NAV just to remove the warning.

**Refresh results:** `synced` means NAV rows were written. `skipped` includes
already-current/no-new-data schemes or missing transaction anchors. A valid empty
response is not a provider failure. Logs still warn when required transaction
NAV dates remain missing. Timeouts, error statuses, and malformed responses count
as `failed`; retry those schemes later. Skipped does not mean fully verified.

### Verify

```bash
cd backend
DJANGO_TEST_USE_SQLITE=1 .venv/bin/python -m pytest tests/test_mutual_fund_nav_validation.py tests/test_mutual_fund_nav_sync.py tests/test_amfi_nav_provider.py -q
```

**Expected:** tests pass. After refresh, an exact-date cached NAV produces
`VERIFIED` only if NAV and market-value tolerances also pass. `NAV_MISMATCH` and
`VALUE_MISMATCH` are separate, genuine discrepancies. No live transaction or cash
ledger edits are needed to repair a stale displayed label.

## Symptom: holdings show stale or missing values

Run:

```bash
make refresh
```

Or targeted sync:

```bash
make sync-prices
make sync-mutual-fund-navs
```

## Symptom: warnings on dashboard

Check `price_status`, `fx_status`, and API `warnings` — often missing FX or price for a symbol/date.

Diagnostics:

```bash
cd backend && python scripts/diagnose_nav_coverage.py
cd backend && python scripts/diagnose_fx_coverage.py
```

Concept: [Cached market data](../concepts/cached-market-data.md)

How-to: [Refresh market cache](../how-to/refresh-market-cache.md)
