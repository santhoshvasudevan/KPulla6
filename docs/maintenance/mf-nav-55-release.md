# Corrected MF NAV main-integration release (#55 / #61)

Release evidence for parent corrective specification
[#55](https://github.com/santhoshvasudevan/KPulla6/issues/55) and integration gate
[#61](https://github.com/santhoshvasudevan/KPulla6/issues/61). This page authorizes
nothing: merge to `main`, live migration, and rollout belong to [#62](https://github.com/santhoshvasudevan/KPulla6/issues/62)
after explicit human approval. [#48](https://github.com/santhoshvasudevan/KPulla6/issues/48)
stays open until rollout is verified.

Prior baseline evidence: [mf-nav-48-release.md](./mf-nav-48-release.md) (`4e01704` feature tip).
Review findings: [#48 comment 7159691028](https://github.com/santhoshvasudevan/KPulla6/issues/48#issuecomment-7159691028).

## Pinned lineage

| Step | Ref | Summary |
|------|-----|---------|
| Feature tip (pre-correction) | `4e01704` | Cache-first provisional MF NAV (#48 chain) |
| Corrections | `92336d1` | Integration of #56–#60 on `codex/mf-nav-55-corrections` |
| `main` at integration | `25419fa` | PR #47 FD interest verification |
| Merge base | `6ffe63f` | FD interest report currency split |
| **Integration candidate** | see verification commit below | `codex/61-main-integration-candidate` |

### Corrections landed (#56–#60)

| Ticket | Commit | Fix |
|--------|--------|-----|
| #56 | `4b34d56` | Scoped MF valuation arithmetic in `finance/mutual_fund_valuation.py` |
| #57 | `fa97b2f` | Unavailable provisional valuations (null, not zero) |
| #58 | `617d4d8` | Valuation-date FX for carried provisional NAV |
| #59 | `352e7a9` | Unified personal Holding XIRR terminal valuation |
| #60 | `5dacba9` | Stale successful fetch finalization fence |

### Merge with `main`

Trial merge `origin/main` into the corrective tip conflicted only in `docs/changelog.md`
(both sides added top entries; **keep both** — FD payment corrections from `main` and the
#56–#60 MF entries). `docs/api-design.md` auto-merged.

## Durable regressions (four review probes)

| Probe | Issue | Primary tests |
|-------|-------|---------------|
| Unknown ≠ zero | #57 | `test_conflicted_provisional_nav_preserves_unavailable_across_surfaces`, scope suite |
| Valuation-date FX | #58 | `test_carried_provisional_nav_uses_valuation_date_fx_not_observation_fx` |
| Personal XIRR parity | #59 | `test_personal_xirr_scoped_overlay_*`, conflict unavailable tests |
| Stale fetch fence | #60 | `test_mf_nav_fetch_stale_finalization.py` |

Permissive zero-fill / constant-FX parity assertions from the #48 review were removed or
replaced with literal expected amounts and `null` checks.

## Migrations

Unchanged from [mf-nav-48-release.md](./mf-nav-48-release.md):

| Migration | Notes |
|-----------|--------|
| `market_data.0007_mutualfundnavfetchstate` | New empty state table |
| `transactions.0006_mutualfundtransactiondetail_nav_provenance` | `nav_source` / `provisional_*` NOT NULL, **no DB default** |

## Rollout and rollback (corrected ordering)

**Stop old writers before schema or serving-checkout changes.** While `transactions.0006`
is applied, application code older than #50 cannot insert MF rows (NOT NULL provenance
columns). Older code may still **update** existing MF rows without sending provenance,
leaving stale `UNKNOWN` markers — treat that as a rollback risk, not a silent OK.

1. **Quiesce.** Stop every running backend/frontend/cron writer on the target environment
   (`make dev`, manual `runserver`, refresh jobs). Confirm no process holds DB connections
   to the portfolio database.
2. **Pin.** Record `git rev-parse HEAD` on the **serving** checkout; must match the approved
   candidate SHA below.
3. **Back up.** `make backup-db`; confirm non-empty artifact.
4. **Safety counts.** `make db-safety-check`; record DB name, transaction count, and
   `showmigrations market_data transactions`.
5. **Explicit approval** citing backup path and counts.
6. **Migrate.** `make migrate` (only `0007` / `0006` expected on first MF rollout).
7. **Deploy code.** Start backend + frontend from the pinned checkout only after migrate
   (or migrate immediately before first start — never run old code against new schema).
8. **Verify.** Separate checks for published commit, local checkout, and running PIDs
   (`lsof` cwd + `git rev-parse`). Health + read-only MF UI smoke; no acceptance fixtures
   on live data.

### Rollback

Prefer forward fix. Same backup/count/approval gate as rollout.

- **Code rollback before schema reverse:** old writers may insert MF rows without provenance →
  failure or stale markers. **Quiesce first**, then reverse migrations if required.
- **To pre-#50 code:** `migrate transactions 0005` **while still on new code** that
  understands the down migration; then check out older code and restart.
- **Also drop fetch state:** `migrate market_data 0006` when returning to pre-#49 code.
- Provenance columns have no database default; do not run legacy writers on the migrated schema.

## Frozen-tree verification

_Worktree used for the gate:_ `/Users/santhosh/Documents/Projects/Ganesha/worktrees/kpulla6-mf-nav-61`  
_Integration branch tip after doc pin fixes:_ `codex/mf-nav-55-corrections` / `codex/61-main-integration-candidate`

_Recorded on the verification commit below. Two later commits only edited this release note
(incorrect SHA pins). Treat **`18c2ef4`** as the frozen evidence SHA for rollout approval.
If you deploy the branch tip instead, re-run the frozen verification on that tip first._

| Field | Value |
|-------|--------|
| **Frozen verification SHA (approve/deploy)** | `18c2ef4c588e2a0033a92f49929e83399b914293` |
| Pre-verification tip | `4a72378885bf043139549fb1a736e2f99a838591` (merge + acceptance handoff) |
| Branch tip after doc-only pin commits | `52c38de1b7fb4e5f53e1a70420a7dbbe5e6b49f5` (and subsequent release-doc fix commits) |
| `origin/main` at merge | `25419fa8b1575369958eb442f6d48ec0305e6c8a` (PR #47) |
| Merge base | `6ffe63fd8b25f1d8c2ece8cfdca35ac62d6126d9` |
| Integration diff at freeze | `git diff --stat 6ffe63f..18c2ef4` → 108 files, +9400/−473 (21 commits) |

| Check | Command | Result |
|-------|---------|--------|
| Backend | `cd backend && DJANGO_TEST_USE_SQLITE=1 .venv/bin/python -m pytest -q` | **1652 passed** |
| Frontend tests | `cd frontend && npm test -- --run` | **45 files, 735 passed** |
| Frontend build | `cd frontend && npm run build` | Built (chunk >500 kB warning) |
| Docs build | `mkdocs build -f ../mkdocs.yml --strict` | Passed |
| Docs check | `scripts/check_docs_consistency.py --strict` | OK |
| Migration drift | `makemigrations --check --dry-run` | No changes detected |
| Migration round-trip | `mf_nav_48_server.py manage` on `/tmp/kp-mfnav-61/run` | Apply / reverse / re-apply OK |
| Whitespace | `git diff --check 6ffe63f..HEAD` | Clean (after release doc fix) |
| Browser | Ports **18100** / **15174** | **112 / 112** checks passed |

### Synthetic browser (#55 probes)

Run directory: `/tmp/kp-mfnav-61/browser-evidence`. Served listeners reported worktree cwd
and matching `git_head` for backend (`…/backend`) and frontend (`…/frontend`). Database:
disposable `acceptance.sqlite3` in the run directory only.

`scripts/acceptance/` — scenario `8-55-corrective-probes` exercises:

- #57 conflicting provisional → `current_value: null` (not zero)
- #58 observation-date history EUR **1142.50** plus pytest oracle for valuation-date FX
- #59 personal XIRR parity (holdings, detail, metrics)
- #60 stale-fetch fence (focused pytest subprocess; disposable SQLite)

Exact EUR **1151.00** headline oracle remains in
`test_carried_provisional_nav_uses_valuation_date_fx_not_observation_fx` (#58).

## Preservation of dirty original checkout

Do not switch or reset `/Users/santhosh/Documents/Projects/Ganesha/KPulla6`. Integration
and evidence use this worktree only. Before any future rollout in the original folder,
stash or branch unrelated edits per user agreement.

## Deferred (non-blocking)

See [mf-nav-48-release.md § Deferred](./mf-nav-48-release.md#deferred-non-blocking).
SQLite stale-fetch tests do not prove PostgreSQL `SELECT … FOR UPDATE` serialization.

Related: [changelog.md](../changelog.md) · [workflows.md](../workflows.md) · #62 rollout