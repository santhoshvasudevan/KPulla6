# Product Rules — KPulla6 (Portfolio Insight)

**Purpose:** Single index of MVP product rules. Deep specifications live in linked docs — do not duplicate them here.

**Canonical deep docs:** [cash-ledger.md](./cash-ledger.md) · [cash-unification.md](./cash-unification.md) · [architecture.md](./architecture.md) · [api-design.md](./api-design.md) · [api-contracts.md](./api-contracts.md) · [frontend-design.md](./frontend-design.md) · [decisions.md](./decisions.md) · [mvp-release-checklist.md](./mvp-release-checklist.md)

**Agent rules:** [AGENTS.md](agents.md) · [Cash Ledger Cursor rule](cursor-rules/320-cash-ledger.md)

---

## A. Cash Ledger rules

| Rule | Summary |
|------|---------|
| Cash is not an investment asset | Cash is a **portfolio balance component**. Stocks and mutual funds are investment assets (FIFO, Metric Sheet, Compare). See [cash-ledger.md §1](./cash-ledger.md). |
| Native-currency balances | Ledger balances are stored **per portfolio, per native currency**. Do not collapse ledger rows into display currency internally. |
| No implicit FX conversion | Display FX uses cached `FXRate` for **presentation only**. No live FX on read paths. |
| Same-currency BUY funding | When `cash_aware_enabled=true`, **BUY** must be funded from ledger cash in the **transaction currency** only. |
| No cross-currency BUY funding | USD cash must **not** automatically fund an EUR purchase (or any other currency pair). |
| Cash in portfolio analytics | Cash is included in **current value**, **allocation**, **value history**, **portfolio XIRR**, **portfolio TWROR**, and **cumulative return** (Cash-6+). |
| Cash excluded from investment analytics | Cash is **not** an Asset Detail Metric Sheet subject and **not** a Compare subject. |
| **Dual ledger (broker + bank)** | **Broker cash** (`CashLedgerEntry`) and **bank cash** (`CashMovement`) are **separate ledgers** — do not merge storage or auto-create cross-ledger entries. Unified at portfolio/UI level only. See [cash-unification.md](./cash-unification.md). |

---

## B. Cash-aware vs legacy portfolios

| Mode | Behavior |
|------|----------|
| **New portfolios / registration default** | `cash_aware_enabled=true` by default (Cash-4A.1). |
| **Existing portfolios** | May remain **legacy** (`cash_aware_enabled=false`) until the user explicitly enables cash-aware mode (Settings, Cash page, or `PUT /portfolios/{id}`). |
| **Legacy** | BUY/SELL treated as external flows for portfolio-level TWROR/cumulative return; no settlement enforcement. |
| **Cash-aware** | Linked `BUY_SETTLEMENT` / `SELL_SETTLEMENT`; portfolio external flows from **cash ledger** (`CASH_DEPOSIT`, `CASH_WITHDRAWAL`, unlinked `ADJUSTMENT`, transfers at single-portfolio scope). |

Do **not** bulk-enable legacy portfolios without per-portfolio user confirmation.

**After enabling cash-aware on a legacy portfolio:** Bulk Cash Entries / manual deposits record funding; they do **not** create historical `BUY_SETTLEMENT` / `SELL_SETTLEMENT` rows. Run `manage.py sync_cash_settlements` (dry-run, then `--apply` after `make backup-db`) — see [cash-ledger.md § CASH-HIST-1](./cash-ledger.md).

---

## C. Transaction and settlement rules

| Event | Rule |
|-------|------|
| Stock/MF transactions | Investment events in `transactions`; source of truth for holdings and asset analytics. |
| Cash ledger entries | Cash events in `cash_ledger_entries`; deposits, withdrawals, settlements, transfers. |
| **BUY** | Creates negative `BUY_SETTLEMENT` linked to transaction (cash-aware). |
| **SELL** | Creates positive `SELL_SETTLEMENT` = calculated proceeds (`qty × price − fees` or MF rules). Optional `actual_cash_received` creates negative `TAX_WITHHELD` for the difference; **net cash** = actual received (cash-aware). |
| **STOCK_SPLIT** | No cash movement. |
| **Mutual fund BUY/SELL** | Settlement uses `paid_value`; ledger **`date` = `investment_date`** (not `nav_date`). |
| Protected rows | `BUY_SETTLEMENT`, `SELL_SETTLEMENT`, `TAX_WITHHELD`, `TRANSFER_IN`, `TRANSFER_OUT`, FX conversion legs, any row with `linked_transaction_id` or `transfer_group_id` — change via transaction or transfer APIs only. |
| Manual cash rows | `CASH_DEPOSIT` / `CASH_WITHDRAWAL` editable via `PUT`/`DELETE /cash/ledger/{id}` only when unlinked and **future-impact validation** passes. |

Settlement sync: `backend/transactions/cash_settlement.py` (atomic with transaction writes).

---

## D. Portfolio return rules

| Topic | Rule |
|-------|------|
| Cash-aware portfolio XIRR | External flows: `CASH_DEPOSIT`, `CASH_WITHDRAWAL`, allowed unlinked `ADJUSTMENT`; terminal includes **holdings + cash**. See [cash-ledger.md §6](./cash-ledger.md). |
| Cash-aware TWROR / cumulative return | Daily **cash-inclusive** portfolio value; external flows from cash ledger; **BUY/SELL internal** at portfolio level. |
| Asset-level analytics | Remain **investment-only** (asset BUY/SELL flows for asset XIRR; not cash ledger). |
| Foreign-currency cash | Multi-currency cash can produce **FX-driven display-currency returns** even without stock/MF activity — not a bug. |
| All-scope transfers | Same-currency transfer **nets to zero** in aggregated external flows; cross-currency uses user-entered amounts (may not net to zero in display currency). |

---

## E. Metric Sheet rules

| Rule | Detail |
|------|--------|
| Primary stats input | **TWROR-style daily returns** from cash-flow-adjusted value series — not raw price-only returns, not XIRR as base input. |
| XIRR scope | **Full-scope** (inception through today) in Metric Sheet responses (`xirr_scope: "full_scope"`). |
| Benchmark metrics | Strict **date alignment** on daily return windows; missing benchmark → null metrics + warnings. |
| React | Displays backend-provided values only — no Sharpe, beta, volatility, drawdown, or periodic-return **calculation** in the client. |

See [architecture.md § Quantitative Statistics](./architecture.md).

---

## F. Transfer rules

| Rule | Detail |
|------|--------|
| Same-currency transfer | `TRANSFER_OUT` / `TRANSFER_IN` with equal amounts; **neutral at all-scope** for TWROR/XIRR and `current_value`. |
| Cross-currency transfer | User enters **source amount** and **target amount** separately; **no FX provider lookup**; no auto-calculated target. |
| Implied rate | `target_amount / source_amount` in API response — **informational only**; not used for valuation or BUY funding. |

Historical funding for legacy gaps: manual deposits/withdrawals or **Bulk Cash Entries** — not the removed backfill wizard.

---

## G. Frontend rules

| Surface | Responsibility |
|---------|----------------|
| React | **Format** values (currency, percent, labels); must **not** calculate financial metrics, cash balances, future-impact, or backfill values. |
| Warnings / errors | Display backend `warnings`, shortfall payloads, and **409** future-impact structures — do not simulate fixes client-side. |
| `/cash` | Cash balances, ledger, deposit/withdrawal, transfer, bulk entries, manual edit/delete. |
| `/transactions` | Asset transaction table, unified Add modal (Cash \| Stock \| MF), CSV import. Cash **writes** via `/cash/*`; cash **ledger edit** on `/cash` only. |

---

## H. Data-safety rules

| Rule | Detail |
|------|--------|
| Live dev database | Treat Postgres (`portfolio_insight_kpulla6`) as production-like. |
| Bulk enable | No bulk-flip of `cash_aware_enabled` without explicit user action per portfolio. |
| Destructive ops | No `flush`, `TRUNCATE`, bulk transaction delete, or `make db-reset` without **backup + safety check + user approval**. |
| Tests | Use `DJANGO_TEST_USE_SQLITE=1` / `make test-backend` for automated tests — not live Postgres unless the user asks. |
| Migrations / real-data scripts | Run `make backup-db` and `make db-safety-check` before and after. |

Full protocol: [data-safety.md](./data-safety.md) · [workflows.md](./workflows.md).

---

## I. Bank cash & cash unification (CASH-MODEL-REFINE-0)

| Rule | Summary |
|------|---------|
| Bank account independence | `BankAccount` is a real-world account; `BankAccount.portfolio` is a **current portfolio link**, not ownership. |
| Bank ledger separate | Bank cash truth is `CashMovement` on `BankAccount` — not `CashLedgerEntry`. |
| Broker vs bank in UI | **Broker Cash** = securities buying power; **Bank Cash** = linked bank balances. Cash tab shows both ([cash-unification.md §5](./cash-unification.md)). |
| Linked vs unlinked | Linked → bank cash in portfolio **Bank Cash**; unlinked → external/unassigned (overview `include_unassigned`). |
| Link/delink | Classification/inclusion only — **no** ledger movements. |
| Transfer vs correction | **Transfer** = actual movement between ledgers (CASH-UNIFY-5). **Correction** = audited fix for mistaken entry (CASH-CORR-1). |
| FD funding — one source | Each FD uses **one** funding path: **linked bank account** OR **broker cash** from portfolio. **No** partial bank+broker split. |
| FD funding — today | **Bank path only** (`FD_OPENING` on bank ledger). Unlinked bank cannot fund FD. Broker-cash path **not implemented**. |
| FD portfolio (bank path) | Explicit `portfolio_id` at create; bank account is funding source only (CASH-MODEL-REFINE-1). |
| Inclusion (today) | `include_in_portfolio_value` opt-in; conservative single-portfolio inference (FD-ACC-7). |
| No cross-ledger auto-writes | Backfill and link/delink set FKs/flags only — no automatic transfer legs (CASH-UNIFY-5 deferred). |
