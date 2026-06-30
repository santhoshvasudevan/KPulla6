# Obsolete / Unused Backend Code Audit

**Date:** 2026-06-30  
**Scope:** `backend/` Python only (conservative static review; no deletions in this audit).  
**Method:** Module inventory, import/reference grep, management-command coverage vs Makefile/tests/docs.

## Summary

The backend is largely clean. No broad unused service layer surfaced. Highest-confidence items are empty analytics stubs and one undertested diagnostic command.

| Confidence | Count | Action |
|------------|-------|--------|
| High | 1 | Defer stub removal |
| Medium | 2 | Investigate / defer |
| Low | 12 | Defer — active, documented, or intentional legacy |

**Nothing was deleted in this audit.**

---

## Findings

### 1. `backend/analytics/serializers.py` — **High**

| Field | Detail |
|-------|--------|
| **Evidence** | One-line docstring only (“Metric Sheet API responses are built in analytics.services”). Zero imports anywhere in the repo. |
| **Recommended action** | **Defer** — safe to remove stub later, or repurpose if DRF serializers are planned. Not loaded at runtime today. |
| **Status** | Deferred |

### 2. `backend/analytics/models.py` — **Medium**

| Field | Detail |
|-------|--------|
| **Evidence** | Placeholder docstring; no models; zero imports. App remains in `INSTALLED_APPS`. |
| **Recommended action** | **Defer** — common Django empty placeholder. |
| **Status** | Deferred |

### 3. `backend/debt/management/commands/bank_balance_timeline.py` — **Medium**

| Field | Detail |
|-------|--------|
| **Evidence** | Documented in changelog/backlog only. Not in `Makefile`. No `call_command` tests. Operational FD/bank timeline diagnostic. |
| **Recommended action** | **Investigate** — confirm ongoing use vs `cash_overview_diagnostics`; add smoke test if kept. |
| **Status** | Deferred |

### 4. `backend/accounts/management/commands/set_user_password.py` — **Low**

| Field | Detail |
|-------|--------|
| **Evidence** | Documented in `auth.md`; referenced in error messages. No dedicated command test. |
| **Recommended action** | **Defer** — intentional local-dev ops tool. |
| **Status** | Deferred |

### 5–8. Thin sync management commands — **Low**

`sync_prices`, `sync_benchmarks`, `sync_fx_rates`, `sync_mutual_fund_navs` — wrappers around service functions. Still wired in `Makefile`, API refresh endpoints, and tests. Overlap with `sync_market_data` is intentional DX, not dead code.

**Status:** Deferred

### 9. `backend/finance/__init__.py` barrel re-exports — **Low**

Large `__all__`; callers import submodules directly. Package init only.

**Status:** Deferred

### 10–12. Diagnostics CLI modules — **Low**

`backend/scripts/diagnose_*.py`, `backend/diagnostics/fx_coverage.py`, `nav_coverage.py` — path-invoked, documented in workflows. Weak automated coverage but actively used operationally.

**Status:** Deferred / investigate test coverage

### 13. `backend/market_data/nav_refresh.py` — **Low**

Used by `NavRefreshView` and `PortfolioForceSyncView`. Thin HTTP adapter, not redundant with management commands.

**Status:** Deferred

### 14. `backend/diagnostics/__init__.py` — **Low**

Package marker only.

**Status:** Deferred

### 15. `finance/mutual_fund_cashflows.build_legacy_portfolio_xirr_flows` — **Low**

Name suggests legacy but used for `cash_aware_enabled=false` portfolios in `portfolios/xirr_service.py`.

**Status:** Deferred — intentional compatibility path

---

## Management command coverage

| Command | Makefile | Tests | Notes |
|---------|----------|-------|-------|
| `sync_market_data` | `make refresh` | Yes | Primary combined sync |
| `sync_prices` / `sync_benchmarks` / `sync_fx_rates` / `sync_mutual_fund_navs` | Yes | Yes | Granular sync entry points |
| `cash_overview_diagnostics` | — | Yes | Cash unification diagnostic |
| `bank_balance_timeline` | **No** | **No** | FD funding diagnostic — weakest coverage |
| `set_user_password` | — | String mention only | Local dev ops |

---

## Intentionally not obsolete

- **`legacy_*` finance helpers** — non-cash-aware portfolio compatibility
- **`backend/scripts/*`** — CLI diagnostics (documented, not imported)
- **Django wiring** (`apps.py`, `urls.py`, empty `__init__.py`)

---

## Recommended next steps (deferred)

1. Remove or implement `analytics/serializers.py` stub when touching analytics package.
2. Add Makefile entry or test smoke for `bank_balance_timeline` if the command stays.
3. Re-run this audit after large refactors (`make docs-check` does not replace code audits).
