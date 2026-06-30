# Database safety problems

## Accidental destructive command

1. Stop further writes (`make stop-dev`)
2. Restore from latest `backups/kpulla6_*.sql` if available
3. Review [data-safety.md](../data-safety.md) incident notes

## Prevention

- Always `make backup-db` before migrations or bulk edits
- Use `make test` (SQLite) for experiments
- Never `flush`, `db-reset`, or bulk delete on live dev Postgres without explicit intent

Concept: [Data safety](../concepts/data-safety.md)

How-to: [Back up and restore](../how-to/backup-restore-database.md)
