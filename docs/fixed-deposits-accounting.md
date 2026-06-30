# Fixed Deposits — Accounting Phase 1

**Status:** **FD-ACC-7 implemented** · **FD-ACC-8B implemented** (value history) · **FD-ACC-8C implemented** (return metrics) · **FD-ACC-9 audited** (2026-06-14) · **FD-ACC-10A implemented** (2026-06-24) · **FD-ACC-10B implemented** (2026-06-24) · **FD-TAX-1/1A/2 implemented** (2026-06-26) · **FD-CASH-ASOF-1 implemented** (2026-06-24, create as-of balance UX).

## FD-INTEREST-MATURITY-LOGIC-1 maturity vs payout estimates (2026-06-30)

| Topic | Rule |
|-------|------|
| **Compounded** | `estimated_maturity_value` = principal + compounded interest (Actual/365 fractional years); `maturity_value_source` = `AUTO_ESTIMATE` or `USER_CONFIRMED` |
| **Payout (monthly/quarterly/half-yearly/annual)** | `estimated_maturity_value` = principal; interest estimated separately as `estimated_total_interest` + `estimated_periodic_interest`; `maturity_value_source` = `AUTO_PRINCIPAL` |
| **Settlement** | Estimates are planning/display only — settlement proceeds remain user-entered; no auto interest payment recording |
| **Legacy inflated payout rows** | API `resolve_maturity_display()` corrects stored inflated maturity to principal unless `USER_CONFIRMED`; optional `recalculate_fd_maturity_estimates --apply` persists |

## FD-HOLDINGS-UX-1 maturity display (2026-06-30)

| Topic | Rule |
|-------|------|
| **Purpose** | `estimated_maturity_value` / `expected_maturity_value` are planning/display fields only |
| **Settlement** | Realized maturity/closure proceeds come from user-entered settlement amounts — not auto-filled from estimates |
| **Legacy FDs** | API computes display estimates when DB fields are null; optional `recalculate_fd_maturity_estimates --apply` persists estimate columns only |

## FD-CASH-ASOF-1 implementation notes (2026-06-24)

| Item | FD-CASH-ASOF-1 outcome |
|------|------------------------|
| **Validation** | FD create checks linked **bank account** ledger balance **as of `investment_date`** (inclusive) |
| **Current vs as-of** | `current_balance` can exceed as-of when movements are dated after investment date |
| **Cash tab** | Portfolio Cash (`CashLedgerEntry`) ≠ Bank Ledger (`CashMovement`) — FD uses bank ledger only |
| **Opening balance** | Reference `opening_balance` not usable until `OPENING_BALANCE` movement seeded on/before investment date |
| **API** | `GET /bank-accounts/{id}/balance?as_of=`; richer insufficient-balance `400` payload |
| **UI** | Create modal shows both balances; structured error panel; auto-scroll/focus on failure |

## FD-TAX-1 implementation notes (2026-06-24)

| Item | FD-TAX-1 outcome |
|------|------------------|
| **API** | `GET /api/v1/reports/fixed-deposit-interest` |
| **Sources** | Interest payments (`is_reversed=false`); settlement final interest (non-zero; excludes renewal-linked settlement); renewal group interest (non-zero) |
| **Exclusions** | Reversed payments; zero-interest settlement/renewal; `CANCELLED` FD rows |
| **Semantics** | `gross_interest`, `tax_withheld`, `net_interest` as stored at source; optional `display_currency` conversion with date-aware FX + fill |
| **Scope** | User-scoped; portfolio filter via existing scope params |
| **Not in scope** | Tax advice; no ledger/performance/summary changes |

## FD-TAX-1A UI polish (2026-06-26)

| Item | FD-TAX-1A outcome |
|------|-------------------|
| **Component** | `FixedDepositInterestReport.jsx` on Fixed Deposits page |
| **Filters** | Default range = current calendar year; **Reset filters**; `group_by` includes **bank** |
| **Notes** | Reversed payments excluded; zero-interest settlement/renewal excluded; not tax advice |
| **Warnings** | FX partial and mixed-currency warnings shown near totals |
| **Table** | Source, Bank/Institution, FD account, display currency columns; readable source labels |
| **No changes** | Report service, ledger, performance, or accounting behavior |

## FD-TAX-2 CSV export (2026-06-26)

| Item | FD-TAX-2 outcome |
|------|------------------|
| **API** | `GET /api/v1/reports/fixed-deposit-interest/export.csv` |
| **Filters** | Same as JSON report: `portfolio_scope` / `portfolio_id`, `start_date`, `end_date`, `display_currency`; `group_by` ignored (detail rows only) |
| **Exclusions** | Same as FD-TAX-1: reversed payments; zero-interest settlement/renewal; `CANCELLED` FD rows |
| **CSV** | UTF-8 `text/csv`; `Content-Disposition` attachment; 16-column header; rows-only (no footer totals); header-only when no rows |
| **Frontend** | **Export CSV** on `FixedDepositInterestReport`; uses current filters; warnings shown in UI only |
| **No changes** | Ledger, performance, summary, or report aggregation logic beyond shared read path |

---

## FD-ACC-10B implementation notes (2026-06-24)

| Item | FD-ACC-10B outcome |
|------|-------------------|
| **Principle** | Corrections via **reversal entries** — no destructive edits/deletes on ledger rows |
| **Manual cash** | `POST /cash-movements/{id}/reverse` — `REVERSAL` opposite direction; `reversal_reason` required |
| **FD interest** | `POST /fixed-deposit-interest-payments/{id}/reverse` — `FD_INTEREST_REVERSAL` DEBIT for net; payment `is_reversed` |
| **Classifier** | Reversal of external contribution → external withdrawal offset; reversal of income → income (bank balance effect); internal reversals → internal |
| **UI** | Cash movement table: Reverse + status labels; FD interest table: Reverse interest |
| **Deferred** | Settlement reversal, renewal reversal, cancel-FD reversal → **FD-ACC-10C** |

### FD-ACC-10A-REPAIR — one-time backfill command (2026-06-24)

For FDs **deactivated via `DELETE` before FD-ACC-10A** that still have an unreversed `FD_OPENING` debit:

```bash
python manage.py repair_deactivated_fd_openings              # dry-run (default)
python manage.py repair_deactivated_fd_openings --apply --fd-id <ID> --reason "..."
```

| Item | Behavior |
|------|----------|
| **Eligible** | `is_active=false`, unreversed `FD_OPENING`, status not `CANCELLED`/`CLOSED`/`MATURED_SETTLED`, no settlement/renewal/interest |
| **Repair** | `FD_OPENING_REVERSAL` CREDIT; `status=CANCELLED`; `is_active=false` retained |
| **Do not** | Add manual deposit — distorts XIRR/TWROR external flows |
| **Skip** | Interest payments, settlement, renewal, ambiguous cases — manual review |

Public `POST .../cancel` rules unchanged.

---

All bank ledger and FD accounting corrections use **linked reversal rows** (`is_reversal=true`, `reverses_id`). Original movements and interest payments remain visible for audit. PUT/PATCH/DELETE on movements and interest payments remain **405**.

---

## FD-ACC-10A implementation notes (2026-06-24)

| Item | FD-ACC-10A outcome |
|------|-------------------|
| **Problem** | Soft deactivate on ledger-backed FD left `FD_OPENING` debit unreversed; bank cash and portfolio value diverged |
| **Cancel** | `POST /fixed-deposits/{id}/cancel` — `FD_OPENING_REVERSAL` CREDIT; `status=CANCELLED`; `is_active=false` |
| **Deactivate** | `DELETE /fixed-deposits/{id}` — **409** when unreversed `FD_OPENING`; legacy no-ledger FDs unchanged |
| **Eligibility** | `ACTIVE`/`MATURED` only; rejects interest payments, settlement, renewal |
| **Value history** | Cancelled FD excluded from FD principal series entirely; bank ledger shows opening + reversal |
| **Historical PV** | Between opening and cancellation: bank debit remains in ledger history; FD principal not counted after cancel (documented dip until reversal date) |
| **Portfolio** | Cancelled FD excluded from summary, holdings, `metric=value` FD series, XIRR/TWROR terminal; bank cash restored via reversal when included |
| **Classifier** | `FD_OPENING_REVERSAL` = internal (not external flow) |
| **Audit** | FD row retained — no destructive delete |
| **Deferred** | Full reversal/correction framework → **FD-ACC-10B** (now implemented — see FD-ACC-10B section) |

### FD lifecycle actions — Deactivate vs Cancel vs Settle vs Renew

| Action | Purpose | API | Bank ledger | Portfolio surfaces after action |
|--------|---------|-----|-------------|--------------------------------|
| **Cancel FD** | Undo mistaken FD creation | `POST /fixed-deposits/{id}/cancel` | `FD_OPENING_REVERSAL` CREDIT | Excluded from summary, holdings, `metric=value` FD series, XIRR/TWROR terminal wealth pool; bank cash restored via reversal |
| **Deactivate** | Hide legacy FD with no ledger opening | `DELETE /fixed-deposits/{id}` | None | Excluded from active list and portfolio value (`is_active=false`); **409** if unreversed `FD_OPENING` |
| **Settle / Close** | Record real maturity or early closure | `POST /fixed-deposits/{id}/settle` | Principal + net interest CREDITs | Principal removed; `MATURED_SETTLED` or `CLOSED` — **not** the same as cancel |
| **Renew** | Record real rollover | `POST /fixed-deposits/{id}/renew` | Settlement legs + optional payout; direct rollover skips reinvest bank movement | Old FD settled; new FD contributes principal |

**Audit:** Cancel, deactivate, settle, and renew all **retain** the FD row — there is no destructive delete API.

**Historical PV (cancel only):** between `FD_OPENING` and `FD_OPENING_REVERSAL` dates, included bank cash reflects the opening debit while cancelled FD principal is excluded from the FD value series — documented dip until reversal date. Broader backdated correction → **FD-ACC-10B**.

---

## FD-ACC-9 audit notes (2026-06-14)

| Item | FD-ACC-9 outcome |
|------|------------------|
| **E2E tests** | `test_fixed_deposit_end_to_end_accounting.py` — five scenario audits |
| **API consistency** | Existing coverage in `test_*_api.py` files verified green |
| **Frontend** | Bank Accounts, Fixed Deposits, Dashboard, Assets tests verified |
| **Docs** | Outdated “design only” / “FDs excluded from value history” statements removed |
| **Graphify** | `make graphify` — `graphify-out/GRAPH_REPORT.md` refreshed |
| **Bugs fixed** | None required during audit |

---

## FD-ACC-8C implementation notes (2026-06-14)

| Item | FD-ACC-8C outcome |
|------|-------------------|
| **Classifier** | `debt/cash_ledger_flows.py` — internal / income / external contribution / withdrawal |
| **XIRR** | Terminal = stocks/MF + broker cash + FD principal + included bank cash |
| **TWROR / cumulative** | Daily PV from FD-ACC-8B merge; external flows += bank manual/seed/adjustment only |
| **Opening balance** | External contribution at seed date |
| **Interest** | Income via PV increase (included bank cash); not external flow |
| **Bank excluded** | FD step changes only; documented conservative behavior |
| **Tests** | `test_fd_cash_flow_classification.py` |

---

## FD-ACC-8B implementation notes (2026-06-14)

| Item | FD-ACC-8B outcome |
|------|-------------------|
| **Scope** | `metric=value` only; dashboard value chart aligned with summary headline |
| **FD series** | `build_fd_value_timeseries` — principal step series; inclusive `investment_date`; exclusive `settlement_date` |
| **Bank cash series** | `build_bank_cash_value_timeseries` — ledger balance as-of each date; FD-ACC-7 scope rules |
| **Merge** | `merge_fd_bank_into_value_timeseries` after `merge_cash_into_value_timeseries` in performance + summary timeseries |
| **Unchanged** | XIRR, TWROR, cumulative return, analytics Metric Sheet, benchmark comparison flows |
| **UI** | Dashboard info banner updated (FD-ACC-8C note for return metrics) |
| **Tests** | `test_fd_performance_timeseries_api.py` |

---

## FD-ACC-8A implementation notes (2026-06-14) — design review only (historical)

**No runtime changes.** This section records approved design for FD/bank cash performance integration before coding.

See **§ FD-ACC-8 performance/timeseries design** below for full detail.

| Item | FD-ACC-8A outcome |
|------|-------------------|
| **Phase split** | **8B** = value history; **8C** = XIRR/TWROR cashflow classification |
| **Recommendation** | Implement **Option B** in 8B first (value series alignment with summary) |
| **Accrued interest** | **No** — principal flat; only recorded payouts move value |
| **FD opening (bank included)** | **Internal transfer** — zero external flow |
| **FD opening (bank excluded)** | **Valuation step** — not external contribution; TWROR spike risk until 8C |
| **Settlement (bank included)** | **Internal transfer** — principal flat |
| **Settlement (bank excluded)** | **Valuation step-down** — not withdrawal; spike risk until 8C |
| **Interest** | Net credited to **included** bank cash increases PV (income); excluded bank → no PV change |
| **Tax withheld** | Already excluded from ledger; reduces net return implicitly |
| **Banner** | Extend `has_fixed_deposits` warning until chart matches summary (8B) |

## FD-ACC-7 implementation notes (2026-06-14)

| Item | Implemented behavior |
|------|----------------------|
| **Opt-in** | `BankAccount.include_in_portfolio_value` default **false**; user toggles in Settings → Bank accounts |
| **Ledger only** | Included value uses ledger-derived `current_balance`; manual/reference balances excluded until seeded |
| **Summary** | `current_value` / `total_invested` include converted bank cash; **Cash / Bank Cash** allocation bucket |
| **Holdings** | `asset_type=BANK_CASH` rows; no quantity/price; unrealized P/L = 0 |
| **Scope `all`** | Each eligible included account counted once |
| **Single portfolio** | Included only when FD + portfolio-tagged movement associations resolve to that portfolio alone; otherwise excluded (conservative) |
| **FD stability** | FD open: cash ↓ FD ↑; settle: FD ↓ cash ↑; interest: cash ↑ — headline total stable for principal |
| **Deferred** | FD performance/XIRR (FD-ACC-8), portfolio-specific ledger sub-balances, transfer/reversal |

## FD-ACC-6 implementation notes (2026-06-14)

| Item | Implemented behavior |
|------|----------------------|
| **Model** | `FixedDepositRenewalGroup` — old/new FD, settlement, direct reinvest vs cash payout breakdown |
| **Renew** | `POST /fixed-deposits/{id}/renew` — atomically settles old FD (`MATURED_SETTLED`), creates renewed FD (`renewal_of`, `ACTIVE`) |
| **Direct rollover** | Reinvested principal **does not** create bank movement; renewed FD **does not** create `FD_OPENING` debit |
| **Cash payout** | `cash_payout_amount` → `FD_MATURITY_PRINCIPAL` CREDIT; net final interest → `FD_MATURITY_INTEREST` CREDIT |
| **Normal FD create** | `POST /fixed-deposits` still requires `FD_OPENING` bank debit (unchanged) |
| **Portfolio** | Old settled FD excluded; new renewed FD principal included in Debt; bank cash still excluded |
| **UI** | Fixed Deposits page — Renew modal for `ACTIVE`/`MATURED` (hidden when settled or `has_renewal`) |
| **Deferred** | Bank cash in portfolio value (FD-ACC-7), performance/XIRR, reversals |

## FD-ACC-1 implementation notes (2026-06-14)

| Item | Implemented behavior |
|------|----------------------|
| **Model** | `CashMovement` in `debt` app — table `cash_movements`; positive `amount` + `direction` (`CREDIT`/`DEBIT`) |
| **Manual API types** | `MANUAL_DEPOSIT`, `MANUAL_WITHDRAWAL`, `ADJUSTMENT` only via `POST /cash-movements` |
| **Opening balance** | `POST /bank-accounts/{id}/seed-opening-balance` — one `OPENING_BALANCE` per account (**409** if already seeded); **400** if `opening_balance ≤ 0` |
| **Balance** | Ledger sum authoritative; `BankAccount.current_balance` cached on write; `balance_source` / `has_ledger_entries` on bank account API |
| **PUT current_balance** | **Rejected (400)** once any ledger row exists for the account |
| **DELETE movement** | **405** — immutable ledger; corrections via future `ADJUSTMENT` / reversal (FD-ACC-2+) |
| **PUT movement** | **405** — immutable |
| **Overdraft** | Not allowed — debits rejected with shortfall payload |
| **Portfolio summary** | Bank cash **not** included; FD principal unchanged |
| **Pure finance** | `finance/bank_cash.py` |
| **Services** | `debt/bank_ledger_services.py` |
| **Deferred** | `TRANSFER_IN`/`OUT` manual API, reversal endpoint, maturity/closure movements |

## FD-ACC-5 implementation notes (2026-06-14)

| Item | Implemented behavior |
|------|----------------------|
| **Status** | `MATURED_SETTLED` added; `ACTIVE`/`MATURED` contribute principal; settled/closed excluded |
| **Model** | `FixedDepositSettlement` — principal/interest breakdown, optional principal/interest cash movements |
| **Mark matured** | `POST /fixed-deposits/{id}/mark-matured` — no ledger; `ACTIVE` → `MATURED` (idempotent if already `MATURED`) |
| **Settle** | `POST /fixed-deposits/{id}/settle` — atomically creates settlement + `FD_*` CREDIT movements; `MATURITY` → `MATURED_SETTLED`, `CLOSURE` → `CLOSED` |
| **Zero net interest** | Gross/tax stored; no zero-amount interest movement |
| **Portfolio** | Summary `current_value` drops by FD principal after settlement; bank cash still excluded |
| **UI** | Mark matured, Settle/Close modal; Settings movements show settlement types |
| **Deferred** | Bank cash in portfolio value (FD-ACC-7), reversals |

## FD-ACC-4 implementation notes (2026-06-14)

| Item | Implemented behavior |
|------|----------------------|
| **Model** | `FixedDepositInterestPayment` — `gross_interest`, `tax_withheld`, `net_interest`, OneToOne `cash_movement` |
| **Movement** | `FD_INTEREST` SYSTEM CREDIT for **net_interest** only; links FD, bank, portfolio |
| **API** | `GET/POST /fixed-deposits/{id}/interest-payments`; `GET /fixed-deposit-interest-payments/{id}`; **405** update/delete |
| **Validation** | `net = gross − tax`; tax ≤ gross; bank account from FD; **400** on `CLOSED` FD; COMPOUNDED → optional `warning` |
| **Portfolio** | FD principal summary unchanged; interest not in portfolio value |
| **UI** | Fixed Deposits page — Record interest modal + expandable payment list; Settings movements show `FD interest` |
| **Deferred** | Maturity/closure/renewal (FD-ACC-5+) |

---

**Related:** [fixed-deposits.md](./fixed-deposits.md) (MVP) · [cash-ledger.md](./cash-ledger.md) (portfolio cash) · [cash-unification.md](./cash-unification.md) (unified domain model) · [database.md](./database.md) · [api-design.md](./api-design.md) · [decisions.md](./decisions.md)

---

## A. Purpose and scope

### Why accounting is separate from FD valuation

Fixed deposits in KPulla6 serve two distinct product concerns:

| Concern | Question it answers | Phase |
|---------|---------------------|-------|
| **Valuation / allocation** | How much of my portfolio is in debt (FD principal)? | **FD MVP (done)** — principal-only |
| **Accounting / cash truth** | Where did cash move when I opened an FD, received interest, paid tax, matured, or renewed? | **FD-ACC-1+ (this design)** |

MVP intentionally treats an FD as a **principal-only debt holding** linked to a portfolio and bank account. It does **not** model cash leaving the bank account on open, interest landing in the bank, or TDS. That keeps summary/holdings stable while the product learns FD usage patterns.

Accounting Phase 1 adds a **bank-account cash ledger** (`CashMovement`) and **interest/settlement workflows** so users can record real-world cash events without changing how FD **portfolio value** is computed.

### In scope for FD Accounting Phase 1 (design)

- Bank account cash ledger / cash movements
- Bank account `current_balance` derived from ledger entries (replacing manual-only balance)
- FD opening cash movement from linked bank account (optional per FD)
- FD interest payments into bank account with gross / TDS / net breakdown
- Maturity / closure settlement workflows
- Renewal workflow (full, partial, direct rollover)
- Future optional inclusion of bank account cash in portfolio value (`include_in_portfolio_value`)

### Explicitly out of scope (this design phase and FD-ACC-1..6)

| Feature | Notes |
|---------|--------|
| **Accrued FD interest in portfolio value** | FD `current_value` stays **principal-only** until a separately approved valuation phase |
| **FD in performance timeseries / XIRR / TWROR** | Deferred to **FD-ACC-7** (decision phase only in this doc) |
| **Automatic interest accrual schedules** | User records actual payouts; no daily accrual engine |
| **Linking bank cash to portfolio `CashLedgerEntry`** | Bank ledger and portfolio cash ledger remain **separate** ledgers (see § B) |
| **Runtime implementation** | This document only — no migrations, APIs, UI, or tests in FD-ACC-0 |

### Relationship to portfolio cash ledger

KPulla6 already has a **portfolio-scoped** cash ledger (`CashLedgerEntry` in the `cash` app) for broker/brokerage cash inside a portfolio. Bank account accounting is **user-scoped** and models real bank/NBFC/post-office accounts used for FD funding.

```
User
├── BankAccount (SBI Savings)     → CashMovement ledger  ← FD-ACC (this design)
└── Portfolio (IndianMF)
    └── CashLedgerEntry           → portfolio cash       ← Cash-1..8 (implemented)
```

These ledgers must **not** be merged in storage. Cross-ledger transfers (e.g. bank withdrawal → portfolio deposit) are a future product decision (**CASH-UNIFY-5**, deferred) and are **not** auto-created in FD-ACC-1 or CASH-UNIFY phases 1–4.

**Unified domain model (CASH-UNIFY-0 + CASH-MODEL-REFINE-0):** Both ledgers represent **cash holdings** at the product level. `BankAccount` is independent; `BankAccount.portfolio` is a **current portfolio link** (not ownership). Link/delink changes inclusion only — no movements. See [cash-unification.md](./cash-unification.md) §4.

**FD portfolio alignment (CASH-MODEL-REFINE-1):** New FDs require explicit `portfolio_id` and `bank_account_id`. Bank account portfolio link is optional and controls cash visibility only. Opening debit checks bank ledger balance as-of `investment_date`. Legacy mismatches flagged read-only (`portfolio_mismatch_warning`). Broker-funded FD **deferred**.

---

## B. MVP accounting principles

1. **Ledger is source of truth for bank cash balance.** Sum of signed `CashMovement` rows for a `bank_account` (as-of date) defines balance. `BankAccount.current_balance` may be cached on write but is never authoritative over the ledger.

2. **FD principal remains portfolio value for FD.** `ACTIVE` and `MATURED` FDs contribute `principal_amount` to summary `current_value` and Debt allocation. **`CLOSED` and `MATURED_SETTLED`** do not contribute after settlement is recorded (see § C — FD status lifecycle).

3. **Interest payment creates a cash movement.** Recording a payout creates `FixedDepositInterestPayment` plus a **net** `CashMovement` (`FD_INTEREST`, positive) crediting the linked bank account. **`COMPOUNDED` FDs:** API/UI returns a **soft warning** when recording periodic interest (do not block — real-world exceptions exist).

4. **Tax withheld is stored separately.** `FixedDepositInterestPayment.tax_withheld` holds TDS; it is **not** subtracted again from the ledger row. The ledger row amount equals **net received** (same pattern as portfolio `SELL_SETTLEMENT` + `TAX_WITHHELD` in [cash-ledger.md](./cash-ledger.md)).

5. **Net received increases bank account cash balance.** `CashMovement.amount` for interest = `net_interest` (positive).

6. **Gross interest can be used later for tax reports.** `gross_interest` and `tax_withheld` on `FixedDepositInterestPayment` enable future tax summaries without inferring from net cash alone.

7. **Existing FD records remain valid without ledger entries.** FDs created in MVP (or before accounting is enabled) continue to contribute principal and appear in holdings. No mandatory backfill. **`BankAccount.opening_balance` is never auto-converted** to a ledger row — opt-in wizard/action only.

8. **Preserve existing product behavior.** Stocks, mutual funds, portfolio cash settlements, dashboard, summary, holdings, analytics, and auth paths are unchanged until explicit FD-ACC implementation phases wire new read paths.

9. **Negative bank balances are not allowed in FD-ACC-1.** Withdrawals and FD debits that would make balance negative are rejected (**400** / **409** future-impact). Overdraft support is out of scope; may be added later as an explicit bank-account setting.

---

## C. Proposed data model

All models below are **conceptual** — not implemented in FD-ACC-0. Target Django app: extend `debt` (alongside `BankAccount`, `FixedDeposit`).

### FD status lifecycle (approved — FD-ACC-0.1)

Maturity and settlement are **separate steps**. Do **not** skip `MATURED` by defaulting straight to a settled status on the maturity date alone.

| Status | Meaning | Contributes principal to portfolio value? |
|--------|---------|------------------------------------------|
| `ACTIVE` | FD is live before maturity (or before user marks matured) | **Yes** |
| `MATURED` | Maturity date has arrived **or** user marked matured; **settlement not yet recorded** | **Yes** |
| `MATURED_SETTLED` | Maturity settlement recorded (cash/renewal accounting complete) | **No** |
| `CLOSED` | Early closure settlement recorded, or legacy MVP closed FD | **No** |
| `CANCELLED` | Mistaken FD cancelled; opening debit reversed (FD-ACC-10A) | **No** |

**Transitions:**

1. `ACTIVE` → `MATURED` — user `PUT` with `status=MATURED`, UI “Mark matured”, or optional future auto-prompt when `maturity_date ≤ today`. **No cash movements.**
2. `MATURED` → `MATURED_SETTLED` — `POST .../settle` (maturity settlement). Creates optional cash movements; removes principal from Debt.
3. `ACTIVE` → `CLOSED` — `POST .../close` (early closure settlement). Same as today’s closed semantics for portfolio value.
4. Renewal — old FD → `MATURED_SETTLED` or `CLOSED` as part of `POST .../renew`; new FD `ACTIVE` with `renewal_of`.
5. `ACTIVE`/`MATURED` → `CANCELLED` — `POST .../cancel` (mistaken creation only; FD-ACC-10A). Creates `FD_OPENING_REVERSAL` CREDIT; `is_active=false`. **Not** a substitute for settle or renew.

**Schema (current):** `ACTIVE`, `MATURED`, `MATURED_SETTLED`, `CLOSED`, `CANCELLED` (migration `debt/0006_fd_cancellation`).

### Signed amount convention

Consistent with portfolio cash: **positive `amount` increases bank account balance; negative decreases.** `clean()` validates sign expectations per `movement_type`.

### `CashMovement` (table: `cash_movements`)

| Field | Type | Notes |
|-------|------|-------|
| `id` | PK | |
| `user` | FK → `auth.User` | Required; all queries scoped by authenticated user |
| `bank_account` | FK → `BankAccount` | Required; must be active, same user |
| `portfolio` | FK → `Portfolio`, **nullable** | See recommendation below |
| `movement_type` | enum | See movement types table |
| `amount` | Decimal | Signed; currency = `currency` |
| `currency` | string(3) | Must match `bank_account.currency` |
| `movement_date` | DateField | Effective ledger date |
| `linked_fixed_deposit` | FK → `FixedDeposit`, nullable | Set for FD-generated movements |
| `linked_interest_payment` | FK → `FixedDepositInterestPayment`, nullable | Set when movement is payout credit |
| `renewal_group` | FK → `FixedDepositRenewalGroup`, nullable | Paired renewal legs |
| `description` | text | User comment / system note |
| `source` | enum | `MANUAL` \| `SYSTEM_GENERATED` |
| `created_at` / `updated_at` | timestamps | Audit |

**Indexes (planned):** `(bank_account, movement_date)`, `(user, bank_account)`, `(linked_fixed_deposit)`, `(renewal_group)`.

#### `portfolio` — nullable, denormalized (recommended)

| Approach | Recommendation |
|----------|----------------|
| **Required always** | Rejected — manual bank deposits (salary, generic transfers) are not portfolio-specific. |
| **Nullable** | **Recommended.** Optional on manual entries; **required and validated** when `linked_fixed_deposit` is set (must equal `fixed_deposit.portfolio`). Enables portfolio-scoped FD accounting reports without forcing every bank movement into a portfolio. |
| **Derived only (no column)** | Possible but slower for list/filter APIs; denormalized FK preferred for KPulla6 read patterns. |

#### `movement_type` enum

| Type | Sign | Balance effect | Typical source |
|------|------|----------------|----------------|
| `OPENING_BALANCE` | + | Increase | Manual / bulk seed |
| `MANUAL_DEPOSIT` | + | Increase | Manual |
| `MANUAL_WITHDRAWAL` | − | Decrease | Manual |
| `TRANSFER_IN` | + | Increase | Manual (external bank transfer in) |
| `TRANSFER_OUT` | − | Decrease | Manual (external transfer out) |
| `FD_OPENING` | − | Decrease | **System on FD create (FD-ACC-3)** — mandatory for new FDs |
| `FD_OPENING_REVERSAL` | + | Increase | **System on FD cancel (FD-ACC-10A)** — reverses mistaken opening |
| `FD_INTEREST` | + | Increase | System on interest payment record |
| `FD_MATURITY_PRINCIPAL` | + | Increase | System on mature |
| `FD_MATURITY_INTEREST` | + | Increase | System on mature (final interest leg) |
| `FD_CLOSURE_PRINCIPAL` | + | Increase | System on early close |
| `FD_CLOSURE_INTEREST` | + | Increase | System on early close |
| `FD_RENEWAL_OUT` | − | Decrease | System — cash leaves bank for renewal (when cash passes through bank) |
| `FD_RENEWAL_IN` | + | Increase | System — cash returns before re-deposit (partial payout leg) |
| `ADJUSTMENT` | ± | Either | Manual reconciliation |

**Note:** Maturity may use separate principal and interest movement types for clarity and tax reporting, even when both credit the same bank account on the same date.

### `FixedDepositInterestPayment` (table: `fixed_deposit_interest_payments`)

| Field | Type | Notes |
|-------|------|-------|
| `id` | PK | |
| `fixed_deposit` | FK → `FixedDeposit` | Required |
| `bank_account` | FK → `BankAccount` | Required; normally FD's linked account; validated same user/currency |
| `payment_date` | DateField | Date cash received |
| `gross_interest` | Decimal | ≥ 0 |
| `tax_withheld` | Decimal | ≥ 0; TDS |
| `net_interest` | Decimal | Must equal `gross_interest − tax_withheld` |
| `currency` | string(3) | Matches FD / bank account |
| `cash_movement` | OneToOne → `CashMovement` | Net credit movement (`FD_INTEREST`) |
| `comment` | text | Optional |
| `created_at` / `updated_at` | timestamps | |

**Validation:** `gross_interest ≥ tax_withheld ≥ 0`; `net_interest = gross − tax`; FD must be active and not closed (or allow final payout on closure — see workflows).

### `FixedDepositSettlement` — recommendation

| Option | Pros | Cons |
|--------|------|------|
| **Separate model** | Rich audit (settlement date, breakdown JSON, who closed) | Extra CRUD; overlaps with interest payment + status |
| **Status transition + generated movements** | Matches `cash_settlement.py` / transfer group pattern; fewer tables | Less standalone "settlement document" |
| **Defer to Phase 2** | Smaller FD-ACC-4 | Harder to group atomic maturity legs |

**Recommendation for FD-ACC-4:** **Status transition + generated cash movements**, no standalone `FixedDepositSettlement` model in Phase 1.

- **Mark matured** (`ACTIVE` → `MATURED`): status update only; **no** ledger writes.
- **Settle** (`POST .../settle` or maturity variant of settle): atomically set `MATURED_SETTLED` (or `CLOSED` for early close), create interest payment row if applicable, create principal/interest `CashMovement` rows when requested.
- Optional **`FixedDepositRenewalGroup`** (below) covers renewal; maturity uses movement types + interest payment link, not a settlement table.
- **Phase 2 optional:** add `FixedDepositSettlement` snapshot if users need downloadable settlement statements or multi-leg approval workflows.

### `FixedDepositRenewal` — recommendation

**Recommended representation:**

1. **New `FixedDeposit` row** with `renewal_of` → previous FD (field already exists in MVP schema).
2. **`FixedDepositRenewalGroup`** (new, optional FK on movements and new FD):

| Field | Notes |
|-------|--------|
| `id` | PK |
| `user` | FK |
| `previous_fixed_deposit` | FK → settled old FD |
| `new_fixed_deposit` | FK → new FD (nullable until created in same transaction) |
| `renewal_date` | Date |
| `rollover_mode` | `DIRECT` \| `VIA_BANK` |
| `direct_reinvest_amount` | Decimal ≥ 0 — principal rolled without bank passthrough |
| `cash_payout_amount` | Decimal ≥ 0 — portion credited to bank (not reinvested) |
| `note` | Optional |

**Invariant:** `direct_reinvest_amount + cash_payout_amount` = settled principal (+ net interest handled separately via interest payment / maturity movements).

3. **Cash movements depend on rollover path:**

| Mode | Bank movements | FD rows | Renewal group |
|------|----------------|---------|---------------|
| **Direct rollover (full)** | **None** — all principal reinvested without bank passthrough | Old → `MATURED_SETTLED`/`CLOSED`; new `renewal_of=old` | `direct_reinvest_amount` = full principal |
| **Direct rollover (partial)** | **Payout portion only** — e.g. `FD_MATURITY_PRINCIPAL` or `FD_RENEWAL_IN` **+10,000** for cash kept in bank; **no movement** for reinvested 90,000 | Same as full direct | `direct_reinvest_amount=90000`, `cash_payout_amount=10000` |
| **Via bank (full)** | Maturity credit principal (+ interest); `FD_OPENING` −reinvest on new FD | Both FD rows; payout = 0 | `direct_reinvest_amount=0`, amounts via movements |
| **Via bank (partial)** | Full principal (+ interest) credits bank; `FD_OPENING` for reinvest; net bank increase = payout | `cash_payout_amount` = portion not reinvested | Movements + group metadata |

**Direct rollover** when principal never hits the bank (common auto-renew at same institution). **Via bank** when cash actually landed in the linked account before re-investment.

---

## D. BankAccount balance strategy

### Opening balance vs ledger-derived balance

| Field / concept | Role after FD-ACC-1 |
|-----------------|---------------------|
| `BankAccount.opening_balance` | **Display/seed only at create** — not authoritative. Conversion to `OPENING_BALANCE` `CashMovement` is **opt-in wizard/action only**; **never auto-backfilled** for existing accounts |
| Ledger sum | **Authoritative** — `Σ amount` for movements with `movement_date ≤ as_of` |
| `BankAccount.current_balance` | **Cached snapshot** — updated atomically with movement writes; **not user-editable** once ledger exists |

### Compute on read vs cache

| Approach | KPulla6 recommendation |
|----------|--------------------------|
| Compute on every read | Correct but slower for bank account list UI with many movements |
| Cached `current_balance` + periodic reconcile | **Recommended** — mirror portfolio cash pattern in `cash/services.py`; pure helper `finance/bank_cash.py` for sum-as-of validation in tests |
| User-editable `current_balance` | **Rejected once ledger is live** — `PUT /bank-accounts` **rejects or ignores** `current_balance`; corrections via `ADJUSTMENT` or reversal `CashMovement` only |

### Negative balances (approved — FD-ACC-0.1)

- **FD-ACC-1:** negative bank balance **not allowed** — same sufficiency and future-impact rules as portfolio cash withdrawals.
- **Overdraft:** out of scope; future optional `allow_overdraft` bank-account flag if product adds it later.

### `include_in_portfolio_value` (future — FD-ACC-6)

| Setting | Behavior |
|---------|----------|
| `false` (default, current MVP) | Bank balance **excluded** from summary `current_value`, allocation, performance timeseries |
| `true` (future) | Bank ledger balance added to portfolio scope as **Cash** allocation — **only when inclusion rules pass** (below) |

**Inclusion restrictions (approved — FD-ACC-0.1):**

- Allow inclusion **only** when the bank account is unambiguously attributable to **one portfolio**, **or** when movements are portfolio-tagged and **portfolio-specific balances** can be computed from ledger rows.
- **Do not** include the full bank balance in **All Portfolios** or a single portfolio if movements span multiple portfolios without per-portfolio balance attribution — that would double-count or misattribute cash.
- UI/API should **block or warn** when toggling `include_in_portfolio_value=true` on accounts with multi-portfolio movement history unless portfolio-specific sub-balances are implemented.

**Why it remains false / not wired:** Including bank cash overlaps with portfolio `CashLedgerEntry`. FD-ACC-6 requires the rules above plus explicit user opt-in. Until then, accounting affects **bank account views only**, not headline portfolio totals (except FD status changes removing principal from Debt when settled).

---

## E. API design proposal

All endpoints require **authenticated session** and **user scoping**. Paths are **planned only** — not implemented in FD-ACC-0.

Base: `/api/v1`

### Cash movements

#### `GET /api/v1/cash-movements`

| Aspect | Detail |
|--------|--------|
| **Purpose** | Paginated bank-account ledger for current user |
| **Query** | `bank_account_id`, optional `portfolio_id`, `movement_type`, `date_from`, `date_to`, `page`, `page_size` |
| **Response** | `{ items[], total, page, page_size, pages }` — each item includes movement fields + `running_balance` optional |
| **Validation** | Unknown bank account → **404**; invalid date range → **400** |
| **Creates movements** | No |

#### `POST /api/v1/cash-movements`

| Aspect | Detail |
|--------|--------|
| **Purpose** | Manual bank ledger entry |
| **Request** | `bank_account_id`, `movement_type` (manual types only), `amount` (positive in request; stored signed), `movement_date`, optional `portfolio_id`, `description` |
| **Response** | **201** — created movement + updated `bank_account.current_balance` |
| **Validation** | Currency match; withdrawal types check sufficient balance (**400** shortfall) + future-impact (**409**); **negative balance disallowed**; `movement_type` must be manual-eligible |
| **Creates movements** | Yes (1 row) |

#### `GET /api/v1/cash-movements/{id}`

Detail for one movement owned by user. **404** if not found.

#### `PUT /api/v1/cash-movements/{id}`

| Aspect | Detail |
|--------|--------|
| **Purpose** | Edit **manual** movements only |
| **Request** | `movement_date`, `amount`, `description` (type immutable) |
| **Validation** | **409** for `SYSTEM_GENERATED`; future-impact negative balance check |
| **Creates movements** | No (updates one row) |

#### `DELETE /api/v1/cash-movements/{id}`

| Aspect | Detail |
|--------|--------|
| **Purpose** | Delete **manual** movements only |
| **Validation** | **409** for system rows or future-impact violation |
| **Creates movements** | No |

**Alternative considered:** nest under `/bank-accounts/{id}/movements` — flatter `/cash-movements` chosen for parity with `/cash/ledger` listing patterns and cross-account reports.

### Fixed deposit interest payments

#### `POST /api/v1/fixed-deposits/{id}/interest-payments`

| Aspect | Detail |
|--------|--------|
| **Purpose** | Record actual interest payout |
| **Request** | `payment_date`, `gross_interest`, `tax_withheld`, optional `bank_account_id` (default FD linked account), `comment` |
| **Response** | **201** — `FixedDepositInterestPayment` + linked `CashMovement` (`FD_INTEREST`, amount = net) |
| **Validation** | FD `ACTIVE` or `MATURED` (not settled/closed), same user; `net = gross − tax`; currency consistency; **`warnings[]`** when FD `interest_payout_frequency=COMPOUNDED` (soft — do not block) |
| **Creates movements** | Yes — 1 `FD_INTEREST` (system) |

#### `GET /api/v1/fixed-deposits/{id}/interest-payments`

List payouts for FD, ordered by `payment_date` desc.

### Fixed deposit lifecycle

#### Mark matured (status only)

| Aspect | Detail |
|--------|--------|
| **Purpose** | Record that maturity date has arrived; **no settlement yet** |
| **Mechanism** | `PUT /fixed-deposits/{id}` with `status=MATURED` (or dedicated action in UI) |
| **Validation** | FD must be `ACTIVE`; `maturity_date` may be validated (warn if early) |
| **Creates movements** | **No** |

#### `POST /api/v1/fixed-deposits/{id}/settle`

| Aspect | Detail |
|--------|--------|
| **Purpose** | Record **maturity settlement** after `MATURED` (or settle in one step from `ACTIVE` when user skips mark-matured) |
| **Request** | `settlement_date`, optional final interest `{ gross_interest, tax_withheld }`, optional `create_cash_movements` (default **true**; **false** for legacy FDs), `settled_status` (`MATURED_SETTLED` default for maturity path), `comment` |
| **Response** | **200** — updated FD (`status=MATURED_SETTLED` or `CLOSED`), created interest payment (if any), movement ids |
| **Validation** | FD must be `ACTIVE` or `MATURED`; not already settled/closed |
| **Creates movements** | Optional — `FD_MATURITY_PRINCIPAL`, `FD_MATURITY_INTEREST` (net), or skip when `create_cash_movements=false` |

**Alias:** `POST .../mature` may alias **settle** when the request body includes settlement fields — **not** for mark-matured-only. Prefer **`/settle`** in new client code.

#### `POST /api/v1/fixed-deposits/{id}/close`

Early closure — same shape as settle with `FD_CLOSURE_*` movement types and `status=CLOSED`; may accept `penalty_amount` (future field) as separate negative movement or reduced principal credit.

#### `POST /api/v1/fixed-deposits/{id}/renew`

| Aspect | Detail |
|--------|--------|
| **Purpose** | Settle old FD and open new FD (renewal chain) |
| **Request** | `renewal_date`, `rollover_mode` (`DIRECT` \| `VIA_BANK`), `new_principal`, `direct_reinvest_amount`, `cash_payout_amount`, optional new FD terms, `create_cash_movements`, optional final interest block |
| **Response** | **201** — `renewal_group_id`, old FD settled, new FD with `renewal_of`, movements summary |
| **Validation** | `direct_reinvest_amount + cash_payout_amount` = settled principal (± closure rules); currency match; **direct rollover:** bank movements **only** for `cash_payout_amount` |
| **Creates movements** | **Direct partial:** payout portion only (e.g. +10000). **Direct full:** none. **Via bank:** per § C renewal table |

### Bank account balance read (extend existing)

#### `GET /api/v1/bank-accounts` / `{id}`

Extend response with `ledger_balance` (computed or cached), `ledger_as_of`, `has_ledger_entries` — **planned FD-ACC-1**.

---

## F. Accounting workflows

### 1. Manual opening bank balance

1. User creates `BankAccount` (MVP API — unchanged in FD-ACC-0).
2. User records opening balance via `POST /cash-movements` with `movement_type=OPENING_BALANCE` **or** dedicated **“Set opening balance”** wizard (UI FD-ACC-2).
3. **Opt-in only:** wizard may offer to create one `OPENING_BALANCE` movement from existing `BankAccount.opening_balance` — user must confirm; **never auto-backfilled** on ledger enable or migration.
4. System creates `CashMovement` (+100000 INR example), updates cached `current_balance`.
5. **No portfolio or FD linkage required.**

### 2. FD opening

**Funding source (CASH-MODEL-REFINE-0):** Each FD requires **one** funding path — linked **bank account** or **broker cash** from the portfolio. Partial bank+broker split is **not** supported. Unlinked bank cannot fund until linked.

**Implemented today (bank path only):**

1. User creates FD via `POST /fixed-deposits` with a **linked** bank account (**FD-ACC-3**).
2. Backend atomically creates `FD_OPENING` movement (−principal) on linked bank account on `investment_date`.
3. **Validation:** bank ledger balance **as of `investment_date`** must cover principal (**400** shortfall). Bank account must be linked (`portfolio` set) per CASH-UNIFY-2.
4. **Backdated FDs:** opening balance seed and manual deposits must use `movement_date` on or before the FD `investment_date`.
5. **Existing MVP FDs:** no movement; FD remains valid; no auto-backfill.

**Deferred (broker-cash path):** Principal debited from portfolio `CashLedgerEntry` (broker ledger) instead of bank `FD_OPENING` — requires dedicated implementation phase; not interchangeable with link/delink or transfer.

### 3. Periodic interest payment

Example: gross = **1000**, TDS = **100**, net = **900**.

1. `POST /fixed-deposits/{id}/interest-payments` with `{ gross_interest: 1000, tax_withheld: 100, payment_date }`.
2. If FD `interest_payout_frequency=COMPOUNDED`, response includes **soft warning** (e.g. `"Compounded FDs typically do not pay periodic interest; confirm this payout is correct."`) — **request still succeeds**.
3. Creates `FixedDepositInterestPayment` (gross/tax/net stored).
4. Creates `CashMovement` `FD_INTEREST` **+900** on linked bank account.
5. Bank `current_balance` increases by 900.
6. **Portfolio summary:** unchanged (interest is not FD principal).
7. Future tax report: sum `gross_interest` and `tax_withheld` by FY.

### 4. Maturity (mark matured → settle)

Example: principal **100000**, final gross interest **5000**, TDS **500**, net **4500**, total cash **104500**.

**Step A — Mark matured (optional if user settles in one step):**

1. User sets `status=MATURED` when `maturity_date` arrives (or UI prompt).
2. FD **still contributes** principal to Debt allocation.
3. **No cash movements.**

**Step B — Settle:**

1. `POST /fixed-deposits/{id}/settle` with settlement date and final interest block.
2. Creates:
   - `FD_MATURITY_PRINCIPAL` **+100000**
   - `FD_MATURITY_INTEREST` **+4500** (net) linked to interest payment row storing gross/tax
3. Sets FD `status=MATURED_SETTLED` (or `CLOSED` if product uses legacy enum until migration).
4. **Portfolio:** Debt allocation −100000; bank balance +104500 (bank views only until FD-ACC-6).
5. If `create_cash_movements=false` (legacy path): status → settled/closed only; **no** bank ledger rows.

### 5. Renewal (direct rollover + partial payout)

Example: old principal **100000**; **90000** directly renewed; **10000** paid to bank.

**Direct rollover (approved workflow):**

1. `POST /fixed-deposits/{id}/renew` with `rollover_mode=DIRECT`, `new_principal=90000`, `direct_reinvest_amount=90000`, `cash_payout_amount=10000`.
2. Old FD → `MATURED_SETTLED` (or `CLOSED`).
3. New FD created with `renewal_of=old`, `principal_amount=90000`, `status=ACTIVE`.
4. **`FixedDepositRenewalGroup`** records `direct_reinvest_amount=90000`, `cash_payout_amount=10000`.
5. **Bank `CashMovement` only for 10000** — e.g. `FD_MATURITY_PRINCIPAL` or `FD_RENEWAL_IN` **+10000** (payout portion). **No movement** for the 90000 rollover.
6. Optional `FD_OPENING` **−90000** only if product records bank debit for via-bank path — **not** for direct rollover.

**Via bank (partial):**

1. Full principal (+ interest) credits bank via maturity movements.
2. `FD_OPENING` **−90000** on new FD; bank net **+10000** after reinvestment debit.

---

## G. Portfolio summary impact

| Event | FD principal (Debt) | Bank cash in portfolio total | Allocation buckets |
|-------|---------------------|------------------------------|-------------------|
| FD `ACTIVE` | +principal | No change when bank excluded; flat when included (FD-ACC-7) | Debt ↑ |
| FD `MATURED` (unsettled) | +principal | No change / flat per inclusion | Debt ↑ (unchanged until settle) |
| Interest payment | No change | +net when bank included (FD-ACC-7/8B) | Cash ↑ when included |
| FD settled (`MATURED_SETTLED` / `CLOSED`) | Removed | +principal+net interest when included; step-down when excluded | Debt ↓, Cash ↑ when included |
| Bank `include_in_portfolio_value=true` (FD-ACC-7) | — | +attributable ledger balance only | Cash / Bank Cash ↑ |
| Maturity settlement with movements | Removed after settle | Cash ↑ when included | Debt ↓, Cash ↑ when included |

**Holdings API:** FD rows `asset_type=FIXED_DEPOSIT`; included bank `asset_type=BANK_CASH`.

**Performance timeseries (FD-ACC-8B/8C):** `metric=value` includes FD principal + included bank cash; TWROR/XIRR use internal/external flow rules from § FD-ACC-8.

---

## FD-ACC-8 performance/timeseries design

**Status:** **FD-ACC-8B implemented (2026-06-14)** — value history includes FD + bank cash. **FD-ACC-8C implemented (2026-06-14)** — XIRR/TWROR/cumulative return aligned.

### Current state (post FD-ACC-8C)

| Surface | Includes FD principal? | Includes included bank cash? | Notes |
|---------|------------------------|------------------------------|-------|
| `GET /portfolio/summary` `current_value` | Yes | Yes (opt-in, ledger-only) | FD-ACC-7 |
| `GET /portfolio/holdings` | Yes | Yes (`BANK_CASH` rows) | |
| `allocation_buckets` | Debt + Cash / Bank Cash | | |
| `GET /portfolio/performance?metric=value` | **Yes** | **Yes** | FD-ACC-8B |
| Portfolio XIRR (`summary` / Metric Sheet) | **Yes** | **Yes** | FD-ACC-8C terminal |
| TWROR / cumulative return | **Yes** in daily PV | **Yes** in daily PV | FD-ACC-8C; internal FD flows excluded |
| `GET /analytics/performance-metrics` | **Yes** | **Yes** | FD-ACC-8C |
| Benchmark comparison | **Yes** in PV series | **Yes** | Return metrics use aligned PV |

**UI:** Dashboard info banner when `has_fixed_deposits`: value chart and return metrics include FD/bank cash.

**Code references (investigation):**

| Area | Location |
|------|----------|
| Value timeseries (stocks/MF) | `portfolios/summary_service.py` `_build_portfolio_value_timeseries` |
| Portfolio broker cash merge | `cash/services.py` `merge_cash_into_value_timeseries` |
| Performance orchestration | `portfolios/performance_service.py` `build_return_value_timeseries`, `build_portfolio_performance` |
| External flows (TWROR) | `portfolios/external_flows_service.py`, `portfolios/cash_ledger_flows.py` |
| XIRR | `portfolios/xirr_service.py` `compute_scope_xirr_detail` |
| Metric Sheet | `analytics/services.py` `build_portfolio_performance_metrics` |
| FD/bank summary value | `debt/portfolio_value.py` |
| Cash-aware precedent | Cash-6C: BUY/SELL = internal; `CASH_DEPOSIT`/`WITHDRAWAL` = external |

---

### 1. What should FD performance mean?

FD performance in KPulla6 is **wealth-pool performance within the portfolio scope**, not standalone FD IRR at the institution.

| Concept | Definition in KPulla6 | In scope for FD-ACC-8? |
|---------|----------------------|------------------------|
| **Principal-only valuation** | `ACTIVE`/`MATURED` FD contributes `principal_amount` to PV; flat between events | **Yes (8B)** — daily step series |
| **Interest cash received** | `FD_INTEREST` / settlement interest credits **net** to bank ledger | **Yes** — increases PV when bank cash **included** in portfolio value |
| **Tax withheld (TDS)** | Stored on `FixedDepositInterestPayment`; **not** credited to ledger | Reduces net return vs gross; no separate PV line |
| **Bank cash included** | Opt-in ledger balance in PV (FD-ACC-7) | **Yes (8B)** — daily balance-as-of series |
| **Bank cash excluded** | Ledger tracked but not in PV | FD open/settle appear as PV step changes only |
| **Time-weighted (TWROR)** | Daily \(r_d = (PV_d - F_d - PV_{d-1})/PV_{d-1}\); \(F_d\) = external flows only | **8C** — FD events must not inflate \(F_d\) |
| **Money-weighted (XIRR)** | Investor flows + terminal PV | **8C** — terminal must include FD + included bank cash; FD internal moves excluded from flows |

**Intentional exclusions:** accrued interest (no daily mark-to-market), tax reporting, standalone FD XIRR at bank/NBFC.

---

### 2. FD principal creation — contribution or internal transfer?

**Approved rule (FD-ACC-8A):**

| Bank cash in portfolio value? | FD `POST` (with `FD_OPENING` debit) | External flow? | PV effect |
|-----------------------------|-------------------------------------|----------------|-----------|
| **Yes** (included, ledger) | Bank ↓, FD ↑ by principal | **None** — **internal reclassification** | Total PV **flat** (± rounding) |
| **No** (excluded) | Bank ledger debited; PV unchanged on bank side | **None** — not a new investor contribution | PV **steps up** by principal on `investment_date` |

**Rationale:** Money already belonged to the user (bank seed/deposit). FD creation reallocates wealth between buckets — it is **not** `CASH_DEPOSIT` and must **not** appear in external-flow maps.

**Legacy FD** (no `FD_OPENING` movement): principal still enters PV on `investment_date` when status is value-contributing — treat as **valuation recognition**, zero external flow.

**TWROR risk (bank excluded):** step-up on open date with \(F_d=0\) produces a **one-day positive return** equal to principal / prior PV. Mitigate in 8B with extended dashboard warning; fix properly in 8C via documented “valuation step” handling or user guidance to enable bank inclusion.

---

### 3. FD settlement — withdrawal or internal transfer?

**Approved rule:**

| Bank cash included? | Settlement (`MATURED_SETTLED` / `CLOSED`) | External flow? | PV effect |
|---------------------|---------------------------------------------|----------------|-----------|
| **Yes** | FD principal removed; bank credited (principal + net interest) | **None** for principal — **internal** | Total PV **flat** for principal; **+net interest** if credited |
| **No** | FD principal removed from PV; bank ledger credited off-PV | **None** | PV **steps down** by principal on `settlement_date` |

Principal return is **never** `CASH_WITHDRAWAL`. Only cash leaving the **entire** tracked wealth pool (e.g. manual `MANUAL_WITHDRAWAL` to external life) would be external — out of scope for FD-ACC-8.

**Direct renewal (FD-ACC-6):** old FD settled + new FD created — net PV change = `cash_payout_amount` (+ net interest) only; reinvested principal is **internal** (no bank movement for direct rollover).

---

### 4. FD interest — how to treat?

**Approved rule:**

| Event | Bank included? | PV change | External flow |
|-------|----------------|-----------|---------------|
| Periodic `FD_INTEREST` (net) | Yes | Bank cash ↑ by net | **None** — portfolio **income** |
| Periodic `FD_INTEREST` (net) | No | **No PV change** | **None** |
| Settlement net interest | Yes | Bank cash ↑ | **None** |
| Tax withheld | Either | **No** separate ledger/PV line | Reduces net vs gross only |

**Not external inflow:** interest is return **on capital already in the portfolio pool**, analogous to portfolio `DIVIDEND_CASH` (internal to wealth, increases PV).

**XIRR/TWROR (8C):** net interest increases terminal/historical PV without a matching negative flow → legitimate positive return. Do **not** add gross interest then subtract tax in flows.

---

### 5. Accrued interest — daily valuation?

**Approved: No.**

- FD `current_value` in performance series = **principal only**, flat from `investment_date` until settlement/closure.
- **Only** recorded `FixedDepositInterestPayment` and settlement interest movements change PV (via included bank cash).
- Compounded accrual, daily yield curves, and mark-to-market are **explicitly deferred** beyond FD-ACC-8.

---

### 6. APIs expected to change in FD-ACC-8B / 8C

| API / surface | FD-ACC-8B (value history) | FD-ACC-8C (returns) |
|---------------|---------------------------|---------------------|
| `GET /portfolio/performance?metric=value` | Merge FD principal daily series + included bank cash daily balance into PV | Unchanged formula; better-aligned PV |
| `GET /portfolio/performance?metric=twror` | Uses updated PV from 8B | FD/bank events **excluded** from \(F_d\) |
| `GET /portfolio/performance?metric=cumulative_return` | Same PV as 8B | Same flow rules as TWROR |
| `GET /portfolio/summary` timeseries (optional) | Align with performance value builder | — |
| `GET /analytics/performance-metrics` | Sharpe/drawdown/etc. from updated daily PV | External flows unchanged until 8C |
| Dashboard value chart | Tracks summary headline better | Banner reduced/removed when aligned |
| `summary.xirr` / Metric Sheet XIRR | — | Terminal PV includes FD + included bank cash; no FD internal flows |
| Benchmark comparison | Compares against fuller PV series | Alpha/beta use same PV; flows unchanged until 8C |

**Implementation sketch (8B):**

1. Add `build_fd_value_timeseries(scope, display_currency, as_of range)` in `debt/portfolio_value.py` — principal steps on `investment_date`, zero on settle/close.
2. Add `build_bank_cash_value_timeseries(user, scope, display_currency, date range)` — ledger balance-as-of per included account (reuse `finance/bank_cash.py`).
3. New merge helper (e.g. `merge_fd_bank_into_value_timeseries`) called from `build_return_value_timeseries` and summary timeseries path — mirror `merge_cash_into_value_timeseries` pattern.
4. Pass `user` into performance builders (session-scoped bank accounts).

---

### 7. Incremental implementation options

| Option | Scope | Pros | Cons |
|--------|-------|------|------|
| **A** | Keep performance excluding FD/bank; warning only | Safest; zero regression risk | Headline vs chart mismatch persists |
| **B** | **FD principal + included bank cash in value history only** | Aligns chart with summary; no flow logic yet | TWROR/XIRR may spike on FD open when bank excluded |
| **C** | Full cashflow-aware FD + bank integration | Correct TWROR/XIRR | High complexity; needs 8B PV first |

**Recommendation (approved):**

1. **FD-ACC-8B** — **Option B**: value history inclusion first.
2. **FD-ACC-8C** — Option C subset: classify FD/bank ledger events as **internal** for external-flow maps; extend XIRR terminal; regression tests for no double-count.
3. Keep **Option A** behavior as fallback flag only if needed for emergency rollback (not default).

**Sequence:** 8B → test PV alignment → 8C → test flows → extend Metric Sheet / benchmark docs.

---

### 8. Risk analysis

| Risk | Severity | Mitigation |
|------|----------|------------|
| Double-count FD + bank cash in PV | High | When bank included, include **both** series; opening debits bank and credits FD same day — net zero; test FD-ACC-7 stability cases on timeseries |
| Internal transfer treated as external flow | High | New `debt/cash_ledger_flows.py` classifier mirroring `cash_ledger_flows.py`; `FD_*` types = internal |
| Settlement misclassified as withdrawal | High | Never map `FD_MATURITY_PRINCIPAL` to external negative flow |
| Return spike on FD open/close (bank excluded) | Medium | Document; extend UI warning; 8C may add “valuation step” note in `warnings[]` |
| Backdated `CashMovement` changes history | Medium | Balance-as-of rebuild on read (same as ledger); test backdated seed/deposit |
| Multi-portfolio bank attribution | Medium | Reuse FD-ACC-7 conservative scope rules for timeseries |
| FX conversion gaps | Medium | Reuse `fx_status` / partial PV null pattern from stocks/MF |
| XIRR terminal without FD | High (today) | 8C: terminal = summary-equivalent holdings + cash + FD + bank |
| Renewal double-count | Medium | Old FD zero from settle date; new FD from `renewal_date`; direct rollover tests |
| Benchmark misalignment | Low | Benchmark uses index returns; portfolio PV gap closes in 8B |

---

### 9. Test plan for FD-ACC-8B

**File targets (planned):** `test_fd_performance_timeseries_api.py`, extend `test_fixed_deposit_summary_api.py`, `test_portfolio_performance_api.py`, `test_analytics_performance_metrics_api.py`.

| # | Case | Expected |
|---|------|----------|
| 1 | FD created from **included** bank cash | `metric=value` total flat ±ε on `investment_date`; summary last point ≈ chart last point |
| 2 | FD created, bank **excluded** | PV steps up by principal; **document** TWROR spike; zero external flow |
| 3 | Interest payment, bank **included** | PV ↑ by net interest on `payment_date`; no external flow |
| 4 | Interest payment, bank **excluded** | PV unchanged |
| 5 | Settlement, bank **included** | Principal flat; net interest ↑ PV |
| 6 | Settlement, bank **excluded** | PV ↓ by principal; not classified as withdrawal |
| 7 | Direct renewal | No double-count old+new principal; payout portion visible in bank series |
| 8 | Backdated `MANUAL_DEPOSIT` before FD | Historical bank balance correct; PV as-of dates consistent |
| 9 | Multi-currency FD + display EUR | FX fill/omit matches summary rules |
| 10 | Single-portfolio scope, multi-portfolio bank | Bank series excluded per FD-ACC-7 rules |
| 11 | `portfolio_scope=all` | Each included bank account once |
| 12 | TWROR on FD open (bank included) | **No** spike > ε (8B baseline; strict assert in 8C) |
| 13 | XIRR unchanged in 8B | Terminal may still omit FD — document until 8C |
| 14 | `has_fixed_deposits` banner | Removed or narrowed when chart includes FD (8B) |
| 15 | Closed/settled FD | Zero contribution after settle date in series |

**FD-ACC-8C additional tests:**

| # | Case | Expected |
|---|------|----------|
| 16 | XIRR terminal includes FD + included bank | Matches summary `current_value` components |
| 17 | `FD_OPENING` not in external flows | TWROR cumulative return stable on open (bank included) |
| 18 | Settlement not in external flows | No artificial withdrawal |
| 19 | Legacy portfolio + FD | Mixed mode does not break |

**Regression commands (8B/8C):**

```bash
make backup-db && make db-safety-check
cd backend && DJANGO_TEST_USE_SQLITE=1 .venv/bin/python -m pytest tests/test_fixed_deposit_summary_api.py tests/test_portfolio_performance_api.py tests/test_portfolio_summary_api.py tests/test_analytics_performance_metrics_api.py -q
cd backend && DJANGO_TEST_USE_SQLITE=1 .venv/bin/python -m pytest -q
cd frontend && npm test -- --run src/pages/Dashboard.test.jsx
make test
```

---

## H. Performance / XIRR impact (superseded by § FD-ACC-8)

**Historical:** No changes in FD-ACC-1..7. See **§ FD-ACC-8 performance/timeseries design** for approved 8B/8C plan.

### Legacy open questions (resolved in FD-ACC-8A)

| Question | FD-ACC-8A decision |
|----------|-------------------|
| FD opening in XIRR? | **Internal** when bank included; **valuation step** when excluded — never external |
| FD interest in XIRR? | Increases PV via included bank cash; **not** external flow |
| FD maturity principal? | **Internal** when bank included; **valuation step-down** when excluded |
| FD in `metric=value`? | **Yes in 8B** — principal step series + included bank balance-as-of |

---

## I. Validation and safety rules

| Rule | Detail |
|------|--------|
| **User scoping** | All reads/writes filter by `request.user`; cross-user FK → **404** |
| **Portfolio ownership** | When `portfolio_id` set, must belong to user; when derived from FD, must match FD.portfolio |
| **Bank account ownership** | Movement.bank_account.user == request.user; FD.bank_account same |
| **Currency consistency** | Movement.currency == bank_account.currency == FD.currency when linked |
| **Negative bank balance** | **Disallowed in FD-ACC-1** — reject debits that would go negative; overdraft deferred |
| **No destructive deletes of history** | Hard delete manual rows only when future-impact allows; system rows **never** hard-deleted via public API |
| **Soft delete** | Prefer `is_voided` flag or reversal movement — **recommended:** reversal via paired `ADJUSTMENT` (implementation choice in FD-ACC-1) |
| **Immutable ledger (recommended)** | Once accounting is enabled for a bank account, **edit history in place is discouraged**; corrections via `ADJUSTMENT` or void+reversal with audit trail |
| **System movement protection** | `PUT`/`DELETE` on `SYSTEM_GENERATED` → **409** (mirror `/cash/ledger` linked rows) |
| **Future-impact** | Edits/deletes that cause negative balance on a later date → **409** with `earliest_negative_date`, `affected_entries[]` (reuse cash ledger shape) |
| **Atomic workflows** | Mature / close / renew / interest payment create FD state + payment + movements in one DB transaction |
| **Legacy FD** | Skip movement requirements; APIs accept `create_cash_movements=false` |

---

## J. Test plan for future implementation

### Backend

| Area | File (planned) | Cases |
|------|----------------|-------|
| CashMovement model validation | `test_bank_cash_movement_models.py` | Sign by type, currency, user/FK rules |
| Balance helpers | `test_finance_bank_cash.py` | Sum-as-of, zero, negative detection |
| Bank account ledger service | `test_bank_cash_services.py` | Create manual, opening balance, cache update |
| Cash movements API | `test_cash_movements_api.py` | CRUD, scoping, 409 system rows, future-impact |
| Interest payments API | `test_fd_interest_payments_api.py` | Gross/tax/net, movement link, closed FD rules |
| Mature / close API | `test_fd_maturity_api.py` | Status transition, principal removed from summary, movements |
| Renewal API | `test_fd_renewal_api.py` | Direct vs via bank, partial payout, `renewal_of` chain |
| Summary integration | `test_fixed_deposit_summary_api.py` (extend) | Principal unchanged on interest; Debt ↓ on close; no double count |
| Legacy FD without ledger | `test_fd_accounting_legacy.py` | MVP FD valid; optional movements |
| Regression | Existing suite | Full `make test-backend` must stay green |

### Frontend

| Area | File (planned) | Cases |
|------|----------------|-------|
| Bank ledger UI | `CashMovementManagement.test.jsx` | List movements, record deposit/withdrawal/adjustment, overdraft error, seed refresh |
| FD interest form | `FixedDeposits.test.jsx` (extend) | Record payout displays gross/tax/net from API |
| Mature / renew modals | `FixedDeposits.test.jsx` | Workflow calls correct endpoints |
| Settings bank balance | `Settings.test.jsx` | Shows ledger-derived balance |
| API client | `api.test.js` | New endpoint wrappers |

---

## K. Phased implementation recommendation

| Phase | Scope | Delivers |
|-------|--------|----------|
| **FD-ACC-0** | **This document** | Design-only; cross-links in docs; no runtime changes |
| **FD-ACC-1** | `CashMovement` model + bank ledger balance | **Done** — schema, services, APIs, seed endpoint; no portfolio summary wiring |
| **FD-ACC-2** | Manual cash movements UI | **Done** — Settings → Bank accounts: movement list, record modal (deposit/withdrawal/adjustment), seed refresh; immutable rows; bank cash not in portfolio value |
| **FD-ACC-3** | Mandatory FD opening bank debit | **Done** — atomic `FD_OPENING` on FD create; insufficient balance rejects; legacy FDs unchanged; immutable fields after opening |
| **FD-ACC-4** | FD interest payments | `FixedDepositInterestPayment` + API + UI |
| **FD-ACC-5** | FD maturity / closure | **Done** — mark matured, settle, `MATURED_SETTLED` |
| **FD-ACC-6** | FD renewal workflow | **Done** — `renew` endpoint, `FixedDepositRenewalGroup`, direct rollover |
| **FD-ACC-7** | Optional bank cash in portfolio value | Wire `include_in_portfolio_value` with multi-portfolio restrictions |
| **FD-ACC-8** | Performance / XIRR integration | **8A done** (design); **8B** value history; **8C** cashflow-aware returns |

**Recommended sequence after FD-ACC-0:** FD-ACC-1 → FD-ACC-2 → FD-ACC-3 → FD-ACC-4 → FD-ACC-5 → FD-ACC-6 → FD-ACC-7.

**Parallel dependency:** FD-ACC-1 has **no** dependency on portfolio cash ledger changes. Do not merge bank and portfolio ledgers.

---

## Approved product decisions (FD-ACC-0.1)

Resolved from FD-ACC-0 open questions — **approved for implementation**.

| # | Decision |
|---|----------|
| 1 | **Maturity status:** `ACTIVE` → `MATURED` (unsettled, still contributes principal) → `MATURED_SETTLED` or `CLOSED` on settlement. **Do not** default to direct `CLOSED` on maturity date alone. |
| 2 | **Direct rollover + partial payout:** New FD with `renewal_of`; **no bank movement** for rolled principal; **bank movement only for `cash_payout_amount`**; `FixedDepositRenewalGroup.direct_reinvest_amount` records rollover without bank passthrough. |
| 3 | **Negative bank balances:** Not allowed in FD-ACC-1; overdraft out of scope until explicit bank-account setting. |
| 4 | **Opening balance seeding:** `opening_balance` → `OPENING_BALANCE` movement **opt-in wizard only**; never auto-backfill existing accounts. |
| 5 | **Manual `current_balance`:** Once ledger exists, ledger sum is authoritative; `PUT /bank-accounts` **rejects or ignores** `current_balance`; corrections via `ADJUSTMENT` / reversal movements. |
| 6 | **`COMPOUNDED` interest payout:** Soft warning in API/UI; **do not block**. |
| 7 | **`include_in_portfolio_value`:** FD-ACC-6 allows inclusion only when bank cash is unambiguously attributable to one portfolio or portfolio-specific balances can be computed; block/warn on multi-portfolio movement history. |

---

## References (current codebase — MVP)

| Area | Location |
|------|----------|
| Bank account / FD models | `debt/models.py` |
| FD portfolio value | `debt/portfolio_value.py`, `finance/fixed_deposits.py` |
| Portfolio cash ledger (separate) | `cash/models.py`, `cash/services.py`, `finance/cash.py` |
| TDS pattern reference | `TAX_WITHHELD` in `cash-ledger.md`, `transactions/cash_settlement.py` |
| FD summary integration | `portfolios/summary_service.py` (FD principal aggregation) |
