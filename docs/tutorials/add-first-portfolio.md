# Add your first portfolio

Create a real portfolio beyond the virtual **All Portfolios** view.

## Before you start

```bash
make dev
```

**Open:** http://127.0.0.1:5173 and sign in — [Login and first use](../getting-started/login-and-first-use.md)

## Steps

### 1. Open portfolio settings

**Settings** → **Portfolios**

### 2. Create a portfolio

Click **Create portfolio**. Enter name, base currency, optional description. Save.

**Expected:** new portfolio appears in the list.

### 3. Switch scope

Use the header **Portfolio view** selector. Pick your new portfolio.

**Expected:** Transactions and holdings filter to that portfolio.

## Rules (short)

- Max **5** active portfolios (including Default)
- **Default Portfolio** cannot be deactivated
- **All Portfolios** is virtual — not a target for new transactions

Product detail: [Product rules](../product-rules.md)

## Optional: move existing transactions

1. Open **Transactions** (single-portfolio scope)
2. Select rows → bulk assign → your new portfolio

## Next

- [Import stock transactions](import-stock-transactions.md)
- UI layout reference: [page-layouts.md](../page-layouts.md)
