# Add a frontend page

Contributor checklist — API-driven UI only.

1. Add route in `frontend/src/App.jsx`
2. Add page under `frontend/src/pages/`
3. Fetch via `frontend/src/api.js` — no FIFO, XIRR, FX, or valuation math in React
4. Match existing layout primitives (`PageHeader`, `AppCard`, etc.)
5. Add Vitest in `frontend/src/pages/*.test.jsx`
6. Document route in [Frontend routes](../reference/frontend-routes.md)

Design rules: [frontend-design.md](../frontend-design.md) · [page-layouts.md](../page-layouts.md)
