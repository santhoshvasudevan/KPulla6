# Docs consistency checks

```bash
make docs-check
```

Runs `mkdocs build --strict` then `scripts/check_docs_consistency.py --strict`.

## What the script checks

| Check | Purpose |
|-------|---------|
| Required Diátaxis pages | Core pages from the doc portal exist |
| `mkdocs.yml` nav | Every nav entry points to a real file |
| Local Markdown links | Internal links resolve under `docs/` |
| API path cross-check | Endpoint index in `api-design.md` matches Django urls |
| Stale terminology | Conservative warnings (e.g. tear-sheet → Metric Sheet) |
| Screenshot backlog | Row marked **Done** must have PNG on disk; placeholder must not remain if PNG exists |

The script is **read-only** — it does not auto-edit files. It does not infer changelog requirements from git (too noisy).

**Policy:** [Documentation update policy](documentation-update-policy.md)

## Terminology warnings

| Pattern | Prefer |
|---------|--------|
| tear-sheet | Metric Sheet |
| sidebar (current UI) | header / top nav |
| planned / not wired | only if still true in code |

How-to: [Audit docs vs code](../how-to/audit-docs-vs-code.md)
