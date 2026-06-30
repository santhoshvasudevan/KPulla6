# Transactions as source of truth

Every holding, cost basis, and cash movement derives from **Transaction** rows.

## Implications

- Edits and imports change downstream holdings, summary, and performance
- Deletes are destructive — use data-safety workflow
- Portfolio assignment is per transaction (bulk assign supported)

## Not source of truth

- Cached prices, FX, NAVs (refreshable)
- Computed metrics (rebuilt from transactions + cache)

## Cash-aware mode

When enabled, trades validate against portfolio cash; settlements post ledger entries.

Details: [cash-ledger.md](../cash-ledger.md) · [product-rules.md](../product-rules.md)
