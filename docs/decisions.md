# Architecture Decisions — KPulla6

## 2026-06-24 — CASH-UNIFY-2: FD portfolio derived from bank account

- **Decision:** New fixed deposits must belong to the same portfolio as their linked bank account. `POST /fixed-deposits` derives `portfolio_id` from `bank_account.portfolio`; client-supplied portfolio must match or be omitted.
- **Unassigned/ambiguous bank accounts:** FD create blocked until user assigns portfolio in Bank Accounts settings.
- **Legacy data:** Existing FD rows with portfolio ≠ bank account portfolio are not auto-rewritten; API returns `portfolio_mismatch_warning`.
- **Deferred:** Cash page UI (CASH-UNIFY-3); broker-bank transfers (CASH-UNIFY-5).

## 2026-06-24 — CASH-UNIFY-1: Bank account portfolio ownership + cash overview API

- **Schema:** nullable `BankAccount.portfolio` FK (`SET_NULL`); user/active portfolio validation in model `clean()`.
- **Inference:** `infer_bank_account_portfolios` command — dry-run default; unambiguous signals from `FixedDeposit.portfolio` + `CashMovement.portfolio`; ambiguous multi-portfolio accounts skipped.
- **Read API:** `GET /api/v1/cash/overview` aggregates broker (`CashLedgerEntry`) and bank (`CashMovement`) balances without merging ledgers; unassigned bank accounts excluded by default.
- **Unchanged:** FD create behavior, cash accounting, `/cash/balances`, summary/performance paths.
- Design: [cash-unification.md](./cash-unification.md).

## 2026-06-24 — CASH-UNIFY-0: Unified cash domain model (design only)

**Docs only — no runtime changes.**

- **Two ledgers, one domain:** Broker cash (`CashLedgerEntry`, portfolio-scoped) and bank cash (`CashMovement`, bank-account-scoped) remain **separate tables**; unified at portfolio/accounting/reporting/UI level only.
- **Portfolio composition:** Securities, mutual funds, fixed deposits, and **cash holdings** (broker cash + bank cash; physical cash deferred).
- **Future ownership:** Bank accounts used for investment activity should link to **exactly one portfolio** via future `BankAccount.portfolio` FK (CASH-UNIFY-1); FD create should **derive portfolio from bank account** (CASH-UNIFY-2).
- **Cash tab future:** “Cash / Liquid Holdings” with Broker Cash, Bank Cash, and Total Cash sections (CASH-UNIFY-3) — no ledger merge.
- **Backfill:** Infer bank account portfolio when unambiguous; leave null and require user assignment when ambiguous; **no automatic cash movements**, **no destructive deletes**, **no double-counting**.
- **Deferred:** Broker ↔ bank transfer workflow (CASH-UNIFY-5); physical/offline cash account (CASH-UNIFY-6).
- Full design: [cash-unification.md](./cash-unification.md).

## 2026-06-24 — FD-CASH-ASOF-1: FD create validates bank ledger as-of investment date

- FD opening debit checks **selected bank account** ledger balance **as of `investment_date`** (inclusive), not today's current balance.
- **Current ledger balance** can exceed **available as of investment date** when deposits/movements are dated after the FD date.
- **Portfolio Cash** (Cash tab / `CashLedgerEntry`) is separate from **Bank Ledger** (`CashMovement` on linked `BankAccount`).
- Reference `opening_balance` on a bank account is not usable ledger cash until `OPENING_BALANCE` is seeded (dated on/before investment date).
- `GET /bank-accounts/{id}/balance?as_of=` for UI; richer insufficient-balance error payload; create modal auto-scrolls to error.

## 2026-06-24 — FD-TAX-1: FD interest/tax withheld report (read-only)

- **Reporting only** — `GET /api/v1/reports/fixed-deposit-interest` aggregates stored gross/tax/net from interest payments, settlements, and renewals without mutating ledger, summary, or performance.
- **Reversed** interest payments excluded; **zero-interest** settlement/renewal rows excluded; **renewal settlements** excluded from settlement source (renewal group row used instead).
- **Cancelled FD** rows excluded from report.
- **Not tax advice**; CSV/export deferred to FD-TAX-2.

## 2026-06-24 — FD-ACC-10A-FX-TERMINAL-FIX: All-scope value terminal alignment

- **Problem:** All Portfolios INR value history dropped while EUR looked fine; latest `metric=value` point did not match summary `current_value`.
- **Root cause:** `load_fx_rate_maps` queried only direct pair direction, missing inverse-only cached rows (e.g. `INR→EUR` for `EUR→INR` conversion). EUR portfolios were excluded from INR performance history after the last direct `EUR→INR` rate date.
- **Terminal alignment:** `metric=value` last point uses summary `current_value` when FX status is `ok`/`filled` (holdings-level terminal valuation + same FX fill as KPI).
- **Historical dates** may remain partial/null when FX is unavailable; cancelled FD was not the cause.

## 2026-06-24 — FD-ACC-10A-REPAIR: one-time deactivated FD repair command

- **Problem:** FDs soft-deactivated before FD-ACC-10A left unreversed `FD_OPENING` debits; bank cash understated; manual deposit fix would distort returns.
- **`repair_deactivated_fd_openings`:** dry-run by default; `--apply` per eligible FD atomically.
- **Does not weaken** public Cancel FD eligibility (`ACTIVE`/`MATURED`, `is_active=true`).
- **Skips** interest/settlement/renewal/already-cancelled cases.

## 2026-06-24 — FD-ACC-10B: General reversal / correction framework

- **Principle:** corrections use **reversal entries** + optional replacement (replacement = separate create after reverse in this phase); no destructive edits/deletes on ledger rows.
- **Existing reversal chain:** `CashMovement.is_reversal`, `reverses_id`, `reversal_reason`; interest payment `is_reversed`, `reversed_at`.
- **Manual cash reversal:** `POST /cash-movements/{id}/reverse` — `REVERSAL` SYSTEM movement, opposite direction, same amount/account/portfolio.
- **FD interest reversal:** `POST /fixed-deposit-interest-payments/{id}/reverse` — `FD_INTEREST_REVERSAL` DEBIT for net; blocks after settlement.
- **Classifier:** reversal rows inherit offset classification from original (external contribution ↔ external withdrawal); income reversals remain income (effect via bank balance, not external flow).
- **Deferred (FD-ACC-10C):** settlement reversal, renewal reversal, cancel-FD reversal.

## 2026-06-24 — FD-ACC-10A: FD cancel / deactivate accounting

- **Root cause:** `DELETE /fixed-deposits/{id}` set `is_active=false` without reversing mandatory `FD_OPENING` debit — bank cash stayed reduced while FD principal left portfolio value.
- **`POST /fixed-deposits/{id}/cancel`:** atomically creates `FD_OPENING_REVERSAL` CREDIT linked to original opening via `reverses` + `is_reversal`; sets `status=CANCELLED`, `is_active=false`.
- **`DELETE`:** **409** when unreversed `FD_OPENING` exists; legacy FDs without ledger opening unchanged.
- **Cancel eligibility:** `ACTIVE`/`MATURED` only; rejects interest payments, settlement, renewal.
- **Value history:** cancelled FD excluded from FD principal series entirely; bank ledger retains opening + reversal (historical PV may dip between open and cancel when bank included — documented).
- **Classifier:** `FD_OPENING_REVERSAL` = internal (not external contribution/withdrawal).
- **Portfolio:** cancelled FD excluded from summary, holdings, value history, XIRR/TWROR terminal; bank cash restored via reversal credit.
- **Audit:** cancel sets `CANCELLED` + `is_active=false` — **no destructive delete**.
- **Deferred:** full correction/reversal framework → **FD-ACC-10B**.

## 2026-06-14 — FD-ACC-8C: FD / bank cash return metrics alignment

- XIRR terminal and TWROR/cumulative-return PV include FD + included bank cash (FD-ACC-8B series).
- `debt/cash_ledger_flows.py` classifies bank movements: internal vs external vs income.
- Opening balance seed = external contribution; FD system movements = internal.
- Accrued interest and standalone FD IRR remain deferred.

## 2026-06-14 — FD-ACC-8B: FD / bank cash in value history

- Implemented **Option B**: `metric=value` includes FD principal + included bank cash ledger balance over time.
- Helpers: `build_fd_value_timeseries`, `build_bank_cash_value_timeseries`, `merge_fd_bank_into_value_timeseries`.
- FD principal step series (no accrued interest); settlement date exclusive; renewal avoids same-day double count.
- **FD-ACC-8C** deferred: XIRR/TWROR/external-flow classification unchanged.

## 2026-06-14 — FD-ACC-8A: FD / bank cash performance design review

**Docs only — no runtime changes.**

- Approved **Option B** for **FD-ACC-8B**: include FD principal + included bank cash in `metric=value` history first.
- **FD-ACC-8C**: XIRR/TWROR cashflow classification (internal vs external) after PV alignment is tested.
- **FD opening** with bank cash included = internal transfer (zero external flow); bank excluded = valuation step (not contribution).
- **Settlement** with bank included = internal transfer; bank excluded = valuation step-down (not withdrawal).
- **Interest**: net credited to included bank cash increases PV (income); tax withheld already excluded from ledger.
- **No accrued interest** daily valuation.
- Full design: [fixed-deposits-accounting.md](./fixed-deposits-accounting.md) § FD-ACC-8.

## 2026-06-14 — FD-ACC-7: Optional bank cash in portfolio value

- **Opt-in only:** `include_in_portfolio_value` default **false**; existing accounts excluded until user enables.
- **Ledger only:** included value uses ledger-derived `current_balance`; manual/reference balances excluded until seeded (`balance_source=ledger`).
- **Scope `all`:** each eligible included account counted once (no double-count across portfolios).
- **Single portfolio:** include bank cash only when FD + portfolio-tagged movement associations resolve to that portfolio alone; otherwise exclude (conservative — no portfolio-specific ledger sub-balances yet).
- **Allocation:** new **Cash / Bank Cash** bucket; portfolio broker cash remains in **Other**.
- **Holdings:** `asset_type=BANK_CASH`; `invested_amount=current_value`; unrealized P/L = 0; no quantity/price.
- **FD stability:** when both FD principal and bank cash included, FD open/settle reclassifies cash ↔ debt without unexpected headline drops (principal); interest increases cash.
- **Performance/XIRR:** unchanged in FD-ACC-1..7 runtime; **FD-ACC-8A** design approved — **8B** value history, **8C** returns.

## 2026-05-19 — Greenfield stack
- **Django + DRF** replace FastAPI for HTTP and ORM
- **PostgreSQL** (Docker Compose) replaces SQLite file persistence
- **React + Vite** retained for frontend
- **KPulla5** remains the behavioral and API contract reference

## Data strategy (inherited)
- Transactions are source of truth
- Historical prices and FX rates cached in DB
- No live external market-data calls during dashboard rendering

## Schema strategy
- Django migrations only; no runtime `ALTER TABLE`

## Finance modules
- Pure Python in `backend/finance/`; no Django/ORM imports in calculation code

## UI strategy (inherited)
- No manual price input
- Prices derived from DB only

## Finance rules (inherited)
- BUY negative cash flow; SELL positive cash flow
- XIRR includes current valuation

## 2026-05-26 — MF-1: Mutual fund schema foundation
- **AMFI `scheme_code`** is the canonical mutual fund identifier (`Asset.symbol`, `MutualFundProfile.scheme_code`); scheme name is display metadata only.
- **Folio required** for mutual fund transactions via `Folio` FK on `MutualFundTransactionDetail` (unique per portfolio + asset + folio_number).
- **NAV date vs investment date** stored separately on `MutualFundTransactionDetail`; NAV date is primary for valuation (MF-3+ will align `Transaction.date`).
- **`HistoricalPrice` unique constraint** unchanged in MF-1: `(asset_symbol, date)` retained; nullable `asset` FK added only.
- **`Asset` uniqueness:** `(asset_type, symbol)` — allows same symbol string across types if needed.
- **`Transaction.asset_id` FK** deferred; stock flows continue using `asset_symbol` only.
- No NAV provider, sync, or read-path integration in MF-1.

## 2026-05-26 — MF-2: Mutual fund NAV cache and sync foundation
- **NAV sync writes** `HistoricalPrice` rows with `asset_type=MUTUAL_FUND`, `asset_symbol=scheme_code`, `source=amfi`, `currency=INR`.
- **NAV lookup** (`latest_nav_for_asset`, `list_mutual_fund_navs_in_range`) reads cached DB rows only — never calls external provider.
- **External provider** used only in explicit sync path (`sync_mutual_fund_navs` command / injected provider); not in holdings, summary, performance, or other read APIs.
- **`AmfiNavProvider`** fetches live NAV via MFAPI in MF-10; injectable `http_get` for tests; read paths still DB-only.
- **`POST /api/v1/nav/refresh`** and `sync_market_data` MF inclusion implemented in MF-9.
- Incremental sync: latest cached NAV + 1 day, else earliest MF transaction/detail `nav_date`; skip profiles with no anchor date.
- Per-scheme provider failure does not abort batch; stock/FX/benchmark sync unchanged.

## 2026-05-26 — MF-3: Mutual fund transaction API
- **`Transaction.date = nav_date`** for MF transactions (valuation-aligned with existing date-based logic).
- **`investment_date`** stored only on `MutualFundTransactionDetail` (cash-flow/reporting date).
- **`fees = paid_value - market_value`** when fees omitted on MF create/update; reject if negative.
- **Field mapping:** `asset_symbol=scheme_code`, `quantity=units_allotted`, `price_per_share=nav`, default `currency=INR`.
- **NAV verification:** optional compare against cached `HistoricalPrice` on write only; no external provider; full tolerance UX deferred to MF-6.
- **Summary/performance MF integration** remains deferred (MF-5).
- Stock transaction API request/response unchanged for non-MF rows.

## 2026-05-26 — MF-4: Mutual fund holdings and asset detail
- **Holdings grouping** for mutual funds: `(scheme_code, folio_number)`; stable `holding_key` = `{scheme_code}:{folio_number}`; stock holdings still group by `asset_symbol` only.
- **`asset_symbol` on MF holding rows** remains `scheme_code` for API compatibility.
- **Valuation read path** uses `latest_nav_for_asset` (cached `HistoricalPrice`, `asset_type=MUTUAL_FUND`) only — no external NAV provider on holdings or asset detail.
- **`nav_status`** on MF rows (`ok` \| `nav_missing`); `price_status` mirrors NAV for UI compatibility; stocks unchanged.
- **Asset detail:** `folio_number` query param required when multiple folios exist for the same scheme; single folio may omit param.
- **Summary/performance** MF inclusion implemented in MF-5 (see below).

## 2026-05-26 — MF-5: Mutual fund summary and performance
- **Valuation date:** `nav_date` → `Transaction.date`; timeseries and FIFO lot updates use NAV date.
- **XIRR / performance cash-flow date:** `investment_date` on `MutualFundTransactionDetail` (not `nav_date`).
- **Cash-flow amounts:** `paid_value` for MF BUY (negative) and SELL (positive); aligns with actual cash movement; stock flows unchanged (`qty×price±fees` on transaction date).
- **FIFO cost basis / summary invested:** NAV × units from transaction rows (fees excluded per existing FIFO); not `paid_value` — document divergence from cash-flow basis.
- **NAV forward-fill:** Last cached NAV per scheme carries forward on non-NAV calendar days (same pattern as stock prices in timeseries).
- **Summary/performance reads:** cached `HistoricalPrice` (`MUTUAL_FUND`) only — no external NAV provider.
- **NAV validation tolerance UX** implemented in MF-6 (backend status only; no frontend).

## 2026-05-26 — MF-6: Mutual fund NAV validation
- **Validation source:** cached `HistoricalPrice` only (`asset_type=MUTUAL_FUND`, `scheme_code`, `nav_date`); no external NAV provider on create/update/read.
- **NAV tolerance:** absolute **0.01 INR** between entered `nav` and `close_price`.
- **Market value tolerance:** absolute **1 INR** between entered `market_value` and `nav × units_allotted`.
- **Mismatch handling:** persist transaction; set `nav_verification_status` / `nav_verification_message` — no hard block unless structurally invalid (400).
- **Status values:** `VERIFIED`, `NAV_MISSING`, `NAV_MISMATCH`, `VALUE_MISMATCH`; legacy `OK`/`WARNING`/`UNCHECKED` retained for existing rows.
- **Helper:** `transactions/mf_nav_validation.py` — `verify_mutual_fund_nav_inputs`.
- Frontend validation UX deferred to MF-8.

## 2026-05-26 — MF-7: Mutual fund classification
- **`Asset.primary_asset_class`** is the MVP classification field (`EQUITY`, `DEBT`, `HYBRID`, `LIQUID`, `COMMODITY`, `OTHER`, `UNKNOWN`).
- **Hybrid funds** map to `HYBRID`, never auto-classified as `EQUITY`.
- **Explicit class wins:** stored non-`UNKNOWN` `Asset.primary_asset_class` is returned with `classification_source=EXPLICIT`.
- **Inference** uses `scheme_category`, `scheme_type`, `scheme_name` only — no external API; conservative keyword rules in `finance/mutual_fund_classification.py`.
- **Cash-equivalent** liquid/overnight/money market → `LIQUID` (not a separate enum).
- **International** funds → `EQUITY` with note; region/exposure split deferred.
- **On MF transaction create/update:** infer and persist class on `Asset` only when unset/`UNKNOWN`; does not override explicit class.
- **Exposure breakdown** and **tax classification** remain deferred (MF-10+ / future).

## 2026-05-26 — MF-10: Live mutual fund NAV provider
- **`AmfiNavProvider`** fetches NAV from MFAPI (`https://api.mfapi.in`) — AMFI-sourced data; `source=amfi` unchanged.
- **`market_data/providers/amfi_nav_parser.py`** — pure JSON/date/NAV parsing; Decimal values; INR currency.
- **Injectable `http_get`** on provider for tests; stdlib `urllib` only (no new dependency).
- **Error handling:** invalid scheme_code → no fetch; latest NAV network/parse errors → `None`; history fetch errors → `AmfiNavFetchError` (sync counts failure per scheme).
- **Read APIs remain DB-only** — no provider calls on holdings/summary/performance/transactions.
- Scheme search, CSV import, grouping setting, exposure/tax UI deferred to MF-11+.

## 2026-06-04 — Cash-4A.2: Cash-aware status and enable UI

- **Visibility:** `CashAwarePortfolioStatus` on Cash + Transactions; Cash-aware column + enable in Settings `PortfolioManagement`.
- **Enable:** confirm → `PUT /portfolios/{id}` with `cash_aware_enabled: true` (and name/base_currency/is_active); `reloadPortfolios()`.
- **All Portfolios scope:** informational note only — no global enable.
- **No** bulk migration, disable CTA, or user deletion.

## 2026-06-04 — Cash-4A.1: New portfolios cash-aware by default

- **New portfolios** (POST `/portfolios` when field omitted, registration default portfolio): `cash_aware_enabled=true` via application services.
- **Explicit legacy:** `POST` may send `cash_aware_enabled=false`.
- **Existing DB rows:** unchanged — model column default stays `false`; no migration that flips existing portfolios.
- **Tester / dev repair:** `PUT /api/v1/portfolios/{id}` with `cash_aware_enabled: true` (no bulk enable-all command in this phase).
- **`Portfolio.id`:** globally unique internal PK; not per-user `id=1`. Future optional UI: `portfolio_number` / `display_order` per user (not implemented).

## 2026-06-04 — REMOVE: Cash shortfall backfill (Cash-7A/7B/7C)

- **`POST /api/v1/cash/backfill-preview`** and **`POST /api/v1/cash/backfill-apply`** **removed** — product direction changed.
- Shortfall simulation (minimum deposits before historical BUYs) is not supported long-term.
- Historical funding → manual `CASH_DEPOSIT` / `CASH_WITHDRAWAL` or **Bulk Cash Entries** (Cash-7D).

## 2026-06-04 — Cash-7D: Bulk cash entries schedule (user-defined funding history)

- **`POST /api/v1/cash/bulk-entries/preview`** and **`apply`** — manual `CASH_DEPOSIT` / `CASH_WITHDRAWAL` schedules (`once`, `monthly`).
- User enters **actual** amounts/dates (opening balance, monthly contributions, withdrawals).
- Apply requires `confirmed: true`; backend recomputes schedule; skips duplicate identical manual rows.
- Withdrawal schedules blocked when running balance would go negative; deposits normally safe.
- No settlements, no transaction mutation, no auto `cash_aware_enabled`.
- `/cash` → **Add Bulk Cash Entries** wizard (`CashBulkEntriesWizard`).

## 2026-06-04 — Cash-4A: Cash-aware BUY/SELL settlements (backend)

- **Gate:** `portfolio.cash_aware_enabled` only; no auto-enable-all.
- **Stock BUY:** `BUY_SETTLEMENT` = −(quantity×price_per_share+fees); sufficiency in `transaction.currency` as of `transaction.date`.
- **Stock SELL:** `SELL_SETTLEMENT` = +(quantity×price_per_share−fees); reject if proceeds ≤ 0.
- **MF BUY:** `BUY_SETTLEMENT` = −`paid_value`; ledger **`date` = `investment_date`** (not `nav_date`).
- **MF SELL:** proceeds = **`paid_value` when &gt; 0**, else `units_allotted×nav−fees`; same ledger date rule.
- **STOCK_SPLIT / DIVIDEND:** no settlement in Cash-4A (dividend deferred).
- **Insufficient BUY:** **400** with same shortfall shape as cash withdrawal API.
- **Delete:** settlement first; block SELL settlement delete if later balances would go negative.
- **Not in scope:** summary/performance/TWROR/XIRR, CSV preview, frontend modal UX (Cash-4B).

## 2026-06-04 — Cash-3A: Manual cash deposit and withdrawal APIs
- **`POST /api/v1/cash/deposits`** and **`POST /api/v1/cash/withdrawals`** create `CashLedgerEntry` rows only — no `Transaction` rows.
- Request amounts are positive; stored signed (+ deposit, − withdrawal).
- Withdrawals rejected with **400** when native-currency balance as of `date` (ledger `date <= withdrawal date`) is insufficient; response includes `required`, `available`, `shortfall`.
- No FX conversion for sufficiency; multi-currency balances stay separate.
- Deposits/withdrawals allowed before `cash_aware_enabled` is true.
- No summary/performance/TWROR/XIRR/BUY-SELL enforcement in this phase.

## 2026-06-04 — Cash-1: Cash Ledger schema foundation

- **New Django app `cash`** for portfolio balance infrastructure (not mixed into `transactions` investment rows).
- **`CashLedgerEntry`** table `cash_ledger_entries`; **`CashTransferGroup`** table `cash_transfer_groups` (schema Cash-1; HTTP writes **Cash-8A/8B**).
- **`Portfolio.cash_aware_enabled`** DB default `false` (existing rows); new portfolios created `true` from Cash-4A.1 onward.
- **Signed `amount`:** positive increases cash, negative decreases; `clean()` enforces sign by `entry_type`.
- **`linked_transaction`:** `PROTECT` — settlement rows block orphan deletes of linked BUY/SELL.
- **20 cash currencies** in `cash.constants.SUPPORTED_CASH_CURRENCIES` (not 22 — doc list aligned to implemented set).
- **Pure helpers:** `finance/cash.py` (`CashLedgerPoint`, balances, shortfall); **ORM:** `cash/services.py` — no HTTP, no summary/performance wiring in Cash-1.

## 2026-06-04 — Cash-0: Cash Ledger architecture (design only)

- **Cash is a portfolio balance component**, not an investment asset. Stocks and mutual funds remain investment assets with FIFO, Metric Sheet, and Compare analytics.
- **Cash contributes** to portfolio current value, value history, allocation, and buying-power checks; **cash does not** receive Asset Metric Sheet analytics (Sharpe, beta, alpha, Compare subjects).
- **Source of truth:** `Transaction` for investments; proposed **`CashLedgerEntry`** for cash movements. BUY/SELL settlements link to transactions via `linked_transaction`.
- **Currency-specific cash balances** stored in native currency; display conversion uses cached `FXRate` only — do not collapse ledger balances into display currency internally.
- **Legacy mode (default):** existing portfolios keep current TWROR/XIRR behavior (`_build_external_flows`: BUY = contribution, SELL = withdrawal) until `cash_aware_enabled` is explicitly enabled.
- **Cash-aware TWROR:** external flows = `CASH_DEPOSIT` / `CASH_WITHDRAWAL` / `TRANSFER_IN` / `TRANSFER_OUT` at single-portfolio scope (+ unlinked `ADJUSTMENT`); BUY/SELL + settlements = **internal** (zero external flow). All Portfolios: same-currency transfers net to zero in aggregated external flows. `STOCK_SPLIT` unchanged. Formula remains `finance/twror.py` `compute_twror_series`.
- **Cash-aware portfolio XIRR (Cash-6C.1 implemented):** external `CASH_DEPOSIT` / `CASH_WITHDRAWAL` / unlinked `ADJUSTMENT`; investor sign convention (deposit negative, withdrawal/terminal positive); terminal **including cash**; BUY/SELL excluded at portfolio level. **Asset-level XIRR** unchanged (asset BUY/SELL flows).
- **All Portfolios XIRR mixed mode:** cash-aware portfolios use ledger external flows; legacy portfolios use transaction BUY/SELL; merged in `display_currency` by date.
- **Cash-6C.2 TWROR/cumulative return:** Same external-flow rules as XIRR but TWROR sign (`CASH_DEPOSIT` positive); daily \(PV_d\) includes cash; `compute_twror_series` formula unchanged. Metric Sheet portfolio metrics use the same inputs. Asset-level and Compare unchanged.
- **All Portfolios scope:** `TRANSFER_OUT` / `TRANSFER_IN` neutral in aggregated TWROR/XIRR (internal between user portfolios).
- **Negative cash:** disallowed by default; optional advanced setting — open question.
- **Implementation phases:** Cash-0 docs → Cash-1 schema → Cash-2 APIs → Cash-3–8 UI/integration. See [cash-ledger.md](./cash-ledger.md).

## Cash Ledger — guardrails (agent summary, 2026-06-04)

Consolidated rules for ongoing Cash phases (detail in [cash-ledger.md](./cash-ledger.md), [.cursor/rules/320-cash-ledger.mdc](../.cursor/rules/320-cash-ledger.mdc)):

| Topic | Decision |
|-------|----------|
| **What cash is** | Portfolio balance component — **not** an investment asset; no Metric Sheet / Compare as AAPL-style subject. |
| **FX / currency** | **No implicit FX conversion** for BUY funding; same-currency cash required; native ledger balances; display FX is presentation only. |
| **Legacy vs cash-aware** | Existing portfolios stay `cash_aware_enabled=false` until explicit enable; **new** portfolios and registration defaults are cash-aware (`true`). |
| **Portfolio IDs** | `Portfolio.id` remains a **globally unique** internal PK (not per-user `id=1`). |
| **Settlements** | BUY/SELL settlements atomic with transactions; protected ledger rows not edited via manual cash APIs. |
| **Frontend** | No cash balance or future-impact math in React; `/cash` for ledger; unified Add modal routes cash to `/cash/*`. |
| **CSV** | No silent deposit creation; preview + user-confirmed auto-deposit only (Cash-5+). |
| **Cash-6+** | Portfolio value and TWROR/XIRR include cash only when that phase is implemented — do not leak cash into summary/performance early. |

## 2026-06-06 — Cash-8B: User-entered cross-currency portfolio transfer

- **`POST /api/v1/cash/transfers`** accepts explicit `source_currency`, `source_amount`, `target_currency`, `target_amount`; legacy `currency` + `amount` still works for same-currency transfers.
- **No market FX lookup** — the app records only what the user says was sent and received; no automatic target-amount calculation, fee calculation, or FX rate storage requirement.
- **`implied_rate`** (`target_amount / source_amount`) returned in API response for display only; not used for valuation, BUY funding, or performance formulas.
- **Source sufficiency** checked only in source currency; target portfolio has no cash requirement.
- **Same-currency** transfers require equal source/target amounts; all-scope TWROR/XIRR remain neutral (unchanged from Cash-8A).
- **Cross-currency** all-scope totals may differ from cached display FX because user-entered amounts are authoritative; no artificial neutralization in this phase.
- **Deferred:** transfer fees, same-portfolio FX conversion (Cash-8C+).

## 2026-05-26 — MF-9: Mutual fund NAV refresh API and combined sync
- **`POST /api/v1/nav/refresh`** — explicit MF NAV sync path only; optional `scheme_codes`; synchronous; returns synced/skipped/failed counts.
- **Read APIs remain DB-only** — no NAV provider on holdings, summary, performance, transactions, or asset detail reads.
- **`sync_market_data` / `force-sync`** include MF NAV sync by default; `--skip-mutual-funds` opts out.
- **MF provider failure** does not fail stock/benchmark/FX success on full sync.
- Live provider implementation completed in MF-10.

## 2026-06-14 — FD-ACC-0: Fixed Deposit Accounting Phase 1 (design only)

- **Bank cash ledger is separate from portfolio cash ledger.** Planned `CashMovement` (user/bank-scoped) must not reuse `CashLedgerEntry` (portfolio-scoped broker cash). Cross-ledger transfers are not auto-created in FD-ACC-1.
- **FD portfolio value stays principal-only** until a separately approved valuation phase; accrued interest is never added to FD `current_value` in FD-ACC-1..6.
- **Ledger is source of truth** for bank `current_balance`; cached balance updated on write; manual balance edits deprecated once ledger is live.
- **Interest accounting:** `FixedDepositInterestPayment` stores gross / tax_withheld / net; `CashMovement` credits **net only** (TDS pattern mirrors portfolio `TAX_WITHHELD` on SELL). **Implemented FD-ACC-4** — immutable interest payment rows; COMPOUNDED FD soft warning.
- **Legacy FDs:** MVP records remain valid without backfilled movements; lifecycle APIs accept `create_cash_movements=false` for optional reconciliation.
- **Settlement model:** maturity/closure via **status transition + generated movements** — mark `MATURED` without movements, then settle to `MATURED_SETTLED`/`CLOSED`; **implemented FD-ACC-5**; settlements immutable.
- **Renewal:** new `FixedDeposit` with `renewal_of`; optional `FixedDepositRenewalGroup`; **direct rollover** skips bank movements for reinvested principal; **movements only for cash payout portion**.
- **`CashMovement.portfolio`:** nullable FK; required and validated when linked to an FD (must match FD portfolio).
- **Performance/XIRR:** integrated in **FD-ACC-8B/8C** — value history + return metrics include FD principal and opt-in bank cash.
- **Runtime:** FD-ACC-0 is docs-only — no migrations, APIs, or UI. See [fixed-deposits-accounting.md](./fixed-deposits-accounting.md).

## 2026-06-14 — FD-ACC-0.1: Approved FD accounting product decisions (docs only)

- **Maturity status flow:** `ACTIVE` → `MATURED` (unsettled; principal still contributes) → `MATURED_SETTLED` or `CLOSED` on settlement. **Do not** skip to direct `CLOSED` on maturity date alone.
- **Direct rollover + partial payout:** new `FixedDeposit` with `renewal_of`; **no bank movement** for rolled principal; movement **only for `cash_payout_amount`**; `FixedDepositRenewalGroup.direct_reinvest_amount` records direct reinvestment.
- **Negative bank balances:** disallowed in FD-ACC-1; overdraft deferred to future explicit bank setting.
- **Opening balance:** `opening_balance` → `OPENING_BALANCE` movement **opt-in wizard only**; never auto-backfill existing accounts.
- **`current_balance` on PUT:** rejected or ignored once ledger exists; corrections via `ADJUSTMENT` / reversal movements.
- **`COMPOUNDED` interest payout:** soft API/UI warning; do not block.
- **`include_in_portfolio_value` (FD-ACC-6):** allow only when bank cash is unambiguously one-portfolio or portfolio-specific balances computable; block/warn on multi-portfolio movement history.
- **Runtime:** docs-only — no code/migrations/API/UI changes.

## 2026-06-14 — FD-ACC-1: Bank CashMovement ledger foundation

- **`CashMovement` model** in `debt` app — positive `amount` + `direction` (`CREDIT`/`DEBIT`); table `cash_movements`.
- **Ledger authoritative** for `BankAccount.current_balance` (cached on write); `finance/bank_cash.py` pure helpers.
- **APIs:** `GET/POST /cash-movements`, `GET /cash-movements/{id}`; `POST /bank-accounts/{id}/seed-opening-balance`.
- **Manual types only** on POST: `MANUAL_DEPOSIT`, `MANUAL_WITHDRAWAL`, `ADJUSTMENT`; opening balance via seed endpoint only.
- **Immutable ledger:** PUT/DELETE on movements return **405**; no hard deletes in FD-ACC-1.
- **Overdraft disallowed;** PUT `current_balance` rejected when ledger exists.
- **Portfolio summary unchanged** — bank cash not included; FD principal unchanged.
- **Frontend:** Settings bank accounts — read-only ledger balance, seed opening balance button, explanatory note.
- **Deferred:** FD renewal movements, reversal API (FD-ACC-6+).

## 2026-06-14 — FD-ACC-3: Mandatory FD opening bank cash outflow

- **New FD create** atomically records `FD_OPENING` system DEBIT (`CashMovement`) from linked bank account for `principal_amount` on `investment_date`.
- **Insufficient bank balance** rejects FD create (**400**) with `required`, `available`, `shortfall`, `currency`; no FD row persisted.
- **Legacy FDs** without opening movement remain valid; no auto-backfill.
- **Immutable after opening movement:** `principal_amount`, `bank_account_id`, `currency`, `investment_date`, `portfolio_id` on PUT.
- **API response:** `has_opening_cash_movement`, `opening_cash_movement_id` on FD list/detail/create.
- **Portfolio summary unchanged** — FD principal included; bank cash excluded.
- **Deferred:** bank cash in portfolio value (FD-ACC-7), backfill wizard.

## 2026-06-14 — FD-ACC-6: Fixed Deposit renewal workflow

- **`FixedDepositRenewalGroup`** audit model links old FD, new FD, settlement, and payout breakdown (`direct_reinvest_amount`, `cash_payout_amount`, interest fields).
- **`POST /fixed-deposits/{id}/renew`** atomically: old FD → `MATURED_SETTLED` with maturity settlement; new FD `ACTIVE` with `renewal_of`.
- **Direct rollover:** no bank `CashMovement` for reinvested principal; renewed FD uses internal `skip_opening_debit=True` on `create_fixed_deposit` — normal `POST /fixed-deposits` still creates `FD_OPENING` debit.
- **Cash payout:** `cash_payout_amount` → `FD_MATURITY_PRINCIPAL` CREDIT only (not full old principal). Net final interest → `FD_MATURITY_INTEREST` CREDIT when `gross_interest − tax_withheld > 0`.
- **Settlement record:** `principal_returned` = old principal (economic); `principal_cash_movement` only when `cash_payout_amount > 0`.
- **Portfolio:** old settled FD excluded; new renewed FD principal included; bank cash still excluded (FD-ACC-7).
- **Deferred:** bank cash in portfolio value (FD-ACC-7), performance/XIRR (FD-ACC-8), reversals.
