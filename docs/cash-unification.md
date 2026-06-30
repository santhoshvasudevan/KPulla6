# Cash Unification — Domain Model & Roadmap (CASH-UNIFY-0)

**Status:** **Stabilized & closed** (MILESTONE-CLOSEOUT-1, 2026-06-26) — phases 0–4B, 4A, CASH-CORR-1A implemented and audited. FD-TAX-1/1A/2 complete.  
**Last updated:** 2026-06-26

**Related:** [cash-ledger.md](./cash-ledger.md) (broker cash) · [fixed-deposits-accounting.md](./fixed-deposits-accounting.md) (bank ledger) · [fixed-deposits.md](./fixed-deposits.md) · [architecture.md](./architecture.md) · [decisions.md](./decisions.md) · [product-rules.md](./product-rules.md)

---

## 1. Problem statement

KPulla6 currently models cash in **two separate ledgers**:

| Ledger | Storage | Scope | Primary use |
|--------|---------|-------|-------------|
| **Broker / portfolio cash** | `CashLedgerEntry` (`cash_ledger_entries`) | Per **portfolio** | Stock/MF settlements, deposits, withdrawals, transfers |
| **Bank account cash** | `CashMovement` (`cash_movements`) | Per **user** bank account | FD opening debits, interest credits, maturity proceeds, manual bank movements |

Both are valid cash holdings from a portfolio perspective, but they feel disconnected in the product:

- The **Cash tab** (`/cash`) shows only broker cash.
- **Bank accounts** live under Settings with their own ledger panel.
- **Fixed deposits** link a bank account and a portfolio independently — the user can pick mismatched portfolios today.
- **Bank accounts** have no `portfolio` FK; portfolio attribution for included bank cash relies on conservative inference from movement/FD tags (FD-ACC-7).

**User expectation:** Cash and liquid holdings normally live **inside an account** that belongs to a portfolio when used for investment activity. Broker cash is portfolio-linked broker account cash. Bank account balance is also a cash holding. The Cash tab should eventually present both clearly without physically merging the two ledgers.

---

## 2. Unified cash domain model

### 2.1 Portfolio composition

A **portfolio** is a wealth pool containing:

```
Portfolio
├── Securities (stocks / ETFs)     → transactions + FIFO + cached prices
├── Mutual funds                   → transactions + folio-scoped FIFO + cached NAV
├── Fixed deposits                 → debt/FixedDeposit (principal-only valuation)
└── Cash holdings (liquid)
    ├── Broker cash account        → CashLedgerEntry (implemented)
    ├── Bank account cash          → CashMovement on BankAccount (implemented)
    └── Physical / offline cash    → deferred (CASH-UNIFY-6)
```

**Cash holdings** are balance components, not investment assets. They participate in portfolio **current value**, **allocation**, and **return metrics** under existing rules (Cash-6, FD-ACC-7/8). They do **not** appear on Asset Metric Sheet or Compare as investment subjects.

### 2.2 Account taxonomy

| Account type | Ledger | Linked to portfolio | Available for |
|--------------|--------|---------------------|---------------|
| **Broker cash account** | `CashLedgerEntry` | Always (required FK) | Securities/MF BUY/SELL settlement, deposits, withdrawals, inter-portfolio transfers |
| **Bank account** | `CashMovement` | **Portfolio link** (`BankAccount.portfolio`, nullable) when used for investment tracking | FD funding, interest, maturity, manual bank deposits/withdrawals |
| **Physical cash** | TBD | Optional future account type | Deferred — not in scope |

### 2.3 Naming glossary

| Term | Meaning | API / UI today |
|------|---------|----------------|
| **Broker Cash** / **Portfolio Cash** | Ledger balance from `CashLedgerEntry` for a portfolio | `/cash/balances`, Cash tab |
| **Bank Cash** / **Bank Ledger** | Ledger balance from `CashMovement` for a `BankAccount` | Settings → Bank accounts; `/bank-accounts/{id}/balance` |
| **Cash / Liquid Holdings** | Unified product concept — broker + bank cash at portfolio scope | Cash tab (`/cash`) — **CASH-UNIFY-3** |
| **Cash / Bank Cash** (allocation bucket) | Opt-in included bank ledger balance in summary allocation | `allocation_buckets` label (FD-ACC-7) |
| **Other** (allocation bucket) | Portfolio broker cash totals today | Summary allocation |

Use **Broker Cash** vs **Bank Cash** in user-facing copy where distinction matters. Avoid implying the two ledgers are the same storage.

---

## 3. Ledger separation (non-negotiable for near term)

### 3.1 Two ledgers remain separate internally

| Aspect | Broker ledger | Bank ledger |
|--------|-----------------|-------------|
| **Table** | `cash_ledger_entries` | `cash_movements` |
| **App** | `cash` | `debt` |
| **Scope key** | `portfolio_id` (required) | `bank_account_id` (required); `portfolio_id` nullable on movements |
| **Settlement behavior** | BUY/SELL via `cash_settlement.py` | FD_OPENING, FD_INTEREST, maturity, renewal legs |
| **Balance helper** | `finance/cash.py` | `finance/bank_cash.py` |

**Do not merge tables** in CASH-UNIFY phases 1–4. Unification is at **domain model**, **portfolio ownership**, **read APIs**, **UI**, and **terminology** — not physical ledger consolidation.

### 3.2 Read-path rules

- **No cross-ledger auto-writes.** Recording a broker deposit does not create a bank movement, and vice versa.
- **No automatic transfer legs** between broker and bank ledgers during migration, backfill, or inference (CASH-UNIFY-5 deferred).
- **Summary/performance** may **aggregate** broker cash + included bank cash + FD principal for display; each component is computed from its own ledger rules (already implemented in FD-ACC-7/8).
- **Double-counting guard:** when bank cash is included in portfolio value, FD opening is an internal reclassification (bank ↓, FD ↑) — net portfolio value flat for principal (FD-ACC-8A).

### 3.3 Where each ledger appears today

| Surface | Broker cash | Bank cash |
|---------|-------------|-----------|
| Cash tab (`/cash`) | Balances + ledger + broker writes + bank cash overview (read-only) | Settings → Bank accounts for movements |
| Settings → Bank accounts | — | Movements + seed opening balance |
| Summary `current_value` | Always (cash-aware / allocation) | Opt-in `include_in_portfolio_value` |
| Holdings | Allocation slices (`Cash EUR`, etc.) | `asset_type=BANK_CASH` when included |
| Performance `metric=value` | Merged via `merge_cash_into_value_timeseries` | Merged via `merge_fd_bank_into_value_timeseries` |
| FD create | Not used for opening debit | `FD_OPENING` debit on linked bank account |

---

## 4. Bank account portfolio link

### 4.1 Product model (refined — CASH-MODEL-REFINE-0)

A **bank account** is an independent real-world cash account (user-scoped). It is **not owned by** a portfolio.

`BankAccount.portfolio` is the **cash visibility portfolio** / **display-under-portfolio-cash link**:

| State | Meaning | Cash page / overview behavior |
|-------|---------|-------------------------------|
| **Linked** (`portfolio` set) | Bank cash is attributed to that portfolio for **cash visibility** | Appears in portfolio-scoped **Bank Cash** when rules include it |
| **Unlinked** (`portfolio` null) | External / unassigned bank cash | Not inside a single portfolio's Bank Cash; visible as unassigned via `include_unassigned` on overview |
| **Ambiguous** (inference conflict) | Multiple portfolio signals on movements/FDs | Excluded from portfolio scope until user resolves link |

**Link/delink rules:**

- Linking or delinking changes **classification and portfolio inclusion only** — **no** `CashMovement` or `CashLedgerEntry` rows are created.
- Bank ledger balance is unchanged; only which portfolio (if any) sees the cash as **Bank Cash** changes.
- **Does not control FD creation** (CASH-MODEL-REFINE-1).

### 4.1a FD funding source (refined — CASH-MODEL-REFINE-1)

FD creation requires **one clear funding source**. The user picks **one** path per FD — **not** a split across ledgers.

| Funding source | Ledger | Requirements | Runtime |
|----------------|--------|--------------|---------|
| **Bank account** | `CashMovement` — `FD_OPENING` debit | Explicit `bank_account_id`; sufficient bank ledger balance as of `investment_date`; bank link optional | **Implemented** (FD-ACC-3) |
| **Broker cash** | `CashLedgerEntry` — broker withdrawal/settlement leg on selected portfolio | Sufficient broker cash in FD currency for selected portfolio | **Not implemented** — target model only |

**Rules:**

- **Partial bank + broker funding is not supported** for a single FD principal.
- **FD portfolio** is the explicitly selected `portfolio_id` at create time — **not** derived from `BankAccount.portfolio`.
- **Unlinked bank accounts** may fund FDs when `portfolio_id` and balance checks pass.
- **Historical seed (FD-FUNDING-MODEL-1):** When as-of bank balance is insufficient for `investment_date`, user may `POST /bank-accounts/{id}/seed-balance` to create an explicit `MANUAL_DEPOSIT` before FD create. Seed does not create FD or portfolio holdings.
- When broker-funded (future): portfolio is the selected portfolio; bank account may still be required for maturity proceeds routing — product detail TBD.
- Choosing funding source is **not** link/delink and **not** transfer — it records which ledger supplies principal at create time.

### 4.2 Three distinct operations (do not conflate)

| Operation | What changes | Ledger writes | Phase |
|-----------|--------------|---------------|-------|
| **Link / delink** | `BankAccount.portfolio` FK; portfolio inclusion | **None** | CASH-UNIFY-4 |
| **Transfer** | Actual cash moves between broker and bank ledgers | Paired legs (future) | CASH-UNIFY-5 (deferred) |
| **Correction / reclassification** | Fix mistaken historical entry type/ledger | Audited reversal + correct entry; preserves trail | CASH-CORR-1 |

| Concept | Changes balances? | Changes portfolio inclusion? | Example |
|---------|-------------------|------------------------------|---------|
| **Link / delink** | No | Yes | Assign bank account to IndianInvestments portfolio |
| **Transfer** | Yes (both ledgers) | No by itself | Move ₹50k from bank to broker |
| **Correction** | Yes (audited fix) | May indirectly | Broker deposit should have been bank deposit |

Example: A manual broker deposit that should have been a bank deposit is **not** fixed by delinking the bank account — it needs **CASH-CORR-1** reclassification with audit trail.

### 4.3 Current implementation (post CASH-UNIFY-2)

- `BankAccount.portfolio` nullable FK exists; create/update API accepts `portfolio_id`.
- `portfolio_assignment_status` on bank account reads: `ASSIGNED` / `UNASSIGNED` / `AMBIGUOUS` (from FK + FD/movement signals).
- **FD create (bank path only today):** Linked bank account + `FD_OPENING` on bank ledger; portfolio from bank link (CASH-UNIFY-2). Broker-cash FD funding **not implemented**.
- Legacy FD rows with portfolio ≠ bank account portfolio remain readable; API exposes `portfolio_mismatch_warning` (no auto-rewrite).
- FD-ACC-7 bank cash inclusion still uses movement/FD association inference when `portfolio` unset.
- **Link/delink UX** — **Done (CASH-UNIFY-4):** Settings → Bank Accounts; `PUT` `portfolio_id` (set or null); no ledger writes; Cash overview inclusion follows link.

### 4.4 Enforcement timeline

| Phase | Behavior |
|-------|----------|
| **CASH-UNIFY-1** | **Done** — `BankAccount.portfolio` FK; read APIs expose link status |
| **CASH-UNIFY-2** | **Done** — FD create derives portfolio from linked bank account |
| **CASH-UNIFY-3** | **Done** — Cash page shows Broker + Bank Cash separately |
| **CASH-UNIFY-3A** | Cash page verification: correct row attribution, broker actions visible, source diagnostics |
| **CASH-UNIFY-4** | **Done** — Link/delink UX; inclusion stabilization; terminology |
| **CASH-UNIFY-4A** | **Done** — Final audit/stabilization; diagnostics command; docs/tests |
| **CASH-CORR-1A** | **Done** — Safe broker cash reversal (opposite entry; bank unaffected) |
| **CASH-CORR-1** | Broader reclassification for mistaken broker ↔ bank entries |
| **CASH-UNIFY-5** | Actual broker ↔ bank transfer workflow (deferred) |
| **FD-FUND-BROKER** | *Deferred* | Broker-cash-funded FD create (single-source; no partial split) |

---

## 5. Cash tab — “Cash / Liquid Holdings” (**CASH-UNIFY-3 implemented**)

**Implemented 2026-06-24.** Cash page consumes `GET /api/v1/cash/overview`; broker and bank ledgers remain separate.

### 5.1 Layout (proposed)

```
┌─────────────────────────────────────────────────────────────┐
│  Cash / Liquid Holdings                    [scope selector] │
├─────────────────────────────────────────────────────────────┤
│  Total Cash (native + optional display currency)            │
│  ┌──────────────┐  ┌──────────────┐                         │
│  │ Broker Cash  │  │  Bank Cash   │   ← section KPIs        │
│  └──────────────┘  └──────────────┘                         │
├─────────────────────────────────────────────────────────────┤
│  Broker Cash                                                │
│  • Per portfolio / currency balances (existing table)       │
│  • Actions: Deposit, Withdrawal, Transfer, Bulk entries     │
│  • Ledger table (existing)                                  │
├─────────────────────────────────────────────────────────────┤
│  Bank Cash                                                  │
│  • Per bank account balances (from overview API)            │
│  • Link → Settings → Bank account / movements               │
│  • Helper: available for FD / bank products (not securities)│
└─────────────────────────────────────────────────────────────┘
```

### 5.2 Distinctions to preserve in copy

| Broker Cash | Bank Cash |
|-------------|-----------|
| Funds available for **securities/MF** purchases (cash-aware mode) | Funds available for **FD** and bank-product workflows |
| Managed on this page (deposits, withdrawals, ledger edit) | Movements managed in Settings (or deep-link) |
| Per-portfolio | Per bank account; filtered by **portfolio link** when set; unlinked = external/unassigned |

### 5.3 Out of scope for Cash tab redesign

- Physical/offline cash account (CASH-UNIFY-6)
- Cross-ledger broker ↔ bank transfer workflow (CASH-UNIFY-5)
- Merging ledger tables or a single combined ledger write path

---

## 6. Existing data & backfill strategy

**Applies to CASH-UNIFY-1 and CASH-UNIFY-2 implementation — documented here for safety.**

### 6.1 BankAccount.portfolio inference

When adding `BankAccount.portfolio` (nullable FK):

1. **Single-portfolio signal:** If all non-null `CashMovement.portfolio` values and all linked `FixedDeposit.portfolio` values for the account point to the **same** portfolio → set `BankAccount.portfolio` to that portfolio (idempotent migration/management command).
2. **Ambiguous:** Movements/FDs reference **more than one** portfolio → leave `portfolio` **null**; surface in UI/API as `portfolio_assignment_status: "ambiguous"` (proposed); block `include_in_portfolio_value=true` and new FD creation until user assigns.
3. **No signal:** No movements with portfolio and no FDs → leave null; user assigns when linking to investment activity.
4. **No destructive changes:** Do not delete movements, FDs, or ledger rows. Do not auto-create balancing entries.

### 6.2 FD portfolio alignment (CASH-UNIFY-2 — implemented)

- **New FDs:** Require explicit `portfolio_id` and `bank_account_id`; portfolio is **not** derived from bank link (CASH-MODEL-REFINE-1).
- **Existing FDs:** If FD.portfolio ≠ bank account cash visibility link, **do not auto-change**. Read-only `portfolio_mismatch_warning` in API.
- **No automatic cash movements** during alignment — accounting history stays intact.

### 6.3 Safety checklist (all backfill phases)

| Rule | Detail |
|------|--------|
| No automatic ledger merging | Tables stay separate |
| No automatic cash movement creation | Backfill sets FKs/flags only |
| No double-counting | Inclusion rules unchanged until explicit ownership + UI |
| No destructive deletes | Soft flags and user assignment only |
| Backup before migration | `make backup-db` + `make db-safety-check` per AGENTS.md |

---

## 7. Safety & accounting rules (epic-wide)

These apply to **all** CASH-UNIFY implementation phases:

1. **Existing FD/bank cash behavior remains valid** until the phase that explicitly changes it ships (with tests + changelog).
2. **Existing broker cash behavior remains valid** — Cash-1..8 rules unchanged unless a phase documents an intentional extension.
3. **No cross-ledger writes** without an approved CASH-UNIFY-5 (or later) transfer product.
4. **Reversal framework** (FD-ACC-10B) stays the correction path for bank movements; broker manual rows stay on `/cash/ledger`.
5. **Read paths:** no live FX/market-data providers; display-currency totals use cached FX (CASH-UNIFY-4 / display-currency sub-phase).
6. **Returns classification:** FD/bank internal vs external flows per `debt/cash_ledger_flows.py` — unification UI must not reclassify flows.

---

## 8. Implementation roadmap

### 8.1 Phase index

| ID | Title | Backlog file | Depends on | Runtime |
|----|-------|--------------|------------|---------|
| **CASH-UNIFY-0** | Unified cash model design | [001-cash-unify-0.md](./backlog/001-cash-unify-0.md) | — | **Docs only** ✓ |
| **CASH-UNIFY-1** | Bank account portfolio link + unified read API | [002-cash-unify-1.md](./backlog/002-cash-unify-1.md) | 001 | **Done** ✓ |
| **CASH-MODEL-REFINE-1** | FD create uses explicit portfolio; bank link optional for funding | — | 004 | **Done** ✓ |
| **CASH-UNIFY-2** | ~~FD portfolio derived from bank account~~ superseded by CASH-MODEL-REFINE-1 | [003-cash-unify-2.md](./backlog/003-cash-unify-2.md) | 002 | **Superseded** |
| **CASH-UNIFY-3** | Unified Cash page UI | [004-cash-unify-3.md](./backlog/004-cash-unify-3.md) | 002 (overview API); 003 recommended | **Done** ✓ |
| **CASH-UNIFY-3A** | Cash page verification & attribution fix | [004a-cash-unify-3a.md](./backlog/004a-cash-unify-3a.md) | 004 | **Done** ✓ |
| **CASH-UNIFY-4** | Bank account link/delink UX + inclusion stabilization | [005-cash-unify-4.md](./backlog/005-cash-unify-4.md) | 004, 004a | **Done** ✓ |
| **CASH-UNIFY-4B** | Bank link modal + display currency auto-select | *(in-repo hotfix)* | 005 | **Done** ✓ |
| **CASH-UNIFY-4A** | Final audit + `cash_overview_diagnostics` | *(in-repo)* | 005 | **Done** ✓ |
| **CASH-CORR-1A** | Safe broker cash reversal | *(in-repo)* | 004a | **Done** ✓ |
| **CASH-CORR-1** | Cross-ledger reclassification + reconciliation API | [012-cash-corr-1.md](./backlog/012-cash-corr-1.md) | 004, 005 (recommended) | **Partial** — 1A done; broader reclassification open |
| **CASH-UNIFY-5** | Broker ↔ bank transfer workflow | *Deferred* | 004 | Optional future epic |
| **CASH-UNIFY-6** | Physical / offline cash account | *Deferred* | — | Optional future account type |

### 8.2 Phase summaries

**CASH-UNIFY-1 — Bank account portfolio ownership + read API (implemented 2026-06-24)**

- Add nullable `BankAccount.portfolio` FK + migration.
- Inference backfill command (dry-run default) per §6.1.
- `GET /api/v1/cash/overview` (or equivalent): `broker_cash`, `bank_cash`, `totals`; each row tagged `ledger_type: PORTFOLIO | BANK`.
- Bank account APIs expose `portfolio_id`, assignment status.
- Document in `api-design.md`; `fetchCashOverview` in `api.js` (no page UI required).

**CASH-UNIFY-2 — FD portfolio derived from bank account (implemented 2026-06-24)**

- FD create: set `portfolio` from `bank_account.portfolio`; reject mismatch/unassigned bank account.
- FD create UI: portfolio field read-only when bank account selected.
- Existing FD mismatch → warning, no silent rewrite.
- **Runtime:** linked-bank funding only (`FD_OPENING`); broker-funded FD deferred (FD-FUND-BROKER).

**CASH-UNIFY-3 — Unified Cash page UI (implemented 2026-06-24)**

- Cash page sections: Broker Cash, Bank Cash, Total Cash (§5).
- Consumes overview API; preserves existing broker write flows.
- Links to Settings for bank movement management.
- Vitest updates; `page-layouts.md` / `frontend-design.md`.
- **Follow-up:** CASH-UNIFY-3A for manual verification issues (swapped values, broker actions visibility).

**CASH-UNIFY-3A — Cash page verification & attribution fix (implemented 2026-06-25)**

- Fixed Broker/Bank row attribution: UI filters overview rows on `ledger_type`; KPIs use `totals.broker_cash*` / `totals.bank_cash*` only (no `/cash/balances` fallback).
- Per-row **source** diagnostics: `cash_ledger_entries` (broker) vs `cash_movements` (bank).
- **Broker Cash actions** visible in page header (deposit, withdrawal, bulk, transfer).
- Bank Cash read-only; always-on **Show unassigned / ambiguous bank accounts** toggle.
- IndianInvestments regression covered in tests (broker 0, bank ~1.1M INR).
- Correction/reclassification deferred to CASH-CORR-1; broker-funded FD deferred.

**CASH-UNIFY-4 — Bank account link/delink + stabilization (implemented 2026-06-26)**

- Clear **link/delink** UX in Settings → Bank Accounts (`BankAccount.portfolio` as current link).
- Link/delink changes inclusion only — no ledger movements.
- Linked bank cash in portfolio Cash holdings; delinked as external/unassigned.
- Display-currency totals and terminology cleanup (cached FX only).

**CASH-UNIFY-4B — Bank link modal + display currency (implemented 2026-06-26)**

- Link/change-link opens dedicated modal; portfolio switch auto-selects supported `base_currency`; All Portfolios preserves current display currency.

**CASH-UNIFY-4A — Audit + diagnostics (implemented 2026-06-26)**

- Read-only `cash_overview_diagnostics` command; final stream stabilization (MILESTONE-CLOSEOUT-1).

**CASH-CORR-1A — Safe broker cash reversal (implemented 2026-06-26)**

- `POST /api/v1/cash/ledger/{id}/reverse` + management command `reverse_broker_cash_entry` (dry-run default).
- Opposite broker entry with audit link; original preserved; bank ledger untouched.
- Example: IndianInvestments broker deposit #103 (+1,109,389 INR) duplicated bank `CashMovement` #2 — reverse broker row only; link HDFC to portfolio deferred to CASH-UNIFY-4.

**CASH-CORR-1 — Safe cash reclassification**

- Audited correction for mistaken entries (e.g. broker deposit → should be bank deposit).
- Preserves audit trail; no silent rewrite.

**CASH-UNIFY-5 — Broker ↔ bank transfer (deferred)**

- User-initiated **actual** cash movement between ledgers (paired legs or guided double-entry).
- Distinct from link/delink (classification only).

**CASH-UNIFY-6 — Physical cash account (deferred)**

- Optional account type with simple ledger; lowest priority.
- **Not scheduled.**

---

## 9. Code references (current implementation)

| Area | Location |
|------|----------|
| Bank account portfolio inference | `backend/debt/bank_account_portfolio.py` |
| Inference command | `backend/debt/management/commands/infer_bank_account_portfolios.py` |
| Cash overview service | `backend/cash/overview_service.py` |
| Cash overview diagnostics | `backend/cash/management/commands/cash_overview_diagnostics.py` |
| Broker ledger model | `backend/cash/models.py` — `CashLedgerEntry` |
| Bank ledger model | `backend/debt/models.py` — `CashMovement`, `BankAccount` |
| FD create + opening debit | `backend/debt/services.py`, `backend/debt/bank_ledger_services.py` |
| Bank cash in portfolio value | `backend/debt/portfolio_value.py` (FD-ACC-7 inference) |
| Broker cash merge (performance) | `backend/cash/services.py` — `merge_cash_into_value_timeseries` |
| FD/bank merge (performance) | `backend/debt/portfolio_value.py` — `merge_fd_bank_into_value_timeseries` |
| Bank flow classifier | `backend/debt/cash_ledger_flows.py` |
| Cash page | `frontend/src/pages/Cash.jsx` |
| Bank account UI | `frontend/src/components/BankAccountManagement.jsx`, `CashMovementManagement.jsx` |

---

## 10. Open questions (resolved or deferred)

| Question | Resolution |
|----------|------------|
| Required vs optional `BankAccount.portfolio` for non-FD accounts | **Resolved (CASH-UNIFY-1/4):** nullable link; user assigns via Settings |
| Block FD create vs warn when bank account unassigned | **Resolved (CASH-UNIFY-2):** create blocked (**400**) until linked |
| Display-currency total when partial FX unavailable | **Resolved (CASH-UNIFY-4):** partial totals + warnings; cached FX only |
| Paired broker-bank transfer API shape | **Deferred:** CASH-UNIFY-5 |
| Portfolio-specific bank sub-balances for multi-portfolio accounts | **Deferred:** post CASH-CORR-1 |
| Broker-cash-funded FD create | **Deferred:** FD-FUND-BROKER |
| FD interest/tax CSV export | **Resolved (FD-TAX-2):** `GET .../export.csv` |

---

## 11. References

- Broker cash spec: [cash-ledger.md](./cash-ledger.md)
- Bank ledger + FD accounting: [fixed-deposits-accounting.md](./fixed-deposits-accounting.md) § A (relationship to portfolio cash)
- Product rules index: [product-rules.md](./product-rules.md) § A, § I (bank cash)
- Backlog operating guide: [backlog/README.md](./backlog/README.md)
