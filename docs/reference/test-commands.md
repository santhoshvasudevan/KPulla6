# Test commands

| Command | Scope |
|---------|--------|
| `make test-backend` | pytest, SQLite (`DJANGO_TEST_USE_SQLITE=1`) |
| `cd frontend && npm test -- --run` | Vitest |
| `make test` | Backend + frontend |
| `make test-critical` | Curated golden flows |

Add tests with every logic/API/UI change. See [workflows.md](../workflows.md) § TDD.

Agent expectation: root `AGENTS.md`
