# AGENTS.md — KPulla6

- Inspect existing code before editing.
- Make the smallest safe change.
- Do not rewrite unrelated files.
- Do not reset, wipe, or recreate user data.
- Add or update tests for logic, API, DB, or calculation changes.
- State test results clearly.
- KPulla5 (`../KPulla5/`) is the reference implementation — do not modify it.
- Backend: Django + Django REST Framework; schema changes via Django migrations only (no runtime `ALTER TABLE`).
- Database: PostgreSQL via Docker Compose (`make db`); do not install PostgreSQL globally.
- Finance logic lives in `backend/finance/` and must stay framework-independent.
- React frontend is API-driven; no finance calculations in the frontend.
- Preserve `/api/v1` contracts where practical when porting from KPulla5.
- Transactions remain source of truth; historical prices and FX rates are cached in DB.
- No live yfinance or external market-data calls during dashboard rendering.
