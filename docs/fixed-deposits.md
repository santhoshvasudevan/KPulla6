# Fixed Deposits (Debt Investments) — KPulla6

## MVP scope (FD phase)

This phase adds **Fixed Deposits** as a debt investment type with **principal-only** portfolio valuation.

### In scope

- User-owned **BankAccount** records (full account numbers stored/displayed; no masking)
- **FixedDeposit** records linked to one real portfolio and one active bank account
- CRUD APIs with per-user scoping; **Cancel FD** for ledger-backed mistakes (FD-ACC-10A); **Deactivate** (`DELETE`) for legacy FDs without `FD_OPENING` only
- Portfolio **summary** and **holdings** include active FD principal in `total_invested` and `current_value`
- FD unrealized P/L is **zero** in MVP (principal-only value)
- **MATURED** deposits still contribute principal while `is_active=true` and status ≠ `CLOSED`
- Dashboard **allocation_buckets** (Equity / Debt / Other) on `GET /portfolio/summary`
- Settings bank-account management UI; dedicated Fixed Deposits page
- Pure finance helper: `finance/fixed_deposits.py` (no Django imports)

### Out of scope (MVP — see accounting design)

| Feature | Notes |
|---------|--------|
| `fixed_deposit_interest_payments` | **Done (FD-ACC-4)** — gross/tax/net payout rows + `FD_INTEREST` bank credit |
| Cash movements on FD open/close/maturity | **Open + settlement done (FD-ACC-3/5)**; **renewal done (FD-ACC-6)** |
| Maturity/closure transactions | **Done (FD-ACC-5)** — mark matured + settle APIs |
| Renewal transactions | **Done (FD-ACC-6)** — `POST .../renew` with `renewal_of` chain |
| Bank account cash in portfolio value | **Done (FD-ACC-7)** — opt-in `include_in_portfolio_value`; ledger balance only |
| FD/bank cash in performance timeseries (`metric=value`) | **FD-ACC-8B done** |
| XIRR / TWROR / cumulative return with FD/bank cash | **FD-ACC-8C done** |
| Accrued interest in portfolio value | Explicitly excluded |
| XIRR / performance timeseries for FDs | **Done (FD-ACC-8B/8C)** |

Schema fields (`renewal_of`, `opening_balance`, `current_balance`, `include_in_portfolio_value`) are reserved for clean future extension.

### Accounting Phase 1 (FD-ACC-1..10B implemented; FD-TAX-1 report)

**Full design:** [fixed-deposits-accounting.md](./fixed-deposits-accounting.md)

Implemented: bank ledger, manual movements (FD-ACC-2), mandatory `FD_OPENING` debit (FD-ACC-3), interest payments (FD-ACC-4), **maturity/closure settlement** (FD-ACC-5), **renewal workflow** (FD-ACC-6), **optional bank cash in portfolio value** (FD-ACC-7), performance/XIRR (FD-ACC-8B/8C), **FD cancel / deactivate accounting** (FD-ACC-10A), **reversal/correction framework** (FD-ACC-10B), **interest/tax withheld report** (FD-TAX-1, read-only).

Key design choices documented there:

- Bank ledger is **separate** from portfolio `CashLedgerEntry` (broker cash)
- Ledger is source of truth for bank `current_balance`; FD principal stays portfolio value until settled
- **New FDs (FD-ACC-3):** principal debited from linked bank account via `FD_OPENING` movement at create time; requires **ledger-derived** bank balance **as of the FD investment date** (seed opening balance or manual deposit on/before that date)
- **Backdated FDs:** seed opening balance and manual deposits must be dated on or before `investment_date`; seeding with today’s date does not fund an earlier investment date. **Current ledger balance** (today) may exceed **available as of investment date** — FD create validates the latter (FD-CASH-ASOF-1).
- **Cash tab vs bank ledger:** Portfolio Cash (`/cash/balances`) is broker cash; FD opening debits use the linked **bank account** cash ledger (`CashMovement`).
- **Interest payments (FD-ACC-4):** periodic payouts via `FD_INTEREST`; immutable; COMPOUNDED soft warning
- **Settlement (FD-ACC-5):** `POST /mark-matured` (no ledger); `POST /settle` credits bank for principal + net final interest; FD leaves portfolio value; bank cash still excluded
- **Renewal (FD-ACC-6):** `POST /renew` settles old FD and creates renewed FD; direct rollover skips bank movements for reinvested principal; renewed FD has no `FD_OPENING` debit; partial `cash_payout_amount` credits bank
- **Status flow:** `ACTIVE` → `MATURED` (mark) → `MATURED_SETTLED` (maturity settle or renewal) or `ACTIVE`/`MATURED` → `CLOSED` (closure settle); mistaken ledger-backed FD → `CANCELLED` via **Cancel FD** (FD-ACC-10A)
- Existing MVP FDs remain valid without backfilled movements
- Performance/XIRR integration **done (FD-ACC-8B/8C)** — see accounting doc § FD-ACC-8

Approved decisions (FD-ACC-0.1): see accounting doc § Approved product decisions.

## Data safety

- Schema changes via Django migrations in `debt/migrations/` (latest: `0007_reversal_framework` for FD-ACC-10B)
- No changes to existing `transactions`, `cash_ledger_entries`, or user transaction rows
- Run `make backup-db` and `make db-safety-check` before applying migrations on dev Postgres
- Tests use SQLite (`DJANGO_TEST_USE_SQLITE=1`)

## BankAccount model

| Field | Type | Notes |
|-------|------|-------|
| `user` | FK → `auth.User` | Required; per-user scoping |
| `name` | string | User-friendly label |
| `institution_name` | string | Bank / NBFC / Post Office |
| `account_number` | string | Full value as entered |
| `currency` | string(3) | Same supported set as cash (`SUPPORTED_CASH_CURRENCIES`) |
| `opening_balance` | decimal | Default 0; future cash balance |
| `current_balance` | decimal | Default 0; future cash balance |
| `include_in_portfolio_value` | bool | Default **false**; when **true** and ledger exists, balance included in portfolio value (FD-ACC-7) |
| `is_active` | bool | Soft delete sets false |
| `comment` | text | Optional |

## FixedDeposit model

| Field | Type | Notes |
|-------|------|-------|
| `user` | FK → `auth.User` | Explicit ownership (also validated via portfolio/bank) |
| `portfolio` | FK → `Portfolio` | Required; must be active, same user |
| `bank_account` | FK → `BankAccount` | Required; must be active, same user |
| `institution_name` | string | e.g. SBI, HDFC, Post Office |
| `deposit_account_number` | string | FD account / receipt number |
| `principal_amount` | decimal | Must be > 0 |
| `currency` | string(3) | Must match linked bank account currency |
| `interest_rate_percent` | decimal | ≥ 0 |
| `interest_payout_frequency` | enum | MONTHLY, QUARTERLY, HALF_YEARLY, ANNUALLY, COMPOUNDED |
| `investment_date` | date | Required |
| `maturity_date` | date | Must be after investment_date |
| `nominee_name` | string | Optional |
| `comment` | text | Optional |
| `status` | enum | ACTIVE (default), MATURED, **MATURED_SETTLED**, CLOSED, **CANCELLED** |
| `renewal_of` | FK → self | Nullable; future renewal chain |
| `is_active` | bool | Soft delete sets false |

### Portfolio value rules (MVP; extended by accounting design)

| Condition | Contributes principal? |
|-----------|-------------------------|
| `is_active=true`, status ACTIVE | Yes |
| `is_active=true`, status MATURED | Yes (unsettled — still in Debt) |
| status MATURED_SETTLED | No |
| status CLOSED | No |
| status CANCELLED | No |
| `is_active=false` | No |

After FD-ACC-4, settlement moves FD to `MATURED_SETTLED` or `CLOSED` and removes principal from portfolio value. **`MATURED` without settlement still contributes** — see [fixed-deposits-accounting.md](./fixed-deposits-accounting.md) § C.

Interest accrual is **not** added to `current_value`.

## API contracts

Base: `/api/v1` · Session auth required.

### Bank accounts

| Method | Path | Behavior |
|--------|------|----------|
| GET | `/bank-accounts` | List active accounts for current user |
| POST | `/bank-accounts` | Create |
| GET | `/bank-accounts/{id}` | Detail (includes inactive) |
| PUT | `/bank-accounts/{id}` | Update active account |
| DELETE | `/bank-accounts/{id}` | Soft deactivate (`is_active=false`) |

### Fixed deposits

| Method | Path | Behavior |
|--------|------|----------|
| GET | `/fixed-deposits` | List active FDs; `portfolio_scope=all` or `portfolio_id` |
| POST | `/fixed-deposits` | Create with validation |
| GET | `/fixed-deposits/{id}` | Detail |
| PUT | `/fixed-deposits/{id}` | Update active FD |
| DELETE | `/fixed-deposits/{id}` | Soft deactivate (`is_active=false`) — **409** when unreversed `FD_OPENING` exists |
| POST | `/fixed-deposits/{id}/cancel` | Cancel mistaken ledger-backed FD; reverses `FD_OPENING`; `status=CANCELLED`; row retained for audit (not deleted) |

### FD lifecycle actions (FD-ACC-10A / FD-ACC-10B)

Use the action that matches the real-world event. These are **not** interchangeable.

| Action | API | When to use | Bank ledger | Portfolio value | Row retained? |
|--------|-----|-------------|-------------|-----------------|-----------------|
| **Cancel FD** | `POST .../cancel` | Mistaken FD creation (wrong portfolio, duplicate, etc.) | `FD_OPENING_REVERSAL` CREDIT restores bank cash | FD principal removed; cancelled FD excluded from summary, holdings, value history, XIRR/TWROR terminal | **Yes** — `status=CANCELLED`, `is_active=false` |
| **Deactivate** | `DELETE .../{id}` | Legacy FD **without** unreversed `FD_OPENING` | None | FD principal removed (`is_active=false`) | **Yes** |
| **Settle / Close** | `POST .../settle` | Real maturity or early closure at institution | `FD_MATURITY_*` / `FD_CLOSURE_*` CREDITs | Principal removed after settlement; bank credited per settlement | **Yes** — `MATURED_SETTLED` or `CLOSED` |
| **Renew** | `POST .../renew` | Real rollover at institution | Settlement + optional payout movements; renewed FD may skip `FD_OPENING` on direct rollover | Old FD settled; new FD principal included | **Yes** — old + new FD rows |

**Blocked:** `DELETE` on ledger-backed FD with unreversed `FD_OPENING` → **409** (“Use Cancel FD”). Cancel rejected when interest payments, settlement, or renewal exist.

| **Reverse interest** | `POST .../fixed-deposit-interest-payments/{id}/reverse` | Mistaken interest payment | `FD_INTEREST_REVERSAL` DEBIT | Bank cash reduced; payment `is_reversed`; not allowed after settlement |
| **Reverse cash movement** | `POST .../cash-movements/{id}/reverse` | Mistaken manual deposit/withdrawal/adjustment/opening seed | `REVERSAL` opposite direction | Original marked reversed; bank balance updated |
| **Repair (one-time)** | `manage.py repair_deactivated_fd_openings` | FD deactivated before FD-ACC-10A with stuck `FD_OPENING` | `FD_OPENING_REVERSAL` CREDIT | Not a user API; dry-run by default |

**Do not fix pre-10A deactivated FDs with a manual deposit** — use the repair command. Manual deposits are external contributions and distort XIRR/TWROR. cancelled FDs are excluded from FD principal history entirely, but included bank cash still reflects the original `FD_OPENING` debit until the reversal date — headline PV may dip between opening and cancellation. Settlement/renewal/cancel-FD reversal → **FD-ACC-10C**.

### FD interest / tax report (FD-TAX-1)

| Method | Path | Behavior |
|--------|------|----------|
| GET | `/reports/fixed-deposit-interest` | Read-only gross/tax/net report from interest payments, settlements, renewals |

**Query:** `portfolio_scope` / `portfolio_id`, `start_date`, `end_date`, optional `display_currency`, `group_by` (`year`, `portfolio`, `bank`, `fd`, `source`, `none`).

**Excludes:** reversed interest payments; zero-interest settlement/renewal rows; `CANCELLED` FD rows; renewal-linked settlement rows (renewal group used instead).

**Not tax advice.** CSV/export deferred (FD-TAX-2). No ledger or performance side effects.

### Summary / holdings integration

- `GET /portfolio/summary` — FD principal added to `total_invested`, `current_value`; optional `allocation_buckets`; `has_fixed_deposits: true` when contributing FDs exist
- `GET /portfolio/holdings` — FD rows with `asset_type=FIXED_DEPOSIT`, `value_status=principal_only`, `asset_symbol` label (e.g. `FD HDFC`)
- `GET /portfolio/performance?metric=value` — includes FD principal + included bank cash (**FD-ACC-8B**).
- `GET /portfolio/performance?metric=twror|cumulative_return` — aligned PV + internal/external flow rules (**FD-ACC-8C**).
- Summary/Metric Sheet XIRR terminal aligns with headline `current_value` (**FD-ACC-8C**).

### Dashboard UX

When `has_fixed_deposits` is true and the performance metric is **Value**, the dashboard shows an info banner: value chart and return metrics include Fixed Deposits and included Bank Cash.

## Allocation buckets (dashboard)

`allocation_buckets` on summary response:

```json
{
  "currency": "INR",
  "fx_status": "ok",
  "buckets": [
    {"label": "Equity", "value": 500000.0},
    {"label": "Debt", "value": 150000.0},
    {"label": "Other", "value": 25000.0}
  ]
}
```

- **Equity:** stocks/ETFs + MF with `primary_asset_class=EQUITY`
- **Debt:** FD principal + MF with `primary_asset_class` in DEBT, LIQUID
- **Cash / Bank Cash:** opt-in ledger bank balances (FD-ACC-7)
- **Other:** hybrid/commodity/unknown + portfolio broker cash totals

React renders buckets only; no frontend finance calculations.

## Tests

| Area | File |
|------|------|
| Bank account API | `tests/test_bank_accounts_api.py` |
| Fixed deposit API | `tests/test_fixed_deposits_api.py` |
| Finance helpers | `tests/test_finance_fixed_deposits.py` |
| Summary/holdings | `tests/test_fixed_deposit_summary_api.py` |
| E2E accounting audit | `tests/test_fixed_deposit_end_to_end_accounting.py` |
| FD cancel / deactivate accounting | `tests/test_fixed_deposit_cancellation_accounting.py` |
| Performance / returns | `tests/test_fd_performance_timeseries_api.py`, `tests/test_fd_cash_flow_classification.py` |
| Frontend | `FixedDeposits.test.jsx`, `BankAccountManagement.test.jsx`, `Assets.test.jsx`, `api.test.js`, `Dashboard.test.jsx` |
