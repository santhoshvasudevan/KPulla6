# Cursor maintenance workflow

How to change KPulla6 safely with Cursor or any editor.

## Before you edit

1. Read [agents.md](../agents.md) — points to root `AGENTS.md`
2. Read the domain doc (cash, FD, API, etc.)
3. Prefer the smallest change that fixes the problem

## While you edit

| Rule | Why |
|------|-----|
| Views stay thin | Logic belongs in `*_services.py` or `backend/finance/` |
| No finance math in React | API returns computed numbers |
| No live market calls on GET | Use cached `HistoricalPrice` / NAV / FX |
| Migrations only for schema | No runtime `ALTER TABLE` |

## Before you commit

**Code or API changes**

```bash
make test-backend          # or targeted pytest file
cd frontend && npm test -- --run   # if UI changed
```

**Docs or API contract changes**

```bash
make docs-check
```

**Expected:** `docs-check: OK`

**Behavior changes:** add a line to [changelog.md](../changelog.md).

## Graphify (optional)

Navigation aid only — not source of truth.

```bash
make graphify
```

Run after major structural changes. Skip for small fixes. Policy: `.cursor/rules/graphify.mdc`.

## Docs site locally

```bash
make docs-serve
```

**Open:** http://127.0.0.1:8002

Audit docs vs code: [Audit docs vs code](../how-to/audit-docs-vs-code.md)

Full dev workflow: [workflows.md](../workflows.md)
