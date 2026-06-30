# Troubleshooting

Pick the symptom. Each page has copy-paste checks and fixes.

## Quick checks

**Are dev servers running?**

```bash
make ports
```

**Expected:** listeners on `8000`, `5173`, `8002`. If not:

```bash
make stop-dev && make dev
```

**Is the API up?**

```bash
curl -s http://127.0.0.1:8000/api/v1/health
```

**Expected:** HTTP 200 with `"status":"ok"`.

## By symptom

| Problem | Page |
|---------|------|
| Cannot log in or redirect loops | [Login issues](login-issues.md) |
| Google OAuth errors | [Google OAuth errors](google-oauth-errors.md) |
| Missing prices or NAVs on dashboard | [Missing prices or NAVs](missing-prices-navs.md) |
| Dashboard feels slow | [Dashboard is slow](dashboard-slow.md) |
| Worried about database safety | [Database safety problems](database-safety.md) |
| Port already in use / wrong URL | [Dev server and port issues](dev-server-ports.md) |

## Still stuck?

1. Run `make docs-check` if you changed docs.
2. Run `make test-critical` if you changed code.
3. See [Data safety](../concepts/data-safety.md) before any destructive DB action.

Deep workflow: [workflows.md](../workflows.md)
