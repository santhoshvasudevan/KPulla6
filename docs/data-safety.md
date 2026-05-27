# Data Safety — KPulla6

## What happened (2026-05-26)

During debugging of a GOOG stock-split valuation issue, an ad-hoc Django script was run against the **live dev Postgres database** (not test SQLite). The script executed:

```python
Transaction.objects.filter(portfolio=p).delete()
```

That removed ~45 real portfolio transactions from the Default Portfolio. Two synthetic GOOG test rows (BUY 2024-06-01, STOCK_SPLIT 2024-07-15) were inserted in their place. Cached market data (`historical_prices`, FX, benchmarks) was **not** wiped.

Evidence in Postgres at the time of investigation:

- `transactions_id_seq` at 47 with only 2 live rows
- 45 dead tuples on `transactions` (hard deletes, sequence not reset)
- Default Portfolio and ~10k `historical_prices` rows unchanged since initial bootstrap

**Not the cause:** migrations, `make seed` / `make bootstrap`, `make db-reset`, or `make test` (tests use in-memory SQLite).

## Authoritative recovery source

If transactions are missing again, restore from (in order of preference):

1. **`make backup-db`** output under `backups/` (after you adopt this workflow)
2. **KPulla5 SQLite:** `../KPulla5/backend/data/portfolio.db` (41 transactions as of investigation)
3. **CSV exports:** `trans.csv` in repo root (partial; 29 rows)

Do **not** use `make db-reset` to “fix” missing rows — it destroys the entire volume including cached prices.

---

## How to avoid recurrence

| Do | Don't |
|----|-------|
| Run `make test` for logic/API changes | Run `python manage.py shell` or `python -c` against dev Postgres to delete data |
| Set `DJANGO_TEST_USE_SQLITE=1` for scratch scripts | Call `Transaction.objects.filter(...).delete()` on dev DB |
| Run `make backup-db` before risky work | Run `make db-reset` or `docker compose down -v` without explicit intent |
| Run `make db-safety-check` before/after phases | Assume Cursor/agents use test DB automatically |

Agents and humans must follow `AGENTS.md` **Data safety** section.

---

## Safe debugging workflow

### 1. Automated tests (preferred)

```bash
make test              # backend (SQLite) + frontend
make test-backend      # pytest with DJANGO_TEST_USE_SQLITE=1
```

No Docker Postgres required for backend unit tests.

### 2. Ad-hoc Django exploration

Use in-memory SQLite:

```bash
cd backend
DJANGO_TEST_USE_SQLITE=1 .venv/bin/python manage.py shell
```

Or a one-off script with the same env var — **never** omit it when mutating data.

### 3. Dev Postgres (read-only checks)

Safe:

```bash
make db-safety-check
make db-shell          # SELECT queries only unless user approved writes
```

### 4. Migration-heavy or data-sensitive phases

See `docs/workflows.md`:

```bash
make backup-db
make db-safety-check
# ... do the work ...
make db-safety-check
```

---

## Backup workflow

### Create a backup

```bash
make db          # ensure Postgres is running
make backup-db
```

Writes `backups/kpulla6_YYYYMMDD_HHMMSS.sql` via `pg_dump` from container `kpulla6_postgres`.

The `backups/` directory is gitignored; keep copies elsewhere if needed.

### Restore from backup (manual — user-initiated only)

**Warning:** restore overwrites current DB contents for the restored objects. Take a fresh backup first.

```bash
make backup-db   # backup current state before restore
make db-shell    # or:
cat backups/kpulla6_YYYYMMDD_HHMMSS.sql | docker exec -i kpulla6_postgres psql -U santhosh_admin -d portfolio_insight_kpulla6
```

For a full DB replace, stop the app, restore, then verify with `make db-safety-check`.

### Re-import from KPulla5 (if no SQL backup)

1. Export transactions from `../KPulla5/backend/data/portfolio.db` to KPulla6 CSV format.
2. Remove any synthetic test rows in KPulla6 if present.
3. `POST /api/v1/transactions/import-csv` or equivalent import path.
4. Run `make db-safety-check` to confirm counts.

---

## Forbidden commands (without explicit user approval)

| Command / action | Risk |
|------------------|------|
| `make db-reset` | Wipes Docker volume `kpulla6_kpulla6_postgres_data` |
| `docker compose down -v` | Same as above |
| `docker volume rm …` | Permanent data loss |
| `manage.py flush` | Deletes all rows in all tables |
| SQL `TRUNCATE` / bulk `DELETE` | Irreversible row loss |
| `Transaction.objects…delete()` on dev DB | Hard delete; API uses this intentionally — scripts must not |
| Ad-hoc `python -c "…django.setup()…delete()…"` on default `DATABASE_URL` | Caused the 2026-05-26 incident |

---

## Quick reference commands

```bash
make db-safety-check   # DB name, counts, last 5 transactions
make backup-db         # timestamped pg_dump to backups/
make test              # safe; never touches dev Postgres
```
