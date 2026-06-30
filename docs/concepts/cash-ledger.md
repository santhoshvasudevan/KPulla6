# Cash ledger

Portfolio cash is tracked in native currency with optional **cash-aware** trade validation.

## Mental model

- Cash balance = ledger entries derived from transactions and settlements
- Trades can preview cash impact before commit
- Bank accounts and fixed deposits extend the debt/cash picture

## Docs

- [cash-ledger.md](../cash-ledger.md) — canonical spec
- [cash-unification.md](../cash-unification.md) — unified cash model
- Cursor rule: [320-cash-ledger](../cursor-rules/320-cash-ledger.md)

Fixed deposits: [Fixed deposits / debt](fixed-deposits-debt.md)
