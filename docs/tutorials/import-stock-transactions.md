# Import stock transactions

Goal: load stock BUY/SELL history from CSV.

## Before you start

- Pick the target **portfolio** in the Transactions page scope (not All Portfolios for writes)
- Ensure CSV matches the stock format — see [CSV formats](../reference/csv-formats.md)

## Steps

1. Open **Transactions**
2. Expand **Supported CSV formats** for column rules
3. Click **Import** and choose your file
4. If cash-aware mode is on and cash is short, use the **cash preview** flow before confirming

## API (optional)

`POST /api/v1/transactions/import-csv` — all-or-nothing; row-level errors return `400`.

## Next

- [Add mutual fund transactions](add-mutual-fund-transactions.md)
- [Transactions as source of truth](../concepts/transactions-source-of-truth.md)

Deep spec: [API design — CSV import](../api-design.md)
