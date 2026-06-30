# Import stock transactions

Load stock BUY/SELL history from CSV.

## Before you start

```bash
make dev
```

Sign in: [Login and first use](../getting-started/login-and-first-use.md)

- Pick the target **portfolio** in the Transactions page scope (not All Portfolios for writes)
- Ensure CSV matches the stock format — see [CSV formats](../reference/csv-formats.md)

## Steps

### 1. Open Transactions

http://127.0.0.1:5173/transactions

<div class="screenshot-placeholder" markdown="1">
!!! warning "Screenshot pending — transaction filters"
    **Save as:** `docs/assets/images/transactions-filters.png`  
    **Capture when:** filter row visible (portfolio, symbols, date mode).  
    **Notice:** Scope matches the portfolio you will import into.  
    **Workflow:** [How to capture screenshots](../maintenance/docs-visual-backlog.md#how-to-capture-screenshots)  
    **Troubleshooting:** [Login issues](../troubleshooting/login-issues.md) if redirected to `/login`.
</div>

### 2. Review CSV format

Expand **Supported CSV formats** for column rules.

### 3. Import

Click **Import** and choose your file.

**Expected:** success toast or row-level errors in the response (all-or-nothing).

### 4. Cash preview (if applicable)

If cash-aware mode is on and cash is short, confirm the **cash preview** flow before importing.

## You are done when…

- [ ] New rows appear in the table for the selected portfolio
- [ ] Holdings update after refresh (if prices are cached)

## API (optional)

`POST /api/v1/transactions/import-csv` — see [Transactions API](../reference/api-transactions.md).

## Troubleshooting

| Issue | Page |
|-------|------|
| `400` row errors | Fix CSV — [CSV formats](../reference/csv-formats.md) |
| Cannot access page | [Login issues](../troubleshooting/login-issues.md) |

## Next

- [Add mutual fund transactions](add-mutual-fund-transactions.md)
- [Transactions as source of truth](../concepts/transactions-source-of-truth.md)

## Related

- [API design — CSV import](../api-design.md)
