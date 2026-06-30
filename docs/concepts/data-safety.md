# Data safety

Your local Postgres database (`portfolio_insight_kpulla6`) holds real portfolio data. Treat it like production.

## Before risky work

```bash
make backup-db
make db-safety-check
```

**Expected from backup:**

```text
Backup written: backups/kpulla6_YYYYMMDD_HHMMSS.sql (… bytes)
```

**Expected from safety check:** transaction count, portfolio count, recent transaction rows.

Record the counts. Compare again after migrations or bulk edits.

## Safe experiments

Use SQLite for tests and scripts:

```bash
make test-backend
```

**Expected:** pytest passes with `DJANGO_TEST_USE_SQLITE=1` — no Docker required.

## Never on live dev Postgres without backup + explicit intent

- `Transaction.objects.delete()` or bulk `.delete()`
- `manage.py flush`
- `make db-reset`
- `docker compose down -v`
- Ad-hoc scripts that mutate transactions

## If something went wrong

1. `make stop-dev`
2. Restore from latest `backups/kpulla6_*.sql`
3. Read [Database safety problems](../troubleshooting/database-safety.md)

## More detail

- Full policy: [data-safety.md](../data-safety.md)
- Backup how-to: [Back up and restore](../how-to/backup-restore-database.md)
