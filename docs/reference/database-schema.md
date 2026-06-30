# Database schema

- **[database.md](../database.md)** — tables, relationships, migrations
- Django migrations under `backend/*/migrations/`

Apply schema changes:

```bash
make migrate
```

Never use runtime `ALTER TABLE` — migrations only.
