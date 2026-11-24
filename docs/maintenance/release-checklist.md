# Release checklist

Pre-release verification:

- **[mvp-release-checklist.md](../mvp-release-checklist.md)**

Includes API smoke tests, migration review, and manual UI checks.

Feature releases with their own evidence and rollout steps:

- [Cache-first provisional MF NAV (#48)](mf-nav-48-release.md)

## Documentation (before release)

1. Read [Documentation update policy](documentation-update-policy.md) — confirm user-visible changes have changelog entries.
2. Update reference pages if API routes, env vars, Makefile targets, or CSV formats changed.
3. Run validation:

```bash
make docs-build
make docs-check
```

**Expected:** `docs-check: OK`

4. If UI workflows changed, check [Docs visual backlog](docs-visual-backlog.md) for pending screenshots.

Related: [current-state.md](../current-state.md) · [changelog.md](../changelog.md)
