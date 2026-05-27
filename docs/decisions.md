# Architecture Decisions — KPulla6

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

## 2026-05-26 — MF-9: Mutual fund NAV refresh API and combined sync
- **`POST /api/v1/nav/refresh`** — explicit MF NAV sync path only; optional `scheme_codes`; synchronous; returns synced/skipped/failed counts.
- **Read APIs remain DB-only** — no NAV provider on holdings, summary, performance, transactions, or asset detail reads.
- **`sync_market_data` / `force-sync`** include MF NAV sync by default; `--skip-mutual-funds` opts out.
- **MF provider failure** does not fail stock/benchmark/FX success on full sync.
- Live provider implementation completed in MF-10.
