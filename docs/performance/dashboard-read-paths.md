# Dashboard read-path performance — design and decision record

**Status:** STAB-5B — performance decision recorded; **optimization deferred**.  
**Related:** [dashboard-read-baseline.md](./dashboard-read-baseline.md) · [workflows.md](../workflows.md) · [product-rules.md](../product-rules.md)

---

## 1. STAB-5B decision

**Current Dashboard backend performance is acceptable for MVP.**

Real Postgres dev profiling (4 active portfolios, `portfolio_scope=all`, EUR display) shows all critical Dashboard endpoints **under 1 second**. The default Dashboard load runs three parallel backend reads; the slowest (Metric Sheet 1Y) is ~**440 ms** — within the ~1 s perceived backend wait target.

**No shared-series refactor will be implemented now.** Endpoints meet targets; duplicate query work is avoidable but not blocking release.

**Revisit optimization when:**

- Any single Dashboard-critical endpoint exceeds **1 s** on dev Postgres, or
- Portfolio count, transaction history, or multi-currency holdings grow materially, or
- Users report Dashboard slowness after data import / sync backfill.

Profiler:

```bash
cd backend
.venv/bin/python scripts/profile_dashboard_read_paths.py --username USERNAME --verbose \
  --json-out tmp/dashboard_read_baseline_postgres.json
```

Use Django **username** (not email). Compare against [dashboard-read-baseline.md](./dashboard-read-baseline.md).

---

## 2. Frontend → backend mapping

| UI area | Frontend call | Backend service |
|---------|---------------|-----------------|
| Headline cards (value, P/L, XIRR) | `fetchDashboardSummary` | `build_portfolio_summary` |
| Value / return chart | `fetchPortfolioPerformance` | `build_portfolio_performance` |
| Quantitative Statistics / **Metric Sheet** | `getPortfolioMetricSheet` | `build_portfolio_performance_metrics` |
| Assets allocation table | `fetchHoldings` (Assets page) | `build_holdings` |

**Dashboard default:** `metric=value`, `timeRange=1Y`, `portfolio_scope=all`, user display currency. Benchmark is optional (cumulative return / TWROR + user selection only).

---

## 3. Real Postgres dev baseline (2026-06-06)

User `santhoshkgvasudevan` · portfolios `[1, 2, 3, 4]` · display EUR. Full table in [dashboard-read-baseline.md](./dashboard-read-baseline.md).

| Path | ms | SQL | Notes |
|------|---:|----:|-------|
| Summary | 293.4 | 194 | Highest SQL; repeated FX + prices |
| Performance value 1Y | 138.1 | 35 | 366 points; early range emit |
| Performance value ALL | 368.0 | 16 | 2432 points; low SQL despite long series |
| Performance cumulative_return 1Y | 297.4 | 75 | Duplicates return-series work |
| Performance TWROR 1Y | 285.5 | 75 | Same family as cumulative_return |
| Metric Sheet 1Y | 440.2 | 106 | Heaviest default Dashboard path |
| Metric Sheet ALL | 762.4 | 87 | Under 1 s; acceptable |
| Holdings | 64.3 | 35 | Assets page |

**Default Dashboard (parallel):** max ~**440 ms** · **335 SQL** (sequential diagnostic sum ~872 ms).

Synthetic SQLite baseline (STAB-5A) remains in [dashboard-read-baseline.md](./dashboard-read-baseline.md) for CI shape checks only.

---

## 4. MVP performance targets

| Target | Rationale | Postgres status |
|--------|-----------|-----------------|
| Individual Dashboard endpoints **< 1 s** | Interactive dev UX | ✅ All pass |
| Default critical path **~< 1 s** (parallel max) | Summary + value 1Y + Metric Sheet 1Y | ✅ ~440 ms |
| **1Y SQL not ∝ calendar days** | B2B bootstrap intent | ✅ 35 SQL for 366 points (value) |
| **Metric Sheet ALL < 1 s** | Acceptable for current data | ✅ 762 ms |
| **No per-day FX queries** (all-scope) | B1 bulk maps | ⚠️ Summary still shows many FX SELECTs — backlog P1 |
| **1Y value not slower than ALL** | Early slicing should help latency | ✅ 138 ms vs 368 ms (ALL does more valuation work) |

Targets are **dev Postgres** guidelines, not hard SLA. Sequential profiler total (~2.6 s / 623 SQL) is **not** a Dashboard page metric — the browser runs the three default reads in parallel.

---

## 5. Observed bottlenecks (real data)

### 5.1 Summary — repeated FX, prices, transactions

194 SQL on dev Postgres; profiler shows **97 FX**, **57 historical price**, **32 transaction** queries. All-scope headline aggregation reloads per-portfolio inputs (holdings, XIRR, display conversion) without cross-portfolio bulk reuse.

### 5.2 Metric Sheet — duplicates value and flow work

106 SQL (1Y); **68 historical price** queries. Rebuilds cash-inclusive value series and external flows already computed on the same request cycle by performance endpoints (separate HTTP calls, no shared context).

### 5.3 cumulative_return and TWROR — duplicate return construction

75 SQL each (1Y); **52 historical price** queries each. Same external-flow + value-series family; late slicing for cumulative_return vs early emit for value.

### 5.4 ALL range — points vs queries

Value ALL: **2432 points**, **16 SQL** — query count does **not** scale with emitted days (desired). Latency (368 ms) reflects valuation work, not N+1 DB loops.

### 5.5 Cross-request duplication (Dashboard session)

Three parallel calls on load do not share work. Navigating metric/range changes re-hit performance + Metric Sheet. Acceptable for MVP; addressed by backlog P2 if needed later.

---

## 6. Optimization backlog (ranked — not scheduled)

Implement **only** when targets are exceeded or data volume forces it. See §8 guardrails.

| Priority | Item | Scope | Target / outcome | Risk |
|----------|------|-------|------------------|------|
| **P1** | **Summary read-path bulk loading** | `summary_service.py`, FX/price lookup | Cut repeated FX + latest-price queries; **summary SQL < 80** on same dev dataset | Low / medium |
| **P2** | **Shared portfolio read context** | New orchestration consumed by performance + Metric Sheet (optionally summary) | Load once: scope, transactions, cash ledger, value series, external flow maps | Medium / **high** (formula sensitivity) |
| **P3** | **Earlier range slicing for cumulative_return** | `performance_service.py` | Reduce full-history work when `range=1Y`; align with value early emit | Medium |
| **P4** | **Metric Sheet warning input reuse** | `analytics/services.py` | Split / NAV / cash warning inputs loaded once per request | Low / medium |
| **P5** | **Optional short-lived cache** | Request or process scope | Only after P1–P4 measured; TTL + invalidation on writes | Medium (invalidation) |
| **P6** | **Dashboard bundle API** | New HTTP surface + frontend | Defer — changes API and client flow | High (API) |

**Deferred from STAB-5A option list:** P2 subsumes shared timeseries + external flows; P6 replaces premature bundle work.

---

## 7. Do not optimize yet

**Avoid major performance refactors while endpoints remain below MVP targets.** Current Postgres numbers justify shipping without deduplication work.

When optimization is undertaken, each change must prove **unchanged results** via:

| Area | Verification |
|------|----------------|
| Summary `current_value` | `test_portfolio_summary_api.py`, `diagnose_summary_vs_performance.py` |
| Latest value history point | Performance value metric tests |
| `cumulative_return` | `test_portfolio_performance_api.py`, finance return tests |
| `twror` | Same + cash-aware external flow tests |
| `xirr` | Summary + Metric Sheet XIRR scope tests |
| **Metric Sheet** metrics / warnings | `test_analytics_performance_metrics_api.py` |
| Warnings (split, NAV, FX) | Analytics split / MF freshness tests |
| All-scope mixed cash-aware / legacy | `test_portfolio_summary_api.py`, cash-aware return tests |

Run **`make test-critical`** before and after any optimization. Re-profile with `profile_dashboard_read_paths.py` on the **same** Postgres database; update [dashboard-read-baseline.md](./dashboard-read-baseline.md).

### Semantics that must not change

- Cash-aware vs legacy rules ([product-rules.md](../product-rules.md))
- FIX-2 all-scope headline aggregation
- Cash-inclusive value, allocation, XIRR, TWROR, cumulative return definitions
- Full-scope Metric Sheet XIRR (`metrics.return.xirr_scope: full_scope`)
- TWROR vs XIRR external flow sign conventions
- Display FX: bulk maps, 7-day fill, no live FX on read paths
- FIFO / split-adjusted valuation invariants

---

## 8. Recommended next phase (STAB-5C+)

When triggers in §1 fire:

1. **P1 only first** — summary bulk FX/price loading; re-profile; stop if summary < 80 SQL and latency acceptable.
2. **P2 behind feature flag or internal API** — shared read context for performance + Metric Sheet; golden diff tests on all metrics.
3. Add profiler **`--compare tmp/dashboard_read_baseline_postgres.json`** for regression gates (optional tooling).
4. **P6 (bundle API)** only if parallel requests still exceed targets after P1–P4.

Until then: monitor via optional release checklist performance step; no code changes required.

---

## 9. Profiler maintenance

| Component | Path |
|-----------|------|
| CLI | `backend/scripts/profile_dashboard_read_paths.py` |
| Helper | `backend/diagnostics/dashboard_read_profile.py` |

Arguments: `--username`, `--portfolio-id`, `--portfolio-scope=all`, `--display-currency`, `--json-out`, `--verbose`

See [workflows.md § Performance profiling](../workflows.md).
