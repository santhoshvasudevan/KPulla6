# Docs images

Store MkDocs screenshots and diagrams here.

## Conventions

| Rule | Detail |
|------|--------|
| Format | PNG or WebP |
| Naming | `section-feature.png` (e.g. `dashboard-overview.png`) |
| Alt text | Descriptive `alt` text in the image tag |
| Size | Prefer width ≤ 1200px for fast loads |

## Usage in pages

From a doc one level below `docs/` (e.g. `tutorials/`, `getting-started/`), embed with a Markdown image. Use a relative path such as `../assets/images/your-file.png` and add optional caption text on the line below.

## Capturing screenshots (manual)

1. Run `make dev`
2. Log in at http://127.0.0.1:5173/login
3. Open the target route (see [visual backlog](../../maintenance/docs-visual-backlog.md#how-to-capture-screenshots))
4. Capture with your OS or browser screenshot tool
5. Save to `docs/assets/images/` with the exact filename from the backlog
6. Replace the pending callout in the doc page with the image markup above
7. Run `make docs-build` and `make docs-check`

Review captures for PII before committing. Do not add credentials to `.env` for documentation work.

### Pass 1 filenames

| File | Route |
|------|-------|
| `docs/assets/images/dashboard-overview.png` | `/` |
| `docs/assets/images/transactions-filters.png` | `/transactions` |
| `docs/assets/images/settings-theme-selector.png` | `/settings#settings-display` |
