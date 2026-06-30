# Add mutual fund transactions

Goal: record MF BUY/SELL with scheme, folio, and NAV.

## Steps

1. Open **Transactions** → **Add transaction**
2. Choose asset type **Mutual fund**
3. Fill scheme code, folio, investment date, NAV date, units, paid/market value
4. Save — backend verifies against **cached NAV** (no live AMFI call on save)

## CSV import

Use the mutual fund CSV format (Scheme Code + Folio Number headers). See [CSV formats](../reference/csv-formats.md).

## Next

- [Refresh market data](refresh-market-data.md) to sync NAV history
- [Mutual funds concept](../concepts/mutual-funds.md)

Deep spec: [mutual-funds.md](../mutual-funds.md)
