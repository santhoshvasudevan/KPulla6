# Dev server and port issues

## Expected ports after `make dev`

| Port | Service |
|------|---------|
| 5432 | PostgreSQL |
| 8000 | Django API |
| 5173 | Vite frontend |
| 8002 | MkDocs docs |

Check:

```bash
make ports
```

## Port already in use

```bash
make stop-dev
# or
make stop-all
```

Then `make dev` again.

## Docs reload loop

If `make docs-serve` rebuilds continuously, something is touching files under `docs/` repeatedly (editor auto-save, agents). Workaround: stop other writers or use `mkdocs serve --no-livereload`.

## Wrong API from iPad

Use `http://<mac-ip>:5173` only — not `:8000`. See [Run on iPad / LAN](../how-to/run-on-ipad-lan.md).

Docs domain: [Local docs domain](../how-to/local-docs-domain.md)
