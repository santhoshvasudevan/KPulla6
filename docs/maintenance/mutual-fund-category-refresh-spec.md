# Draft specification: Cache mutual fund categories during NAV refresh

## Problem

The local database has 24 mutual fund profiles. None has a nonblank scheme category or scheme type. The profile already has fields for both. The NAV provider currently reads NAV points and drops the response metadata, so refreshing prices does not fill the existing category field. Assets therefore shows “Category not recorded.”

## Source and terminology

MFAPI documents category and scheme type separately in the NAV response metadata. A live request to the public latest-NAV endpoint confirmed the shape. [MFAPI documentation](https://www.mfapi.in/docs/)

- **Provider category:** The first part of the provider's category string, with a trailing “Scheme” removed for display.
- **Provider subcategory:** The rest after the first category separator, retaining any internal hyphens.
- **Asset class:** The portfolio's investment classification, which is separate from the provider taxonomy. A fund that counts as Equity in the overview may have provider category Other and subcategory Index Funds.
- **Scheme type:** The provider's open-ended or closed-ended designation, separate from category.

## Proposed solution

1. Capture metadata from successful per-scheme NAV history or latest responses already fetched during refresh. Validate the normalized scheme code against the requested scheme before storing anything. Use the existing scheme profile as the owner of metadata. Never match by fund name or folio.
2. Keep the full provider category in the existing `scheme_category` field and store the provider scheme type in `scheme_type`. Derive normalized category and subcategory with a shared backend parser. Storing the raw field preserves both pieces and avoids duplicate category fields; provenance flags keep provider metadata out of asset-class inference. The first separator between terms is the split point, with support for surrounding whitespace and spaced dash variants. Preserve hyphens within names. An unsplit value gives a category with no subcategory. Empty values leave both unavailable.
3. Agreed ownership rule: fill blank fields. Missing, malformed, mismatched or blank metadata cannot erase valid stored values. A conflict with an existing nonblank value is reported for review. The metadata update is idempotent and does not require a new NAV row to have been inserted.
4. Ensure held schemes skipped by the NAV freshness check can still get metadata. Reuse any response already obtained in the refresh. If no response was obtained and category is missing, use a bounded, rate-limited latest request for that scheme. A failed metadata request must not undo valid NAV updates. Report how many profiles were filled, unchanged, unavailable or conflicting.
5. Provide a read-only backfill preview with scheme code, existing value, proposed category/subcategory and reason if skipped. Apply only after the preview is reviewed and the database backup and safety checks have passed. Normal refresh can fill blank metadata once the behavior is released. No edits to transaction or cash rows.
6. Assets Breakdowns reads cached data only. Group by effective category → subcategory → scheme as described below. Use the provider labels where the user has no personal assignment. Skip an absent subcategory level. Keep missing metadata visible and preserve existing value, weight, count and scheme-unit rules. Do not change the Equity/Debt classification policy as part of this work.

## Proposed personal categories

- A **personal category** is a user-defined category and optional subcategory for a scheme in Assets Breakdowns. It applies to all folios of that scheme across that user's portfolios. The provider category and portfolio asset class remain separate.
- Store the assignment against the authenticated user and stable scheme profile. One assignment per user and scheme. Category is required; subcategory is optional. Validate and trim labels. Suggest that user's existing labels to avoid accidental duplicates.
- Assets uses the personal pair when present, otherwise the cached provider pair. Mark personalized rows and show the provider label in the edit view. Provide a reset to provider action. Edits and resets do not change the shared fund profile, other users' reports, overview Equity/Debt totals, holdings, or NAV.
- Example: a user assigns both Tata Nifty 50 Index Fund and Sundaram Nifty 100 Equal Weight Fund to **Equity → Index Fund**. They appear together in the personal category breakdown, even if the provider uses a different label. Group the category breakdown by the effective category and subcategory across visible funds so an asset-class wrapper cannot split that personal group. The Equity/Debt filters and overview cards continue to use portfolio asset class.
- Proposed first interface: edit or reset categorization from the scheme row in Breakdowns and reuse previously entered labels. Keep bulk assignment and a separate category-management screen for a later decision.
- A per-user assignment requires a Django migration. The provider metadata cache uses the existing profile fields with provenance flags.

## Acceptance and tests

- `Equity Scheme - ELSS` displays as Equity → ELSS; `Other Scheme - Index Funds` displays as Other → Index Funds under its existing asset class.
- Split once. A subcategory with embedded hyphens stays intact. Test whitespace, unsplit strings, dash variants and missing or malformed metadata.
- A matched provider response fills the existing profile even if cached NAV rows already exist. Repeating the same refresh changes nothing.
- Test code mismatch, missing metadata, timeout and nonblank conflicts. Verify existing prices and portfolio records survive each case.
- Preview is read-only and identifies missing profiles without applying changes. Verify implementation with provider fixtures, SQLite refresh tests, scoped holdings API tests and an expandable Breakdowns UI test.

- Two schemes with different provider classifications can share one personal category. Test two folios, two portfolios and two users; assignments apply to all folios for the owning user only. Verify refresh and reset, cross-user access controls, and unchanged overview classifications.
- Test category-only assignments, unknown provider metadata with a personal assignment, and unchanged percentages and units when schemes move groups.

## Out of scope

Changing portfolio asset exposure through a personal category, fetching metadata on page load, changing NAV math, adding new asset types, and modifying transactions or cash ledger data.

## AMC metadata and folio grouping

Fill a blank scheme profile fund house from verified MFAPI metadata in refresh and backfill, including profiles that already have category and scheme type. Preserve existing nonblank names and report conflicting provider values. Preview must show the existing and proposed fund house before applying changes.

By AMC uses the cached fund house. By folio groups by normalized fund-house name and folio number. Two schemes with the same verified fund house and folio appear in one expandable row. When the fund house is unavailable, retain the scheme-specific fallback so unrelated folios are never merged on number alone. No transaction, folio, or NAV rows need edits.
