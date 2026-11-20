# CSV import asks for cash again after confirmation

## Symptom

**This import requires additional cash** remains open after clicking
**Add required cash deposits and import all rows**, and the import fails.

The initial dialog is expected for an unfunded cash-aware portfolio. BUYs need
broker cash in their native currency. Bank cash or another currency does not
automatically fund them.

## Likely causes

- Confirmation flags are absent from the import request.
- A backend validation error leaves the confirmation dialog open.
- **Confirmed precision bug:** CSV preview used unrounded cash effects while the
  ledger accepts four decimal places. High-precision MF values or stock quantity
  times price could produce invalid proposed deposits. The backend returned HTTP
  500 with `ValidationError` on `amount`: **Ensure that there are no more than 4
  decimal places.**

## Quick checks

1. Inspect the import request in browser developer tools (Network), not just the
   dialog heading. The confirmed request must include `create_cash_deposits=true`
   and `cash_preview_confirmed=true`, with the intended `portfolio_id`.
2. Check backend logs for the precision error above. Do not share cookies, tokens,
   or personal CSV contents.

**Expected:** an unconfirmed cash shortfall returns 409 without writes. A confirmed
valid import returns HTTP 200 with `success: true`. HTTP 500 is not expected.

## Fix

1. Use the corrected backend: preview rounds each simulated BUY/SELL cash effect
   to four decimal places with `ROUND_HALF_UP`, matching settlement persistence
   before computing shortfalls. No CSV rounding workaround or schema change is
   required for this fix.
2. Restart the backend if automatic reload is disabled.
3. Inspect Transactions and Broker Cash before retrying if the previous request's
   outcome is uncertain. Successful imports are not idempotent.
4. Preview again and confirm once. If it still fails, inspect the response and
   logs; the dialog remaining open does not mean confirmation was ignored.

**Data safety:** deposits, transactions, and settlements are one atomic import.
Tests verify rollback on deposit validation failure and later transaction failure,
including earlier writes from that attempt. Preview and unconfirmed 409 responses
write nothing. Do not delete a profile, reset the database, or manually add
duplicate deposits to work around an unexplained failure.

## Verify

Confirm the imported row count and same-currency deposits and settlements in the
selected portfolio. Run the regression tests in isolated SQLite:

```bash
cd backend
DJANGO_TEST_USE_SQLITE=1 .venv/bin/python -m pytest tests/test_csv_import_cash_preview.py -q
```

**Expected:** all tests pass, including precision and atomic rollback coverage.

## Related

- [Troubleshooting overview](index.md)
- [Cash ledger](../cash-ledger.md)
- [CSV API contract](../api-design.md#csv-cash-preview-cash-5)
- [Database safety problems](database-safety.md)
