# Backend module map

| Area | Location |
|------|----------|
| API views | `backend/*/views.py` |
| Services | `backend/*/services.py`, `*_services.py` |
| Pure finance | `backend/finance/` |
| Portfolio scope | `backend/portfolios/` |
| Transactions | `backend/transactions/` |
| Debt / FD / banks | `backend/debt/` |
| Sync commands | `backend/market_data/management/commands/` |

Architecture: [architecture.md](../architecture.md) · Graphify: `make graphify` (optional navigation aid)
