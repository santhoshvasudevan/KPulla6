# Common commands

Copy-paste commands for daily work. Full Makefile: [Make commands](../reference/make-commands.md).

## Daily dev

**Start everything**

```bash
make dev
```

**Then open:** http://127.0.0.1:5173 (app) · http://127.0.0.1:8002 (docs)

**See what is listening**

```bash
make ports
```

**Expected:** lines for ports `8000`, `5173`, and `8002`, or `(none)` if stopped.

**Stop app + docs (keep Postgres)**

```bash
make stop-dev
```

**Stop everything including Postgres**

```bash
make stop-all
```

## Database

**Start Postgres only**

```bash
make db
```

**Apply migrations**

```bash
make migrate
```

**Expected:** `Applying debt.0012_... OK` (or “No migrations to apply”).

**Backup before risky work**

```bash
make backup-db
```

**Expected:** `Backup written: backups/kpulla6_YYYYMMDD_HHMMSS.sql`

**Safety snapshot**

```bash
make db-safety-check
```

**Expected:** transaction count, portfolio count, last 5 transactions printed.

Details: [Data safety](../concepts/data-safety.md)

## Market data

**Sync all caches**

```bash
make refresh
```

**Expected:** `Refresh complete (stocks, benchmarks, FX, mutual fund NAVs)`

**Stocks only**

```bash
make sync-prices
```

**MF NAVs only**

```bash
make sync-mutual-fund-navs
```

## Tests

**Backend + frontend**

```bash
make test
```

**Golden flows before merge**

```bash
make test-critical
```

Uses SQLite — no Docker required.

## Documentation

**Docs only (no app)**

```bash
make docs-serve
```

**Then open:** http://127.0.0.1:8002

**Build static site**

```bash
make docs-build
```

**Expected:** `Documentation built in … seconds` · output in `site/`

**Validate links and nav**

```bash
make docs-check
```

**Expected:** `docs-check: OK`
