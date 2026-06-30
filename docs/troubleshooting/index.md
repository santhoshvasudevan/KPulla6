# Troubleshooting

Pick a **symptom**. Run the quick checks first.

## Quick checks

```bash
make ports
curl -s http://127.0.0.1:8000/api/v1/health
```

| Check | Expected |
|-------|----------|
| `make ports` | Listeners on `8000`, `5173`, `8002` |
| Health `curl` | HTTP 200, `"status":"ok"` |

If ports are wrong: [Dev server and port issues](dev-server-ports.md)

## By symptom

| Symptom | Page |
|---------|------|
| Cannot log in / redirect loop | [Login issues](login-issues.md) |
| Google OAuth error | [Google OAuth errors](google-oauth-errors.md) |
| Missing prices or NAVs | [Missing prices or NAVs](missing-prices-navs.md) |
| Dashboard slow | [Dashboard is slow](dashboard-slow.md) |
| Database safety concern | [Database safety problems](database-safety.md) |
| Port in use / wrong URL | [Dev server and port issues](dev-server-ports.md) |

!!! tip "Template"
    Contributors: follow [Doc page templates](../maintenance/doc-page-templates.md) § Troubleshooting.

## Still stuck?

1. `make docs-check` — if you changed docs
2. `make test-critical` — if you changed code
3. [Data safety](../concepts/data-safety.md) — before any destructive DB action

## Next

- [Quickstart](../getting-started/quickstart.md)
- [Common commands](../getting-started/common-commands.md)

## Related

- [workflows.md](../workflows.md) · [data-safety.md](../data-safety.md)
