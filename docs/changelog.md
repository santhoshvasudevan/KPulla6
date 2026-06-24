# Changelog — KPulla6

## 2026-06-24 — CASH-UNIFY-2: FD portfolio derived from bank account

- **FD create:** `POST /api/v1/fixed-deposits` derives `FixedDeposit.portfolio` from `bank_account.portfolio`. Optional `portfolio_id` must match or is omitted; conflicting or unassigned/ambiguous bank accounts return **400** with structured fields (`bank_account_id`, `bank_account_portfolio_id`, `portfolio_assignment_status`, `hint`, …).
- **FD update:** When `bank_account_id` or `portfolio_id` is editable (no opening movement), portfolio must align with the selected bank account.
- **Renewal:** Unchanged accounting; new FD portfolio must match bank account portfolio (rejects legacy mismatch).
- **Read API:** `portfolio_mismatch_warning` on FD list/detail when legacy `fd.portfolio_id ≠ bank_account.portfolio_id` (no auto-rewrite).
- **Frontend:** FD create modal shows derived portfolio read-only; blocks unassigned/ambiguous bank accounts.
- **Deferred:** Cash page UI redesign (CASH-UNIFY-3).

## 2026-06-24 — CASH-UNIFY-1: Bank account portfolio ownership + cash overview API

### Added
- **`BankAccount.portfolio`** — nullable FK to `Portfolio` (migration `debt/0009_bankaccount_portfolio`); exposed on bank account CRUD as `portfolio_id`, `portfolio_name`, `portfolio_assignment_status` (`ASSIGNED` / `UNASSIGNED` / `AMBIGUOUS`).
- **`manage.py infer_bank_account_portfolios`** — dry-run default; `--apply` sets portfolio when FD/movement signals are unambiguous; never creates cash movements.
- **`GET /api/v1/cash/overview`** — read-only unified broker + bank cash rows (`ledger_type`: `BROKER_CASH` | `BANK_CASH`); optional `display_currency`, `include_unassigned`; exclusion counts/warnings for unassigned/ambiguous bank accounts.
- **Frontend:** `fetchCashOverview` in `api.js`.

### Unchanged
- FD create portfolio selection (CASH-UNIFY-2). **Done (CASH-UNIFY-2).**
- Cash page UI (CASH-UNIFY-3).
- `/cash/balances`, ledger writes, summary/performance valuation.
- No ledger merge or auto-created movements.

## 2026-06-24 — CASH-UNIFY-0: Unified cash domain model (design only)

- **Design doc:** [cash-unification.md](./cash-unification.md) — portfolio cash holdings taxonomy (broker + bank; physical deferred), two-ledger separation, future `BankAccount.portfolio` ownership, FD portfolio derivation from bank account, future Cash tab layout, backfill strategy, safety rules, implementation phases CASH-UNIFY-1..6.
- **ADR:** [decisions.md](./decisions.md) § CASH-UNIFY-0.
- **Backlog aligned:** [002](./backlog/002-cash-unify-1.md)–[005](./backlog/005-cash-unify-4.md) scopes updated to match roadmap (ownership → FD derivation → UI → terminology/display-currency).
- **No runtime, API, migration, or frontend behavior changes.**

## 2026-06-24 — FD-CASH-ASOF-1: FD create as-of bank balance diagnostics and UX

- **Root cause:** FD create validates **bank ledger balance as of `investment_date`**; create form showed **current** ledger balance only, which can exceed as-of balance when deposits are dated after the FD investment date.
- **API:** richer `400` on insufficient balance (`available_as_of_date`, `current_balance`, `investment_date`, `shortfall`, `hint`, `latest_ledger_balance_date`); new `GET /api/v1/bank-accounts/{id}/balance?as_of=YYYY-MM-DD`.
- **Frontend:** create modal shows current vs as-of balances; structured error panel; auto-scroll/focus on create failure; Cash tab vs Bank Ledger helper text.
- **Clarified:** Portfolio Cash (broker `CashLedgerEntry`) ≠ Bank Ledger (`CashMovement`); reference `opening_balance` is not ledger cash until seeded.
- **No accounting rule changes.**

## 2026-06-24 — FD-CASH-ASOF-1: FD create as-of bank balance diagnostics and UX

- **Root cause:** FD create validates **bank ledger balance as of `investment_date`**; create form showed **current** ledger balance only, which can exceed as-of balance when deposits are dated after the FD investment date.
- **API:** richer `400` on insufficient balance (`available_as_of_date`, `current_balance`, `investment_date`, `shortfall`, `hint`, `latest_ledger_balance_date`); new `GET /api/v1/bank-accounts/{id}/balance?as_of=YYYY-MM-DD`.
- **Frontend:** create modal shows current vs as-of balances; structured error panel; auto-scroll/focus on create failure; Cash tab vs Bank Ledger helper text.
- **Clarified:** Portfolio Cash (broker `CashLedgerEntry`) ≠ Bank Ledger (`CashMovement`); reference `opening_balance` is not ledger cash until seeded.
- **No accounting rule changes.**

## 2026-06-24 — FD-TAX-1: Fixed Deposit interest and tax withheld report

### Added
- **`GET /api/v1/reports/fixed-deposit-interest`** — read-only report of FD gross interest, tax withheld, and net interest.
- Sources: non-reversed `FixedDepositInterestPayment`, settlement final interest (non-renewal), renewal interest (`FixedDepositRenewalGroup`); zero-interest rows excluded; cancelled FD rows excluded; renewal settlements not double-counted.
- Query: `portfolio_scope` / `portfolio_id`, `start_date`, `end_date`, `display_currency`, `group_by` (`year`, `portfolio`, `bank`, `fd`, `source`, `none`).
- Frontend: **Interest & Tax report** section on Fixed Deposits page (summary KPIs, filters, table, grouped totals).

### Notes
- Reporting only — no accounting, ledger, or performance changes.
- Not tax advice. CSV/export deferred to FD-TAX-2.

---

## 2026-06-24 — FD-ACC-10A-FX-TERMINAL-FIX: All Portfolio value-history terminal alignment

### Problem
- After the prior all-scope aggregation fix, **All Portfolios INR** value history could still show a sudden drop while **EUR** looked fine.
- Latest `metric=value` point did not match summary `current_value` (e.g. ~7.1M vs ~16.8M INR on dev DB).
- Root cause: bulk FX map loader queried only the direct pair direction (`EUR→INR`) and missed inverse-only rows (`INR→EUR`), so EUR portfolios were excluded from INR performance history after the last direct rate date. Secondary gap: daily timeseries holdings vs summary terminal valuation differed slightly.

### Fixed
- `fx/lookup.py` — `load_fx_rate_maps` loads both directions of each requested pair (matches `get_fx_rate_on_date` inverse semantics).
- `portfolios/performance_service.py` — `_align_terminal_value_with_summary()` sets the terminal value point from summary KPI when FX is available/filled (same scope, currency, date).

### Tests
- `backend/tests/test_all_scope_fx_terminal_alignment.py` (new)
- `backend/tests/test_fx_sync.py` — inverse-only bulk map regression

### Notes
- Cancelled FD was not the root cause of this mismatch.
- Historical all-scope dates may still be partial/null when FX is unavailable; terminal date aligns with summary when conversion succeeds.

---

## 2026-06-24 — All Portfolios value chart: cancelled-FD / cash-only drop fix

### Problem
- After FD-ACC-10A-REPAIR, **All Portfolios** value history could drop to a single portfolio’s broker cash (e.g. 1,109,389 INR) when another child portfolio had `portfolio_value: null` (FX unavailable).
- Root cause: all-scope aggregation poisoned the sum when any child was `null`; `merge_cash_into_value_timeseries` then substituted broker cash as the total.

### Fixed
- `portfolios/summary_service.py` — `_aggregate_timeseries_lists` sums known child values; one child’s `null` no longer nulls the entire all-scope row.
- `cash/services.py` — `merge_cash_into_value_timeseries` no longer replaces unknown investment value with cash-only totals.
- `debt/portfolio_value.py` — `merge_fd_bank_into_value_timeseries` forward-fills investment value on FD/bank union dates instead of starting from zero.

### Tests
- `backend/tests/test_cancelled_fd_all_scope_value_history.py` — cancelled repaired FD excluded; FX-gap child does not collapse to cash-only; active FD still included.

---

## 2026-06-24 — FD-ACC-10A-REPAIR: one-time repair for pre-10A deactivated FDs

### Added
- **`python manage.py repair_deactivated_fd_openings`** — dry-run by default; `--apply` creates `FD_OPENING_REVERSAL` and sets `status=CANCELLED` for eligible inactive FDs deactivated before Cancel FD workflow.
- Filters: `--fd-id`, `--user-id`, `--reason`.
- Unsafe cases (interest, settlement, renewal, already cancelled) skipped with report.

### Notes
- Do **not** manually add a deposit to fix this — use the repair command.
- Public Cancel FD API unchanged.

---

## 2026-06-24 — FD-ACC-10B: General reversal / correction framework

### Added
- **`POST /api/v1/cash-movements/{id}/reverse`** — reverses eligible manual movements (`MANUAL_DEPOSIT`, `MANUAL_WITHDRAWAL`, `ADJUSTMENT`, `OPENING_BALANCE`) via `REVERSAL` SYSTEM movement; original retained and linked.
- **`POST /api/v1/fixed-deposit-interest-payments/{id}/reverse`** — reverses interest payment via `FD_INTEREST_REVERSAL` DEBIT; marks payment `is_reversed`.
- **Classifier** — reversal rows offset original external-flow classification; income reversals stay income (not external withdrawal); internal reversals stay internal.
- **UI** — Reverse action on eligible cash movements; Reverse interest on active FD payments; status labels (Reversed / Reversal).
- **Audit fields** — `CashMovement.reversal_reason`; `FixedDepositInterestPayment.is_reversed`, `reversed_at`.

### Migration
- `debt.0007_reversal_framework` — `REVERSAL`, `FD_INTEREST_REVERSAL` types; reversal/interest-reversal fields.

### Tests
- `test_cash_movement_reversals_api.py`, `test_fixed_deposit_interest_reversals_api.py` (new); classifier and cancellation regression tests updated.

### Deferred (FD-ACC-10C)
- Settlement reversal, renewal reversal, cancel-FD reversal.

---

## 2026-06-24 — FD-ACC-10A: FD cancel / deactivate accounting fix

### Problem
- `DELETE /fixed-deposits/{id}` soft-deactivated ledger-backed FDs without reversing `FD_OPENING` bank debit.
- Bank cash stayed reduced; portfolio value dropped FD principal but cash was not restored.

### Fixed
- **`POST /fixed-deposits/{id}/cancel`** — reverses unreversed `FD_OPENING` via `FD_OPENING_REVERSAL` CREDIT; sets `status=CANCELLED`, `is_active=false`; row retained (not deleted).
- **`DELETE /fixed-deposits/{id}`** — **409** when unreversed `FD_OPENING` exists; legacy FDs without opening movement still deactivate.
- **Classifier** — `FD_OPENING_REVERSAL` treated as internal (not external flow).
- **UI** — ledger-backed FDs show **Cancel FD** with explainer; legacy FDs show **Deactivate**.
- **Docs** — lifecycle table distinguishes Cancel vs Deactivate vs Settle vs Renew; historical PV limitation documented (FD-ACC-10B deferred).

### Migration
- `debt.0006_fd_cancellation` — `CANCELLED` status; `FD_OPENING_REVERSAL` movement type.

### Tests
- `test_fixed_deposit_cancellation_accounting.py` (new); updates to summary/API/classifier tests.

### Deferred
- Full correction/reversal framework → **FD-ACC-10B**.

---

## 2026-06-23 — P11: Final frontend redesign audit

### Audit
- Verified all 11 routed pages redesigned (P4–P10): Dashboard, Transactions, Cash, Assets, Asset Detail, Fixed Deposits, Compare, Settings, Login, Register, Forgot Password.
- Verified single top nav, no permanent left sidebar, auth shell isolation, API/CSRF/session preservation, and no new frontend finance calculations.
- Aligned `docs/page-layouts.md` and `docs/frontend-design.md` with implemented shell, primitives, and phase status.

### Changed (minor)
- `Settings.jsx` — display currency hint label: “Header selector” (was “Sidebar selector”).

### Tests
- No test weakening; `make test-frontend` 534/534 at audit time.

### Notes
- Executive Portfolio OS frontend redesign **complete**. Deferred items documented in `page-layouts.md` §17.

---

## 2026-06-23 — P10: Auth pages and global polish

### Changed
- **Auth pages** — Executive Portfolio OS `AuthShell`: KPulla6 brand mark, elevated auth panel, token-based form fields, primary submit buttons, alert/status roles for errors and success.
- **Global responsive** — sticky section-nav horizontal scroll on small screens; header nav scrollbar styling; KPI grid gap tightening on mobile.
- **Global dark-mode** — refined card/chart/table shell borders in dark theme; shared `focus-visible` on links and section nav.

### Tests
- `Login.test.jsx` — KPulla6 brand identity on login shell.
- `Register.test.jsx` — registration form fields and actions.
- `ForgotPassword.test.jsx` — KPulla6 brand on reset page.
- `AuthShell.test.jsx` — brand identity and panel title.

### Notes
- No route, API, backend, database, auth/session, or finance-calculation changes.
- Business pages unchanged structurally (CSS polish only).

---

## 2026-06-23 — P9: Settings page redesign

### Changed
- **Settings** — Executive Portfolio OS workspace: `PageHeader` with subtitle, sticky Display/Portfolios/Bank Accounts/Data Sync section nav, full-width `AppCard` sections replacing `SectionCard`, responsive display/tax form grid.
- **Settings.css** — centered column layout, section nav, form grid; child component table styles preserved.

### Tests
- `Settings.test.jsx` — page header, section nav, main section headings.

### Notes
- No route, API, backend, database, auth/session, or finance-calculation changes.
- Portfolio, bank account, and cash movement child components unchanged in behavior.
- P4R left-heavy layout deferred item resolved.

---

## 2026-06-23 — P8: Compare page redesign

### Changed
- **Compare** — Executive Portfolio OS analytics layout: `AppCard` setup panel with asset pickers, selected-subject chips, and `ChartControls`; sticky section nav; `KpiCard` summary strip from backend metrics; `ChartFrame` + `ChartLegend` wrapping `CompareNormalizedChart`; `AppCard` metric comparison section.
- **compareDisplay** — Display-only helpers: `compareOptionLabel`, `compareBenchmarkLabel`, `compareChartLegendItems`, `compareSubjectSummaryKpis`.
- **CompareNormalizedChart** — Optional `hideLegend` prop for external `ChartLegend`.

### Tests
- `Compare.test.jsx` — setup panel, section nav, subject chips, chart frame, KPI summary.
- `compareDisplay.test.js` — label resolution, legend items, KPI extraction.

### Notes
- No route, API, backend, database, auth/session, or finance-calculation changes.
- Dashboard, Transactions, Cash, Assets, Fixed Deposits, Settings, and auth pages unchanged.

---

## 2026-06-23 — P7: Fixed Deposits redesign

### Changed
- **Fixed Deposits** — Executive Portfolio OS layout: `KpiCard` overview counts (backend status only), sticky Overview/Deposits section nav, `DataTableShell` + `AppTable` holdings table with `StatusBadge` lifecycle labels, right-aligned currency/rate columns, readable maturity dates and payout labels.
- **fdDisplay** — Display-only helpers: `fdStatusBadgeProps`, `fdPayoutLabel`, `fdStatusCounts`.

### Tests
- `FixedDeposits.test.jsx` — page header, KPI overview, section nav, status badge, payout label.
- `fdDisplay.test.js` — status badge mapping, payout labels, status counts.

### Notes
- No route, API, backend, database, auth/session, or finance-calculation changes.
- Dashboard, Transactions, Cash, Assets, Compare, Settings, and auth pages unchanged.

---

## 2026-06-23 — P6: Assets and Asset Detail redesign

### Changed
- **Assets** — Holdings hub layout: `KpiCard` overview counts, sticky Holdings/Allocation section nav, `DataTableShell` + `AppTable` holdings table with `AssetClassPill` and sortable columns, cash balances table, `ChartCard` allocation donut, `AppCard` previous holdings.
- **Asset Detail** — Tear-sheet layout: `AssetClassPill` header eyebrow, `KpiCard` hero strip, sticky Overview/Metrics/Details/Transactions nav, `AppCard` detail grid, `DataTableShell` transaction history.
- **transactionDisplay** — `holdingAssetClassVariant()` display-only helper for asset class pills.

### Tests
- `Assets.test.jsx` — page header, section nav, asset class pills, Holdings section heading.
- `AssetDetail.test.jsx` — tear-sheet header, section nav, transaction history section.
- `transactionDisplay.test.js` — asset class variant mapping.

### Notes
- No route, API, backend, database, auth/session, or finance-calculation changes.
- Dashboard, Transactions, Cash, and other pages unchanged.

---

## 2026-06-23 — P5: Transactions and Cash redesign

### Changed
- **Transactions** — Premium activity ledger layout: `AppCard` filter section, `DataTableShell` + `AppTable` for the transaction table, right-aligned numeric columns, preserved type/NAV badges, filters, pagination, CSV import/cash preview, bulk assign, and CRUD flows.
- **Cash** — Cash ledger/overview layout: header primary actions, `KpiCard` balance overview from backend totals, `DataTableShell` balances table, `AppCard` ledger section with `StatusBadge` entry types and `AppTable` ledger rows.
- **TransactionFilterBar** — `embedded` mode for use inside `AppCard` without duplicate chrome.
- **cashDisplay** — `cashEntryBadgeStatus()` display-only helper for ledger type badges.

### Tests
- `Transactions.test.jsx` — page header and Activity ledger section coverage.
- `Cash.test.jsx` — updated for KpiCard overview and premium section structure.

### Notes
- No route, API, backend, database, auth/session, or finance-calculation changes.
- Dashboard, Assets, Settings, and other pages unchanged.

---

## 2026-06-22 — P4R: Dashboard anchor scroll offset and shell review

### Changed
- **Dashboard** — Section anchor targets use `--dashboard-anchor-offset` (`scroll-margin-top`) to clear sticky header and sticky section nav; Metric Sheet anchor moved to `MetricSheetSection` so its heading is the scroll target.
- **Layout** — Shell CSS variables `--shell-sticky-offset` and `--dashboard-anchor-offset` for consistent anchor behavior.

### Notes
- Settings page left-heavy layout deferred to Settings redesign (P9); no Settings page redesign in P4R.
- No route, API, backend, database, or auth/session behavior changes.

---

## 2026-06-22 — P4.4: Navigation architecture unified

### Changed
- **Layout** — Removed permanent left context sidebar (`CONTEXT_NAV`); single global top navigation for all routes.
- **Layout** — Main content centered globally with max-width ~1520px; cached-data note moved to compact header line.
- **Dashboard** — Section nav is in-page anchors only (Overview, Performance, Allocation, Health, Metric Sheet); no cross-route duplicate labels.

### Notes
- No route, API, backend, database, or auth/session behavior changes.
- Future Settings/Assets section navigation can be added during those page redesign phases.

---

## 2026-06-21 — Docs: Frontend redesign PRD

### Added
- `docs/frontend-redesign-references.md` — Product Requirement Document for the future **KPulla6 Executive Portfolio OS**, based on Ghostfolio UI benchmarking, chart benchmarking, and Direction 5 exploration.

### Changed
- `docs/dashboard-redesign-directions.md` — added a short note that Direction 5 is the preferred reference direction.

### Notes
- Documentation only; no runtime behavior changes.
- No frontend code, backend code, API client code, tests, migrations, database data, or KPulla5 files changed.

---

## 2026-06-19 — Docs: Frontend redesign readiness governance

### Updated
- `docs/page-layouts.md` — expanded app shell, auth pages, Compare, Cash, Fixed Deposits, Transactions, and frontend API preservation contracts for future redesign work.
- `docs/frontend-design.md` — resolved Dashboard chart documentation conflict; current Invested vs Current chart remains preserved unless a future `page-layouts.md` proposal is approved.
- `.cursor/rules/200-frontend-design.mdc` — added redesign preservation, auth/session, and optional `DataTable` guidance.

### Notes
- Documentation/rules only; no runtime behavior changes.
- No app code, backend code, tests, API client code, migrations, or database data changed.

---

## 2026-06-14 — FD-ACC-9: FD accounting stabilization and audit

### Added
- `backend/tests/test_fixed_deposit_end_to_end_accounting.py` — five E2E scenario audits (full lifecycle, renewal, excluded bank cash, unseeded balance, portfolio scope)

### Verified (no product feature changes)
- End-to-end FD accounting: opening debit, interest/TDS, mark matured, settlement, renewal
- Bank cash ledger vs manual/reference balance; as-of-date validation
- Portfolio summary, holdings, allocation, `metric=value`, XIRR, TWROR, Metric Sheet alignment
- API user/portfolio scoping; immutable ledger rows; dashboard banner copy
- Frontend: Bank Accounts, Fixed Deposits, Dashboard, Assets smoke/regression tests

### Documentation
- `current-state.md`, `fixed-deposits.md`, `fixed-deposits-accounting.md`, `database.md`, `decisions.md` — removed outdated “design only” / “not implemented” FD accounting statements
- Graphify refreshed via `make graphify`

### Deferred (unchanged)
- Reversals/corrections, transfer workflows, tax reporting, standalone FD IRR, accrued interest valuation, automatic bank cash inclusion, portfolio-specific bank sub-balances, via-bank renewal path

---

### Added
- `backend/debt/cash_ledger_flows.py` — classifies bank `CashMovement` rows for return metrics
- XIRR terminal includes FD principal + opt-in included bank cash ledger balance
- TWROR/cumulative return daily PV extended via FD-ACC-8B merge; bank external flows merged
- Backend tests: `test_fd_cash_flow_classification.py` (9 cases)

### Changed
- `portfolios/xirr_service.py` — wealth-pool terminal + bank XIRR flows (FD-ACC-8C)
- `portfolios/external_flows_service.py` — bank TWROR external flows when user scoped
- `portfolios/performance_service.py` — return timeseries includes FD/bank; flow maps extended
- `analytics/services.py` + views — pass `user` for Metric Sheet alignment
- Dashboard banner updated: return metrics now include FD/bank cash

### Cash-flow classification (included bank accounts)
- **Internal:** `FD_OPENING`, settlement principal, renewals, transfers
- **Income/return:** `FD_INTEREST`, settlement interest (PV increase, not external flow)
- **External contribution:** `MANUAL_DEPOSIT`, `OPENING_BALANCE` seed, `ADJUSTMENT` CREDIT
- **External withdrawal:** `MANUAL_WITHDRAWAL`, `ADJUSTMENT` DEBIT

### Unchanged / deferred
- Accrued interest valuation, standalone FD IRR, transfer/reversal workflows, tax reporting
- Bank excluded from portfolio value: FD open/settle remain step-based PV changes only

---

## 2026-06-14 — FD-ACC-8B: FD principal + included bank cash in value history

### Added
- `build_fd_value_timeseries`, `build_bank_cash_value_timeseries`, `merge_fd_bank_into_value_timeseries` in `debt/portfolio_value.py`
- `metric=value` performance series and summary timeseries (when requested) include FD principal + opt-in ledger bank cash
- Backend tests: `test_fd_performance_timeseries_api.py` (17 cases)

### Changed
- `portfolios/performance_service.py` — merge FD/bank into value metric only; pass `user` from performance view
- `portfolios/summary_service.py` — FD/bank merge on single-portfolio and all-scope timeseries
- Dashboard value-chart info banner: value chart includes FD/bank cash; return metrics note for FD-ACC-8C
- `test_fixed_deposit_summary_api.py` — performance value aligns with summary for FD principal

### Unchanged
- XIRR, TWROR, cumulative return formulas, analytics Metric Sheet flows, external-flow classification (deferred **FD-ACC-8C**)
- No accrued-interest FD valuation; no standalone FD IRR

### Date rules (value series)
- FD principal: inclusive from `investment_date`; exclusive from `settlement_date` when settled
- Bank cash: ledger balance as-of each date; FD-ACC-7 scope attribution

---

## 2026-06-14 — FD-ACC-8A: FD / bank cash performance design review

### Added
- **FD-ACC-8 performance/timeseries design** section in `fixed-deposits-accounting.md` — answers contribution vs internal transfer, settlement, interest, accrued interest, API scope, options A/B/C, risks, 8B test plan
- Phase split: **FD-ACC-8B** (value history) · **FD-ACC-8C** (XIRR/TWROR cashflow classification)

### Changed
- `architecture.md`, `decisions.md`, `current-state.md`, `fixed-deposits.md` — cross-links and status updates

### Unchanged
- **No runtime code** — performance API, XIRR, TWROR, summary behavior identical to FD-ACC-7

### Recommendation
- **Option B** for 8B: align `metric=value` with summary (FD principal + included bank cash) before touching external-flow maps

---

## 2026-06-14 — FD-ACC-7: Optional bank cash in portfolio value

### Added
- Opt-in `include_in_portfolio_value` wiring: ledger-derived bank balance in summary `current_value`, holdings, and **Cash / Bank Cash** allocation bucket
- Portfolio scope rules: included accounts once in `all`; single portfolio only when FD/movement associations resolve to that portfolio alone
- Settings → Bank accounts: include toggle with ledger-seed warning
- Backend tests in `test_fixed_deposit_summary_api.py` (FD create/settle/interest stability, scope, FX)
- Frontend tests: `BankAccountManagement`, `Assets`, `Dashboard`

### Changed
- `debt/portfolio_value.py` — bank cash aggregation, attribution, allocation bucket
- Summary/holdings services merge included bank cash when `include_in_portfolio_value=true` and ledger exists

### Unchanged
- FD accounting movements, stock/MF valuation, FD performance/XIRR (FD-ACC-8), transfer/reversal workflows
- Manual/reference `current_balance` excluded until seeded into ledger

### Documentation
- `fixed-deposits-accounting.md`, `fixed-deposits.md`, `database.md`, `api-design.md`, `current-state.md`, `decisions.md`, `frontend-design.md`, `page-layouts.md`

---

## 2026-06-14 — FD-ACC-6: Fixed Deposit renewal workflow

### Added
- `FixedDepositRenewalGroup` model — renewal audit trail (old/new FD, settlement, payout breakdown)
- API: `POST /fixed-deposits/{id}/renew` — direct rollover + partial cash payout
- Renewed FD created without `FD_OPENING` debit; normal FD create unchanged
- Fixed Deposits UI: Renew modal for `ACTIVE`/`MATURED`; `has_renewal` on FD list
- Backend tests: `test_fixed_deposit_renewals_api.py` (17 cases)
- Frontend tests: renewal actions, modal, payload, validation in `FixedDeposits.test.jsx`; `renewFixedDeposit` in `api.test.js`

### Changed
- Portfolio Debt allocation swaps old settled principal for new renewed principal (no double count)

### Unchanged
- Bank cash in portfolio value (FD-ACC-7), FD performance/XIRR (FD-ACC-8), transfer/reversal workflows

### Documentation
- `fixed-deposits.md`, `fixed-deposits-accounting.md`, `database.md`, `api-design.md`, `current-state.md`, `decisions.md`, `frontend-design.md`

---

## 2026-06-14 — FD-ACC-5: Fixed Deposit maturity / closure settlement

### Added
- `MATURED_SETTLED` FD status; `FixedDepositSettlement` model with principal/interest ledger credits
- Cash movement types: `FD_MATURITY_PRINCIPAL`, `FD_MATURITY_INTEREST`, `FD_CLOSURE_PRINCIPAL`, `FD_CLOSURE_INTEREST`
- APIs: `POST /fixed-deposits/{id}/mark-matured`, `POST /fixed-deposits/{id}/settle`, `GET /fixed-deposits/{id}/settlements`, `GET /fixed-deposit-settlements/{id}`; **405** on update/delete
- Fixed Deposits UI: Mark matured, Settle/Close modal, settlement movement labels
- Backend tests: `test_fixed_deposit_settlements_api.py`

### Changed
- Portfolio summary excludes `MATURED_SETTLED` and `CLOSED` FD principal; bank proceeds still excluded from portfolio value

### Unchanged
- Renewal, bank cash in portfolio value, FD performance/XIRR, transfer/reversal workflows

### Documentation
- `fixed-deposits.md`, `fixed-deposits-accounting.md`, `database.md`, `api-design.md`, `current-state.md`, `decisions.md`, `frontend-design.md`, `page-layouts.md`

---

## 2026-06-14 — FD-ACC-4: Fixed Deposit interest payments

### Added
- `FixedDepositInterestPayment` model — gross interest, tax withheld, net interest, linked `CashMovement`
- `CashMovementType.FD_INTEREST` — SYSTEM CREDIT for net interest received into linked bank account
- APIs: `GET/POST /fixed-deposits/{id}/interest-payments`, `GET /fixed-deposit-interest-payments/{payment_id}`; **405** on PUT/PATCH/DELETE
- COMPOUNDED FD soft `warning` on POST (does not block)
- Fixed Deposits page: Record interest modal, expandable interest payments list
- `CashMovementManagement` labels `FD_INTEREST` as “FD interest”
- Backend tests: `test_fixed_deposit_interest_payments_api.py`

### Unchanged
- FD portfolio value remains **principal-only**; interest does not increase summary `current_value`
- Bank cash still excluded from portfolio value
- Maturity/closure/renewal still deferred

### Documentation
- `fixed-deposits.md`, `fixed-deposits-accounting.md`, `database.md`, `api-design.md`, `current-state.md`, `decisions.md`, `frontend-design.md`

---

## 2026-06-14 — FD-ACC-3.1: FD opening balance as-of-date UX

### Changed
- Fixed Deposits create modal explains that bank balance is validated **as of the FD investment date**
- Backdated FD guidance when ledger exists and investment date is set
- Insufficient-balance errors label API `available` as as-of investment date and include backdated FD hint
- Backend FD create insufficient-balance response includes backdated hint when ledger exists but balance is short

### Documentation
- `fixed-deposits.md`, `fixed-deposits-accounting.md`, `current-state.md` — seed/movement dates vs backdated FD investment dates

---

## 2026-06-14 — FD-ACC-3 fix: unseeded opening balance UI mismatch

### Fixed
- Fixed Deposits create modal now shows **ledger balance available for FD** (0 when no cash movements), not misleading manual `current_balance`
- Warning when `opening_balance > 0` but not seeded; Create disabled until ledger balance covers principal
- FD create insufficient-balance API response includes `hint` when opening balance is not seeded

---

## 2026-06-14 — FD-ACC-3: Mandatory FD opening bank cash outflow

### Added
- `CashMovementType.FD_OPENING` — system DEBIT on new fixed deposit create
- `create_fd_opening_cash_movement` service; atomic FD + opening movement in `create_fixed_deposit`
- FD API fields: `has_opening_cash_movement`, `opening_cash_movement_id`
- Immutable FD fields after opening movement: `principal_amount`, `bank_account_id`, `currency`, `investment_date`, `portfolio_id`
- Backend tests in `test_fixed_deposits_api.py`; `tests/debt_test_helpers.py` (`fund_bank_account`)
- Frontend: FD create modal debit explainer, bank balance display, immutable field disable on edit

### Changed
- New FD creation requires sufficient linked bank account balance; returns structured 400 on shortfall
- Existing legacy FDs without opening movement remain valid and editable

### Deferred
- FD interest payments (FD-ACC-4), maturity/closure proceeds (FD-ACC-5), renewal, bank cash in portfolio value, backfill wizard

---

## 2026-06-14 — FD-ACC-2: Manual cash movement UI

### Added
- `CashMovementManagement.jsx` — per-bank-account movement history and create modal (Settings → Bank accounts)
- Manual movement types in UI: `MANUAL_DEPOSIT`, `MANUAL_WITHDRAWAL`, `ADJUSTMENT`
- Frontend API client tests for `fetchCashMovements` / `createCashMovement`
- Component tests: `CashMovementManagement.test.jsx`; extended `BankAccountManagement.test.jsx`

### Changed
- Settings → Bank accounts: **View movements** expands ledger panel; seed opening balance refreshes movement list when expanded
- Docs: `fixed-deposits-accounting.md`, `frontend-design.md`, `page-layouts.md`, `current-state.md`

### Notes
- Ledger rows are immutable in UI (no edit/delete)
- Bank cash remains excluded from portfolio value
- FD interest, FD opening movements, maturity/closure, renewal, transfer/reversal workflows remain deferred

---

## 2026-06-14 — FD-ACC-1: Bank CashMovement ledger foundation

### Added
- `CashMovement` model + migration `debt/migrations/0002_cash_movement.py`
- `finance/bank_cash.py`, `debt/bank_ledger_services.py`
- APIs: `GET/POST /api/v1/cash-movements`, `GET /api/v1/cash-movements/{id}`, `POST /api/v1/bank-accounts/{id}/seed-opening-balance`
- Bank account API fields: `has_ledger_entries`, `opening_balance_seeded`, `balance_source`
- Settings UI: ledger-derived balance display, seed opening balance action
- Tests: `test_cash_movements_api.py`, `test_bank_ledger_services.py`, `test_finance_bank_cash.py`, `BankAccountManagement.test.jsx`

### Changed
- `PUT /bank-accounts/{id}` rejects manual `current_balance` when ledger exists

### Deferred
- FD interest/open/mature/renewal, bank cash in portfolio value, cash movement list UI (FD-ACC-2+)

---

## 2026-06-14 — FD-ACC-0.1: FD Accounting approved product decisions (design only)

### Updated
- `docs/fixed-deposits-accounting.md` — resolved open questions: status lifecycle (`MATURED` → settle → `MATURED_SETTLED`), direct rollover partial payout, negative balance rule, opening balance opt-in, `current_balance` PUT rejection, `COMPOUNDED` warning, `include_in_portfolio_value` multi-portfolio restrictions
- `docs/fixed-deposits.md`, `docs/database.md`, `docs/api-design.md`, `docs/current-state.md`, `docs/architecture.md`, `docs/decisions.md`

### Runtime
- **No code, migrations, API, UI, or test changes** — documentation only

---

## 2026-06-14 — FD-ACC-0: Fixed Deposit Accounting Phase 1 (design only)

### Added
- `docs/fixed-deposits-accounting.md` — bank cash ledger, interest payments, maturity/closure/renewal workflows, API proposal, phased implementation plan (FD-ACC-1..7)

### Updated
- `docs/fixed-deposits.md` — link to accounting design; clarify MVP vs future accounting
- `docs/database.md` — planned FD accounting tables (design only)
- `docs/api-design.md` — planned FD accounting endpoints (not implemented)
- `docs/current-state.md` — FD-ACC-0 status
- `docs/architecture.md` — debt / bank ledger module note
- `docs/decisions.md` — FD-ACC-0 architecture decisions

### Runtime
- **No code, migrations, API, UI, or test changes** — documentation only

---

## 2026-06-14 — FD: Fixed Deposits / Debt investments MVP

### Added
- `debt` Django app — `BankAccount`, `FixedDeposit` models and migration `0001_initial`
- APIs: `GET/POST/PUT/DELETE /api/v1/bank-accounts`, `GET/POST/PUT/DELETE /api/v1/fixed-deposits`
- Pure helper `finance/fixed_deposits.py` — principal-only value + optional maturity estimate
- Portfolio summary/holdings integration (principal-only; FD unrealized P/L = 0)
- Summary `allocation_buckets` (Equity / Debt / Other) for dashboard pie chart
- Settings bank account management; `/fixed-deposits` page and sidebar nav
- `docs/fixed-deposits.md`

### Updated
- `docs/database.md`, `docs/api-design.md`, `docs/current-state.md`, `docs/frontend-design.md`, `docs/page-layouts.md`

### Tests
- Backend: `test_bank_accounts_api.py`, `test_fixed_deposits_api.py`, `test_finance_fixed_deposits.py`, `test_fixed_deposit_summary_api.py`
- Frontend: `FixedDeposits.test.jsx`, `Dashboard.test.jsx` (allocation chart), `api.test.js`

### Deferred
- Interest payments, cash movements, maturity/closure accounting, renewal accounting
- Bank account cash balance in portfolio value; accrued interest in portfolio value

---

## 2026-06-08 — CASH-SELL-1B: Actual SELL proceeds + TAX_WITHHELD ledger row

### Added
- Transaction fields `actual_cash_received` (optional, SELL only) and `settlement_note`
- Cash ledger entry type `TAX_WITHHELD` — negative amount linked to SELL when actual broker cash is below calculated proceeds
- Accounting-style SELL settlement: `SELL_SETTLEMENT` = calculated proceeds; `TAX_WITHHELD` = −(calculated − actual); net cash = actual received
- Transaction modal SELL fields: calculated proceeds preview, actual cash received, withheld preview, settlement note
- Cash ledger displays `TAX_WITHHELD` rows (protected; type label “Tax withheld”)

### Updated
- `docs/product-rules.md`, `docs/cash-ledger.md`, `docs/api-contracts.md`, `docs/api-design.md`, `docs/frontend-design.md`, `docs/page-layouts.md`, `docs/current-state.md`
- `backend/transactions/cash_settlement.py`, serializers, `cash/ledger_details.py`, `portfolios/cash_ledger_flows.py`
- `frontend/src/components/TransactionModal.jsx`, `frontend/src/utils/cashDisplay.js`

### Tests
- `backend/tests/test_cash_sell_tax_withheld.py`, updates to cash-aware / performance / XIRR tests
- Frontend: `TransactionModal.test.jsx`, `Cash.test.jsx`

---

## 2026-06-07 — UX: Cash page full-width layout + ledger details (CASH-UI-1)

### Fixed
- Cash Balances and Cash Ledger `SectionCard` sections now span full content width (override global 480px `SectionCard` max-width on `/cash` only)

### Added
- Backend `details` field on `GET /cash/ledger` items — human-readable context for deposits, settlements, transfers, and system rows (`cash/ledger_details.py`)
- Cash ledger **Details** column (replaces separate Source/Note columns); React displays API value only

### Updated
- `docs/page-layouts.md`, `docs/api-contracts.md`, `docs/cash-ledger.md`, `docs/current-state.md`
- `backend/tests/test_cash_api.py`, `frontend/src/pages/Cash.test.jsx`

### Tests
- Backend: `pytest tests/test_cash_api.py` — ledger details cases
- Frontend: `npm test -- --run src/pages/Cash.test.jsx` — full-width + details column

---

## 2026-06-07 — FIX: Historical cash settlement sync (CASH-HIST-1)

### Root cause
- Enabling `cash_aware_enabled` on a legacy portfolio does not backfill `BUY_SETTLEMENT` / `SELL_SETTLEMENT` for pre-existing transactions.
- Observed on portfolio **Scalablefolio** (id=2): 37 missing settlements; cash balance reflected deposits only; Value History dipped on SELL dates.

### Added
- `transactions/cash_settlement_sync.py` — plan, negative-cash validation, atomic idempotent apply
- `manage.py sync_cash_settlements` — `--portfolio-id` (required), dry-run default, `--apply`, `--allow-legacy`, `--json`
- `backend/tests/test_cash_settlement_sync_command.py` (12 cases)
- Assets Overview **Cash balances** section (`Assets.jsx`) — native + display values; cash excluded from holdings table clicks

### Updated
- `docs/cash-ledger.md`, `docs/product-rules.md`, `docs/workflows.md`, `docs/mvp-release-checklist.md`, `docs/current-state.md`
- `backend/tests/conftest.py` — shared `cash_aware_portfolio` fixture
- `frontend/src/pages/Assets.test.jsx` — cash visibility tests

### Tests
- Backend: `pytest tests/test_cash_settlement_sync_command.py tests/test_cash_aware_transactions_api.py tests/test_cash_api.py tests/test_portfolio_performance_api.py tests/test_diagnostics_integrity.py` — **181 passed**
- Frontend: `npm test -- --run src/pages/Assets.test.jsx src/pages/Cash.test.jsx src/api.test.js` — **85 passed**; `npm run build` — OK

---

## 2026-06-07 — DOCS: Developer documentation index (STAB-7)

### Added
- `docs/README.md` — main documentation landing page (product overview, architecture, rules, API, cash, Metric Sheet, workflow, testing, diagnostics, performance, release readiness, deferred roadmap)

### Updated
- `AGENTS.md`, `docs/current-state.md`, `docs/workflows.md`, `.cursor/rules/project-core.mdc` — links to `docs/README.md`
- `docs/current-state.md` — STAB-7 maintenance row

### Notes
- Documentation only — no production code changes
- No backend/frontend tests run — documentation-only change

---

## 2026-06-06 — RELEASE: MVP sign-off (MVP-RELEASE-1)

### Status
- **MVP release-ready with accepted limitations** — not production-deployed
- Manual golden-flow browser QA **complete** (user sign-off)
- Automated STAB-6 gates previously passed; no re-run required for this docs-only sign-off

### Sign-off
- **Date:** 2026-06-06
- **Branch:** `main` (stabilization commit pending)
- **Tester:** Manual QA completed per [mvp-release-checklist.md](./mvp-release-checklist.md) § C

### Accepted limitations
- Transfer fees deferred (Cash-8C)
- Same-portfolio FX conversion deferred
- Dashboard performance optimization deferred (STAB-5B baseline acceptable)
- Background scheduler / Celery deferred
- Full browser E2E suite deferred

### Updated
- `docs/current-state.md` — MVP release-ready status, commit-prep summary
- `docs/mvp-release-checklist.md` — checklist completed, § E sign-off

### Notes
- Documentation only — no production code changes in MVP-RELEASE-1
- Next: commit STAB-1 through MVP-RELEASE-1 working tree; optional tag `mvp-2026-06-06`

---

## 2026-06-06 — QA: MVP release checklist execution (STAB-6)

### Executed (automated)
- `makemigrations --check --dry-run` — no pending model changes
- `make db-safety-check` — Postgres healthy (67 transactions, 5 portfolios)
- `make test-fast` — 127 passed
- `make test-critical` — 302 backend + 239 frontend passed
- `make test-all` — 840 backend + 384 frontend + `npm run build` passed
- Read-only diagnostics (user `santhoshkgvasudevan`, all scope) — all exit 0
- `profile_dashboard_read_paths.py` — no major regression vs STAB-5B baseline
- `make graphify` — `graphify-out/GRAPH_REPORT.md` updated

### Pending
- ~~Manual golden-flow browser QA~~ — **Complete** (MVP-RELEASE-1)
- Git commit of STAB-1–MVP-RELEASE-1 working tree before release tag

### Updated
- `docs/current-state.md` — STAB-6 release QA table and verdict

### Notes
- No production code changes in STAB-6
- Verdict: **Ready with accepted limitations** (manual QA + commit pending)

---

## 2026-06-06 — DOCS: Dashboard performance decision and optimization backlog (STAB-5B)

### Added
- Real Postgres dev baseline in `docs/performance/dashboard-read-baseline.md` (user `santhoshkgvasudevan`, portfolios 1–4, EUR)
- STAB-5B decision: MVP performance acceptable; optimization deferred
- Ranked optimization backlog P1–P6 and **do not optimize yet** guardrails in `docs/performance/dashboard-read-paths.md`

### Updated
- `docs/performance/dashboard-read-paths.md` — decision record, Postgres observations, test verification matrix
- `docs/current-state.md` — STAB-5B complete; implementation deferred
- `docs/mvp-release-checklist.md` — optional Dashboard profiler step before release

### Notes
- Documentation only — no production code, formula, or API changes
- Profiler username is Django `username`, not email

---

## 2026-06-06 — DOCS/TOOLS: Dashboard read-path baseline (STAB-5A)

### Added
- `backend/diagnostics/dashboard_read_profile.py` — structured Dashboard endpoint profiling (timing, SQL count, notes)
- `docs/performance/dashboard-read-paths.md` — bottleneck/design report and STAB-5B options
- `docs/performance/dashboard-read-baseline.md` — reference snapshot table (SQLite synthetic portfolio)

### Updated
- `backend/scripts/profile_dashboard_read_paths.py` — argparse (`--username`, `--portfolio-id`, `--display-currency`, `--json-out`, `--verbose`); measures summary, performance, Metric Sheet, holdings paths
- `docs/workflows.md` — Performance profiling section
- `docs/current-state.md` — STAB-5A complete; STAB-5B planned

### Notes
- Measurement/design only — no production behavior, formula, or API changes
- Re-profile on Postgres dev data before STAB-5B optimizations; `backend/tmp/*.json` is local output only

---

## 2026-06-06 — DOCS/TOOLS: Read-only diagnostics scripts (STAB-4)

### Added
- `backend/diagnostics/` — reusable read-only integrity check helpers
- `backend/scripts/diagnose_settlement_integrity.py` — cash-aware settlement link/orphan/duplicate/mismatch checks
- `backend/scripts/diagnose_negative_cash.py` — chronological negative running cash balances
- `backend/scripts/diagnose_summary_vs_performance.py` — summary `current_value` vs performance `metric=value`
- `backend/scripts/diagnose_fx_coverage.py` — cached FX gaps for display-currency conversion (DB only)
- `backend/scripts/diagnose_nav_coverage.py` — held MF scheme NAV missing/stale coverage (DB only)
- `backend/tests/test_diagnostics_integrity.py` — lightweight helper tests

### Updated
- `docs/workflows.md` — Diagnostics section lists all scripts with examples
- `docs/mvp-release-checklist.md` — optional pre-release / pre-migration diagnostics
- `docs/current-state.md` — STAB-4 complete

### Notes
- Read-only: no model saves/deletes, no external API calls
- Scripts exit `1` when issues found (optional CI gate); exit `0` when clean
- No production runtime or API behavior changes

---

## 2026-06-06 — TEST: Full backend suite restored after cash-aware default (STAB-3B)

### Fixed
- **72 failing backend tests** after Cash-4A.1 default `cash_aware_enabled=true` — tests that POST BUY/MF rows without ledger funding now use `legacy_seeded` when exercising non–cash-enforcement behavior (holdings, filters, split valuation, MF NAV/import/summary helpers, analytics split/MF freshness)
- `test_mutual_fund_summary_performance_api.py::test_summary_mf_xirr_uses_investment_date_and_paid_value` — add INR→EUR FX + fixed `current_date`; default summary scope (`all`) with EUR display requires FX for INR MF XIRR flows

### Updated
- `backend/tests/conftest.py` — `legacy_seeded` docstring: when to use vs `seeded` + explicit `CASH_DEPOSIT`
- `docs/current-state.md`, `docs/workflows.md` — full suite green; fixture decision note

### Notes
- No production backend or frontend behavior changes
- Cash-aware enforcement, summary/TWROR/XIRR formulas unchanged
- **834** backend pytest · **384** frontend Vitest · `make test-all` passes

---

## 2026-06-06 — DOCS/TEST: Test infrastructure and golden-flow targets (STAB-3)

### Added
- `make test-fast` — finance unit + cash service pytest subset
- `make test-critical` — curated golden-flow backend APIs + key frontend Vitest files
- `make test-all` — full `make test` + frontend production build

### Updated
- `make test-frontend` — runs `npm test -- --run` (non-watch)
- `frontend/src/pages/Cash.test.jsx` — bulk wizard modal, preview totals from server, ledger refresh on apply, full preview payload fields
- `frontend/src/api.test.js` — `previewCashBulkEntries` CashApiError parsing
- `backend/tests/test_analytics_asset_metrics_api.py`, `test_analytics_compare_api.py` — use `legacy_seeded` for BUY-without-deposit scenarios (cash-aware default portfolio)
- `docs/mvp-release-checklist.md`, `docs/workflows.md`, `docs/current-state.md` — test target documentation

### Notes
- No production backend or frontend behavior changes
- Bulk Cash Entries frontend coverage gap closed (tests in existing `Cash.test.jsx`)

---

## 2026-06-06 — DOCS: MVP release checklist and API contracts index (STAB-2)

### Added
- `docs/mvp-release-checklist.md` — pre-release safety, automated checks, manual golden-flow QA, known limitations, release sign-off
- `docs/api-contracts.md` — thin endpoint index (frontend client, tests, key response/error shapes) with links to `api-design.md`

### Updated
- `docs/current-state.md` — STAB-2 status; links to checklist and contracts index
- `docs/workflows.md` — pointers to checklist and contracts index
- `AGENTS.md` — release and contract doc links
- `docs/api-design.md` — cross-link to `api-contracts.md`

### Notes
- No production backend or frontend behavior changes
- No migrations or data mutations
- STAB-3 (`make test-critical`, `make test-fast`) still planned

---

## 2026-06-06 — DOCS: MVP maintenance baseline (STAB-1)

### Added
- `docs/product-rules.md` — canonical product-rules index (cash, returns, Metric Sheet, transfers, frontend, data safety)

### Updated
- `docs/current-state.md` — MVP status, deferred items, removed contradictory “not implemented” Metric Sheet entries, STAB tracker
- `docs/architecture.md` — module boundaries, implemented Cash Ledger / Metric Sheet UI / cash-aware returns; `cash_settlement.py`
- `docs/api-design.md` — Implemented Endpoint Index; removed stale Planned/Proposed blocks for shipped endpoints
- `docs/workflows.md` — Graphify Usage, TDD/test workflow, Diagnostics sections
- `AGENTS.md` — product-rules pointer, TDD expectations, Graphify policy
- `.cursor/rules/graphify.mdc`, `project-core.mdc`, `django-drf.mdc`, `200-frontend-design.mdc`

### Fixed
- `Makefile` `graphify` target — `graphify update .` (was broken `graphify .`)
- Graphify policy aligned to “major structural changes only”

### Graphify
- Regenerated via `graphify update .`; `graphify-out/GRAPH_REPORT.md` refreshed

### Notes
- No production backend or frontend behavior changes
- No migrations or data mutations

---

## 2026-06-06 — FEAT: User-entered cross-currency portfolio transfer (Cash-8B)

### Added
- `POST /api/v1/cash/transfers` accepts `source_currency`, `source_amount`, `target_currency`, `target_amount` for cross-currency moves
- Legacy `currency` + `amount` payload retained for same-currency transfers
- Response includes `source_*`, `target_*`, and informational `implied_rate` (`target_amount / source_amount`; not used for valuation)
- Transfer modal: separate source/target currency and amount fields; no market FX lookup or suggested target amount

### Behavior
- Source sufficiency and future-impact validation use **source currency outflow only**
- Same-currency transfers require equal source/target amounts; all-scope remains neutral
- Cross-currency all-scope totals reflect user-entered amounts converted for display (may differ from cached FX); no forced neutralization

---

## 2026-06-06 — QA: Same-currency transfer validation (Cash-8A-QA)

### Validated
- Transfer success creates exactly one `CashTransferGroup` and two ledger rows; balances update correctly
- Insufficient cash and future-impact rejections create no transfer rows
- All-scope `current_value`, value history, TWROR, and XIRR unchanged after same-currency internal transfer
- Transfer modal copy and protected-row tooltip clarified

### Tests
- DB row-count assertions on failed transfers; all-scope `current_value` assertion on success path
- Frontend label and success-message coverage

---

## 2026-06-06 — FEAT: Same-currency portfolio cash transfers (Cash-8A)

### Added
- `POST /api/v1/cash/transfers` — same-currency portfolio-to-portfolio transfer; atomic `CashTransferGroup` + `TRANSFER_OUT` / `TRANSFER_IN` ledger rows
- Source sufficiency + future-impact validation on source portfolio (parity with withdrawals)
- Transfer rows protected from manual `PUT`/`DELETE /cash/ledger/{id}`
- `/cash` → **Transfer Cash** modal (`createCashTransfer`)
- Cash-aware external flows: `TRANSFER_IN` / `TRANSFER_OUT` count as contribution/withdrawal at single-portfolio scope; **All Portfolios** aggregates net to zero (no artificial TWROR/XIRR spike)

### Documented
- Same-currency transfer only in Cash-8A; no FX conversion or transfer fees yet (Cash-8B)
- All-scope transfer neutralization behavior

---

## 2026-06-04 — FEAT: Transaction edit/delete future-impact errors (TXN-AUDIT-2/3)

### Added
- `PUT`/`DELETE /api/v1/transactions/{id}` return structured **409** future-impact payload when linked settlement change would drive later cash negative (parity with `/cash/ledger` edit/delete)
- `/transactions` delete blocked UX — `CashFutureImpactDisplay` inline panel (replaces `alert`)
- `TransactionModal` edit — future-impact panel; insufficient BUY shortfall unchanged
- `futureImpactFromApiError` in `api.js`; `deleteTransaction` uses `TransactionApiError` with full payload
- Backend + frontend regression tests (TXN-AUDIT-1 extended)

### Documented
- Editing legacy-created transactions after enabling cash-aware mode may require funding first
- Linked `BUY_SETTLEMENT` / `SELL_SETTLEMENT` rows remain protected from manual cash ledger edit

---

## 2026-06-04 — REMOVE: Cash shortfall backfill APIs (Cash-7A/7B)

### Removed
- `POST /api/v1/cash/backfill-preview` and `POST /api/v1/cash/backfill-apply`
- `cash/backfill_preview.py`, `cash/backfill_apply.py`
- Backfill serializers, views, routes
- `tests/test_cash_backfill_preview_api.py`, `tests/test_cash_backfill_apply_api.py`

### Product
- Shortfall backfill (minimum deposits before historical BUYs) is no longer supported
- Historical actual funding → manual cash entries or **Bulk Cash Entries** (Cash-7D)

### Unchanged
- Cash-7D bulk entries, cash-aware BUY/SELL, manual ledger CRUD, CSV cash preview, cash-aware returns

---

## 2026-06-04 — FEAT: Bulk cash entries schedule (Cash-7D)

### Added
- `POST /api/v1/cash/bulk-entries/preview` and `POST /api/v1/cash/bulk-entries/apply` — manual `CASH_DEPOSIT` / `CASH_WITHDRAWAL` schedules (`once`, `monthly`)
- `cash/bulk_entries.py` — server-side date generation, withdrawal balance check, duplicate skip on apply
- `/cash` → **Add Bulk Cash Entries** wizard (`CashBulkEntriesWizard`)
- `tests/test_cash_bulk_entries_api.py`; frontend Vitest for wizard + API client

### Behavior
- Apply requires `confirmed: true`; backend recomputes schedule; skips identical manual rows
- Withdrawal schedules blocked when running balance would go negative
- No settlements, no transaction mutation, no auto-enable cash-aware

---

## 2026-06-04 — REVERT: Cash backfill wizard UI removed (Cash-7C)

### Removed
- `/cash` **Backfill Cash** button and `CashBackfillWizard` modal
- Frontend `previewCashBackfill` / `applyCashBackfill` API client helpers
- Cash-7C Vitest coverage

### Unchanged
- Backend `POST /cash/backfill-preview` and `POST /cash/backfill-apply` (Cash-7A/7B) remain available; not linked from UI
- Cash-aware BUY/SELL enforcement, manual deposit/withdrawal, ledger edit/delete on `/cash`

### Product
- Historical cash is entered via manual deposits/withdrawals or a future **Bulk Cash Entries / Recurring Cash Deposits** feature — not the shortfall backfill wizard

### Next
- Bulk Cash Entries / Recurring Cash Deposits (planned)

---

## 2026-06-04 — FEAT: Cash backfill wizard UI (Cash-7C)

### Added
- `/cash` — **Backfill Cash** button; `CashBackfillWizard` modal (configure → preview → review → apply → optional enable)
- `previewCashBackfill` / `applyCashBackfill` in `frontend/src/api.js`
- Vitest: `Cash.test.jsx` backfill flow; `api.test.js` backfill client

### Behavior
- React displays backend preview/apply only; proposed amounts not editable; `confirmed: true` on apply; double-submit guarded
- After apply with creates: refreshes balances + ledger; optional `PUT /portfolios/{id}` to enable cash-aware (user confirmation)

### Next
- Cash-8 — portfolio transfers / FX conversion APIs + UI

---

## 2026-06-04 — FEAT: Cash backfill apply API (Cash-7B)

### Added
- `POST /api/v1/cash/backfill-apply` — user-confirmed, atomic creation of proposed `CASH_DEPOSIT` rows from server-side preview recompute
- `cash/backfill_apply.py` — duplicate skip for identical backfill deposits; amounts quantized to ledger precision
- `tests/test_cash_backfill_apply_api.py` — confirmation, apply, idempotency, MF/FX/same-currency, no settlement/transaction mutation

### Unchanged
- No `cash_aware_enabled` auto-enable; no `BUY_SETTLEMENT` / `SELL_SETTLEMENT` for historical transactions; no transaction mutation
- No implicit FX; backend remains source of truth (frontend must not compute backfill)

---

## 2026-06-04 — FEAT: Cash backfill preview API (Cash-7A)

### Added
- `POST /api/v1/cash/backfill-preview` — read-only shortfall simulation for legacy → cash-aware migration
- `cash/backfill_preview.py` — chronological ledger + transaction simulation; same-currency BUY sufficiency; merged proposed deposits
- `tests/test_cash_backfill_preview_api.py` — stock/MF/SELL/split/cash-aware/404/400/read-only cases

### Unchanged
- No `CashLedgerEntry` writes; no `cash_aware_enabled` toggle (Cash-7B/C)
- No implicit FX; no display-currency logic in preview

### Next
- Cash-7C — backfill wizard UI

---

## 2026-06-04 — DOC/TEST: Cash-only multi-currency FX return behavior

### Documented
- Cash-only portfolios with cash in a currency ≠ `display_currency` may show non-zero XIRR/TWROR/cumulative return from cached FX (`docs/cash-ledger.md`, `docs/api-design.md`). Tester portfolio (USD+EUR cash, EUR display) reproduces ~9% XIRR — expected, not stale settlements.

### Added
- Regression tests: same-currency cash-only ~0 returns; USD cash + EUR display FX-driven non-zero; delete BUY restores cash-only returns.

---

## 2026-06-04 — QA: Cash-aware return validation (Cash-6D)

### Added
- `backend/scripts/diagnose_cash_aware_returns.py` — read-only diagnostic (summary, performance metrics, cash balances, external flows)
- Cash-6D regression tests in `test_portfolio_performance_api.py` and `test_analytics_performance_metrics_api.py` (seven validation scenarios)

### Verified (no formula changes)
- Deposit-only, deposit+BUY flat, growth ~10%, sell-to-cash continuity, withdrawal vs TWROR, mixed all-scope, same-currency BUY (existing Cash-4E tests)

### Next
- Cash-7 — transfers, backfill

---

## 2026-06-04 — FEAT: Cash-aware TWROR and cumulative return (Cash-6C.2)

### Added
- `portfolios/cash_ledger_flows.py` — shared ledger external-flow classification (TWROR vs XIRR sign)
- `portfolios/external_flows_service.py` — legacy transaction flows + cash-aware ledger flows; mixed all-scope
- `portfolios/performance_service.build_return_value_timeseries` — cash-inclusive values for cash-aware portfolios
- Portfolio Metric Sheet daily returns use cash-inclusive values + cash-aware flows (CAGR, volatility, Sharpe, drawdowns, etc.)
- Performance API `twror` / `cumulative_return` warnings when FX missing on external flows

### Unchanged
- Asset-level Metric Sheet, Compare, asset-level XIRR
- Legacy portfolio TWROR/cumulative return (investment-only)
- `finance/twror.py` period-return formula

### Next
- Cash-7 — transfers, backfill, all-scope transfer neutralization

---

## 2026-06-04 — FEAT: Cash-aware portfolio-level XIRR (Cash-6C.1)

### Added
- `portfolios/xirr_service.py` — `compute_scope_xirr_detail` / `compute_scope_xirr` with legacy vs cash-aware modes
- Cash-aware XIRR: `CASH_DEPOSIT` / `CASH_WITHDRAWAL` / unlinked `ADJUSTMENT` as external flows; terminal = holdings + cash
- All Portfolios: per-portfolio rules, flows merged in `display_currency` (mixed cash-aware + legacy)
- Summary + Metric Sheet share the same helper; XIRR FX warnings in `warnings`
- `finance/xirr.solve_xirr`, `finance/mutual_fund_cashflows.build_legacy_portfolio_xirr_flows`
- Backend tests: cash-aware growth/deposit-only/withdrawal/FX/mixed-scope; unit tests for ledger flow selection

### Unchanged
- Asset-level XIRR, Compare, TWROR, cumulative_return, performance daily risk metrics
- No migrations; React does not compute XIRR

### Next
- Cash-6C.2 — cash-aware TWROR / cumulative_return

---

## 2026-06-04 — FEAT: Cash in portfolio value history (Cash-6B)

### Added
- Daily cash balance timeseries from `CashLedgerEntry` (`build_cash_value_timeseries`, `merge_cash_into_value_timeseries`)
- `GET /portfolio/performance?metric=value` and summary `timeseries` include cash converted to `display_currency`
- Last `metric=value` point aligns with summary `current_value` when FX is available
- Optional performance response `{"points", "warnings"}` when cash FX is partial
- Dashboard Value History reads backend series (supports `points` + warnings wrapper)

### Unchanged
- `metric=cumulative_return` and `metric=twror` use investment-only daily values
- XIRR, Metric Sheet, Compare, holdings table — no cash
- Cached FX only; ledger balances count regardless of `cash_aware_enabled`

### Next
- Cash-6C — cash in TWROR / XIRR

---

## 2026-06-04 — FEAT: Cash in summary current value and allocation (Cash-6A)

### Added
- `GET /api/v1/portfolio/summary` — `current_value` includes native cash balances converted to `display_currency`; optional `cash_summary` block
- `GET /api/v1/portfolio/holdings` — `allocation` array with investment slices + `Cash {currency}` rows (`asset_type=CASH`, `is_cash=true`); `holdings` remains stocks/MF only
- `cash/services.py` — `build_cash_display_summary`, `cash_allocation_rows`, `cash_summary_payload`
- Assets allocation chart reads backend `allocation`; Compare picker excludes cash rows
- Backend/frontend tests for EUR/INR cash conversion, all-scope aggregation, missing FX warnings, legacy portfolios with ledger entries

### Unchanged
- Performance timeseries, TWROR, XIRR, Metric Sheet — investment-only (Cash-6B/6C)
- No fake `Asset` rows; cached FX only; no external API calls on read

### Next
- Cash-6B — cash in performance value history / daily timeseries
- Cash-6C — cash in TWROR / XIRR

---

## 2026-06-04 — FEAT: CSV import cash shortfall preview (Cash-5)

### Added
- `POST /api/v1/transactions/import-csv/preview-cash` — chronological cash simulation; `shortfalls`, `proposed_deposits`, `summary`
- `POST /api/v1/transactions/import-csv` — query `create_cash_deposits=true` + `cash_preview_confirmed=true` creates same-currency deposits then imports (atomic)
- Cash-aware import without confirmation → **409** with preview payload; legacy portfolios unchanged
- `CsvImportCashPreviewModal` on Transactions page — user must confirm before deposits are created

### Unchanged
- No silent deposits; no FX conversion; summary/performance/TWROR/XIRR

### Next
- Cash-6 — integrate cash into summary/performance/allocation

---

## 2026-06-04 — FEAT: Add missing cash and continue purchase (Cash-4C)

### Added
- `TransactionModal` — **Recommended action** panel on stock/MF BUY shortfall: user-confirmed `POST /cash/deposits` using backend `shortfall` + `currency`, then retries original BUY
- `PurchaseShortfallAction.jsx`, `purchaseShortfallHelpers.js` — deposit date (stock `date`, MF `investment_date`); partial-success warning when deposit succeeds but retry fails
- Transactions page success banner: **Cash deposit added and purchase recorded.**

### Unchanged
- No FX conversion; no CSV preview; no summary/performance integration; backend unchanged

### Next
- Cash-5 — CSV import cash shortfall preview

---

## 2026-06-04 — FEAT: Same-currency cash enforcement verification (Cash-4E)

### Added
- Backend tests: EUR BUY ignores USD-only or partial EUR with USD present; sufficient EUR BUY leaves USD unchanged
- `CashShortfallDisplay` `variant="purchase"` — same-currency guidance for stock/MF BUY; withdrawal path unchanged
- `TransactionModal` — **Open Cash page** link; no copy suggesting automatic FX conversion

### Documented
- Same-currency funding required for cash-aware BUY; implicit FX and Cash FX conversion deferred (Cash-8)

### Unchanged
- No FX conversion APIs/UI; no Cash-4C auto-deposit; summary/performance/allocation; TWROR/XIRR

### Next
- Cash-4C — confirm + auto-deposit on BUY shortfall

---

## 2026-06-04 — FEAT: Cash ledger edit/delete with future impact validation (Cash-4D)

### Added
- `PUT` / `DELETE /api/v1/cash/ledger/{id}` — manual `CASH_DEPOSIT` / `CASH_WITHDRAWAL` only; rejects linked/system rows with **409**
- Future-impact simulation: **409** with `earliest_negative_date`, `lowest_balance`, `affected_entries` (up to 10, includes `asset_symbol` when linked)
- `/cash` UI: edit/delete actions, `CashFutureImpactDisplay` on rejection; no cascade delete of asset transactions

### Unchanged
- Summary/performance/TWROR/XIRR; no CSV preview; no auto-deposit (Cash-4C)

---

## 2026-06-04 — FEAT: Cash-aware status and enable UI (Cash-4A.2)

### Added
- `CashAwarePortfolioStatus` on Cash and Transactions pages (sidebar-selected portfolio)
- Settings portfolio table: Cash-aware On/Off column + **Enable cash-aware** per legacy portfolio
- `PUT /api/v1/portfolios/{id}` enable flow documented for tester repair (e.g. portfolio id 5)

### Unchanged
- No bulk auto-enable; no user deletion; no Cash-4C auto-deposit

---

## 2026-06-04 — FEAT: New portfolios cash-aware by default (Cash-4A.1)

### Changed
- `POST /api/v1/portfolios` — `cash_aware_enabled` defaults to **true** when omitted; explicit `false` allowed for legacy mode
- Registration / `ensure_default_portfolio` — new default portfolios created with `cash_aware_enabled=true`
- Model DB default remains `false` — **no data migration**; existing rows unchanged

### Tester repair
- `PUT /api/v1/portfolios/{id}` with `"cash_aware_enabled": true` (documented; no bulk auto-enable)

### Unchanged
- Summary/performance/allocation/TWROR/XIRR; no auto-deposit; no CSV preview; portfolio `id` remains globally unique

---

## 2026-06-04 — FEAT: Transaction modal BUY shortfall UX (Cash-4B)

### Added
- `TransactionApiError` / `ApiError` — structured transaction write errors; JSON parsed once per response
- `CashShortfallDisplay.jsx` — shared required / available / shortfall panel (`CurrencyValue`)
- `TransactionModal` — stock/MF **BUY** shows purchase shortfall + link to `/cash`; cash withdrawal shortfall unchanged

### Unchanged
- No auto-deposit, no shortfall confirmation step, no CSV preview, no summary/performance integration, no React cash balance math

### Next
- Cash-5 CSV cash preview; or Cash-4C confirm + auto-deposit on BUY shortfall

---

## 2026-06-04 — FEAT: Cash-aware BUY/SELL settlements (Cash-4A)

### Added
- When `portfolio.cash_aware_enabled=true`, stock/MF `POST/PUT/DELETE /api/v1/transactions` create/update/delete linked `BUY_SETTLEMENT` / `SELL_SETTLEMENT` rows
- `transactions/cash_settlement.py` — settlement sync; `finance/cash.py` settlement amount helpers
- `assert_sufficient_cash_for_purchase` in `cash/services.py` (purchase shortfall payload)
- Stock BUY: required = qty×price+fees; SELL: proceeds = qty×price−fees; ledger date = `transaction.date`
- MF BUY: required = `paid_value`; MF SELL: `paid_value` if &gt; 0 else units×NAV−fees; ledger date = **`investment_date`**
- Insufficient BUY → **400** with `detail`, `required`, `available`, `shortfall`, `currency`
- Tests: `tests/test_cash_aware_transactions_api.py` (16 cases)

### Unchanged
- Legacy portfolios (`cash_aware_enabled=false`); no backfill; no summary/performance/TWROR/XIRR; no CSV preview; no auto-enable flag

### Next
- Cash-4B: frontend `CashApiError`-style UX on stock/MF `TransactionModal`

---

## 2026-06-04 — FEAT: Unified Add Transaction modal (Cash-3G)

### Added
- `/transactions` **Add Transaction** modal: **Record type** Cash / Stock / Mutual Fund
- Cash branch: Deposit / Withdrawal → `POST /cash/deposits` or `POST /cash/withdrawals` (not `/transactions`)
- `CashEntryFormFields.jsx` — shared cash form fields; insufficient-withdrawal shortfall display
- Success banner on Transactions after cash record + link to `/cash` ledger; asset table not refetched

### Rules
- Cash ledger edit/delete remains on `/cash` only
- No unified activity list, no BUY/SELL enforcement, no summary/performance changes

### Next
- Cash-4: cash-aware BUY/SELL enforcement on stock/MF transaction path.

---

## 2026-06-04 — FEAT: Cash ledger edit/delete (Cash-3D)

### Added
- `PUT /api/v1/cash/ledger/{id}` — update manual deposit/withdrawal (date, currency, amount, source, note)
- `DELETE /api/v1/cash/ledger/{id}` — delete manual entries when running balance stays non-negative
- `validate_non_negative_cash_after_change` in `cash/services.py`
- `/cash` ledger Actions: Edit / Delete for manual rows only
- API client: `updateCashLedgerEntry`, `deleteCashLedgerEntry`

### Rules
- Only `CASH_DEPOSIT` / `CASH_WITHDRAWAL` without `linked_transaction` or `transfer_group`
- Linked/system entries return **409**; portfolio change not allowed on edit

### Next
- Cash-4: cash-aware BUY/SELL enforcement.

---

## 2026-06-04 — FEAT: Cash page UI (Cash-3B)

### Added
- Route `/cash` and sidebar **Cash** nav (after Transactions)
- `frontend/src/pages/Cash.jsx` — native balances table, paginated ledger, deposit/withdrawal modals
- API client: `fetchCashBalances`, `fetchCashLedger`, `createCashDeposit`, `createCashWithdrawal` (`CashApiError` for insufficient-cash payloads)
- `frontend/src/constants/cashCurrencies.js` (20 supported currencies)
- Tests: `Cash.test.jsx`, `api.test.js`, `Layout.test.jsx`

### Notes
- React displays backend balances/ledger only — no client-side cash math or display-currency totals.
- Portfolio scope from sidebar; All Portfolios requires portfolio pick for writes.
- Not integrated into Dashboard, Metric Sheet, or performance APIs.

### Next
- Cash-4: cash-aware BUY/SELL enforcement on manual transactions.

---

## 2026-06-04 — FEAT: Cash deposit and withdrawal write APIs (Cash-3A)

### Added
- `POST /api/v1/cash/deposits` — creates `CASH_DEPOSIT` (positive signed amount); `201` + ledger item body
- `POST /api/v1/cash/withdrawals` — creates `CASH_WITHDRAWAL` (negative signed amount); blocks insufficient cash with `required` / `available` / `shortfall`
- `create_cash_deposit`, `create_cash_withdrawal` in `cash/services.py` (atomic; uses `finance/cash` balance helpers)
- Tests: deposit/withdrawal cases in `test_cash_api.py`, service tests in `test_cash_services.py`

### Impact
- No migrations. No transaction rows created/modified. No summary/performance/TWROR changes.
- Deposits allowed when `cash_aware_enabled=false`. Next: Cash-3B UI or Cash-4 BUY/SELL enforcement.

---

## 2026-06-04 — FEAT: Cash read APIs (Cash-2)

### Added
- `GET /api/v1/cash/balances` — native-currency balances by portfolio/currency; `as_of_date`, `currency` filters
- `GET /api/v1/cash/ledger` — paginated ledger (`date` desc, `id` desc); scope/filters aligned with holdings
- `cash/views.py`, `cash/serializers.py`, `cash/urls.py`; service helpers in `cash/services.py`
- `Portfolio.cash_aware_enabled` exposed on portfolio CRUD (editable via PUT; no runtime effect yet)
- Tests: `backend/tests/test_cash_api.py`

### Impact
- Read-only; no summary/performance/allocation or BUY/SELL enforcement changes.
- Next: Cash-3 deposit/withdrawal write APIs.

---

## 2026-06-04 — FEAT: Cash Ledger schema foundation (Cash-1)

### Added
- Django app `cash`: `CashLedgerEntry`, `CashTransferGroup`, `cash/constants.py` (20 supported currencies)
- `Portfolio.cash_aware_enabled` (default `false`)
- `finance/cash.py` — pure balance/shortfall/timeseries helpers
- `cash/services.py` — ORM ledger listing and balance computation (no HTTP)
- Migrations: `portfolios/0003_portfolio_cash_aware_enabled`, `cash/0001_initial`
- Tests: `test_cash_ledger_models.py`, `test_finance_cash.py`, `test_cash_services.py`

### Impact
- No change to summary, performance, transactions, or CSV import while `cash_aware_enabled` is false (all existing portfolios).
- Dev DB: transaction count unchanged after migrate (67); backup `backups/kpulla6_20260604_131711.sql` taken before migrate.
- Next: Cash-2 read APIs.

---

## 2026-06-04 — DOCS: Cash Ledger architecture and migration design (Cash-0)

### Added
- `docs/cash-ledger.md` — product model, `CashLedgerEntry` / `CashTransferGroup` schema, currencies, TWROR/XIRR impact, manual/CSV UX, backfill (Scalablefolio / IndianMF), transfers, portfolio value integration, API roadmap, phases Cash-0–Cash-8, open questions

### Changed
- `docs/architecture.md` — Cash Ledger architecture reference
- `docs/database.md` — planned cash tables (not implemented)
- `docs/api-design.md` — planned `/api/v1/cash/*` endpoints (not implemented)
- `docs/current-state.md` — Cash Ledger planned status
- `docs/frontend-design.md` — future Cash UI surfaces
- `docs/page-layouts.md` — planned Cash / backfill / import preview layouts
- `docs/decisions.md` — cash mental model and TWROR/XIRR decisions

### Impact
- Documentation only; no code, migrations, or data changes. Next phase: **Cash-1** schema foundation.

---

## 2026-06-03 — FEAT: App shell theme selector (Light / Dark / System)

- Header theme select (System / Light / Dark) with `localStorage` key `kpulla6.themePreference` (default system)
- Early `theme-init.js` + `ThemeProvider` apply `data-theme` on `<html>`; light token overrides under `[data-theme='light']`
- Recharts `chartTheme.js` reads CSS variables per resolved theme
- Docs: `docs/frontend-design.md`, `docs/current-state.md`

---

## 2026-06-03 — FEAT: User authentication and per-user data scoping

### Added
- Session auth API: `/api/v1/auth/login`, `logout`, `register`, `me`, `password-reset`, `csrf`
- Google OAuth via django-allauth (`/accounts/google/login/`)
- `Portfolio.user` FK and `AppSettings.user` OneToOne (per-user settings)
- Data migration assigning existing portfolios/settings to `santhoshkgvasudevan@gmail.com`
- Management command: `set_user_password` (uses `INITIAL_USER_PASSWORD` env var)
- Frontend login/register/forgot-password pages, auth context, protected routes, sidebar logout
- Docs: `docs/auth.md`

### Changed
- All `/api/v1` portfolio/transaction/settings/analytics routes require authentication (`401`/`403` when unauthenticated)
- DRF default: `SessionAuthentication` + `IsAuthenticated`; health + auth endpoints remain public
- Frontend API client sends `credentials: 'include'` and CSRF token on mutating requests

### Impact
- Unauthenticated users land on `/login`; existing dashboard remains at `/` after sign-in
- Transaction count unchanged after migration (verified via `make db-safety-check`)

## 2026-06-02 — FEAT: Metric Sheet visualization charts (Phase 13C)

### Added
- `MetricSheetYearlyReturnChart` — Calendar-Year Return bar chart from `periodic_returns.yearly` with TWROR helper copy
- `MetricSheetDrawdownChart` — drawdown area chart from `drawdown_series` with worst-episode shading by `drawdown_periods.worst` rank
- `metricSheetMonthlyHeatmap.js` — five-band monthly return heatmap tone mapping
- `metricSheetChartHelpers.js` — display-only chart data organization helpers

### Changed
- `MetricSheetMonthlyReturnsGrid` — stronger heatmap background scale (red / yellow / green bands) with visible cell text
- Dashboard + Asset Detail Metric Sheet — Calendar-Year Return chart above Periodic Returns; Drawdown chart above Worst Drawdowns

### Impact
- Metric Sheet periodic/drawdown sections are easier to scan; Compare page unchanged (tables only)

## 2026-06-02 — FEAT: Metric Sheet drawdown series + Calendar-Year Return contract (Phase 13B)

### Changed
- `periodic_returns.yearly` documented as **Calendar-Year Return** — cash-flow-adjusted daily TWROR returns compounded per calendar year (existing `resample_yearly_returns` semantics; no duplicate calculation)
- `drawdown_periods.worst` entries now include `rank` (1 = deepest drawdown)

### Added
- `drawdown_series` top-level array on portfolio, asset, and compare Metric Sheet responses — dated running drawdown fractions (0 or negative) from `finance/drawdowns.drawdown_series`
- Compare subjects include `drawdown_series` on the aligned common window
- Tests: drawdown series shape/fractions, worst-period rank, calendar-year return cash-flow regression in `test_finance_returns.py`

### Impact
- Backend contract ready for Phase 13C frontend charts (Calendar-Year Return bar chart, drawdown line chart with worst-region shading)

## 2026-06-02 — Phase 13A: Sidebar context controls at top

### Changed
- **Layout:** Portfolio View and Display Currency selectors moved from sidebar bottom to directly below the Portfolio Insight brand header, above main navigation
- **Layout.css:** Controls use compact spacing with bottom divider; footer keeps `margin-top: auto` so the cached-data note stays at the sidebar bottom on desktop

### Added
- `Layout.test.jsx` — verifies portfolio view and display currency appear before navigation links in DOM order

### Impact
- Primary portfolio scope and display currency controls are immediately visible without scrolling the sidebar

## 2026-06-01 — FIX: Metric Sheet cumulative return and CAGR aligned with performance chart

### Changed
- `build_metric_sheet_from_daily_returns` — `metrics.return.cumulative_return` uses the money-weighted terminal formula from `GET /portfolio/performance?metric=cumulative_return` (not compounded TWROR daily returns); removed TWROR fallback when compounding was unavailable
- `metrics.return.cagr` — annualizes that economic cumulative return over the selected range (`cagr_from_total_return`), not TWROR compounding
- `finance/performance_stats.py` — `economic_cumulative_return_fraction`, `contributions_and_withdrawals_through`, `cagr_from_total_return`; shared flow rollup used by `performance_service`

### Added
- Backend regression: Metric Sheet cumulative return matches performance API; cumulative return ≠ TWROR with staggered buys
- Frontend regression: Metric Sheet summary cards render distinct cumulative return, CAGR, TWROR, and XIRR values

### Impact
- Dashboard Metric Sheet headline return metrics now match the performance chart for the same portfolio, range, and display currency

## 2026-05-31 — PERF: Range-aware all-scope value series builder (Phase B2B)

### Changed
- `_build_portfolio_value_timeseries` / `build_all_scope_portfolio_value_timeseries` — optional `emit_start_date`; non-ALL ranges bootstrap opening holdings/prices/NAV/FX at range start and emit only the requested window (ALL unchanged)
- `last_stock_prices_on_or_before` / `last_mutual_fund_navs_on_or_before` — bootstrap helpers for price/NAV forward-fill before range start
- `build_portfolio_performance` / `build_portfolio_performance_metrics` — pass `emit_start_date` for non-ALL ranges; cumulative return iterates the shorter series only
- `_slice_timeseries_for_range` — accepts optional true `inception` when series is pre-sliced

### Added
- `backend/tests/test_range_aware_series_b2b.py` — parity vs full-build+slice, opening holdings, NAV/FX bootstrap, split, TWROR re-chain, 1Y bulk-FX query guard

### Impact
- Non-ALL performance/Metric Sheet paths emit ~366 days instead of ~2,426; service-layer 1Y latency roughly halved with unchanged API shapes and financial semantics

## 2026-05-31 — PERF: All-scope bulk FX maps for performance and Metric Sheet (Phase B1)

### Changed
- `build_all_scope_portfolio_value_timeseries` — preloads `load_fx_rate_maps()` per child portfolio and converts daily values via `convert_amount_with_fill_from_maps()` / `fx_lookup_from_maps()` instead of per-day `convert_amount_with_fill()` DB lookups
- `build_all_scope_external_flows` — same bulk FX map approach for flow conversion
- `fx.lookup.convert_amount_with_fill_from_maps()` — in-memory 7-day fill helper matching `convert_amount_with_fill` semantics

### Added
- Regression: `test_performance_all_scope_value_history_uses_bulk_fx_lookup` (query count guard)

### Impact
- All-scope performance and Metric Sheet read paths drop from ~9,000 FX SELECTs to a handful of bulk loads; endpoint latency reduced with unchanged financial semantics and API shapes

## 2026-05-31 — FIX: All Portfolios cumulative_return and TWROR gaps (Phase 12B follow-up #3)

### Fixed
- `build_portfolio_performance` (`metric=cumulative_return` / `twror`, `portfolio_scope=all`) — uses the same all-scope display-currency value series as `metric=value`, plus aggregated per-portfolio external flows converted to display currency (`build_all_scope_external_flows`)
- `build_portfolio_performance_metrics` (Metric Sheet) — same all-scope display-currency value/flow path for `portfolio_scope=all`

### Added
- `build_all_scope_external_flows()` in `portfolios/performance_service.py`
- Regressions: `test_performance_all_scope_cumulative_return_no_gap_with_pln_stock_and_inr_mf`, `test_performance_all_scope_twror_no_gap_with_pln_stock_and_inr_mf`, `test_performance_all_scope_value_cumulative_twror_share_valid_calendar`, `test_analytics_scope_all_pln_stock_uses_display_currency_series`

### Impact
- All-scope TWROR semantics: computed from aggregated display-currency portfolio value and external cash-flow series
- Dashboard Cumulative Return and TWROR charts no longer show multi-year null gaps when PLN/EUR/INR portfolios are combined

## 2026-05-31 — FIX: All Portfolios value history gap after DNP.WA buy (Phase 12B follow-up #2)

### Fixed
- `build_portfolio_performance` (`metric=value`, `portfolio_scope=all`) — uses per-portfolio value timeseries converted to display currency and aggregated (same strategy as summary), instead of one pooled series in a single `portfolio_base`
- Root cause: pooled all-scope build used INR as base (earliest transaction); Scalablefolio `DNP.WA` (PLN-denominated) required missing `PLN→INR` FX from 2024-03-27 until 2026-05-28, nulling 792 daily points
- `build_all_scope_portfolio_value_timeseries` in `portfolios/summary_service.py`; shared `_aggregate_timeseries_lists` helper

### Added
- Regression: `test_performance_all_scope_eur_value_history_no_gap_with_pln_stock`

### Impact
- Dashboard Value History line is continuous for All Portfolios + EUR display; last chart point equals Current Value KPI (same valuation/FX path as summary)

## 2026-05-31 — FIX: All Portfolios value history vs summary current value (Phase 12B follow-up)

### Fixed
- `build_portfolio_value_timeseries` — stock holdings now convert to `portfolio_base` before summing with mutual fund values (fixes mixed EUR stock + INR MF portfolios under `portfolio_scope=all` where EUR amounts were added to INR totals)
- Regression: `test_all_scope_summary_current_value_matches_performance_last_value`

### Impact
- Dashboard Value History last point now aligns with Current Value KPI for All Portfolios + display currency EUR (within FX timing tolerance)

## 2026-05-31 — FIX: Dashboard Metric Sheet layout + MF NAV freshness warnings (Phase 12B)

### Fixed
- Dashboard Metric Sheet uses full content width (overrides SectionCard 480px cap); section moved outside chart wrapper with increased internal spacing
- MF NAV Metric Sheet warnings use freshness rule (`MF_NAV_STALE_AFTER_DAYS = 5`): no warning for weekend/holiday gaps when latest cached NAV is recent; stale vs missing copy separated

### Added
- Tests: `test_analytics_mf_nav_freshness.py`; asset metrics NAV freshness API cases; Dashboard full-width layout assertion

### Changed
- `docs/api-design.md`, `docs/architecture.md`, `docs/frontend-design.md`, `docs/current-state.md`

### Impact
- UX/data-quality refinement only; no new metrics, caching, exports, or read-path external calls

## 2026-05-31 — AUDIT: Metric Sheet release readiness (Phase 12A)

### Fixed
- Compare API: TWROR (and cumulative fallback) now computed on the aligned common window, not the independent range slice (`analytics/services.py`)
- Compare metric table labels aligned with Dashboard/Asset Detail (`Volatility (annualized)`, `Sharpe Ratio`, etc.)
- Yearly fallback table wrapped in `.metric-sheet-table-scroll`
- Dashboard benchmark table guard matches Asset Detail (`selectedBenchmark` required)

### Added
- Compare API contract tests: common-window warning, `xirr_scope`, metrics shape, aligned TWROR
- Frontend tests: warning severity mapping, XIRR note on Compare, yearly scroll wrapper, empty yearly compare state

### Changed
- `docs/api-design.md`, `docs/frontend-design.md`, `docs/current-state.md`

### Impact
- Regression audit and small consistency fixes only; no new metrics, routes, exports, or caching

## 2026-05-31 — FEAT: Compare metric scanability (Phase 11B)

### Added
- `compareMetricRanking.js` — display-only two-subject metric comparison for highlight state (`better` / `worse` / `tie` / `neutral` / `unknown`)
- Subtle per-cell highlights in `CompareMetricTable` with accessible labels and legend note
- Tests: `compareMetricRanking.test.js`; Compare + monthly grid updates in `metricSheet.test.jsx`

### Changed
- `MetricSheetMonthlyReturnsGrid` — yearly total column header renamed to **Year Return**
- Compare drawdown sections verified to use `.metric-sheet-table-scroll` wrappers
- `docs/frontend-design.md`, `docs/current-state.md`

### Impact
- Frontend display enhancement only; no backend APIs, exports, or client-side analytics calculations

## 2026-05-31 — FEAT: Metric Sheet monthly returns grid (Phase 11A)

### Added
- `MetricSheetMonthlyReturnsGrid` — year × month grid from backend `periodic_returns.monthly`; full-year column from `periodic_returns.yearly`
- `metricSheetMonthlyGrid.js` — display-only period parsing and grid layout helpers
- Tests: `metricSheetMonthlyGrid.test.js`; updates to `metricSheet.test.jsx`, `Dashboard.test.jsx`

### Changed
- `MetricSheetPeriodicReturnsTable` — monthly list replaced by grid; compact yearly table only when monthly is empty
- Compare page unchanged (yearly side-by-side only)
- `docs/frontend-design.md`, `docs/current-state.md`

### Impact
- Frontend display enhancement only; no backend APIs, caching, exports, or client-side return calculations

## 2026-05-31 — FIX: Metric Sheet polish (Phase 10B)

### Changed
- Dashboard Metric Sheet benchmark selector moved to section header (always visible/editable); chart overlay still uses the same benchmark when cumulative return or TWROR is selected
- `.metric-sheet-table-scroll` wrappers on wide Metric Sheet / Compare tables
- Asset Detail waits for `settingsLoaded && apiQuery` before fetching asset detail
- Dashboard stale Metric Sheet response test added
- `analytics/services.py` — clearer missing cached price / NAV warnings; split-warning path reuses pre-built asset timeseries
- Tests: Dashboard, Asset Detail, Metric Sheet component, analytics asset API

### Impact
- UX/reliability polish only; no new metrics, caching, or schema changes

## 2026-05-31 — FEAT: Metric Sheet periodic returns and drawdown periods UI (Phase 9B)

### Added
- `MetricSheetPeriodicReturnsTable`, `MetricSheetDrawdownPeriodsTable`
- `ComparePeriodicReturnsSection` (yearly side-by-side), `CompareDrawdownPeriodsSection` (per subject)
- Dashboard, Asset Detail, and Compare integration; fixture and test updates

### Changed
- `docs/frontend-design.md`, `docs/current-state.md`

### Impact
- Display-only; no backend or finance logic changes

## 2026-05-31 — FEAT: Metric Sheet periodic returns and drawdown periods (Phase 9A)

### Added
- `worst_drawdown_periods` in `finance/drawdowns.py` — peak/trough/recovery episodes from dated daily returns
- `periodic_returns` (`monthly`, `yearly`) and `drawdown_periods.worst` on portfolio, asset, and compare Metric Sheet APIs
- Tests: `test_finance_drawdowns.py` (worst periods), analytics API tests for new blocks

### Changed
- `analytics/services.py` — `build_periodic_returns_block`, `build_drawdown_periods_block`, empty payloads
- `docs/api-design.md`, `docs/current-state.md`

### Impact
- Fractional returns only; no DB migrations; no frontend changes; existing `metrics` fields unchanged

## 2026-05-31 — FEAT: Metric Sheet UX hardening (Phase 8E)

### Changed
- Compare asset pickers prefer open holdings; closed labeled `(closed)` with optgroups
- Compare range context: requested range + common aligned dates in one note
- XIRR full-scope helper text clarified across summary cards and compare table
- `MetricSheetWarnings` severity mapping for FX, NAV, price, and benchmark overlap messages
- Tests: `compareHoldings.test.js`, `metricSheetCopy.test.js`; updates to Compare and Metric Sheet tests

### Impact
- No backend or finance logic changes; display-only UX pass before Phase 9

## 2026-05-31 — FEAT: Compare Metric Sheet UI (Phase 8D)

### Added
- `/compare` route and sidebar **Compare** navigation
- `Compare.jsx` — dual asset pickers from holdings, range/benchmark controls, `getCompareMetricSheet` fetch
- `CompareNormalizedChart`, `CompareMetricTable`, compare CSS and test fixture
- Tests: `Compare.test.jsx`, `metricSheet.test.jsx` compare cases, Layout nav test

### Changed
- `frontend/src/App.jsx`, `frontend/src/components/Layout.jsx`, `metricSheet/index.js`
- `docs/frontend-design.md`, `docs/current-state.md`

### Impact
- Normalized cumulative return chart and side-by-side metrics from backend only; MF multi-folio shows friendly error without folio picker UX

## 2026-05-30 — FEAT: Asset Detail Metric Sheet integration (Phase 8C)

### Added
- `AssetDetailMetricSheet` component with local range and benchmark controls
- Asset Detail page integration below hero KPIs via `getAssetMetricSheet`
- `AssetDetail.test.jsx` Metric Sheet tests (9 cases)

### Changed
- `frontend/src/pages/AssetDetail.jsx`, `AssetDetail.css`
- `docs/frontend-design.md`, `docs/current-state.md`

### Impact
- Independent Metric Sheet loading/errors; folio_number passed for MF assets; Compare UI deferred

## 2026-05-30 — FEAT: Dashboard Metric Sheet integration (Phase 8B)

### Added
- Portfolio Metric Sheet section on Dashboard below the main performance chart
- Independent `getPortfolioMetricSheet` fetch with section-local loading and error states
- Dashboard tests for Metric Sheet API params, rendering, warnings, null metrics, and isolated failures

### Changed
- `frontend/src/pages/Dashboard.jsx`, `Dashboard.css`, `Dashboard.test.jsx`
- `docs/frontend-design.md`, `docs/current-state.md`

### Impact
- Reuses Dashboard scope, currency, range, and benchmark controls; no finance calculations in React
- Asset Detail and Compare UI deferred to Phase 8C+

## 2026-05-30 — FEAT: Metric Sheet frontend foundation (Phase 8A)

### Added
- `getPortfolioMetricSheet`, `getAssetMetricSheet`, `getCompareMetricSheet` in `frontend/src/api.js`
- `frontend/src/utils/metricFormatters.js` — display-only fraction/ratio/day formatting
- `frontend/src/components/metricSheet/` — reusable Metric Sheet section, summary cards, risk/return tables, benchmark table, warnings
- Tests: `metricFormatters.test.js`, `metricSheet.test.jsx`; API client tests in `api.test.js`

### Changed
- `docs/frontend-design.md`, `docs/current-state.md` — Phase 8A status

### Impact
- No page integration yet; no backend changes; no finance calculations in React

## 2026-05-30 — FEAT: Compare API for Quantitative Statistics (Phase 7)

### Added
- `GET /api/v1/analytics/compare` — two-asset side-by-side Metric Sheet comparison
- `align_multi_subject_returns`, `normalized_cumulative_return_series` in `finance/comparison.py`
- `_prepare_asset_daily_metrics_inputs`, `build_analytics_compare`, `parse_compare_subjects` in `analytics/services.py`
- `CompareAnalyticsView` in `analytics/views.py`
- `backend/tests/test_analytics_compare_api.py` (15 cases); finance compare alignment tests

### Changed
- Asset Metric Sheet path refactored to shared `_prepare_asset_daily_metrics_inputs`
- `docs/api-design.md`, `docs/current-state.md`, `docs/architecture.md`

### Impact
- No DB migrations; no frontend; portfolio/asset Metric Sheet response shapes unchanged
- Compare metrics computed over common overlapping dates only; unknown asset in scope → 404

## 2026-05-30 — HARDENING: Metric Sheet stock split × cached price invariant (Phase 6B)

### Added
- `_split_adjusted_price_inconsistency_warnings` in `analytics/services.py` — detects likely raw nominal prices around splits
- `backend/tests/test_analytics_split_metrics_api.py` (6 cases): adjusted-price stability, raw-price warning, split flow neutrality

### Changed
- `docs/architecture.md`, `docs/api-design.md`, `docs/current-state.md` — split-adjusted price invariant documented
- Metric Sheet portfolio + asset endpoints append warning when raw split-price mismatch detected

### Impact
- No formula changes; no migrations; yfinance sync already stores Adj Close
- Raw manually inserted nominal prices: metrics may compute but API warns — not silently trusted

## 2026-05-30 — FEAT: Asset-level analytics Metric Sheet API (Phase 6)

### Added
- `GET /api/v1/analytics/assets/{asset_symbol}/performance-metrics` — stock + MF asset Metric Sheet
- `build_asset_performance_metrics`, `build_metric_sheet_from_daily_returns` in `analytics/services.py`
- `AssetPerformanceMetricsView` in `analytics/views.py`
- `backend/tests/test_analytics_asset_metrics_api.py` (11 cases)

### Changed
- Portfolio Metric Sheet assembly refactored to shared `build_metric_sheet_from_daily_returns`
- `docs/api-design.md`, `docs/current-state.md`, `docs/architecture.md`

### Impact
- No DB migrations; no frontend; summary/performance API shapes unchanged
- Asset series built from scoped transactions + cached prices/NAV/FX (reuses `build_portfolio_value_timeseries` for single asset/MF holding)

## 2026-05-30 — REFACTOR: Analytics Metric Sheet API boundaries (Phase 5B)

### Changed
- `portfolios/summary_service.py` — public `compute_scope_xirr()` wrapper (full-scope XIRR shared by summary and analytics)
- `backend/analytics/services.py` — import public XIRR helper; `metrics.return.xirr_scope: "full_scope"`; docstring notes on ratio vs currency
- `backend/tests/test_analytics_performance_metrics_api.py` — public-import guard + `xirr_scope` assertions (12 cases)
- `docs/api-design.md` — XIRR full-scope vs range-based metrics; ratio/currency wording

### Impact
- No finance formula changes; summary/performance response shapes unchanged
- Analytics clients can distinguish range-sliced metrics from full-scope XIRR before Phase 6 asset-level work

## 2026-05-30 — FEAT: Portfolio analytics API (Phase 5)

### Added
- `GET /api/v1/analytics/performance-metrics` — portfolio Metric Sheet (return, risk, drawdown, period metrics; optional benchmark block)
- `backend/analytics/services.py`, `views.py`, `urls.py`, `serializers.py` (placeholder)
- `backend/tests/test_analytics_performance_metrics_api.py` (10 cases)
- `portfolios/performance_service.py` — `portfolio_external_flows`, `portfolio_flows_known_on_date` public helpers

### Changed
- `backend/api/urls.py` — include `analytics.urls`
- `docs/api-design.md`, `docs/current-state.md`, `docs/architecture.md`

### Impact
- Read path uses cached DB only; metrics computed on query from value/flow → `daily_returns_from_values`. No frontend UI. Summary/performance API shapes unchanged.

## 2026-05-30 — FEAT: Benchmark-relative Metric Sheet metrics (Phase 4)

### Added
- `backend/finance/comparison.py` — `align_return_series`, `correlation`, `beta`, `alpha`, `tracking_error`, `active_return`, `information_ratio`, `treynor_ratio`, `benchmark_summary`
- `backend/tests/test_finance_comparison.py` — alignment, correlation, beta, alpha, tracking error, active return, information ratio, Treynor, summary tests

### Changed
- `backend/finance/__init__.py` — export comparison helpers
- `docs/current-state.md`, `docs/architecture.md` — Phase 4 status; clarify `benchmarks.py` vs `comparison.py`

### Impact
- Pure finance only; no API/UI/DB. `finance/benchmarks.py` unchanged (performance chart rebasing).

## 2026-05-30 — FEAT: Core Metric Sheet performance metrics (Phase 3)

### Added
- `backend/finance/performance_stats.py` — `cumulative_return`, `cagr`, `best_return`, `worst_return`, `win_rate`, `average_return`, `period_summary`
- `backend/finance/risk_metrics.py` — `annualized_volatility`, `downside_deviation`, `sharpe_ratio`, `sortino_ratio`
- `backend/finance/drawdowns.py` — `drawdown_series`, `max_drawdown`, `longest_drawdown_days`, `calmar_ratio`
- `backend/finance/_return_inputs.py` — shared parsing for `DailyReturnPoint` / bare fractions
- Tests: `test_finance_performance_stats.py`, `test_finance_risk_metrics.py`, `test_finance_drawdowns.py`

### Changed
- `backend/finance/__init__.py` — export Phase 3 helpers
- `docs/current-state.md`, `docs/architecture.md`

### Impact
- Pure finance only; no API, UI, DB persistence, or benchmark-relative metrics (Phase 4).

## 2026-05-30 — FEAT: Finance return-series foundation (Phase 2)

### Added
- `backend/finance/returns.py` — framework-independent helpers: `period_return`, `daily_returns_from_values`, `daily_returns_from_twror_series`, `compound_return`, `chain_returns`, `resample_monthly_returns`, `resample_yearly_returns`; datatypes `ValuePoint`, `DailyReturnPoint`, `PeriodReturnPoint`.
- `backend/tests/test_finance_returns.py` — golden tests for period/daily/TWROR-derived returns, compounding, monthly/yearly resampling, and `None` handling.

### Changed
- `backend/finance/__init__.py` — export new return helpers.
- `docs/current-state.md`, `docs/architecture.md` — Phase 2 return module documented.

### Impact
- No API routes, frontend UI, DB migrations, or persisted derived metrics. Metrics layer (`performance_stats`, `risk_metrics`, etc.) not wired yet.

## 2026-05-30 — DOCS: Analytics documentation terminology cleanup (Phase 1B)

### Changed
- Replaced external package/report terminology (`QuantStats`, `tear sheet`, etc.) with app-owned terms: **Quantitative Statistics**, **Metric Sheet**, **performance metric sheet**, **analytics metrics** across `docs/architecture.md`, `docs/current-state.md`, `docs/api-design.md`, `docs/frontend-design.md`, and the Phase 1 changelog entry.

### Impact
- Documentation only. No code, API, or runtime behavior change.

## 2026-05-30 — DOCS: Quantitative Statistics / Metric Sheet architecture (Phase 1)

### Added
- `docs/architecture.md` — **Quantitative Statistics / Metric Sheet architecture**: subject levels (portfolio, asset, compare), TWROR-derived daily returns as primary technical input, separate XIRR/FIFO roles, planned `finance/` modules (`returns`, `performance_stats`, `risk_metrics`, `drawdowns`, `comparison`), `analytics/services` orchestration, proposed API routes, frontend surfaces, warning behavior, MVP on-query calculation (no persistence of derived metrics), deferred cache design.
- `docs/api-design.md` — **Proposed** analytics endpoints (`performance-metrics`, asset metrics, `compare`) with rough JSON shapes; marked not implemented.
- `docs/frontend-design.md` — Future Metric Sheet UI: Performance Quality cards, risk/return table, drawdown and periodic return tables, asset detail section, compare page; API-only values.
- `docs/current-state.md` — Analytics Metric Sheet planned; Phase 1 docs complete; no runtime change.

### Impact
- Documentation/design only. No migrations, models, API routes, `finance/` implementation, or frontend UI in this phase.

## 2026-05-29 — PERF: Dashboard summary skips unused timeseries

### Changed
- Dashboard `fetchDashboardSummary` now passes `include_timeseries=false` — KPI cards and XIRR do not need summary timeseries; charts continue to use `GET /portfolio/performance`.
- `api.js` — `fetchDashboardSummary(scopeParams, options)` supports `{ includeTimeseries: false }`; summary in-flight cache key includes `include_timeseries` so lightweight and full responses do not collide.

### Impact
- All-scope summary load drops from ~20s to ~0.1s on typical dev data (investigation); Dashboard initial load is no longer blocked on unused daily series computation.

## 2026-05-29 — FEAT: Transactions page column filters (portfolio / symbol / date)

### Added
- **Transactions filter bar** — filter the full transaction dataset (not just the visible page) by portfolio, symbol (searchable multi-select), and date (Earlier than / Later than / Between). Active filter chips + Clear filters; filters reset to page 1 and are preserved across pagination.
- `GET /api/v1/transactions` query params: `symbols` (comma-separated, case-insensitive), `date_from`, `date_to`, plus `date_after` / `date_before` aliases. Existing `asset_symbol` and scope params unchanged.
- `GET /api/v1/transactions/filter-options` — distinct portfolios / symbols / types / date bounds for the current scope.
- Frontend `TransactionFilterBar` component (+ CSS); `fetchTransactionFilterOptions` and `filters` arg on `fetchTransactions` in `api.js`.

### Changed
- `transactions/services.py` — `list_transactions` accepts `symbols` / `date_from` / `date_to` (applied before pagination); new `get_transaction_filter_options`.
- `transactions/views.py` — date format / range validation returns `400`; new `TransactionFilterOptionsView`; route registered in `api/urls.py`.

### Tests
- `backend/tests/test_transaction_filters_api.py` — symbol/date/portfolio filters, pagination ordering, `400` validation, MF scheme code, filter-options scoping.
- `frontend/src/pages/Transactions.test.jsx` — filter controls, per-filter API params, page reset, pagination preservation, clear, chips.

## 2026-05-28 — FIX-2: All Portfolios summary aggregation (mixed currency / MF)

### Fixed
- **`portfolio_scope=all` under-counted headline totals** when active portfolios mixed EUR stocks and INR mutual funds — stock EUR and MF INR were merged before FX alignment, then treated as one base currency
- All Portfolios `current_value` / `total_invested` / P/L fields now equal the sum of individual active portfolio summaries in the requested `display_currency`

### Changed
- `portfolios/summary_service.py` — `_build_all_active_portfolio_summary()` aggregates per-portfolio `_build_single_portfolio_summary()` results; single-portfolio path unchanged
- All-scope response `base_currency` set to `display_currency`; `fx_status` combined from child summaries; warnings prefixed with portfolio name

### Added
- `backend/tests/test_portfolio_summary_all_scope_aggregation.py` — mixed stock/MF, INR display, inactive exclusion, fx_status, monetary field sums

## 2026-05-28 — FIX-1: Dashboard display-currency flicker and stale API responses

### Fixed
- **Dashboard currency flicker** — `PortfolioProvider` no longer fires scoped API calls before `GET /settings` completes; `apiQuery` is `null` until `settingsLoaded`
- **Stale summary/performance overwrite** — Dashboard uses monotonic request IDs so older in-flight responses are ignored when `apiQuery` changes

### Changed
- `portfolioContext.jsx` — `settingsLoaded`, `selectedDisplayCurrency` starts `null`, optional `initialDisplayCurrency` for test harnesses with `disableFetch`
- `Dashboard.jsx` — waits for settings readiness; sequence guards on summary and performance effects
- `Layout.jsx` — display currency selector disabled until settings load

### Added
- Frontend tests: `portfolioContext.test.jsx`, stale-response and settings-delay cases in `Dashboard.test.jsx`, sidebar currency tests in `Layout.test.jsx`

## 2026-05-28 — SYNC-1: Incremental sync correctness and benchmark backfill parity

### Fixed
- **Benchmark sync** — same start-date rules as stock sync: warm cache → latest index date + 1; backfill when earliest non-MF transaction anchor predates first cached index row
- **Benchmark anchor** — uses `earliest_stock_transaction_date()` (excludes mutual fund buys) instead of global `earliest_transaction_date()`

### Added
- `earliest_stock_transaction_date()` in `market_data/services/symbols.py`
- Benchmark warm-cache, backfill, anchor, and combined `sync_all_market_data` incremental tests in `test_market_data_sync.py`

### Changed
- Docs: `workflows.md`, `current-state.md`, `database.md`, `api-design.md` — refresh / incremental sync behavior

### Notes
- Stock, FX, and MF NAV sync behavior unchanged in this phase
- MF scheme codes remain excluded from yfinance stock sync

## 2026-05-28 — Dashboard KPI overflow for large INR amounts

### Fixed
- **MetricCard / CurrencyValue** — fluid `clamp()` typography, `nowrap`, grid `min-width: 0`, and ellipsis fallback so large INR KPI values stay inside card bounds
- **CurrencyValue** — `title` attribute carries full formatted amount for hover when truncated

### Added
- Frontend tests: `ui.test.jsx`, `Dashboard.test.jsx`

## 2026-05-28 — Stock price sync excludes mutual fund scheme codes

### Fixed
- **`make refresh` / `sync_market_data`** — stock/yfinance price sync no longer collects AMFI scheme codes from mutual fund transactions; MF NAV sync continues to handle those codes separately via AMFI
- **`stock_transaction_symbols()`** in `market_data/services/symbols.py` — excludes transactions with `MutualFundTransactionDetail` and symbols registered as `AssetType.MUTUAL_FUND`

### Added
- Regression tests in `test_market_data_sync.py` — stock symbol collection, stock sync, and combined `sync_all_market_data` routing

### Notes
- Fixes yfinance 404 / “possibly delisted” warnings for numeric MF scheme codes (e.g. 119062) during `make refresh`
- Benchmark, FX, and MF NAV sync unchanged

## 2026-05-27 — LAN / iPad access via Vite (port 5173)

### Changed
- **Vite** — `server.host: true` in `vite.config.js`; `make frontend` / `make dev` pass `--host 0.0.0.0`
- **Docs** — iPad/home LAN section in `workflows.md`, `README.md`; `.env.example` notes for empty `VITE_API_BASE_URL`

### Notes
- iPad opens `http://<mac-lan-ip>:5173` only; `/api` proxied to Django on the Mac (no CORS or `ALLOWED_HOSTS` LAN IP required for that path)

## 2026-05-27 — Makefile: `make refresh` includes mutual fund NAVs

### Changed
- **Makefile** — removed duplicate sync targets that bypassed `.env` / `setup-backend`; `make refresh` and `make sync-market-data` run `sync_market_data` (stocks, benchmarks, FX, mutual fund NAVs) with clear echo output
- **`make sync-mutual-fund-navs`** — runs `manage.py sync_mutual_fund_navs`
- **`sync_market_data` command** — WARNING styling when `mutual_funds_failed > 0` (failures visible in stdout)
- Docs: `workflows.md`, `README.md`, `current-state.md`

### Notes
- Backend `sync_all_market_data()` already included MF NAV sync by default (MF-9); Makefile now documents and routes through that single command
- Opt out: `python manage.py sync_market_data --skip-mutual-funds`

## 2026-05-27 — MF-11b: Mutual fund CSV import guidance (frontend)

### Added
- **Transactions** expandable “Supported CSV formats” panel — stock vs mutual fund column lists, import rules, inline MF example
- **Download sample MF CSV** — client-generated template (`csvImportGuidance.js`); no backend or NAV logic
- Frontend tests: `Transactions.test.jsx` (guidance, download button, import button unchanged), `csvImportGuidance.test.js`

### Changed
- Transactions import info banner — stock split/SWAP note retained; MF format details moved to expandable panel
- Docs: `current-state.md`, `frontend-design.md`, `page-layouts.md`

### Notes
- Backend MF CSV import unchanged (MF-11a)
- No stock sample CSV download in this phase

## 2026-05-27 — MF-11a: Mutual fund CSV import (backend)

### Added
- **Mutual fund CSV import** via existing `POST /api/v1/transactions/import-csv`
- Header detection: `Scheme Code` + `Folio Number` → MF format; stock CSV unchanged
- `parse_mutual_fund_transaction_csv`, `parse_import_csv` in `transactions/csv_import.py`
- MF rows routed to `create_mutual_fund_transaction()` (Asset, Profile, Folio, detail upsert)
- Cached DB NAV verification on import — no external AMFI/MFAPI calls
- `backend/tests/test_mutual_fund_csv_import.py` — 16 tests

### Changed
- `import_transactions_from_csv` branches on detected CSV format (stock vs MF)
- Docs: `api-design.md`, `mutual-funds.md`, `current-state.md`

### Notes
- Mixed stock + MF columns in one file → header validation error (not supported in MF-11a)
- Stock CSV import behavior and tests unchanged
- No frontend changes in this phase

## 2026-05-27 — Portfolio CRUD UI + bulk transaction assignment

### Added
- **Settings → Portfolios:** create, edit (name/description/base currency), deactivate non-default portfolios; max 5 active enforced in UI; backend validation errors displayed
- **`portfolioContext.reloadPortfolios()`** and **`selectPortfolio()`** — sidebar Portfolio View updates after portfolio changes; new portfolio auto-selected after create
- **Transactions bulk assign:** row checkboxes, select-all on page, toolbar to move selected transactions to a real portfolio via sequential full PUT (`buildTransactionUpdatePayload`)
- `frontend/src/utils/transactionPayload.js` — shared PUT payload builders for stock, MF, and STOCK_SPLIT reassignment
- Frontend tests: Settings portfolio CRUD, Layout selector refresh, Transactions bulk assign (including partial failure and split fields)

### Changed
- `Transactions.jsx` — selection state, bulk toolbar, assign flow
- `Settings.jsx` — Portfolios section with `PortfolioManagement` component
- Docs: `current-state.md`, `frontend-design.md`, `page-layouts.md`

### Notes
- **All Portfolios** remains virtual; cannot receive transactions directly
- Default Portfolio cannot be deactivated from UI
- No backend changes; no new bulk API endpoint

## 2026-05-27 — FX sync backfill for coverage gaps

### Fixed
- `sync_fx_rates` / `sync_fx_pair` backfill from earliest required valuation date when cached `FXRate` rows start later (GOOG USD prices from 2022-05-02 with USD→EUR FX from 2022-12-20 only → summary `portfolio_value: null`, `fx_status: fx_unavailable`)
- `earliest_required_fx_date` derives required start from transaction dates, cached stock price dates, and implied currency pairs (price→holding, price→display, holding→display)
- Incremental FX sync (latest cached date + 1) preserved when cache already covers from required inception

### Added
- `resolve_fx_sync_start_date`, `_earliest_fx_date`, `earliest_required_fx_date` in `fx/services.py`
- Backfill and summary integration tests in `test_fx_sync.py`

### Notes
- Read APIs unchanged (DB-only); 7-day FX fill on reads preserved; no live transaction data modified
- Backend: 393 pytest tests pass

## 2026-05-27 — Stock price sync backfill for coverage gaps

### Fixed
- `sync_prices` / `sync_one_stock_symbol` backfills from earliest transaction date when cached `HistoricalPrice` starts after first transaction (GOOG BUY 2022-05-02 with prices from 2022-12-23 only → summary `portfolio_value: 0` while `invested_amount > 0`)
- Incremental sync (latest cached date + 1) preserved when cache already covers from transaction inception

### Added
- `resolve_stock_sync_start_date` in `market_data/services/price_sync.py`
- Backfill regression tests in `test_market_data_sync.py`

### Notes
- Read APIs unchanged (DB-only); no live transaction data modified
- Backend: 385 pytest tests pass

## 2026-05-27 — Fix split-adjusted value history valuation

### Fixed
- Summary and performance value timeseries now consistently pair cached split-adjusted historical prices with split-adjusted transaction quantities (`build_split_adjusted_lot_snapshots` in `finance/fifo.py`)
- Prevents GOOG-style dashboards showing ~95% artificial loss on split dates when yfinance-adjusted prices were multiplied by unadjusted share counts
- Performance `value`, `cumulative_return`, and `twror` inherit the corrected value series; `STOCK_SPLIT` rows remain excluded from external cash-flow calculations

### Added
- `backend/tests/test_stock_split_valuation_api.py` — GOOG-like regression tests (summary, performance metrics, symbol/date isolation, missing price/FX, no yfinance on reads)
- Domain test for `build_split_adjusted_lot_snapshots` in `test_finance_domain.py`

### Changed
- `portfolios/summary_service.py` — uses shared finance timeline builder; holdings path relies on FIFO internal split adjustment (no double-apply)

### Notes
- No live transaction data modified; adjustment is in-memory at read time only
- No schema migrations; response shapes unchanged

## 2026-05-27 — Data safety guardrails

### Added
- `docs/data-safety.md` — incident summary, safe debugging, backup/restore, forbidden commands
- `make backup-db` — timestamped `pg_dump` to `backups/` via `kpulla6_postgres`
- `make db-safety-check` — DB name, transaction/portfolio/historical_price counts, last 5 transactions

### Changed
- `AGENTS.md` — mandatory data-safety rules for agents (no live DB deletes, backup before destructive ops, SQLite for ad-hoc work)
- `docs/workflows.md` — backup/safety-check bookends for data-sensitive phases; links to data-safety doc
- `.gitignore` — ignore `backups/` (local SQL dumps)

### Notes
- No application code, models, migrations, or API behavior changed
- Root cause of May 2026 transaction loss: ad-hoc script `Transaction.objects.filter(portfolio=…).delete()` on dev Postgres during split debugging

## 2026-05-26 — Phase MF-10: Live mutual fund NAV provider

### Added
- `market_data/providers/amfi_nav_parser.py` — MFAPI JSON/date/NAV parsing (Decimal, INR)
- Live `AmfiNavProvider` via MFAPI (`https://api.mfapi.in`) with injectable `http_get`
- `backend/tests/test_amfi_nav_provider.py` — 20 tests (parser, provider, sync, API; mocked HTTP)

### Changed
- `market_data/providers/mutual_fund_nav_provider.py` — live fetch for latest NAV and date-range history
- Docs: `api-design.md`, `database.md`, `current-state.md`, `decisions.md`, `mutual-funds.md`

### Notes
- External NAV calls only in sync paths; read APIs unchanged (DB-only)
- No new Python dependencies (stdlib `urllib`)
- All tests mock HTTP — no real network in CI
- Backend: 371 pytest tests pass

## 2026-05-26 — Phase MF-9: Mutual fund NAV refresh API and combined sync

### Added
- `POST /api/v1/nav/refresh` — manual MF NAV sync; optional `scheme_codes`; synced/skipped/failed response
- `market_data/nav_refresh.py` — refresh payload helpers
- `backend/tests/test_mutual_fund_nav_refresh_api.py` — 11 tests

### Changed
- `market_data/services/market_data_sync.py` — includes `sync_mutual_fund_navs` by default
- `POST /api/v1/portfolio/force-sync` — extended response with MF counts and warnings
- `sync_market_data` command — `--skip-mutual-funds`; output includes MF stats
- `Makefile` `refresh` / `sync-market-data` — uses combined `sync_market_data` command
- Settings page — Data & sync explainer (no new external calls from frontend)
- Docs: `api-design.md`, `database.md`, `current-state.md`, `decisions.md`, `mutual-funds.md`

### Notes
- Stock `POST /api/v1/prices/refresh` unchanged
- Read APIs still DB-only for NAV
- `AmfiNavProvider` placeholder unchanged
- Backend: 351 pytest tests pass

## 2026-05-26 — Phase MF-8: Frontend mutual fund transactions

### Added
- `TransactionModal` asset type selector — Stock (default) and Mutual fund modes
- MF form fields mapped to backend API (`scheme_code`, `folio_number`, `nav_date`, etc.)
- Transactions table: scheme/folio display, units/NAV columns, calm NAV verification badge
- `frontend/src/utils/transactionDisplay.js` — display helpers (no finance math)
- Frontend tests: MF create/edit/display in `TransactionModal.test.jsx`, `Transactions.test.jsx`, `transactionDisplay.test.js`

### Changed
- `frontend/src/pages/Assets.jsx` — safe MF holding labels (scheme name, folio, `holding_key`)
- `frontend/src/api.js` — field-level validation error messages from backend
- `StatusBadge` — `verified` / `nav_warning` variants for NAV status
- Docs: `frontend-design.md`, `current-state.md`, `mutual-funds.md`

### Notes
- Stock transaction form and CSV import unchanged
- No frontend external NAV/AMFI calls
- Backend contracts unchanged

## 2026-05-26 — Phase MF-7: Mutual fund classification

### Added
- `finance/mutual_fund_classification.py` — conservative metadata inference
- `market_data/mutual_fund_classification_bridge.py` — Asset/profile bridge + upsert helper
- MF holdings/asset detail fields: `primary_asset_class`, `classification_source`, `classification_notes`
- `PrimaryAssetClass.UNKNOWN` choice on `Asset`
- `backend/tests/test_mutual_fund_classification.py` — 16 tests

### Changed
- `portfolios/holdings_service.py`, `holdings_views.py` — MF classification on read
- `transactions/mutual_fund_services.py` — infer class on create/update when not explicit
- Docs: `api-design.md`, `database.md`, `current-state.md`, `decisions.md`

### Notes
- Hybrid → HYBRID, not EQUITY; stock rows unchanged
- No external API in classification
- Backend: 340 pytest tests pass

## 2026-05-26 — Phase MF-6: Mutual fund NAV validation

### Added
- `transactions/mf_nav_validation.py` — `verify_mutual_fund_nav_inputs` (cached NAV + market value tolerances)
- `NavVerificationStatus`: `VERIFIED`, `NAV_MISSING`, `NAV_MISMATCH`, `VALUE_MISMATCH`, `WARNING_ACCEPTED`
- `backend/tests/test_mutual_fund_nav_validation.py` — 11 tests

### Changed
- `transactions/mutual_fund_services.py` — MF-6 validation on create/update (replaces ratio-based MF-3 check)
- `backend/tests/test_mutual_fund_transactions_api.py` — `VERIFIED` expectation
- Docs: `api-design.md`, `database.md`, `current-state.md`, `decisions.md`

### Notes
- Mismatch saves with status/message; structural errors still 400
- No external NAV provider on transaction write/read
- Backend: 324 pytest tests pass

## 2026-05-26 — Phase MF-5: Mutual fund summary and performance

### Added
- Summary and performance include MF positions (cached NAV, forward-fill, INR FX conversion)
- `finance/mutual_fund_cashflows.py` — `merge_portfolio_xirr` with MF `investment_date` / `paid_value`
- `market_data/nav_repository.py` — `list_mutual_fund_navs_for_schemes`, `latest_mutual_fund_navs_by_scheme`
- `backend/tests/test_mutual_fund_summary_performance_api.py` — 14 tests

### Changed
- `portfolios/summary_service.py` — MF holdings, timeseries merge, combined XIRR
- `portfolios/performance_service.py` — MF external flows and timeseries via `transactions_by_mf_holding`
- Docs: `api-design.md`, `database.md`, `current-state.md`, `decisions.md`

### Notes
- Stock summary/performance unchanged when no MF transactions
- No external NAV provider on summary/performance reads
- Backend: 313 pytest tests pass; frontend: 79 vitest tests pass

## 2026-05-26 — Phase MF-4: Mutual fund holdings and asset detail

### Added
- `GET /api/v1/portfolio/holdings` — MF rows grouped by `scheme_code` + `folio_number`; `holding_key`, `latest_nav`, `nav_status`, `units`
- `GET /api/v1/portfolio/assets/{scheme_code}?folio_number=...` — folio-scoped MF asset detail with MF transaction fields
- `backend/tests/test_mutual_fund_holdings_api.py` — 14 tests

### Changed
- `portfolios/holdings_service.py` — separate stock vs MF paths; DB-only NAV via `latest_nav_for_asset`
- `portfolios/holdings_views.py` — `folio_number` query param; MF response fields on asset detail
- Docs: `api-design.md`, `database.md`, `current-state.md`, `decisions.md`

### Notes
- Stock holdings and asset detail behavior unchanged; existing holdings/summary/performance tests pass
- No external NAV provider on holdings/asset detail reads
- Summary/performance MF integration deferred to MF-5
- Backend: 299 pytest tests pass

## 2026-05-26 — Phase MF-3: Mutual fund transaction API

### Added
- `POST/PUT /api/v1/transactions` with `asset_type=MUTUAL_FUND` — BUY/SELL, scheme/folio/dual dates/NAV/units/values
- `transactions/mutual_fund_services.py` — validation, Asset/Profile/Folio upsert, atomic create/update
- `MutualFundTransactionWriteSerializer`; MF fields on `TransactionSerializer` read output
- `backend/tests/test_mutual_fund_transactions_api.py` — 16 tests

### Changed
- `transactions/views.py` — route MF vs stock create/update
- `transactions/services.py` — prefetch MF detail on list/get
- Docs: `api-design.md`, `database.md`, `current-state.md`, `decisions.md`

### Notes
- Stock transaction API unchanged for non-MF requests
- No external NAV provider on transaction read/write; optional cached NAV status only
- Holdings/summary/performance/frontend not wired
- Backend: 285 pytest tests pass; frontend: 79 vitest tests pass

## 2026-05-26 — Phase MF-2: Mutual fund NAV cache and sync foundation

### Added
- `market_data/providers/mutual_fund_nav_provider.py` — `NavPoint`, `MutualFundNavProvider`, `AmfiNavProvider` (placeholder)
- `market_data/services/mutual_fund_nav_sync.py` — incremental idempotent NAV upsert to `HistoricalPrice`
- `market_data/nav_lookup.py` — `latest_nav_for_asset`, `NavLookupResult` (DB only)
- `market_data/nav_repository.py` — `list_mutual_fund_navs_in_range` (DB only)
- Management command: `sync_mutual_fund_navs` with optional `--scheme-code`
- `backend/tests/test_mutual_fund_nav_sync.py` — 12 tests

### Notes
- No read API or holdings/summary/performance integration; no frontend changes
- `AmfiNavProvider` does not call live AMFI in MF-2; inject mock/real provider at sync time
- `POST /api/v1/nav/refresh` and `sync_market_data` MF wiring deferred
- Backend: 269 pytest tests pass; frontend: 79 vitest tests pass

## 2026-05-26 — Phase MF-1: Mutual fund schema foundation

### Added
- `market_data.models.Asset`, `MutualFundProfile`, `PrimaryAssetClass`; `AssetType.MUTUAL_FUND`
- `transactions.models.Folio`, `MutualFundTransactionDetail`, `NavVerificationStatus`
- Nullable `HistoricalPrice.asset` FK (non-breaking)
- Migrations: `market_data/0002_mutual_fund_schema`, `transactions/0002_mutual_fund_schema`
- `backend/tests/test_models_mutual_funds.py` — 12 model tests

### Changed
- `HistoricalPrice.asset_type` max_length 8 → 16 (supports `MUTUAL_FUND`)
- `docs/database.md`, `docs/current-state.md`, `docs/decisions.md`

### Notes
- Stock, FX, benchmark, holdings, summary, performance, and transaction APIs unchanged
- MF transaction detail not wired to CRUD APIs yet (MF-3)
- Backend: 257 pytest tests pass; frontend: 79 vitest tests pass

## 2026-05-26 — Phase MF-0: Indian Mutual Funds design documentation

### Added
- `docs/mutual-funds.md` — purpose, MVP scope, target data model (`Asset`, `MutualFundProfile`, folio strategy, transaction details), NAV cache/validation/sync, holdings grouping, summary/performance impact, classification, frontend impact, phased plan MF-1–MF-9, risks, open questions

### Changed
- `docs/database.md` — planned MF tables and `HistoricalPrice`/`AssetType` extensions (marked not implemented)
- `docs/api-design.md` — planned MF transaction, holdings, sync, and read-path contracts (marked not implemented)
- `docs/current-state.md` — Planned / MF-0 section

### Notes
- Documentation only; no backend runtime code, migrations, frontend, or test changes
- Preserves existing stock, FX, benchmark, holdings, summary, performance, and transaction behavior
- Read APIs must use cached DB NAV/prices only — no external AMFI calls on dashboard/holdings reads

## 2026-05-25 — Page layout governance documentation

### Added
- `docs/page-layouts.md` — source of truth for per-page layout; change process and ownership table
- Cross-reference from `docs/frontend-design.md`

### Notes
- Documentation only; no app code changes

## 2026-05-25 — Dev stack stop commands

### Added
- Makefile targets: `ports`, `stop-backend`, `stop-frontend`, `stop-dev`, `stop-all`, `clean-dev`
- Configurable `BACKEND_PORT` and `FRONTEND_PORT` for dev server start/stop

### Notes
- `stop-all` uses `docker compose stop postgres` (no volume removal)
- Documented in `docs/workflows.md` and `README.md`

## 2026-05-25 — Phase 8B: Legacy CSS alias removal

### Changed
- **Tokens:** removed legacy alias block from `frontend/src/index.css`; canonical Institutional Slate tokens only
- **Docs:** frontend design migration marked complete

### Notes
- No app behavior changes; `chartTheme.js` unchanged (Recharts hex mirrors); `DataTable` still deferred

## 2026-05-25 — Phase 7B: Frontend cleanup

### Changed
- **TransactionModal:** canonical Institutional Slate tokens, Slate overlay, modal-local form styles, error styling, `Button` for Cancel/Save
- **Shared styles:** transaction type badges (`.ui-txn-type`) in `ui.css`; used on Transactions and Asset Detail
- **Dead CSS removed:** unused globals from `index.css`; unused `.needs-review-banner` from modal CSS

### Notes
- Legacy alias block in `index.css` retained for Phase 8; `DataTable` still deferred

## 2026-05-25 — Phase 6: Transactions page polish

### Changed
- **Transactions:** `PageHeader` with record count and Add/Import actions; `LoadingState` / `ErrorState` / `EmptyState`; CSV import feedback via `WarningBanner`
- Table uses Institutional Slate styling, type badges (BUY/SELL/DIVIDEND/STOCK_SPLIT), `CurrencyValue`, and `Button` edit/delete controls

### Notes
- Transaction CRUD, CSV import API, pagination params, modal, and line-total display semantics unchanged; `DataTable` still deferred

## 2026-05-25 — Phase 5B: Assets allocation chart and closed holdings polish

### Changed
- **Assets:** allocation pie chart wrapped in `ChartCard` with Institutional Slate colors from `chartTheme.js`, Dashboard-aligned tooltip/legend, and responsive table-primary layout (~35% chart width on desktop)
- Previous holdings section uses `SectionCard` + `Button` toggle; legacy chart CSS and neon pie colors removed

### Notes
- Holdings fetch, sorting, row navigation, chart data filtering, and closed-holdings logic unchanged; `DataTable` still deferred

## 2026-05-25 — Phase 5A: Assets page structure and holdings table

### Changed
- **Assets:** `PageHeader` with portfolio/currency subtitle; `LoadingState` / `ErrorState`; FX warning via `WarningBanner`
- Holdings table uses Institutional Slate styling, `StatusBadge`, `CurrencyValue`, `PercentValue`; avg cost from `avg_cost_per_share` when present
- Empty holdings and chart unavailable states use `EmptyState`; closed-holdings toggle restyled

### Notes
- `fetchHoldings`, sorting, row navigation, and allocation chart data unchanged; chart color polish deferred to Phase 5B

## 2026-05-25 — Phase 4: Asset Detail Metric Sheet migration

### Changed
- **Asset Detail:** Metric Sheet layout with `PageHeader` (symbol title, Assets breadcrumb, portfolio/currency subtitle), hero KPI row (`MetricCard` + `CurrencyValue` / `PercentValue`), grouped `SectionCard` sections (position, market, data quality, transactions), `StatusBadge` for holding/price/FX status, `WarningBanner` for API warnings, `LoadingState` / `ErrorState` / `EmptyState`
- Transaction table styling improved with type badges and right-aligned numeric columns

### Notes
- `fetchAssetDetails` and API params unchanged; no client-side finance calculations
- Assets list and other pages unchanged; `DataTable` deferred

## 2026-05-25 — Phase 3B: Dashboard chart container and theme

### Added
- `ChartCard` and `SegmentedControl` UI primitives with tests
- `frontend/src/components/charts/chartTheme.js` — centralized Recharts colors and styles

### Changed
- **Dashboard:** performance chart wrapped in `ChartCard`; metric and range controls use `SegmentedControl`; benchmark select styled via CSS class
- Chart empty state uses `EmptyState`; loading/benchmark warnings remain `WarningBanner`
- Recharts grid, axis, tooltip, and series colors use Institutional Slate palette
- “Invested vs Current” bar chart demoted to compact secondary `ChartCard`

### Notes
- API fetch params, `mergeComparisonSeries`, and chart data semantics unchanged
- Assets, other pages unchanged

## 2026-05-25 — Phase 3A: Dashboard structure, states, and KPI cards

### Changed
- **Dashboard:** `PageHeader`, `MetricCard`, `CurrencyValue`, `PercentValue`, `LoadingState`, `ErrorState`, and `WarningBanner` replace raw header, KPI cards, loading/error, and FX/chart warnings
- KPI row shows Current Value (hero), Total Invested, Total P/L, XIRR, plus Realized/Unrealized P/L when present in summary API
- Chart controls, Recharts logic, and Invested vs Current bar chart unchanged

### Notes
- No API, fetch params, or finance calculation changes
- Chart theme, SegmentedControl, and ChartCard deferred to Phase 3B+

## 2026-05-25 — Phase 2: App shell / sidebar polish

### Changed
- **Layout:** Institutional Slate sidebar with brand area, navigation, bottom context controls, and cached-data footer note
- Active nav uses accent left border and raised surface (replaces inverted high-contrast style)
- Portfolio and display currency selectors restyled with focus rings and custom chevron; logic unchanged
- Main content area uses consistent padding and surface separation from sidebar
- Responsive stacking below 900px; compact nav grid on very narrow screens
- Portfolio load warning uses `WarningBanner` primitive

### Notes
- Routing, `portfolioContext`, API calls, and page content unchanged
- Dashboard, Assets, AssetDetail, Transactions page markup unchanged

## 2026-05-25 — Phase 1: UI primitive components

### Added
- Reusable UI primitives in `frontend/src/components/ui/`: Button, PageHeader, MetricCard, SectionCard, StatusBadge, WarningBanner, EmptyState, LoadingState, ErrorState, CurrencyValue, PercentValue
- Shared `ui.css` styled with Institutional Slate tokens; barrel export via `index.js`
- Vitest/RTL tests for UI primitives (`ui.test.jsx`)

### Changed
- **Settings page:** uses PageHeader, SectionCard, Button, LoadingState, ErrorState, and WarningBanner (form behavior and API calls unchanged)
- `docs/frontend-design.md` — component catalog updated with implemented APIs

### Notes
- Dashboard, Assets, AssetDetail, and Transactions unchanged
- No finance calculations, API, or backend changes

## 2026-05-19 — Assets page fixes (post Phase 11)

### Fixed
- **Holdings price lookup:** converts cached `HistoricalPrice` from stored currency (e.g. USD) into each asset's transaction currency via cached FX — same pattern as summary service
- **`fx_status` false positive:** no longer reports `fx_unavailable` when `display_currency` matches holding currency but prices are stored in USD
- **Oversold false positives:** `detect_oversell` now passes `STOCK_SPLIT` rows into split adjustment (ANET/TSLA-style 1:N splits no longer flagged)
- **Assets UI:** allocation chart empty state when all `current_value` are zero; chart CSS; price-missing message (no polling/"fetching"); FX warning only when display currency differs from holdings

### Tests
- Backend: USD→EUR price conversion, FX ok with matching display currency, split-adjusted oversell, price missing without FX
- Frontend: chart render/empty state, FX warning gating, oversold row, price-missing wording

## 2026-05-19 — Phase 11: React frontend integration

### Added
- Full React UI ported from KPulla5 patterns: Layout, Dashboard, Assets, AssetDetail, Transactions, Settings
- `portfolioContext.jsx`, centralized `api.js` with `VITE_API_BASE_URL`
- Vitest/RTL tests (API client, layout, dashboard, assets, transactions, settings)
- `make test-frontend`; `make test` runs backend + frontend

### Notes
- No finance, FX, or benchmark calculations in the browser
- Dev: Vite proxies `/api` to Django when `VITE_API_BASE_URL` is empty

## 2026-05-19 — Phase 10: Portfolio performance API

### Added
- `GET /api/v1/portfolio/performance` — `value`, `cumulative_return`, `twror`, `range`, optional benchmark
- `portfolios/performance_service.py`, `portfolios/performance_views.py`, `portfolios/dates.py`
- `finance/performance_range.py`, `finance/benchmarks.py`
- `market_data/price_repository.list_index_prices_in_range`

### Tests
- `backend/tests/test_portfolio_performance_api.py`
- `backend/tests/test_performance_range.py`, `backend/tests/test_benchmarks_finance.py`

### Not included
- Frontend performance charts, automatic background scheduler

## 2026-05-19 — Phase 9: Portfolio summary API

### Added
- `GET /api/v1/portfolio/summary` — FIFO metrics, XIRR, optional timeseries, display currency
- `portfolios/summary_service.py`, `portfolios/summary_views.py`
- `market_data/price_repository.py` — bulk historical / latest price queries
- `fx/lookup.convert_amount_with_fill`, `load_fx_rate_maps`, `fx_lookup_from_maps`
- `finance/xirr.calculate_portfolio_xirr` — multi-asset portfolio XIRR

### Tests
- `backend/tests/test_portfolio_summary_api.py` (28 cases)

### Not included
- Performance/TWROR endpoint, benchmark overlay, frontend, auto-sync on read

## 2026-05-19 — Phase 8: Historical prices, FX cache, benchmark sync

### Added
- `POST /api/v1/prices/refresh`, `POST /api/v1/portfolio/force-sync`, `GET /api/v1/benchmarks/indices`
- `market_data/services/` (`price_sync`, `benchmark_sync`, `market_data_sync`)
- `market_data/providers/yfinance_provider.py` (mockable)
- `fx/lookup.py`, `fx/services.py`, `fx/providers/yfinance_fx.py`
- Commands: `sync_prices`, `sync_benchmarks`, `sync_fx_rates`, `sync_market_data`
- Makefile: `sync-prices`, `sync-benchmarks`, `sync-fx`, `sync-market-data`
- Dependencies: `yfinance`, `pandas`

### Tests
- `backend/tests/test_market_data_sync.py`, `backend/tests/test_fx_sync.py`

### Notes
- Manual API sync is synchronous (no Celery/RQ)
- Holdings/summary reads still do not call external market-data APIs

## 2026-05-19 — Phase 7: Holdings and asset detail APIs

### Added
- `GET /api/v1/portfolio/holdings` — FIFO metrics, XIRR, price_status, holding_status, oversell warnings
- `GET /api/v1/portfolio/assets/{asset_symbol}` — per-asset FIFO metrics + transaction history
- `portfolios/holdings_service.py`, `portfolios/holdings_views.py`, `market_data/price_lookup.py`, `finance/oversell.py`

### Tests
- `backend/tests/test_holdings_api.py` (30 cases)

### Not included
- Summary/performance APIs, price/FX sync, frontend

## 2026-05-19 — Phase 6: Finance domain layer

### Added
- `backend/finance/` — `types`, `splits`, `fifo`, `xirr`, `twror` (framework-independent)
- `transactions/finance_adapter.py` — Django Transaction → finance DTO
- Dependency: `pyxirr`

### Tests
- `backend/tests/test_finance_domain.py` — FIFO, splits, XIRR, TWROR
- `backend/tests/test_finance_adapter.py`

### Not included
- Holdings/summary/performance APIs, sync, frontend

## 2026-05-19 — Phase 5 assumptions closed (pre–Phase 6)

### Docs
- `docs/api-design.md` — Phase 5 closed assumptions table (direct `STOCK_SPLIT`, `SWAP`, currency, 404, UTF-8/MIME)
- `docs/current-state.md` — Phase 5 marked closed for Phase 6
- `docs/database.md` — split `currency` note

### Tests
- `test_csv_import_api.py` — direct split EUR/`quantity`/`price_per_share`; currency in `Price/Share` rejected; import `portfolio_id` 404 shape

## 2026-05-19 — Phase 5: CSV import and stock splits

### Added
- `POST /api/v1/transactions/import-csv` — multipart upload, optional `portfolio_id`, all-or-nothing import
- `transactions/csv_import.py` — CSV parsing, SWAP→`STOCK_SPLIT`, direct `STOCK_SPLIT` rows
- `import_transactions_from_csv` in `transactions/services.py` (atomic DB transaction)

### Tests
- `backend/tests/test_csv_import_api.py` — import success/validation, SWAP pairs, all-or-nothing

### Docs updated
- `docs/api-design.md`, `docs/architecture.md`, `docs/current-state.md`, `docs/database.md`

### Not included
- Holdings/summary/performance, XIRR/TWROR, price/FX/benchmark sync, frontend

## 2026-05-19 — Phase 4 contracts documented and tested

### Added
- Explicit Phase 4 behavioral contracts in `docs/api-design.md` and `docs/current-state.md`
- Tests: PUT preserves portfolio when `portfolio_id` omitted; transaction hard delete vs portfolio soft delete

### Docs updated
- `docs/database.md` — split fields; hard vs soft DELETE semantics

## 2026-05-19 — Phase 4: Transaction CRUD APIs

### Added
- `GET/POST /api/v1/transactions` — pagination, portfolio scope, asset filter
- `PUT/DELETE /api/v1/transactions/{id}`
- `portfolios/scope.py` — portfolio scope resolution
- `transactions/services.py`, serializers, views

### Tests
- `backend/tests/test_transactions_api.py`

### Docs updated
- `docs/api-design.md`, `docs/architecture.md`, `docs/current-state.md`

### Not included
- CSV import, market price validation, sync, analytics, frontend

## 2026-05-19 — Phase 3: Settings and Portfolios APIs

### Added
- `GET/PUT /api/v1/settings` — singleton AppSettings, display currency validation
- `GET/POST/PUT/DELETE /api/v1/portfolios` — active list, create, update, soft deactivate
- `portfolios/services.py`, `settings_app/services.py` with DRF serializers/views

### Tests
- `backend/tests/test_settings_api.py`
- `backend/tests/test_portfolios_api.py`

### Docs updated
- `docs/api-design.md`, `docs/architecture.md`, `docs/current-state.md`

### Not included
- Transactions, analytics, sync, frontend

## 2026-05-19 — Phase 2: Django models, migrations, seed

### Added
- Models: `Portfolio`, `Transaction`, `HistoricalPrice`, `FXRate`, `BenchmarkIndexConfig`, `AppSettings`
- Initial migrations per app (`0001_initial.py`)
- `manage.py seed_initial_data` — Default Portfolio, AppSettings (`pk=1`), five benchmark indices
- `make seed`, `make bootstrap` (db + migrate + seed)
- `portfolios/constants.py` — default/virtual portfolio names

### Tests
- `backend/tests/test_models_phase2.py` — seed idempotency, uniqueness, portfolio FK, virtual portfolio guard

### Docs updated
- `docs/database.md`, `docs/architecture.md`, `docs/current-state.md`

### Not included
- REST APIs, finance calculations, sync workers, frontend features

## 2026-05-19 — Initial foundation (Django + DRF + React + Docker PostgreSQL)

### Added
- KPulla6 project structure separate from KPulla5
- `docker-compose.yml` — PostgreSQL 16 (`postgres` service)
- `Makefile` — `db`, `db-stop`, `db-logs`, `db-shell`, `backend`, `frontend`, `migrate`, `test`, `dev`
- Django project (`backend/config/`) with DRF
- Django apps: `portfolios`, `transactions`, `market_data`, `fx`, `analytics`, `settings_app`
- `backend/finance/` package placeholder for framework-independent logic
- `GET /api/v1/health` endpoint
- `.env.example` for PostgreSQL and Django settings
- React + Vite frontend scaffold with API proxy and health check UI
- `AGENTS.md` and docs adapted from KPulla5 for the new stack

### Tests
- Backend: `backend/tests/test_health.py`
- Frontend: `frontend/src/App.test.jsx`

### Docs updated
- `docs/current-state.md`, `docs/architecture.md`, `docs/api-design.md`, `docs/database.md`
- `docs/workflows.md`, `docs/decisions.md`, `docs/migration-readiness.md`, `docs/project-summary.md`

### Not included (by design)
- Business logic port (transactions, portfolios, analytics, sync)
- SQLAlchemy / FastAPI code copy
- Production secrets or data migration from KPulla5 SQLite
