# Docs visual backlog

Screenshot and diagram follow-up work. Review captures for PII (emails, balances, account names) before committing.

## Status

| Asset file | Status | Page(s) | Notes |
|------------|--------|---------|-------|
| `dashboard-overview.png` | **Pending** | [read-the-dashboard.md](../tutorials/read-the-dashboard.md), [index.md](../index.md) | Placeholder in doc — capture manually while logged in |
| `transactions-filters.png` | **Pending** | [import-stock-transactions.md](../tutorials/import-stock-transactions.md) | Placeholder in doc — capture manually while logged in |
| `settings-theme-selector.png` | **Pending** | [login-and-first-use.md](../getting-started/login-and-first-use.md) | Settings **Display** section — placeholder in doc |
| `fixed-deposits-holdings.png` | **Pending** | FD pages | Out of scope — do not capture in pass 1 |
| `metric-sheet-preview.png` | **Pending** | Metric Sheet / analytics pages | Out of scope — do not capture in pass 1 |

## How to capture screenshots

1. Run `make dev`
2. Log in normally through the browser at http://127.0.0.1:5173/login
3. Navigate to the target page (table below)
4. Capture the screenshot manually (OS shortcut, browser, or screenshot tool)
5. Save under `docs/assets/images/` using the **exact path** in the table
6. Replace the `!!! warning "Screenshot pending"` callout with a Markdown image + short caption
7. Run `make docs-build` and `make docs-check`
8. Mark the row **Done** in the status table above

### Pass 1 targets

| What to capture | Save as | Route | What to show |
|-----------------|---------|-------|--------------|
| Dashboard overview | `docs/assets/images/dashboard-overview.png` | `/` | KPI cards, allocation, performance chart |
| Transaction filters | `docs/assets/images/transactions-filters.png` | `/transactions` | Filter row (portfolio, symbols, dates) |
| Display preferences | `docs/assets/images/settings-theme-selector.png` | `/settings#settings-display` | Display currency + tax rate form |

**Tips:** Prefer width ≤ 1200px. Crop to the relevant UI. Do not seed or mutate portfolio data for screenshots — use your existing dev login and data.

### Embed after capture

From a tutorial or getting-started page (one level below `docs/`), add a standard Markdown image whose path is `../assets/images/<filename>.png`, plus an optional caption line below.

## Placeholder pattern (current)

Until PNGs exist, pages use:

```markdown
!!! warning "Screenshot pending — …"
    **Save as:** `docs/assets/images/….png`
    …
```

## Related

- [Documentation update policy](documentation-update-policy.md)
- [Doc page templates](doc-page-templates.md)
- [Images guide](../assets/images/guide.md)
