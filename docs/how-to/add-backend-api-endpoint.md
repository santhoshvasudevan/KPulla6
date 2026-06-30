# Add a backend API endpoint

Contributor checklist — keep views thin.

1. Read [API design](../api-design.md) and [architecture](../architecture.md)
2. Add business logic in `*_service.py` or `backend/finance/` (pure Python)
3. Wire `urls.py` under `/api/v1/`
4. Add serializer validation only — no heavy math in serializers
5. Add pytest in `backend/tests/`
6. Update `docs/api-design.md` and run `make docs-check`

## Patterns

- Portfolio scope: `portfolios/scope.py`
- Finance DTOs: `transactions/finance_adapter.py`
- No live market-data calls on GET read paths

Agent rules: [Agent rules](../maintenance/agent-rules.md)
