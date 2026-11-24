# Cache-first provisional MF NAV release (#48)

Release evidence and rollout handoff for parent issue
[#48](https://github.com/santhoshvasudevan/KPulla6/issues/48). Prepared by
[#54](https://github.com/santhoshvasudevan/KPulla6/issues/54). This page authorizes
nothing: publication, merge, and the live migration each need the user's explicit
approval. No live database, live portfolio, or live provider was used for this evidence.

## Pinned lineage

| Step | Commit | Summary |
|------|--------|---------|
| Strict-NAV baseline | `9d5237f1a3f9ffc918a05ede05a669233d0c02ef` | Cached MF NAV writes and safe historical corrections |
| #49 | `8e2eecfd2d5619a40da37b88317b5094ed823dd3` | Exact-date missing NAV fetch with cooldown |
| #50 | `28dff3a55cada06ab4cded972ffdfd360607afc7` | Confirmed provisional BUY, backend Market Value |
| #51 | `c73e18896e2bc1e9200df4f43b7a1fd7bda8adf5` | Provisional SELLs and transaction edits |
| #52 | `c9b3553e9411a642be716523ff73ff07abd430d6` | Provisional valuation across scopes, folios, currencies |
| #53 | `49a3fd39e63a17c9782c786e12693667964761f5` | Provider-only fund analytics, review states, strict CSV |
| #54 | Commit adding this page on `agent/54-mf-nav-acceptance-release` | Release evidence, acceptance harness, rollout notes |

The tickets form one linear chain on the baseline. Integration branch `codex/mf-nav-48`
(local and `origin`) points at `49a3fd3`, the #53 tip. #54 adds only documentation and
`scripts/acceptance/`; it changes no application code, migration, or frontend source.

Integration diff `git diff 9d5237f..49a3fd3`: 59 files, +5465/−174. Per ticket: #49 18 files
(+1048/−8), #50 29 (+1905/−133), #51 22 (+1006/−57), #52 15 (+688/−16), #53 26 (+891/−33).

### Relationship to `main`

`main` does **not** contain the baseline. The baseline commit sits on
`origin/local/fd-rollout`, one commit after merge-base `6ffe63f` ("Use deposit currency for
FD interest report splits"). `origin/main` (`25419fa`, PR #47) has two commits since that
merge-base, with no migrations. A trial `git merge-tree origin/main 49a3fd3` auto-merges
`docs/api-design.md` and conflicts only in `docs/changelog.md` (both sides add top entries;
keep both). Releasing to `main` therefore also releases the baseline commit `9d5237f`.

## Migrations

| Migration | Operation | Data effect |
|-----------|-----------|-------------|
| `market_data.0007_mutualfundnavfetchstate` | Creates `mutual_fund_nav_fetch_states` (unique `scheme_code`+`nav_date`) | New, empty table; no backfill |
| `transactions.0006_mutualfundtransactiondetail_nav_provenance` | Adds `nav_source` (default `UNKNOWN`), `provisional_confirmed_at`, `provisional_confirmed_by`, `provisional_failure_reason`, `provisional_attempt_id` to `mutual_fund_transaction_details` | Existing rows get `UNKNOWN`/empty; no row rewrite |

Both migrations are additive. Their reverse operations drop the new table or columns.
`nav_source` and `provisional_failure_reason` are `NOT NULL` with no database default.
Django sets the default only while adding the column, and the SQLite DDL check confirmed
this. Code older than #50 does not send these columns, so its MF inserts fail once
`transactions.0006` is applied (see [Rollback](#rollback)).

## Frozen-tree verification

All commands ran against the #54 tree: application code identical to `49a3fd3`, plus the
files added by #54. The dev Postgres database was never used.

| Check | Command | Result |
|-------|---------|--------|
| Backend suite | `cd backend && DJANGO_TEST_USE_SQLITE=1 .venv/bin/python -m pytest -q` | 1623 passed |
| Frontend suite | `cd frontend && npm test -- --run` | 45 files, 734 tests passed |
| Frontend build | `cd frontend && npm run build` | Built (existing >500 kB chunk warning) |
| Docs build | `cd backend && .venv/bin/python -m mkdocs build -f ../mkdocs.yml --strict` | Passed |
| Docs check | `cd backend && .venv/bin/python ../scripts/check_docs_consistency.py --strict` | `docs-check: OK` |
| Migration drift | `cd backend && DJANGO_TEST_USE_SQLITE=1 .venv/bin/python manage.py makemigrations --check --dry-run` | No changes detected |
| Migration apply/reverse | Disposable SQLite file via `scripts/acceptance/mf_nav_48_server.py manage`: `migrate`, `migrate market_data 0006_…`, `migrate transactions 0005_…`, `migrate` | Apply, unapply, and re-apply OK for both |
| Whitespace | `git diff --check 9d5237f..HEAD` | Clean |

## Synthetic browser acceptance

The harness lives in `scripts/acceptance/`:

- `mf_nav_48_server.py serve` refuses to start when `DATABASE_URL` is set. It creates a new
  SQLite file database in `--run-dir`, migrates it, and seeds synthetic users,
  portfolios, NAV cache, and INR↔USD FX. It swaps the MF NAV provider for a stub that
  reads `provider_book.json` and logs every call to `provider_calls.jsonl`. It also blocks
  every non-loopback socket and logs attempts to `blocked_network.jsonl`.
- `mf_nav_48_vite.mjs` starts Vite from `frontend/` with the unmodified `vite.config.js`
  and points the proxy at the acceptance backend.
- `mf_nav_48_browser.cjs` uses Playwright (headless Chromium) to drive the real UI. It
  uses in-page `fetch` for API assertions. Results and screenshots go to the run directory,
  outside the repository.

```bash
backend/.venv/bin/python scripts/acceptance/mf_nav_48_server.py serve \
  --run-dir /tmp/kp-mfnav-48/run --port 18000 --frontend-origin http://127.0.0.1:15173
node scripts/acceptance/mf_nav_48_vite.mjs --backend http://127.0.0.1:18000 --port 15173
PLAYWRIGHT_MODULE=/path/to/node_modules/playwright \
  node scripts/acceptance/mf_nav_48_browser.cjs --run-dir /tmp/kp-mfnav-48/run
```

Playwright is not a project dependency. Point `PLAYWRIGHT_MODULE` at any local install
whose Chromium is already downloaded.

**Served checkout:** the driver resolves each listening PID with `lsof`, then reads the
PID's working directory and runs `git rev-parse` there. Backend
(`…/kpulla6-mf-nav-48/backend`) and frontend (`…/kpulla6-mf-nav-48/frontend`) both
reported this worktree and its `HEAD`. The backend database was
`/private/tmp/kp-mfnav-48/<run>/acceptance.sqlite3`. Health through the Vite proxy returned
`{"status":"ok","database":"ok"}`. Both migrations were applied.

**Result: 98 of 98 checks passed.** The provider stub saw exactly 6 calls. Three were
explicit **Fetch missing NAV** clicks, two came from the explicit `POST /nav/refresh`, and
one was the owner's attempt in the isolation scenario. No call came from a read path. No
external network connection was attempted.

| Scenario | Checks | What was verified |
|----------|--------|-------------------|
| Served checkout | 4 | Listener PIDs, cwd, and commit; SQLite file DB; migrations applied |
| Cache hit, no provider | 6 | Lookup fills the read-only NAV; no fetch button; BUY saved as `PROVIDER_CACHE`; explicit fetch returns `cache_hit` with no provider call |
| Missing date, fetch success | 6 | Save blocked while missing; one exact-date provider call; NAV cached; BUY saved |
| Unavailable, cooldown, provisional BUY | 14 | `date_unavailable` with 60 s countdown and disabled button; server Market Value; save blocked until both confirmations; provenance saved; NAV cache unchanged; one cash settlement; a new form gets `cooldown` with no provider call |
| Timeout, provisional SELL | 13 | `timeout` with countdown; server-calculated proceeds (units × NAV − fees); one SELL settlement credit; API repeat returns `cooldown` |
| Provisional edit | 7 | Edit keeps id, provisional NAV, and provenance; Market Value recalculated by the server; linked cash row updated in place, no orphan |
| Scope, FX, provider-only analytics (read-only) | 19 | Provisional banners and badges on Dashboard and Assets. INR and All scopes flag provisional; USD scope does not. INR/USD/EUR reads return 200. USD display uses cached FX; missing EUR FX is flagged `fx_unavailable` with a banner. Asset Detail and Compare are provider-only (`fund_nav_source: PROVIDER_CACHE`, no fund series from a provisional NAV) and badge **Includes provisional NAV**. Reads made no provider calls and no NAV cache writes |
| Later cached valuation and review | 18 | Explicit refresh caches later NAVs. Holdings use the newest provider NAV and the banner clears. History stays flagged only for uncovered provisional days. Recorded rows are untouched. The list shows **Provider NAV now available — review** and **Provisional NAV — awaiting provider**. `preview_mf_nav_corrections` reports `Review rows: 2 (provisional: 1, … cached_discrepancy: 1). No records changed.` An explicit re-save moves the row to `PROVIDER_CACHE` with statement fields and its single cash row preserved |
| Auth, CSRF, cross-user | 9 | Missing CSRF token returns 403; anonymous requests return 403; the other user sees no rows, gets 404 editing them, sees cooldown without the owner's `attempt_id`, and gets 400 when reusing it |
| Console | 2 | Only HTTP errors were the pre-login `/auth/me` probe and the deliberate 4xx checks |

The provider stub and network block mean the acceptance never contacts MFAPI. The real
MFAPI request and parsing paths are covered by pytest. The in-flight claim (30 s) is
covered by pytest rather than the browser run.

## Review notes

- **API compatibility:** response fields are additive (`nav_source`, `nav_provisional`,
  `provisional_*`, `nav_review`, `fund_nav_source`, holdings and summary `nav_provisional`).
  The new endpoints are `POST /nav/fetch-missing` and `POST /nav/provisional-preview`.
  CSV now rejects provisional and consent columns, and a failing batch rolls back fully.
- **Provider on read:** only `fetch-missing` and the existing refresh paths call the
  provider. Reads across every scope and display currency made no provider calls.
- **Frontend finance:** Market Value, SELL proceeds, and tax come from the server. The UI
  only displays them.

## Rollout (requires explicit approval)

Do not run `make dev` or `make migrate` against the live dev database before step 4.
`make dev` applies migrations on startup.

1. **Pin.** Confirm the approved commit is published (`git ls-remote origin
   refs/heads/<branch>`). Update the serving checkout to it and verify `git rev-parse
   HEAD` and `git status --short --branch`. Record any local work before switching.
2. **Back up.** Run `make backup-db` and confirm that the backup file exists and is not empty.
3. **Safety counts.** Run `make db-safety-check`. Record the database name and the
   transaction, portfolio, and historical price counts. Also record
   `cd backend && .venv/bin/python manage.py showmigrations market_data transactions`.
4. **Approval.** Get the user's explicit approval to migrate, citing the backup file and counts.
5. **Migrate.** `make migrate`. Only `market_data.0007` and `transactions.0006` should apply.
6. **Post-check.** Run `make db-safety-check` again; counts must match step 3. Confirm both
   migrations show `[X]`. Restart the stack from the pinned checkout, then verify the
   process working directories (`lsof -a -p <pid> -d cwd`), `curl -fsS
   http://127.0.0.1:8000/api/v1/health`, and the frontend.
7. **Feature check, read-only.** Open Transactions and an existing MF edit form, and
   confirm the NAV lookup status shows. Optionally run `preview_mf_nav_corrections
   --user-id ID` and keep its output private. Existing rows show `UNKNOWN` provenance and
   change only when explicitly re-saved. Do not create live rows as acceptance fixtures;
   use the synthetic harness instead.
8. **Report** three results separately: published commit, local checkout commit, and
   running app verified (health and feature checks, plus anything blocked or unverified).

### Rollback

Prefer fixing forward. A rollback needs the same backup, counts, and approval as the rollout.

- **To #49 (`8e2eecf`) or earlier:** first, while still on the release checkout, list
  provisional rows (`preview_mf_nav_corrections`, `review_class: provisional`), because
  their unverified marker is about to be dropped. Then run
  `manage.py migrate transactions 0005_transaction_dividend_cash_fields`. That removes
  `nav_source` and `provisional_*`; NAV, units, Paid Value, and cash are kept. Only then
  check out the older commit and restart. Switching code without this step leaves reads
  working, but every MF create, edit, or import fails on the `NOT NULL` provenance columns.
- **To the baseline (`9d5237f`) or earlier:** also run
  `manage.py migrate market_data 0006_personalfundcategory_classification`, which drops
  the cooldown and attempt state. Older code ignores that table, so this step is optional.
- **Between #50 and #53:** no schema change; check out the commit and restart.
- Migrations never rewrite transactions, settlements, or the NAV cache. If the
  post-rollback counts differ from step 3, restore the step 2 backup per
  [Back up and restore](../how-to/backup-restore-database.md).

## Deferred (non-blocking)

- Per-point provenance on performance points (range-level warning only) (#52).
- Oversell with provisional folios; MF value-history days with zero MF value still need
  INR FX in non-INR base portfolios (existing policy) (#52).
- Future-impact recheck for stock/ETF edits (#51).
- Metric Sheet/Compare `personal_metrics.xirr` uses the latest cached NAV, while the
  holdings/Asset Detail header XIRR uses the provisional overlay (#53).
- Observed during acceptance, **pre-existing** since the initial commit: when display FX
  is missing, `GET /portfolio/summary` reports `fx_status: fx_unavailable`, but the
  headline `current_value` falls back to the unconverted base-currency investment subtotal
  instead of null.
- The provenance columns have no database default, so code older than #50 cannot write
  MF rows on the migrated schema. Adding `db_default` would need a new migration; this
  release does not include one.
- Merge into `main` must resolve the `docs/changelog.md` conflict described above.

Related: [current-state.md](../current-state.md) ·
[changelog.md](../changelog.md) ·
[MF save or import blocked by cached NAV](../troubleshooting/mf-cached-nav-writes.md) ·
[Release checklist](release-checklist.md)
