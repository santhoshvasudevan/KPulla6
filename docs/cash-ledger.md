# Cash Ledger — Design & Migration (Cash-0)

**Status:** Cash-1 through Cash-7D **done**; **Cash-8A** same-currency and **Cash-8B** user-entered cross-currency portfolio transfers **done**. Transfer fees and same-portfolio FX conversion remain deferred.

**Related:** [architecture.md](./architecture.md) · [database.md](./database.md) · [api-design.md](./api-design.md) · [frontend-design.md](./frontend-design.md) · [data-safety.md](./data-safety.md) · [cash-unification.md](./cash-unification.md) · Cursor rule [`.cursor/rules/320-cash-ledger.mdc`](../.cursor/rules/320-cash-ledger.mdc)

---

## 1. Product mental model

| Concept | Role |
|---------|------|
| **Cash** | Portfolio **balance component** — money held in the portfolio’s cash account(s), tracked **per portfolio** and **per currency**. |
| **Stock / ETF** | **Investment asset** — valued from cached `HistoricalPrice` + FIFO holdings. |
| **Mutual fund** | **Investment asset** — valued from cached NAV + folio-scoped FIFO. |

### Included in portfolio analytics (cash-aware mode)

- **Current value** — cash balances converted to display currency (presentation) and summed with stock + MF values.
- **Value history** — daily cash balances merged into portfolio timeseries.
- **Allocation** — cash appears as labeled slices (e.g. Cash EUR, Cash INR), not as an investment asset class for performance attribution.
- **Buying-power checks** — manual BUY and CSV import validate available cash in the transaction currency before settlement.

### Excluded from investment-style analytics

Cash must **not** be analyzed like a stock or mutual fund:

- No Asset Metric Sheet at cash “symbol” level (Sharpe, beta, alpha, drawdowns, etc.).
- No Compare page subject of type `cash:…`.
- No FIFO cost basis, realized/unrealized P/L, or split logic on cash rows.
- React remains **API-driven** — no cash balance, TWROR, XIRR, or FX math in the frontend.

**Transactions remain the source of truth** for investment activity; the **cash ledger** is the source of truth for cash balance movement (deposits, withdrawals, settlements, transfers).

---

## 2. Cash ledger model (Cash-1 implemented)

**App:** `backend/cash/` — portfolio balance infrastructure separate from `transactions` investment rows.

**`linked_transaction`:** `PROTECT` — prevents deleting a transaction that still has settlement ledger rows (integrity for cash-aware mode).

**Signed `amount`:** positive increases cash, negative decreases; `clean()` enforces expected sign per `entry_type` (`ADJUSTMENT` may be either).

### `CashLedgerEntry` (Django model — `cash_ledger_entries`)

| Field | Type / notes |
|-------|----------------|
| `id` | Primary key |
| `user` | Optional direct FK to `auth.User`, **or** derived only through `portfolio.user` (implementation choice in Cash-1; queries always scope by authenticated user’s portfolios) |
| `portfolio` | FK → `Portfolio` (`PROTECT`) |
| `date` | `DateField` — ledger effective date |
| `currency` | ISO 4217 code (3 chars) — **native cash account currency** for this entry |
| `entry_type` | Enum — see below |
| `amount` | `DecimalField` — signed convention: **positive increases cash**, **negative decreases cash** (document consistently in Cash-1 implementation) |
| `source_of_funds` | Optional enum/string — external deposit source category (see open questions) |
| `linked_transaction` | Optional FK → `Transaction` — BUY/SELL/DIVIDEND settlement link |
| `transfer_group` | Optional FK → `CashTransferGroup` — portfolio transfer or FX conversion pair |
| `note` | Optional text |
| `created_at` / `updated_at` | Audit timestamps |

**Indexes (planned):** `(portfolio, currency, date)`, `(portfolio, date)`, `(linked_transaction)` where not null.

### Entry types

| `entry_type` | Effect on cash | External flow (single portfolio) | Notes |
|--------------|----------------|----------------------------------|-------|
| `CASH_DEPOSIT` | Increase | **Contribution** | Money from outside the portfolio (bank, broker funding) |
| `CASH_WITHDRAWAL` | Decrease | **Withdrawal** | Money leaving the portfolio to the user |
| `BUY_SETTLEMENT` | Decrease | **Internal** | Cash used to pay for a BUY (`linked_transaction` → BUY) |
| `SELL_SETTLEMENT` | Increase | **Internal** | Calculated SELL proceeds credited to cash (audit gross) |
| `TAX_WITHHELD` | Decrease | **Internal** | Tax withheld / broker adjustment when `actual_cash_received` &lt; calculated proceeds |
| `DIVIDEND_CASH` | Increase | Internal or external depending on product rule | Cash dividend credited (may link to `DIVIDEND` txn) |
| `INTEREST` | Increase | Usually internal | Broker interest on cash balance |
| `FEE` | Decrease | Internal | Cash fees (account, wire) |
| `TAX` | Decrease | Internal | Withholding or tax payment from cash |
| `ADJUSTMENT` | ± | Internal | User-confirmed correction / reconciliation |
| `TRANSFER_OUT` | Decrease | **Withdrawal** (source portfolio) | To another portfolio — Cash-8A same-currency implemented |
| `TRANSFER_IN` | Increase | **Contribution** (target portfolio) | From another portfolio — Cash-8A same-currency implemented |
| `FX_CONVERSION_OUT` | Decrease | Internal | Leg of same-portfolio FX conversion |
| `FX_CONVERSION_IN` | Increase | Internal | Paired leg; linked via `transfer_group` |

**Clarifications:**

- **`BUY_SETTLEMENT`** reduces cash by settlement amount (typically `qty × price + fees` in transaction currency).
- **`SELL_SETTLEMENT`** increases cash by **calculated** proceeds (typically `qty × price − fees`).
- **`TAX_WITHHELD`** decreases cash by `calculated − actual_cash_received` when the user enters a lower actual received amount on SELL. Net cash impact = `actual_cash_received`. Tax reporting is a future feature; the ledger row is the foundation.
- **`CASH_DEPOSIT` / `CASH_WITHDRAWAL`** are **external** portfolio flows for TWROR/XIRR at portfolio scope.
- **`TRANSFER_OUT` / `TRANSFER_IN`:** external for the **individual** portfolio’s TWROR/XIRR; **neutral** when `portfolio_scope=all` (internal movement between user portfolios).

### `CashTransferGroup` (Django model — `cash_transfer_groups`; write API Cash-8A)

Implemented in Cash-1 for schema linkage; **same-currency** HTTP transfer endpoint in Cash-8A.

| Field | Notes |
|-------|--------|
| `source_portfolio` | FK → `Portfolio` |
| `target_portfolio` | FK → `Portfolio` (same user) |
| `source_currency` | ISO code |
| `target_currency` | ISO code |
| `source_amount` | Decimal in source currency |
| `target_amount` | Decimal in target currency |
| `user_rate` | Optional explicit rate used (`target_amount / source_amount` or stored separately) |
| `fees` | Decimal — currency documented in open questions |
| `date` | Transfer date |
| `note` | Optional |

Same-currency transfer: one `CashTransferGroup`, `TRANSFER_OUT` + `TRANSFER_IN` entries. Cross-currency: add `FX_CONVERSION_OUT` / `FX_CONVERSION_IN` on source portfolio (or split across portfolios per Cash-8 design).

---

## 3. Supported cash currencies

**20 currencies** in `cash.constants.SUPPORTED_CASH_CURRENCIES`:

`EUR`, `USD`, `INR`, `GBP`, `CHF`, `JPY`, `CNY`, `CAD`, `AUD`, `HKD`, `SGD`, `KRW`, `BRL`, `MXN`, `ZAR`, `SEK`, `NOK`, `DKK`, `PLN`, `AED`

(First five overlap `AppSettings.display_currency` / portfolio `base_currency` choices.)

### Rules

- **Cash balances are currency-specific** — running balance = sum of ledger entries in that currency; no silent merging of EUR + USD into one native balance.
- **Display currency conversion is presentation only** — summary, allocation, and charts convert each currency’s cash to `display_currency` using **cached `FXRate` only** (same-date + 7-day fill as existing summary/performance).
- **Do not internally collapse all cash into display currency** for ledger storage, enforcement, or buying-power checks. Buying-power for a USD BUY uses **USD cash balance**, not EUR cash converted on the fly unless product explicitly adds cross-currency funding (out of MVP).
- **Same-currency funding (Cash-4E, enforced):** cash-aware **BUY** (stock or MF) requires ledger cash in the **transaction currency** only. Another currency’s balance is **not** consumed implicitly. No automatic FX conversion on purchase; **Cash FX conversion** (`FX_CONVERSION_*` entries, Cash-8) is **deferred**.
- **Insufficient BUY:** API **400** with `required`, `available`, `shortfall`, `currency` (all in transaction currency). UI directs user to add or edit cash in that currency on `/cash` — not to convert another currency.

---

## 4. TWROR design impact

### Current (legacy, no cash ledger)

`portfolios/performance_service._build_external_flows` treats:

- **BUY** → positive external flow (contribution into portfolio value)
- **SELL** → negative external flow (withdrawal)

Portfolio value on BUY/SELL days still moves from holdings; flows neutralize double-counting in `period_return`:

\[
r_d = \frac{PV_d - F_d - PV_{d-1}}{PV_{d-1}}
\]

(`finance/twror.py` — `compute_twror_series`)

This models “money appears on BUY day” even when the user already held cash inside the broker account.

### Cash-aware TWROR / cumulative return (Cash-6C.2 — implemented)

| Event | TWROR external flow \(F_d\) |
|-------|------------------------------|
| `CASH_DEPOSIT` | Positive (contribution) |
| `CASH_WITHDRAWAL` | Negative (withdrawal) |
| Unlinked `ADJUSTMENT` | Signed ledger `amount` (±) |
| `BUY` + `BUY_SETTLEMENT` | **Zero** — internal cash → asset |
| `SELL` + `SELL_SETTLEMENT` | **Zero** — internal asset → cash |
| `STOCK_SPLIT` | Zero (unchanged) |
| `TRANSFER_*` (manual edit) / `FX_CONVERSION_*` / linked rows | Manual edit excluded; transfers created via `POST /cash/transfers` (Cash-8A) |

Daily portfolio value \(PV_d\) = **investment value + cash** (same series as `metric=value`, Cash-6B).

**Display currency vs native cash (cash-only portfolios):**

- When **all cash is in the same currency as `display_currency`** and there are **no investments**, portfolio XIRR, TWROR, and cumulative return should be **approximately 0** (deposits are external flows that match the cash-inclusive value series).
- When **cash is held in a currency different from `display_currency`**, cached **USD/EUR (etc.) FX movement** changes the display-currency value on days without deposits → TWROR and cumulative return may be **non-zero** even with no stocks/MF. Portfolio XIRR can also be non-zero because deposit flows and the terminal value use FX at **different dates** (multi-currency cash is not a bug; it is display-currency FX exposure).
- Example: USD cash deposits with `display_currency=EUR` and a rising USD/EUR rate produces positive TWROR/cumulative return and can produce ~9% XIRR on a cash-only book — **expected**, not stale transaction data.
- `display_currency=USD` with only USD cash → returns ≈ 0; EUR ledger rows without USD→EUR FX may be excluded from value/XIRR with warnings (partial portfolio).

**Implementation:** `portfolios/external_flows_service.py` (flows), `portfolios/performance_service.build_return_value_timeseries` (values), `finance/twror.compute_twror_series` (formula unchanged).

**Cumulative return:** \((PV_d + W_d - C_d) / C_d\) in percent points, with \(C_d\) / \(W_d\) from cash-aware external flows and \(PV_d\) cash-inclusive — aligned with Metric Sheet `economic_cumulative_return_fraction`.

### Worked example

1. **Deposit €1,000** (`CASH_DEPOSIT`) — PV rises €1,000; \(F_d = +1000\) → period return **0%**.
2. **Buy €1,000 stock** (`BUY` + `BUY_SETTLEMENT −1000`) — PV unchanged (cash down, holdings up); \(F_d = 0\) → period return **0%**.
3. **Stock marks to €1,100** — PV €1,100; no flow → \(r = (1100 - 1000) / 1000 = **10%**\) TWROR.

Legacy mode without cash ledger continues to treat step 2’s BUY as external contribution until the user enables cash-aware mode and records actual cash funding.

**Implementation note (future):** extend `_build_external_flows` (or parallel `build_cash_aware_external_flows`) in a service layer; keep formula in `finance/twror.py`.

---

## 5. XIRR design impact

### Portfolio-level XIRR (cash-aware — Cash-6C.1 implemented)

**Sign convention** (investor perspective, consistent with `finance/xirr.py`):

| Event | XIRR amount |
|-------|-------------|
| `CASH_DEPOSIT` / contribution | **Negative** (cash leaves investor) |
| `CASH_WITHDRAWAL` / withdrawal | **Positive** (cash returns to investor) |
| Terminal portfolio value | **Positive** (mark-to-market exit) |

Ledger signed amounts use deposit **+** / withdrawal **−**; external flows map as **`xirr_amount = −converted_ledger_amount`**.

- **External flows:** `CASH_DEPOSIT`, `CASH_WITHDRAWAL`, and **unlinked** `ADJUSTMENT` (manual reconciliation only).
- **External rows:** `CASH_DEPOSIT`, `CASH_WITHDRAWAL`, unlinked `ADJUSTMENT`, and **`TRANSFER_IN` / `TRANSFER_OUT`** (Cash-8A).
- **Excluded internal rows:** `BUY_SETTLEMENT`, `SELL_SETTLEMENT`, `TAX_WITHHELD`, `FEE`, `TAX`, `DIVIDEND_CASH`, `INTEREST`, `FX_CONVERSION_*`, rows with `linked_transaction`, and `transfer_group` rows that are not transfer legs (FX conversion).
- **Terminal value:** investment holdings **plus** cash balances in the calculation currency (cached FX, 7-day fill; missing FX → `xirr: null` + warning).
- **BUY/SELL transactions** are **not** portfolio-level external XIRR flows when `cash_aware_enabled=true`.

**Implementation:** `portfolios/xirr_service.py` (`compute_scope_xirr_detail`); shared by summary and Metric Sheet via `compute_scope_xirr`.

### Asset-level XIRR (unchanged principle)

- Asset-level XIRR may still use **asset BUY/SELL** cash flows — capital moving into/out of **that asset** is distinct from portfolio-level external funding.
- Compare and Asset Metric Sheet `xirr_scope: "full_scope"` behavior preserved for investment assets.

### Legacy behavior

- Portfolios in **legacy mode** (`cash_aware_enabled=false`) keep today’s XIRR: BUY negative, SELL positive, terminal = holdings only (cash in `current_value` but not in XIRR terminal).
- Toggling cash-aware mode requires explicit user action; historical funding via manual or bulk cash entries (§9).

### All Portfolios (`portfolio_scope=all`) — mixed mode (Cash-6C.1)

- Each active portfolio applies its own rule (cash-aware vs legacy).
- External flows are converted to the request **`display_currency`** and **aggregated by date** across portfolios.
- Terminal value = sum of per-portfolio holdings + cash in `display_currency`.
- **`TRANSFER_IN` / `TRANSFER_OUT`:** external at single-portfolio scope (Cash-8A); all-scope aggregation nets same-currency transfers to zero.

---

## 6. Manual transaction UX (planned)

On **manual BUY** (stock or MF):

1. Resolve **transaction currency** and **required cash** (e.g. `paid_value` for MF, `qty × price + fees` for stock).
2. Load **available cash** for `(portfolio, currency)` from ledger.
3. If **sufficient:** create `Transaction` + `CashLedgerEntry` `BUY_SETTLEMENT` (linked).
4. If **insufficient:** show confirmation dialog:
   - required cash, available cash, shortfall
   - recommended action: add missing cash deposit before purchase
   - `source_of_funds` selection for auto-deposit
5. If user **confirms:** create `CASH_DEPOSIT` (shortfall) → `BUY` → `BUY_SETTLEMENT` atomically.
6. If user **declines:** reject with clear insufficient-cash message.
7. **Default:** do not allow negative cash balances.

**SELL:** create `SELL` + `SELL_SETTLEMENT` (credit cash). Optional future: auto-withdraw vs keep in cash.

---

## 7. CSV import UX (planned)

Flow:

1. Upload CSV (existing `POST /transactions/import-csv` or dedicated preview endpoint).
2. **Pre-validate all rows in date order** (per portfolio + currency).
3. **Simulate** running cash balances; detect shortfalls before any insert.
4. Show **one import summary** (not row-by-row modals).

**Recommended default option (user must confirm before apply):**

> Auto-create cash deposits before purchases where cash is insufficient.

**Other options:**

- Reject rows with insufficient cash (strict).
- Import without cash validation (**legacy mode only** — explicit opt-in).

User confirmation required before auto-creating `CASH_DEPOSIT` rows. All-or-nothing atomic import preserved.

Suggested endpoint: `POST /api/v1/transactions/import-csv/preview-cash` (or equivalent aligned with import service) — see [api-design.md](./api-design.md).

---

## 8. Cash-aware BUY/SELL settlements (Cash-4A — implemented)

Gate: `portfolio.cash_aware_enabled == true` only. No auto-enable.

| Asset | BUY | SELL | Split / dividend |
|-------|-----|------|------------------|
| Stock/ETF | `BUY_SETTLEMENT` = −(qty×price+fees), date = `transaction.date` | `SELL_SETTLEMENT` = +(qty×price−fees); optional `TAX_WITHHELD` = −(calculated−actual) | No ledger row |
| Mutual fund | `BUY_SETTLEMENT` = −`paid_value`, date = **`investment_date`** | `SELL_SETTLEMENT` = +calculated proceeds; optional `TAX_WITHHELD` when `actual_cash_received` set, date = **`investment_date`** | N/A |

- Update/delete: settlement row updated or removed with the transaction; BUY updates re-check cash excluding the old settlement.
- Delete: settlement removed first; deleting a SELL settlement blocked if later cash would go negative.
- **TXN-AUDIT-2:** `PUT`/`DELETE /transactions/{id}` return structured **409** future-impact payload (`currency`, `earliest_negative_date`, `lowest_balance`, `affected_entries`) when settlement sync would break later balances — same shape as manual cash ledger edit/delete.
- **Legacy → cash-aware edit:** transactions created while legacy may gain a linked settlement on first `PUT` after enable; fails with **400** shortfall if funding is missing (no retroactive auto-deposit).
- Linked settlements remain **protected** from `PUT`/`DELETE /cash/ledger/{id}` (409).
- **Cash-6A (done):** Summary `current_value` and holdings `allocation` include native cash converted to `display_currency` via cached FX.
- **Cash-6B (done):** Summary timeseries and `GET /portfolio/performance?metric=value` include cash.
- **Cash-6C.1 (done):** Portfolio-level XIRR uses cash ledger external flows when cash-aware; legacy portfolios unchanged.
- **Cash-6C.2 (done):** Cash-aware TWROR / cumulative_return (cash-inclusive daily values + ledger external flows).
- **Cash-6D (done):** Regression tests for deposit/BUY/growth/sell/withdrawal/mixed-scope; read-only `backend/scripts/diagnose_cash_aware_returns.py` (use `DJANGO_TEST_USE_SQLITE=1` or an approved DB).

---

## 9. Legacy mode and historical cash funding

### Principles

- **Existing transactions remain undisturbed** — no automatic rewrite of historical BUY/SELL.
- **Cash enforcement** applies only when **cash-aware mode** is enabled for a portfolio.
- Portfolios may stay in **legacy mode** indefinitely until the user explicitly enables cash-aware mode.
- **Historical funding** uses **actual** deposit/withdrawal amounts — manual entries or **Bulk Cash Entries** schedules — not shortfall simulation. Never silent mass insert on production-like dev DB without explicit approval ([data-safety.md](./data-safety.md)).

### Portfolio flag (Cash-4A.1)

`Portfolio.cash_aware_enabled` — **existing rows** keep stored value (typically `false`). **New** portfolios and registration defaults are created with `true` via application services. Explicit `POST` with `false` creates legacy mode.

**Enable legacy portfolio:** Settings → Portfolios → **Enable cash-aware**, or Cash/Transactions when a single portfolio is selected → **Enable cash-aware mode** (confirmation). API: `PUT /api/v1/portfolios/{id}` with full portfolio fields and `"cash_aware_enabled": true` (tester portfolio id 5). All Portfolios scope shows a per-portfolio note only — no global enable button.

**Important (CASH-HIST-1):** Flipping `cash_aware_enabled` to `true` does **not** automatically create `BUY_SETTLEMENT` / `SELL_SETTLEMENT` rows for transactions that existed while the portfolio was legacy. New writes sync settlements; historical rows need a one-time repair.

| Step | Purpose |
|------|---------|
| 1. Bulk Cash Entries / manual deposits | Record **funding events** (money entering the portfolio) |
| 2. `sync_cash_settlements` | Record **historical BUY/SELL cash movements** linked to existing transactions |
| 3. `diagnose_settlement_integrity.py` | Confirm zero `missing_settlement` issues |

Both steps are required for accurate historical cash balance, Value History (`metric=value`), and cash-aware TWROR/cumulative return.

```bash
make backup-db
make db-safety-check
cd backend
.venv/bin/python manage.py sync_cash_settlements --portfolio-id PORTFOLIO_ID          # dry-run (default)
.venv/bin/python manage.py sync_cash_settlements --portfolio-id PORTFOLIO_ID --apply # after backup
```

- Dry-run by default; `--apply` writes rows (atomic, idempotent).
- One portfolio per run; portfolio must be `cash_aware_enabled=true` unless `--allow-legacy`.
- Skips `STOCK_SPLIT`; does not duplicate existing settlements; reports mismatches without silent overwrite.
- Blocks `--apply` when simulated historical balance would go negative — add deposits first, then re-run.
- Implementation: `transactions/cash_settlement_sync.py`, management command `sync_cash_settlements`.

### Scalable portfolio historical funding example

| Portfolio | Scalablefolio |
|-----------|----------------|
| Currency | EUR |
| 2022-05-01 | Opening cash deposit **€12,500** (`once`) |
| 2022-05-01 | Monthly contribution **€900** |
| 2022-06-01 … 2022-12-01 | **€900** monthly |
| 2023-01-01 … 2023-12-01 | **€945** monthly |
| 2024-01-01 … 2024-12-01 | **€992** monthly |
| 2025-01-01 … 2025-12-01 | **€1,042** monthly |

Enter via `/cash` → **Add Bulk Cash Entries** (one schedule per amount/rate period) or individual deposit modals. Dates should match actual bank/broker transfer dates.

**Cash-7D (done):** `POST /api/v1/cash/bulk-entries/preview` and `apply` create manual deposit/withdrawal schedules (`once`, `monthly`). Duplicate identical manual rows skipped on apply; withdrawal schedules blocked if future balance would go negative.

**Removed (Cash-7A/7B/7C):** Shortfall backfill preview/apply APIs and wizard — product direction changed; minimum-deposit simulation before historical BUYs is not supported.

### IndianMF historical funding approach

1. Enter **INR `CASH_DEPOSIT`** rows (manual or bulk schedule) for actual funding before historical MF/stock purchases.
2. Enable cash-aware mode when ready.
3. Run `sync_cash_settlements --portfolio-id …` (dry-run, then `--apply` after backup) to backfill historical BUY/SELL settlements.
4. **Future purchases require sufficient INR cash** (or confirmed auto-deposit in TransactionModal).

---

## 9. Portfolio-to-portfolio transfers

### Same currency (Cash-8A — implemented)

- `POST /api/v1/cash/transfers` with `source_portfolio_id`, `target_portfolio_id`, `date`, `currency`, `amount`, optional `note`.
- Source and target must be different active portfolios owned by the current user.
- Source must have sufficient same-currency cash as of `date`; future-impact validation blocks transfers that would make later source balances negative.
- Creates one `CashTransferGroup` (`source_currency = target_currency`, `user_rate = 1`, `fees = 0`) and paired ledger rows atomically:
  - Source: `TRANSFER_OUT` (−amount)
  - Target: `TRANSFER_IN` (+amount)
- Transfer rows are **system-protected** (no manual edit/delete via `/cash/ledger/{id}`).
- **Single-portfolio TWROR/XIRR:** `TRANSFER_OUT` = external withdrawal; `TRANSFER_IN` = external contribution (signed ledger `amount`).
- **All Portfolios scope:** per-portfolio external flows are summed in display currency; same-currency transfer on the same date **nets to zero** — no change to all-scope `current_value`, TWROR, or XIRR (validated Cash-8A-QA).

### Cross-currency (Cash-8B — implemented)

- Request: `source_currency`, `source_amount`, `target_currency`, `target_amount` (+ portfolios, date, optional note).
- **No market FX lookup** — user enters amount sent and amount actually received.
- Creates `CashTransferGroup` with differing currencies/amounts; `user_rate` = `target_amount / source_amount` (stored; informational).
- Ledger: `TRANSFER_OUT` −source_amount in source currency; `TRANSFER_IN` +target_amount in target currency.
- `implied_rate` in API response is informational only.
- Source sufficiency/future-impact validated in **source currency only**; target portfolio needs no prior balance in target currency.
- **All Portfolios:** not forced neutral — display totals follow user-entered amounts converted for presentation; may differ from cached FX.

### Deferred

- Transfer fees (separate `FEE` rows or `fees` on group)
- Same-portfolio currency conversion (`FX_CONVERSION_*` legs)

---

## 10. Portfolio value integration (planned)

### Current value

```
portfolio_current_value =
  sum(stock/ETF holdings at cached prices, display-converted)
+ sum(MF holdings at cached NAV, display-converted)
+ sum(cash balances per currency, display-converted via cached FX only)
```

Implemented in `portfolios/summary_service.py`, `portfolios/performance_service.py`, and `cash/services.py` (**Cash-6A** headline `current_value` + allocation; **Cash-6B** value history for `metric=value` and summary timeseries).

### Value history

- Daily investment asset values (existing split-adjusted lot snapshots + prices/NAV).
- Daily **cash balance** per currency from ledger as-of each date, converted to `display_currency` for `metric=value` and summary timeseries (**Cash-6B**).
- Merge and convert to `display_currency` for timeseries points.
- **No live FX** on read — same `FXRate` rules as Phase 9/10.
- **`metric=value`**, **`metric=twror`**, and **`metric=cumulative_return`** use cash-inclusive values and cash-aware external flows when `cash_aware_enabled=true` (Cash-6C.2). Legacy portfolios remain investment-only for TWROR/cumulative return.

### Allocation

- Slices: `Cash EUR`, `Cash INR`, `Cash USD`, etc. (native currency in label).
- Cash allocation % = cash display value / total portfolio display value.
- **Not** included in investment performance tables or Metric Sheet risk/return series.

---

## 11. API roadmap (planned — not implemented)

All endpoints require **authenticated session** and scope to the **current user’s portfolios** only (`401`/`403` otherwise). Follow existing `portfolio_scope` / `portfolio_id` validation where applicable.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/cash/balances` | Per-portfolio (or scope) cash balances by currency; display-converted totals optional via `display_currency` |
| GET | `/api/v1/cash/ledger` | Paginated ledger entries; filters: portfolio, currency, date range, `entry_type` |
| POST | `/api/v1/cash/deposits` | Create `CASH_DEPOSIT` |
| POST | `/api/v1/cash/withdrawals` | Create `CASH_WITHDRAWAL` |
| POST | `/api/v1/cash/transfers` | Portfolio transfer (same or cross currency) |
| POST | `/api/v1/cash/bulk-entries/preview` | **Done** (Cash-7D) — schedule preview |
| POST | `/api/v1/cash/bulk-entries/apply` | **Done** (Cash-7D) — confirmed bulk manual entries |
| POST | `/api/v1/transactions/import-csv/preview-cash` | CSV cash simulation + shortfall report (or nested under import service) |

Preserve existing `/api/v1` contracts; cash endpoints are **additive**. Detail shapes documented in [api-design.md](./api-design.md) when implemented.

---

## 12. Implementation phases

| Phase | Scope | Status |
|-------|--------|--------|
| **Cash-0** | Design docs only (`cash-ledger.md`, doc cross-links) | **This document** |
| **Cash-1** | Schema + migrations + `CashLedgerEntry` / `CashTransferGroup`; `Portfolio.cash_aware_enabled`; `finance/cash.py`; `cash/services.py` | **Done** |
| **Cash-2** | Cash balance read APIs (`GET /cash/balances`, `GET /cash/ledger`); `cash_aware_enabled` on portfolio API | **Done** |
| **Cash-3A** | `POST /cash/deposits`, `POST /cash/withdrawals` (backend only) | **Done** |
| **Cash-3B** | Manual cash deposit/withdrawal UI (`/cash`) | **Done** |
| **Cash-3D** | Edit/delete manual `CASH_DEPOSIT` / `CASH_WITHDRAWAL` (`PUT`/`DELETE /cash/ledger/{id}`) | **Done** |
| **Cash-4D** | Future-impact validation on manual edit/delete; structured `affected_entries`; `/cash` UI | **Done** |
| **Cash-3G** | Unified Add Transaction modal on `/transactions` (Cash / Stock / MF); cash writes via `/cash/*` only | **Done** |
| **Cash-4A** | Cash-aware BUY/SELL settlements on `POST/PUT/DELETE /transactions` when `cash_aware_enabled` | **Done** |
| **Cash-4A.1** | New portfolios / registration default `cash_aware_enabled=true`; existing rows unchanged | **Done** |
| **Cash-4A.2** | UI: cash-aware status + enable per portfolio (`CashAwarePortfolioStatus`, Settings table) | **Done** |
| **Cash-4B** | Frontend insufficient-cash UX on stock/MF transaction modal | **Done** — `TransactionApiError`, `CashShortfallDisplay`, BUY shortfall in `TransactionModal` |
| **Cash-4E** | Same-currency BUY enforcement verification + purchase shortfall guidance | **Done** — backend tests (USD ignored for EUR BUY); UI same-currency copy; no implicit FX |
| **Cash-4C** | Manual BUY add missing cash + continue (`TransactionModal`) | **Done** — user-confirmed deposit in shortfall currency, then retry BUY; no implicit FX |
| **Cash-5** | CSV import cash shortfall preview + confirmed deposits | **Done** — `preview-cash`; import 409 without confirm; same-currency only |
| **Cash-6A** | Summary `current_value` + holdings `allocation`; exclude cash from Metric Sheet / Compare | **Done** |
| **Cash-6B** | Cash in performance value history / daily timeseries (`metric=value`, summary timeseries) | **Done** |
| **Cash-6C.1** | Portfolio-level XIRR (cash-aware external flows + terminal) | **Done** |
| **Cash-6C.2** | TWROR / cumulative_return cash-aware flows | **Done** |
| **Cash-6D** | Cash-aware return QA regression + `scripts/diagnose_cash_aware_returns.py` | **Done** |
| **Cash-7A/7B/7C** | Shortfall backfill preview/apply APIs + wizard | **Removed** |
| **Cash-7D** | Bulk cash entries schedule (`bulk-entries/preview` + `apply`; `/cash` wizard) | **Done** |
| **Bulk Cash Entries** | Quarterly/yearly frequencies (optional later) | Planned |
| **Cash-8A** | Same-currency portfolio transfer (`CashTransferGroup` + `/cash/transfers`) | **Done** |
| **Cash-8B** | User-entered cross-currency portfolio transfer | **Done** |
| **Cash-8C** | Transfer fees; same-portfolio FX conversion legs | Planned |
| **CASH-HIST-1** | Historical settlement backfill (`sync_cash_settlements`); Assets Overview cash balances card | **Done** |
| **CASH-UI-1** | Cash page full-width layout; ledger `details` API field + UI column | **Done** |

**Recommended next phase:** **Cash-8C** transfer fees; optional quarterly/yearly bulk frequencies.

---

## 13. Open questions

| # | Question |
|---|----------|
| 1 | Should **cash-aware mode** be a **portfolio-level toggle** or a **global user setting**? |
| 2 | Should existing transactions be allowed to remain **legacy forever** without enabling cash-aware mode? |
| 3 | Should **negative cash** be allowed behind an advanced setting (reconciliation / margin)? |
| 4 | Should dividends be entered as **`DIVIDEND` transaction first** vs direct **`DIVIDEND_CASH` ledger** entries? |
| 5 | Should **`CASH_DEPOSIT`** require **`source_of_funds`** categories (salary, bonus, gift, other)? |
| 6 | Should **bulk-schedule deposits** be editable after creation (same as manual entries)? |
| 7 | Should **transfer fees** be recorded in **source currency**, **target currency**, or separate `FEE` ledger row? |
| 8 | Should cash appear in the **Assets table** (row per currency) vs a dedicated **Cash** page / Settings section? |

---

## Appendix — Unified cash taxonomy (CASH-UNIFY-0)

KPulla6 has **two cash ledgers** that represent **cash holdings** within a portfolio at the product level:

| Ledger | Model | Scope | User-facing name |
|--------|-------|-------|------------------|
| Portfolio / broker | `CashLedgerEntry` | Per portfolio | **Broker Cash** |
| Bank account | `CashMovement` | Per `BankAccount` | **Bank Cash** |

**Rules:**

- Do **not** merge `cash_ledger_entries` and `cash_movements` in storage.
- Do **not** auto-create cross-ledger entries on read or backfill.
- Summary/performance may **aggregate** both for headline value when bank cash is opt-in included (FD-ACC-7/8).
- FD workflows debit **bank** ledger only; stock/MF settlements use **broker** ledger.

**Roadmap:** [cash-unification.md](./cash-unification.md) — ownership, unified Cash page UI, terminology. Bank ledger detail: [fixed-deposits-accounting.md](./fixed-deposits-accounting.md) § A.

---

## References (current codebase)

| Area | Location |
|------|----------|
| Cash constants | `cash/constants.py` |
| Cash models | `cash/models.py` |
| Cash ORM service (no HTTP) | `cash/services.py` |
| Pure cash balances | `finance/cash.py` |
| Portfolio flag | `portfolios/models.py` — `cash_aware_enabled` |
| External flows (legacy) | `portfolios/performance_service.py` — `_build_external_flows` |
| TWROR formula | `finance/twror.py` — `compute_twror_series` |
| XIRR | `finance/xirr.py`, `finance/mutual_fund_cashflows.py`, `portfolios/xirr_service.compute_scope_xirr_detail` |
| Portfolio value timeseries | `portfolios/summary_service.py` |
| Metric Sheet flows | `analytics/services.py` (reuses performance flow builders) |
| Transactions | `transactions/models.py` |
| Settlement sync (create/update on write) | `transactions/cash_settlement.py` |
| Historical settlement backfill | `transactions/cash_settlement_sync.py`, `manage.py sync_cash_settlements` |
