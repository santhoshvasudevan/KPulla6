# Back up and restore the database

## Backup

```bash
make backup-db
```

Writes `backups/kpulla6_YYYYMMDD_HHMMSS.sql`.

## Safety check

```bash
make db-safety-check
```

Records transaction and portfolio counts before risky work.

## Restore (manual)

Only when you intentionally replace data — stop the app first:

```bash
make stop-dev
# restore with psql or docker exec pg_restore pattern — see data-safety.md
```

**Never** run `make db-reset`, `docker compose down -v`, or `flush` on personal dev data without explicit intent and a fresh backup.

Full policy: [Data safety](../concepts/data-safety.md) · [data-safety.md](../data-safety.md)

Troubleshooting: [Database safety problems](../troubleshooting/database-safety.md)
