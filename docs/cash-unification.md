# Cash Unification — Domain Model & Roadmap (CASH-UNIFY-0)

**Status:** Design only (CASH-UNIFY-0) — **no runtime changes**.  
**Last updated:** 2026-06-24

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
| **Bank account** | `CashMovement` | **Future:** explicit FK when used for investment activity | FD funding, interest, maturity, manual bank deposits/withdrawals |
| **Physical cash** | TBD | Optional future account type | Deferred — not in scope |

### 2.3 Naming glossary

| Term | Meaning | API / UI today |
|------|---------|----------------|
| **Broker Cash** / **Portfolio Cash** | Ledger balance from `CashLedgerEntry` for a portfolio | `/cash/balances`, Cash tab |
| **Bank Cash** / **Bank Ledger** | Ledger balance from `CashMovement` for a `BankAccount` | Settings → Bank accounts; `/bank-accounts/{id}/balance` |
| **Cash / Liquid Holdings** | Unified product concept — broker + bank cash at portfolio scope | **Future** Cash tab (CASH-UNIFY-3) |
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
| Cash tab (`/cash`) | Balances + ledger + writes | Not shown |
| Settings → Bank accounts | — | Movements + seed opening balance |
| Summary `current_value` | Always (cash-aware / allocation) | Opt-in `include_in_portfolio_value` |
| Holdings | Allocation slices (`Cash EUR`, etc.) | `asset_type=BANK_CASH` when included |
| Performance `metric=value` | Merged via `merge_cash_into_value_timeseries` | Merged via `merge_fd_bank_into_value_timeseries` |
| FD create | Not used for opening debit | `FD_OPENING` debit on linked bank account |

---

## 4. Portfolio ownership (future rules)

### 4.1 Design intent

Bank accounts used for **investment activity** (FD funding, included bank cash in portfolio value) should be linked to **exactly one portfolio**.

| Rule | Detail |
|------|--------|
| **BankAccount.portfolio** | **Future field** (nullable). Required when account is flagged for investment use or when creating FDs. |
| **FD portfolio derivation** | **Future:** `FixedDeposit.portfolio` defaults from `bank_account.portfolio` on create; user cannot silently pick a different portfolio. |
| **Consistency** | FD portfolio must equal bank account portfolio when both are set. |
| **Ambiguous accounts** | Accounts whose movements/FDs span multiple portfolios remain **unassigned** or **blocked from inclusion** until user resolves or portfolio-specific sub-balances exist (FD-ACC-7 conservative rule continues until then). |
| **Non-investment bank accounts** | Salary/generic savings with no portfolio link remain user-scoped; optional `portfolio_id` on manual movements for reporting only (current behavior). |

### 4.2 Current state (post CASH-UNIFY-2)

- `BankAccount.portfolio` nullable FK exists; create/update API accepts `portfolio_id`.
- `portfolio_assignment_status` on bank account reads: `ASSIGNED` / `UNASSIGNED` / `AMBIGUOUS` (from FK + FD/movement signals).
- **FD create derives `FixedDeposit.portfolio` from `bank_account.portfolio`**; unassigned/ambiguous banks and conflicting `portfolio_id` are rejected (**400**).
- Legacy FD rows with portfolio ≠ bank account portfolio remain readable; API exposes `portfolio_mismatch_warning` (no auto-rewrite).
- FD-ACC-7 bank cash inclusion still uses movement/FD association inference when `portfolio` unset.

### 4.3 Enforcement timeline

| Phase | Behavior |
|-------|----------|
| **Today** | Independent FD/bank portfolio pick allowed; inclusion uses inference |
| **CASH-UNIFY-1** | Add `BankAccount.portfolio` (nullable); read APIs expose ownership; inference backfill |
| **CASH-UNIFY-2** | **Done** — FD create derives portfolio from bank account; validate match on write |
| **CASH-UNIFY-3+** | UI reflects ownership; ambiguous accounts prompt assignment |

---

## 5. Future Cash tab — “Cash / Liquid Holdings”

**Target phase:** CASH-UNIFY-3 (backlog `004-cash-unify-3.md`). **Design only here** — no UI changes in CASH-UNIFY-0.

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
| Per-portfolio | Per bank account; **future:** filtered by portfolio ownership |

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

- **New FDs:** `portfolio` derived from `bank_account.portfolio`; reject create if bank account unassigned/ambiguous or user-supplied portfolio differs.
- **Existing FDs:** If FD.portfolio ≠ bank account portfolio, **do not auto-change**. Read-only `portfolio_mismatch_warning` in API; assign bank account in Settings → Bank Accounts.
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
| **CASH-UNIFY-1** | Bank account portfolio ownership + unified read API | [002-cash-unify-1.md](./backlog/002-cash-unify-1.md) | 001 | **Done** ✓ |
| **CASH-UNIFY-2** | FD portfolio derived from bank account | [003-cash-unify-2.md](./backlog/003-cash-unify-2.md) | 002 | Write validation + backfill flags |
| **CASH-UNIFY-3** | Unified Cash page UI | [004-cash-unify-3.md](./backlog/004-cash-unify-3.md) | 002 (overview API); 003 recommended | Frontend |
| **CASH-UNIFY-4** | Terminology, display-currency totals, stabilization | [005-cash-unify-4.md](./backlog/005-cash-unify-4.md) | 003 | Read API + docs + tests |
| **CASH-UNIFY-5** | Broker ↔ bank transfer workflow | *Deferred* | 004 | Optional future epic |
| **CASH-UNIFY-6** | Physical / offline cash account | *Deferred* | — | Optional future account type |

### 8.2 Phase summaries

**CASH-UNIFY-1 — Bank account portfolio ownership + read API (implemented 2026-06-24)**

- Add nullable `BankAccount.portfolio` FK + migration.
- Inference backfill command (dry-run default) per §6.1.
- `GET /api/v1/cash/overview` (or equivalent): `broker_cash`, `bank_cash`, `totals`; each row tagged `ledger_type: PORTFOLIO | BANK`.
- Bank account APIs expose `portfolio_id`, assignment status.
- Document in `api-design.md`; `fetchCashOverview` in `api.js` (no page UI required).

**CASH-UNIFY-2 — FD portfolio derived from bank account**

- FD create: set `portfolio` from `bank_account.portfolio`; reject mismatch/unassigned bank account.
- FD create UI: portfolio field read-only or hidden when bank account selected.
- Existing FD mismatch → warning, no silent rewrite.
- Tests for create validation and inference edge cases.

**CASH-UNIFY-3 — Unified Cash page UI**

- Cash page sections: Broker Cash, Bank Cash, Total Cash (§5).
- Consume overview API; preserve existing broker write flows.
- Links to Settings for bank movement management.
- Vitest updates; `page-layouts.md` / `frontend-design.md`.

**CASH-UNIFY-4 — Terminology, display-currency, stabilization**

- Display-currency converted totals on overview + Cash page (cached FX; warnings when unavailable).
- Allocation/summary copy: clarify Broker vs Bank Cash buckets.
- Regression tests (`make test-critical`); docs audit; epic changelog closure.
- Resolve MVP deferred item: “Display-currency cash totals on `/cash`”.

**CASH-UNIFY-5 — Broker ↔ bank transfer (deferred)**

- Product decision: user-initiated paired legs (bank withdrawal + broker deposit) or manual double-entry guidance only.
- Likely overlaps [CASH-CORR-1](./backlog/012-cash-corr-1.md) reconciliation UX.
- **Not scheduled** in current backlog index.

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

## 10. Open questions (deferred to implementation phases)

| Question | Deferred to |
|----------|-------------|
| Required vs optional `BankAccount.portfolio` for non-FD accounts | CASH-UNIFY-1 product review |
| Block FD create vs warn when bank account unassigned | CASH-UNIFY-2 |
| Display-currency total when partial FX unavailable | CASH-UNIFY-4 |
| Paired broker-bank transfer API shape | CASH-UNIFY-5 |
| Portfolio-specific bank sub-balances for multi-portfolio accounts | Post CASH-UNIFY-4 / CASH-CORR-1 |

---

## 11. References

- Broker cash spec: [cash-ledger.md](./cash-ledger.md)
- Bank ledger + FD accounting: [fixed-deposits-accounting.md](./fixed-deposits-accounting.md) § A (relationship to portfolio cash)
- Product rules index: [product-rules.md](./product-rules.md) § A, § I (bank cash)
- Backlog operating guide: [backlog/README.md](./backlog/README.md)
