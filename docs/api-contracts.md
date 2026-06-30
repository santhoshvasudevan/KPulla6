# API Contracts Index — KPulla6

**Purpose:** Thin lookup table linking endpoints → frontend client → tests → key response/error shapes. **Not** a duplicate of [api-design.md](./api-design.md) — follow detail links for full request/response specs.

**Base URL:** `/api/v1` · **Auth:** session required except health/auth csrf/login/register.

**Product rules:** [product-rules.md](./product-rules.md)

---

## Shared error and warning shapes

| Shape | HTTP | Fields | Used by |
|-------|------|--------|---------|
| **Insufficient cash (shortfall)** | 400 | `detail`, `required`, `available`, `shortfall`, `currency` | Cash-aware BUY, withdrawal, transfer source, bulk apply |
| **Future cash impact** | 409 | `detail`, `currency`, `earliest_negative_date`, `lowest_balance`, `affected_entries[]` (`id`, `date`, `entry_type`, `amount`, …) | `PUT`/`DELETE` `/cash/ledger/{id}`, `PUT`/`DELETE` `/transactions/{id}` when settlement sync breaks future balance |
| **Protected cash row** | 409 | `detail` (linked/system entry) | Manual edit/delete of settlement or transfer legs |
| **Missing FX** | 200 + warnings | `fx_status: "fx_unavailable"`, `warnings[]` (summary/performance/holdings) | Display currency ≠ native; partial cash conversion |
| **Missing NAV (MF)** | 200 + warnings | NAV freshness / missing messages in `warnings[]` | Asset/portfolio Metric Sheet, holdings |
| **Split price warning** | 200 + warnings | Split-date valuation warning in `warnings[]` | Metric Sheet when cached prices likely raw nominal |
| **CSV row errors** | 400 | Row-level error list; import all-or-nothing | `POST /transactions/import-csv` |
| **CSV cash preview block** | 409 | Preview body + shortfall rows | Import without `create_cash_deposits` + confirm |
| **Auth / ownership** | 401 / 403 / 404 | `detail` | All scoped endpoints; foreign portfolio/ledger row |

Detail: [api-design.md](./api-design.md) — transactions cash-aware errors, Cash-4D future impact, Cash-5 CSV preview.

---

## Portfolio

| Method | Endpoint | Purpose | Frontend | Key 200 blocks | Errors / warnings | Backend tests | Frontend tests |
|--------|----------|---------|----------|----------------|-------------------|---------------|----------------|
| GET | `/portfolio/summary` | FIFO headline metrics, optional timeseries, cash-inclusive `current_value` | `fetchDashboardSummary` | `total_invested`, `current_value`, `realized_pl`, `unrealized_pl`, `xirr`, `timeseries[]`, optional `cash_summary`, `warnings[]` | 422 scope; 404 portfolio; `fx_status`, cash FX warnings | `test_portfolio_summary_api.py` | `Dashboard.test.jsx`, `api.test.js` |
| GET | `/portfolio/performance` | Value / cumulative return / TWROR series; optional benchmark | `fetchPortfolioPerformance` | `metric`, `range`, `points[]`, optional `benchmark`, `warnings[]` | 422 benchmark; missing index warnings | `test_portfolio_performance_api.py` | `Dashboard.test.jsx`, `api.test.js` |
| GET | `/portfolio/holdings` | Holdings table + allocation (includes cash) | `fetchHoldings` | `holdings[]`, `allocation[]`, `warnings[]`, per-row `price_status`, `fx_status` | Oversell warnings; price/FX missing | `test_holdings_api.py` | `Assets.test.jsx`, `api.test.js` |

Detail: [api-design.md § Phase 9–10](./api-design.md), holdings § MF-4.

---

## Analytics (Quantitative Statistics / Metric Sheet)

| Method | Endpoint | Purpose | Frontend | Key 200 blocks | Errors / warnings | Backend tests | Frontend tests |
|--------|----------|---------|----------|----------------|-------------------|---------------|----------------|
| GET | `/analytics/performance-metrics` | Portfolio Metric Sheet | `getPortfolioMetricSheet` | `metrics`, `periodic_returns`, `drawdown_periods`, `drawdown_series`, `warnings[]`; `metrics.return.xirr_scope: "full_scope"` | Benchmark null metrics; split/NAV/FX warnings | `test_analytics_performance_metrics_api.py` | `Dashboard.test.jsx`, `metricSheet/*.test.*`, `api.test.js` |
| GET | `/analytics/assets/{asset_symbol}/performance-metrics` | Asset Metric Sheet | `getAssetMetricSheet` | Same block shape per asset; MF: `folio_number` query | 404 asset; split price warning | `test_analytics_asset_metrics_api.py`, `test_analytics_split_metrics_api.py` | `AssetDetail.test.jsx`, `metricSheet.test.jsx` |
| GET | `/analytics/compare` | Two-asset Metric Sheet compare | `getCompareMetricSheet` | `subjects[]`, `normalized_series`, per-subject metrics, `warnings[]` | Subject alignment; common-date window | `test_analytics_compare_api.py` | `Compare.test.jsx`, `api.test.js` |

Detail: [api-design.md § analytics](./api-design.md), [architecture.md § Metric Sheet](./architecture.md).

---

## Cash

| Method | Endpoint | Purpose | Frontend | Key 200/201 blocks | Errors / warnings | Backend tests | Frontend tests |
|--------|----------|---------|----------|-------------------|-------------------|---------------|----------------|
| GET | `/cash/balances` | Native-currency balances | `fetchCashBalances` | `balances[]` (`currency`, `balance`) | 404 scope | `test_cash_api.py` | `Cash.test.jsx`, `api.test.js` |
| GET | `/cash/overview` | Broker + bank cash rows (read-only) | `fetchCashOverview` | `rows[]`, `totals`, `warnings` | 404 scope | `test_cash_overview_api.py` | `api.test.js` |
| GET | `/cash/ledger` | Paginated ledger | `fetchCashLedger` | `items[]` incl. `details`, `total`, `page` | 404 scope | `test_cash_api.py` | `Cash.test.jsx` |
| POST | `/cash/deposits` | Manual deposit | `createCashDeposit` | Single ledger item | 400 validation | `test_cash_api.py` | `Cash.test.jsx`, `api.test.js` |
| POST | `/cash/withdrawals` | Manual withdrawal | `createCashWithdrawal` | Single ledger item | **400 shortfall** | `test_cash_api.py` | `Cash.test.jsx` |
| PUT | `/cash/ledger/{id}` | Edit manual row | `updateCashLedgerEntry` | Updated item | **409** future impact / protected | `test_cash_api.py` | `Cash.test.jsx` |
| DELETE | `/cash/ledger/{id}` | Delete manual row | `deleteCashLedgerEntry` | 204 | **409** future impact / protected | `test_cash_api.py` | `Cash.test.jsx` |
| POST | `/cash/transfers` | Same- or cross-currency transfer | `createCashTransfer` | `transfer_group_id`, `source_*`, `target_*`, `implied_rate`, `entries[]` | **400 shortfall**; **409** future impact on source | `test_cash_api.py` | `Cash.test.jsx`, `api.test.js` |
| POST | `/cash/bulk-entries/preview` | Schedule preview | `previewCashBulkEntries` | `entries[]`, `total_by_currency`, `warnings[]` | 400 schedule invalid | `test_cash_bulk_entries_api.py` | `Cash.test.jsx` |
| POST | `/cash/bulk-entries/apply` | Confirmed bulk write | `applyCashBulkEntries` | `created_count`, `skipped_existing_count`, `created_entries[]` | 400 negative balance preview | `test_cash_bulk_entries_api.py` | `Cash.test.jsx` |
| POST | `/cash/ledger/{id}/reverse` | Reverse manual broker entry (CASH-CORR-1A) | `reverseCashLedgerEntry` | Reversal entry + audit link | 400/409 ineligible | `test_cash_ledger_reversals_api.py` | `Cash.test.jsx` |

**Removed:** `POST /cash/backfill-preview`, `POST /cash/backfill-apply`.

**Diagnostics (management command):** `cash_overview_diagnostics` — read-only broker/bank summary (CASH-UNIFY-4A). Not a REST endpoint.

Detail: [api-design.md § Cash API](./api-design.md).

---

## Bank accounts (debt / bank ledger)

| Method | Endpoint | Purpose | Frontend | Key blocks | Errors | Backend tests | Frontend tests |
|--------|----------|---------|----------|------------|--------|---------------|----------------|
| GET/PUT | `/bank-accounts` | List / update incl. `portfolio_id` link | `fetchBankAccounts`, `updateBankAccount` | `portfolio_id`, `portfolio_assignment_status`, balances | 400 portfolio conflict | `test_bank_accounts_api.py` | `BankAccountManagement.test.jsx` |
| GET | `/bank-accounts/{id}/balance` | Ledger balance (optional `as_of`) | `fetchBankAccountBalance` | `current_balance`, `as_of_date` | 404 | `test_bank_accounts_api.py` | `FixedDeposits.test.jsx` |

**Link/delink:** `PUT` `portfolio_id` set or `null` — inclusion only; no `CashMovement` created (CASH-UNIFY-4).

Detail: [api-design.md § Bank accounts](./api-design.md), [fixed-deposits-accounting.md](./fixed-deposits-accounting.md).

---

## Reports (FD tax)

| Method | Endpoint | Purpose | Frontend | Key blocks | Errors | Backend tests | Frontend tests |
|--------|----------|---------|----------|------------|--------|---------------|----------------|
| GET | `/reports/fixed-deposit-interest` | FD interest/tax JSON report | `fetchFixedDepositInterestReport` | `rows`, `totals`, `grouped_totals`, `warnings` | 400 bad `group_by` | `test_fixed_deposit_interest_report_api.py` | `FixedDepositInterestReport.test.jsx` |
| GET | `/reports/fixed-deposit-interest/export.csv` | CSV export (detail rows) | `exportFixedDepositInterestReportCsv` | `text/csv` attachment | same filters as JSON | same | same |

Read-only. Not tax advice. No accounting side effects.

Detail: [api-design.md § FD interest report](./api-design.md), [fixed-deposits.md](./fixed-deposits.md).

---

## Transactions

| Method | Endpoint | Purpose | Frontend | Key 200/201 blocks | Errors / warnings | Backend tests | Frontend tests |
|--------|----------|---------|----------|-------------------|-------------------|---------------|----------------|
| GET | `/transactions` | Paginated list + filters | `fetchTransactions` | `items[]`, `total`, `page`, `pages` | 422 scope; filter 400 | `test_transactions_api.py`, `test_transaction_filters_api.py` | `Transactions.test.jsx` |
| POST | `/transactions` | Create stock/MF | `createTransaction` | Transaction object incl. optional SELL `actual_cash_received`, `settlement_note` | **400 shortfall** (cash-aware BUY); **400** if actual &gt; calculated proceeds | `test_transactions_api.py`, `test_cash_aware_transactions_api.py`, `test_cash_sell_tax_withheld.py` | `TransactionModal.test.jsx` |
| PUT | `/transactions/{id}` | Full update | `updateTransaction` | Transaction object | **400 shortfall**; **409** future impact | same | `TransactionModal.test.jsx` |
| DELETE | `/transactions/{id}` | Hard delete | `deleteTransaction` | 204 | **409** future impact | same | `TransactionModal.test.jsx` |
| POST | `/transactions/import-csv` | CSV import | `importTransactionsCsv` | `success`, `imported_count` | Row errors 400; cash 409 without confirm | `test_csv_import_api.py`, `test_mutual_fund_csv_import.py` | `Transactions.test.jsx` |
| POST | `/transactions/import-csv/preview-cash` | Cash shortfall preview | `previewCsvImportCash` | Preview rows, shortfalls | No writes | `test_csv_import_cash_preview.py` | `Transactions.test.jsx` |

Detail: [api-design.md § Transactions](./api-design.md), CSV § Cash-5.

---

## Portfolios and settings

| Method | Endpoint | Purpose | Frontend | Key blocks | Errors | Backend tests | Frontend tests |
|--------|----------|---------|----------|------------|--------|---------------|----------------|
| GET | `/portfolios` | List active portfolios | `fetchPortfolios` | Array incl. `cash_aware_enabled` | — | `test_portfolios_api.py` | `portfolioContext.test.jsx`, `Settings.test.jsx` |
| POST | `/portfolios` | Create portfolio | `createPortfolio` | Portfolio object | 400 max active | `test_portfolios_api.py` | `Settings.test.jsx` |
| PUT | `/portfolios/{id}` | Update incl. cash-aware enable | `updatePortfolio` | Portfolio object | 404; cannot deactivate default | `test_portfolios_api.py` | `Settings.test.jsx`, `CashAwarePortfolioStatus.test.jsx` |
| DELETE | `/portfolios/{id}` | Soft deactivate | `deletePortfolio` | 200 | 400 default | `test_portfolios_api.py` | `Settings.test.jsx` |
| GET | `/settings` | App settings | `getSettings` | `display_currency`, `tax_rate_percentage` | — | `test_settings_api.py` | `Settings.test.jsx`, `portfolioContext.test.jsx` |
| PUT | `/settings` | Update settings | `updateSettings` | Same as GET | 400 bad currency | `test_settings_api.py` | `Settings.test.jsx` |

Detail: [api-design.md § Settings & Portfolios](./api-design.md).

---

## Quick detail links

| Topic | Section in api-design.md |
|-------|--------------------------|
| Implemented Endpoint Index (compact table) | Top of [api-design.md](./api-design.md) |
| Summary cash + XIRR tables | Phase 9 — `/portfolio/summary` |
| Performance metrics + range | Phase 10 — `/portfolio/performance` |
| Metric Sheet query params | Analytics — common query parameters |
| Transfer request/response (8A/8B) | Cash — `POST /cash/transfers` |
| Future impact 409 (cash ledger) | Cash-4D — `PUT`/`DELETE /cash/ledger/{id}` |
| Broker ledger reversal (CORR-1A) | Cash — `POST /cash/ledger/{id}/reverse` |
| Cash overview (unified read) | Cash — `GET /cash/overview` |
| FD interest/tax report + CSV | Reports — `/reports/fixed-deposit-interest` |
| Bank account portfolio link | Bank accounts — `PUT /bank-accounts/{id}` `portfolio_id` |
