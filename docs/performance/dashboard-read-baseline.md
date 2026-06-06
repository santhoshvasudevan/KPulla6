# Dashboard read-path baseline snapshot

Reference timings from `backend/scripts/profile_dashboard_read_paths.py` (service-layer, read-only).  
Re-run before major releases or when Dashboard feels slow:

```bash
cd backend
.venv/bin/python scripts/profile_dashboard_read_paths.py --username USERNAME --verbose \
  --json-out tmp/dashboard_read_baseline_postgres.json
```

Use the Django **username** (not email). JSON output stays under `backend/tmp/` (gitignored).

---

## Real Postgres dev baseline (STAB-5B)

**Captured:** 2026-06-06  
**Environment:** Local Postgres dev database  
**User:** `santhoshkgvasudevan` · **Scope:** `all_active` · **Portfolio IDs:** `[1, 2, 3, 4]` · **Display:** EUR

### Endpoint table

| Endpoint ID | HTTP equivalent | ms | SQL | Points | Warnings |
|-------------|-----------------|----:|----:|-------:|---------:|
| summary | `GET /portfolio/summary?…&include_timeseries=false` | 293.4 | 194 | — | — |
| performance_value_1y | `GET /portfolio/performance?…&metric=value&range=1Y` | 138.1 | 35 | 366 | — |
| performance_value_all | `GET /portfolio/performance?…&metric=value&range=ALL` | 368.0 | 16 | 2432 | — |
| performance_cumulative_return_1y | `GET /portfolio/performance?…&metric=cumulative_return&range=1Y` | 297.4 | 75 | 366 | — |
| performance_twror_1y | `GET /portfolio/performance?…&metric=twror&range=1Y` | 285.5 | 75 | 366 | — |
| metric_sheet_1y | `GET /analytics/performance-metrics?…&range=1Y` | 440.2 | 106 | — | — |
| metric_sheet_all | `GET /analytics/performance-metrics?…&range=ALL` | 762.4 | 87 | — | — |
| holdings | `GET /portfolio/holdings?…` | 64.3 | 35 | — | — |
| **Sequential total** | *(all 8 paths, not one page load)* | **2649.3** | **623** | | |

### Dashboard default load (parallel requests)

The Dashboard fires **three** backend reads on initial load (`metric=value`, `timeRange=1Y`):

| Path | ms | SQL |
|------|---:|----:|
| Summary | 293.4 | 194 |
| Performance value 1Y | 138.1 | 35 |
| Metric Sheet 1Y | 440.2 | 106 |

**Parallel critical path (max of three):** ~**440 ms** backend service time  
**Sequential sum (diagnostic only):** ~**872 ms** · **335 SQL**

All three endpoints are **under the 1 s MVP target** on this dev dataset.

### Top repeated SQL (real Postgres)

| Endpoint | Dominant patterns |
|----------|-------------------|
| **summary** | 97 FX · 57 historical prices · 32 transactions |
| **Metric Sheet 1Y** | 68 historical prices · 21 transactions · 14 FX |
| **cumulative_return / TWROR 1Y** | 52 historical prices · 13 transactions · 8 FX each |

**Observation:** Summary query count (194) is high relative to latency — repeated FX and price lookups, not linear growth with 1Y day count. Value ALL has **2432 points** but only **16 SQL** (good bulk-load pattern).

---

## Synthetic SQLite baseline (STAB-5A reference)

**Environment:** SQLite in-memory (`DJANGO_TEST_USE_SQLITE=1`), synthetic legacy portfolio  
**User:** `profileuser` · **Scope:** `all_active` (1 portfolio) · **Display:** EUR  
**Data:** 3 AAPL BUY rows (~522 calendar days of value history)

| Endpoint ID | ms | SQL | Points |
|-------------|---:|----:|-------:|
| summary | 9.3 | 16 | — |
| performance_value_1y | 4.1 | 5 | 366 |
| performance_value_all | 4.3 | 4 | 522 |
| performance_cumulative_return_1y | 6.5 | 10 | 366 |
| performance_twror_1y | 7.1 | 10 | 366 |
| metric_sheet_1y | 8.9 | 13 | — |
| metric_sheet_all | 10.2 | 12 | — |
| holdings | 2.0 | 4 | 1 |
| **Sequential total** | **52.4** | **74** | |

Use SQLite numbers for **CI / regression shape** only; use Postgres baseline for MVP performance decisions.

---

## MVP targets (STAB-5B decision)

| Target | Real Postgres status |
|--------|----------------------|
| Individual Dashboard endpoint < 1 s | ✅ All measured paths pass |
| Default Dashboard critical path ~< 1 s (parallel) | ✅ ~440 ms max |
| 1Y query count not ∝ range days | ✅ Value 1Y: 35 SQL / 366 points |
| Metric Sheet ALL < 1 s | ✅ 762 ms (acceptable for current data volume) |

See [dashboard-read-paths.md](./dashboard-read-paths.md) for the optimization backlog and **do not optimize yet** guardrails.
