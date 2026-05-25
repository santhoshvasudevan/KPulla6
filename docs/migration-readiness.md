# Migration Readiness — KPulla5 → KPulla6

## Status
KPulla6 is the **active greenfield** implementation. KPulla5 (FastAPI + SQLite) is frozen as reference.

## Layer mapping

| KPulla5 | KPulla6 |
|---------|---------|
| `backend/api/main.py` | DRF views/viewsets in domain apps + `api/` |
| `backend/api/services/` | Django services in `analytics`, app-specific modules |
| `backend/api/repositories/` | Django ORM querysets / repository modules per app |
| `backend/finance/*` | `backend/finance/*` (reused logic, framework-free) |
| `backend/api/schemas.py` | DRF serializers |
| `backend/api/models.py` (SQLAlchemy) | Django models per app |
| FastAPI `BackgroundTasks` | TBD: Celery, RQ, or Django-Q |
| SQLite `portfolio.db` | PostgreSQL via Compose |

## Completed (foundation)
- Project skeleton, Docker Postgres, Makefile, health endpoint
- Django apps created (empty models)
- Docs adapted for new stack

## Next phases
1. **Models + migrations** — port table definitions from KPulla5 to Django models
2. **Repositories / services** — ORM adapters calling `finance/` modules
3. **API endpoints** — port `/api/v1/*` incrementally with contract tests from KPulla5
4. **Background sync** — historical prices + FX (no request-time yfinance)
5. **Frontend pages** — Dashboard, Assets, Transactions, Settings

## Risks
- Hidden SQLAlchemy assumptions in KPulla5 services — validate with integration tests per endpoint
- Postgres date/time types vs SQLite — use `DateField` consistently
- Auth not yet in scope for either app

## Reference
See `../KPulla5/docs/migration-readiness.md` for the original FastAPI→Postgres/Django analysis.
