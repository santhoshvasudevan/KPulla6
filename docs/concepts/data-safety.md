# Data safety

The local Postgres database (`portfolio_insight_kpulla6`) holds real dev portfolio data — treat it as production-like.

## Never without backup + explicit intent

- `Transaction.objects.delete()` / bulk `.delete()`
- `manage.py flush`
- `make db-reset`, `docker compose down -v`
- Ad-hoc scripts mutating transactions on live Postgres

## Safe workflow

1. `make backup-db`
2. `make db-safety-check`
3. Use `make test` / SQLite for experiments

Full guide: [data-safety.md](../data-safety.md) · How-to: [Back up and restore](../how-to/backup-restore-database.md)

Troubleshooting: [Database safety problems](../troubleshooting/database-safety.md)
