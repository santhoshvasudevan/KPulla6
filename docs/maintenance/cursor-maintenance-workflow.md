# Cursor maintenance workflow

## Day to day

1. Read `AGENTS.md` and relevant domain doc before editing
2. Smallest safe change; views thin, logic in services/finance
3. Run targeted tests + `make docs-check` when docs or API contracts change
4. Update `docs/changelog.md` for behavior changes

## Graphify

Optional codebase navigation — run `make graphify` after major structural changes only. See `.cursor/rules/graphify.mdc`.

## Docs site

```bash
make docs-serve    # http://127.0.0.1:8002
make docs-check    # before merging doc-heavy PRs
```

How-to: [Audit docs vs code](../how-to/audit-docs-vs-code.md)

Workflow detail: [workflows.md](../workflows.md)
