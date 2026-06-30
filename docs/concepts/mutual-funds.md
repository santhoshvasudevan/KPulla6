# Mutual funds

Mutual funds are first-class assets with scheme code, folio, NAV date, and cached NAV validation.

## Key behaviors

- NAV lookup from DB cache on save (no live AMFI on POST)
- Holdings and summary include MF positions like equities
- CSV import uses MF-specific columns

## Sync

`make sync-mutual-fund-navs` or `POST /api/v1/nav/refresh`

Tutorial: [Add mutual fund transactions](../tutorials/add-mutual-fund-transactions.md)

Full spec: [mutual-funds.md](../mutual-funds.md)
