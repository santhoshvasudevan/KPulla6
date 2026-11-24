# MF save or import blocked by cached NAV

## Symptom

MF create, update, or CSV import reports that exact-date cached NAV is required.
Or a historical NAV correction prompts for cash or retains `VALUE_MISMATCH`.

## Likely causes

- The scheme has no positive INR `MUTUAL_FUND` cache row on the exact `nav_date`.
  A newer or adjacent NAV does not qualify; refresh may not supply unpublished dates.
- A correction changes a statement/cash field, is a SELL or a no-op NAV save,
  or already has linked cash. Normal cash checks still apply in those cases.
- Statement market value differs from canonical NAV times units by more than
  1 INR. This is a warning, not permission to recalculate statement amounts.

## Quick checks

Use an authenticated session to request the exact scheme and statement NAV date:

```bash
curl -s -b cookies.txt \
  'http://127.0.0.1:8000/api/v1/nav/lookup?scheme_code=120503&nav_date=2026-11-20'
```

**Expected:** `200` with `scheme_code`, `nav_date`, `nav` (decimal string or null),
and `status` (`available` or `missing`). The example uses synthetic inputs.
Lookup does not refresh providers or change data. Keep session cookies private.

## Fix

1. Confirm the scheme and NAV date against the statement. In the transaction
   form, click **Fetch missing NAV** (only shown when lookup says `missing`). It
   calls `POST /api/v1/nav/fetch-missing` for that exact scheme/date, which writes
   only that market-cache row and never saves the transaction:

   ```bash
   curl -s -b cookies.txt -H "X-CSRFToken: $CSRF" -H 'Content-Type: application/json' \
     -d '{"scheme_code":"120503","nav_date":"2026-11-20"}' \
     'http://127.0.0.1:8000/api/v1/nav/fetch-missing'
   ```

   `outcome` `fetched` or `cache_hit` means the NAV is now cached. `date_unavailable`
   means MFAPI has no NAV for that date; `timeout` or `provider_failure` means try
   again after `retry_after_seconds` (60-second cooldown); `in_flight` means another
   request is already fetching it. Bulk `POST /api/v1/nav/refresh` with
   `scheme_codes` remains available for profiled schemes. If lookup still says
   `missing`, leave CSV imports blocked and investigate coverage. Never
   substitute an investment date or nearby NAV. CSV cannot carry a provisional
   NAV: provisional or consent columns reject the whole file.
   For a manual **BUY or SELL**, after `date_unavailable`, `timeout`, or
   `provider_failure`, the form offers a provisional NAV: enter the statement NAV,
   click **Get market value**, enter fees, and confirm both the unverified NAV and
   the actual paid value (BUY) or redemption proceeds (SELL). See
   [provisional BUY](../reference/api-transactions.md#provisional-mf-buy-50) and
   [provisional SELL and edits](../reference/api-transactions.md#provisional-mf-sell-and-edits-51).
   Editing a provisional row with a changed type, NAV date, or NAV needs a new
   **Fetch missing NAV**. If the edit returns "would make future cash balance
   negative", later cash entries depend on the old proceeds or date; the form keeps
   your values for review and nothing was saved.
2. Retry only after exact-date cache is available. The backend supplies canonical
   NAV. Preserve statement units, fees, market value, and paid value; do not alter
   them to suppress `VALUE_MISMATCH`.
3. For historical review, use `python manage.py preview_mf_nav_corrections --user-id ID`
   in the backend environment against an authorized database. It emits JSONL
   review rows plus a non-JSON summary and has **no apply mode**. Each row's
   `review_class` is `provisional` (awaiting provider NAV), `legacy`
   (pre-provenance row with no cache), `missing` (provider-sourced row whose cache
   is gone), or `cached_discrepancy` (reviewable against a cached NAV). The
   Transactions list shows the same states. Keep all personal
   output private, outside version control, public docs, issues, PRs, and shared logs.
4. Review each correction explicitly. Only a NAV-changing existing BUY with no
   linked cash and all statement/cash fields unchanged skips historical settlement
   backfill. Otherwise follow normal cash validation; do not invent funding or
   run a bulk historical rewrite. See the [complete guard](../cash-ledger.md#nav-only-mf-buy-correction-2026-11-24).

## Verify

- Exact-date lookup returns `available` with a positive decimal-string NAV.
- An authorized save/import uses canonical NAV while keeping statement amounts.
  Genuine `VALUE_MISMATCH` can remain; that does not mean cache lookup failed.
- A qualifying NAV-only BUY correction creates no historical cash rows. Other
  edits continue to enforce cash rules. Read-only preview ends with
  `Review rows: N. No records changed.` and never changes transactions or cash.

Do not perform live-data edits merely to verify documentation. Use synthetic
records for write acceptance checks and follow [data safety](../data-safety.md).
The synthetic SQLite harness, migration rollout, and rollback steps are in the
[provisional MF NAV release note](../maintenance/mf-nav-48-release.md). If
**Fetch missing NAV** or provisional saves fail with a missing table or column, the
`market_data.0007` / `transactions.0006` migrations have not been applied yet.

## Related

- [Transaction API](../reference/api-transactions.md)
- [MF validation and correction preview](../mutual-funds.md#nav-validation-strategy)
- [NAV verification after refresh](missing-prices-navs.md#symptom-transactions-shows-nav-not-in-cache-after-refresh)
