# Docs consistency checks

```bash
make docs-check
```

## What runs

1. **`mkdocs build --strict`** — broken links and nav errors fail the build
2. **`scripts/check_docs_consistency.py --strict`** — nav files, local links, API path cross-check, terminology warnings

## Terminology warnings

| Pattern | Prefer |
|---------|--------|
| tear-sheet | Metric Sheet |
| sidebar (current UI) | header / top nav |
| planned / not wired | only if still true in code |

The script is **read-only** — it does not auto-edit files.

How-to: [Audit docs vs code](../how-to/audit-docs-vs-code.md)
