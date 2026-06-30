# Portfolio performance: XIRR, TWROR, cumulative return

All metrics are computed **server-side** in `backend/finance/`.

| Metric | Meaning (short) |
|--------|------------------|
| **XIRR** | Money-weighted annualized return (IRR on cash flows) |
| **TWROR** | Time-weighted return — strips effect of external cash flows |
| **Cumulative return** | Total return over the selected range |

## UI

Dashboard performance chart toggles these metrics. Summary headline shows **XIRR** for the scope.

## Rules

- Frontend must not reimplement formulas
- Benchmark overlay uses cached index prices, not live feeds

Deep spec: [product-rules.md](../product-rules.md) · [Return metrics](../portfolio-finance/04-return-metrics.md)
