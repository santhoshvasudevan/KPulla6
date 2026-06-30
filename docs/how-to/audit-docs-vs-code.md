# Audit docs vs code

## Automated check

```bash
make docs-check
```

Runs:

1. `mkdocs build --strict`
2. `scripts/check_docs_consistency.py --strict`

Checks include: nav files exist, local links resolve, API index paths vs Django URLs, stale terminology warnings.

## Manual review areas

| Area | Doc |
|------|-----|
| Implementation status | [current-state.md](../current-state.md) |
| API contracts | [api-design.md](../api-design.md) |
| Product rules | [product-rules.md](../product-rules.md) |
| Obsolete backend code | [Obsolete code audit](../maintenance/obsolete-code-audit.md) |

## Contributor workflow

See [Cursor maintenance workflow](../maintenance/cursor-maintenance-workflow.md) and root `AGENTS.md`.
