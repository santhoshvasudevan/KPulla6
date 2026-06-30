.PHONY: db db-stop db-logs db-shell db-reset backup-db db-safety-check backend frontend migrate seed bootstrap test test-backend test-frontend test-fast test-critical test-all dev setup-backend setup-frontend setup-docs docs-serve docs-build docs-check sync-prices sync-benchmarks sync-fx sync-mutual-fund-navs sync-market-data refresh graphify ports stop-backend stop-frontend stop-docs stop-dev stop-all clean-dev

BACKEND_DIR := backend
FRONTEND_DIR := frontend
VENV := $(BACKEND_DIR)/.venv
PYTHON := .venv/bin/python3
PIP := .venv/bin/pip

BACKEND_PORT ?= 8000
FRONTEND_PORT ?= 5173
DOCS_PORT ?= 8002
POSTGRES_CONTAINER := kpulla6_postgres
POSTGRES_DB ?= portfolio_insight_kpulla6
POSTGRES_USER ?= santhosh_admin
BACKUP_DIR := backups

db:
	docker compose up -d postgres

db-stop:
	docker compose stop postgres

db-logs:
	docker compose logs -f postgres

db-shell:
	docker exec -it kpulla6_postgres psql -U santhosh_admin -d portfolio_insight_kpulla6

db-reset:
	docker compose down -v
	docker compose up -d postgres

backup-db: db
	@mkdir -p $(BACKUP_DIR)
	@set -a && [ -f .env ] && . ./.env; set +a; \
	BACKUP_FILE="$(BACKUP_DIR)/kpulla6_$$(date +%Y%m%d_%H%M%S).sql"; \
	echo "Backing up $${POSTGRES_DB:-$(POSTGRES_DB)} to $$BACKUP_FILE"; \
	docker exec $(POSTGRES_CONTAINER) pg_dump -U $${POSTGRES_USER:-$(POSTGRES_USER)} -d $${POSTGRES_DB:-$(POSTGRES_DB)} --no-owner --no-acl > "$$BACKUP_FILE"; \
	echo "Backup written: $$BACKUP_FILE ($$(wc -c < "$$BACKUP_FILE" | tr -d ' ') bytes)"

db-safety-check: db
	@set -a && [ -f .env ] && . ./.env; set +a; \
	DB=$${POSTGRES_DB:-$(POSTGRES_DB)}; \
	USER=$${POSTGRES_USER:-$(POSTGRES_USER)}; \
	echo "=== KPulla6 database safety check ==="; \
	echo "Database: $$DB"; \
	echo "Container: $(POSTGRES_CONTAINER)"; \
	echo ""; \
	docker exec $(POSTGRES_CONTAINER) psql -U $$USER -d $$DB -c "SELECT COUNT(*) AS transaction_count FROM transactions;" -c "SELECT COUNT(*) AS portfolio_count FROM portfolios;" -c "SELECT COUNT(*) AS historical_price_count FROM historical_prices;" -c "SELECT id, type, asset_symbol, date, created_at FROM transactions ORDER BY id DESC LIMIT 5;"

setup-backend:
	test -d $(VENV) || python3 -m venv $(VENV)
	cd $(BACKEND_DIR) && $(PIP) install -r requirements.txt

setup-frontend:
	cd $(FRONTEND_DIR) && npm install

setup-docs: setup-backend
	cd $(BACKEND_DIR) && $(PIP) install -r ../requirements-docs.txt

docs-serve: setup-docs
	@set -a && [ -f .env ] && . ./.env; set +a; \
	cd $(BACKEND_DIR) && $(PYTHON) -m mkdocs serve -f ../mkdocs.yml -a 127.0.0.1:$(DOCS_PORT)

docs-build: setup-docs
	@set -a && [ -f .env ] && . ./.env; set +a; \
	cd $(BACKEND_DIR) && $(PYTHON) -m mkdocs build -f ../mkdocs.yml

docs-check: setup-docs
	@set -a && [ -f .env ] && . ./.env; set +a; \
	cd $(BACKEND_DIR) && $(PYTHON) -m mkdocs build -f ../mkdocs.yml --strict
	cd $(BACKEND_DIR) && $(PYTHON) ../scripts/check_docs_consistency.py --strict

backend: setup-backend db
	@set -a && [ -f .env ] && . ./.env; set +a; \
	cd $(BACKEND_DIR) && $(PYTHON) manage.py runserver 0.0.0.0:$(BACKEND_PORT)

frontend: setup-frontend
	cd $(FRONTEND_DIR) && npm run dev -- --host 0.0.0.0 --port $(FRONTEND_PORT)

migrate: setup-backend db
	@set -a && [ -f .env ] && . ./.env; set +a; \
	cd $(BACKEND_DIR) && $(PYTHON) manage.py migrate

seed: setup-backend db migrate
	@set -a && [ -f .env ] && . ./.env; set +a; \
	cd $(BACKEND_DIR) && $(PYTHON) manage.py seed_initial_data

bootstrap: db migrate seed

test: test-backend test-frontend

test-backend: setup-backend
	@set -a && [ -f .env ] && . ./.env; set +a; \
	cd $(BACKEND_DIR) && DJANGO_TEST_USE_SQLITE=1 $(PYTHON) -m pytest

test-frontend: setup-frontend
	cd $(FRONTEND_DIR) && npm test -- --run

# Fast feedback: pure finance + cash service unit tests (~1 min)
test-fast: setup-backend
	@set -a && [ -f .env ] && . ./.env; set +a; \
	cd $(BACKEND_DIR) && DJANGO_TEST_USE_SQLITE=1 $(PYTHON) -m pytest \
	  tests/test_finance_returns.py \
	  tests/test_finance_performance_stats.py \
	  tests/test_finance_risk_metrics.py \
	  tests/test_finance_drawdowns.py \
	  tests/test_finance_comparison.py \
	  tests/test_finance_domain.py \
	  tests/test_finance_cash.py \
	  tests/test_cash_services.py \
	  -q

# Golden-flow confidence before major merges (backend API + key frontend pages)
test-critical: setup-backend setup-frontend
	@set -a && [ -f .env ] && . ./.env; set +a; \
	cd $(BACKEND_DIR) && DJANGO_TEST_USE_SQLITE=1 $(PYTHON) -m pytest \
	  tests/test_cash_api.py \
	  tests/test_cash_aware_transactions_api.py \
	  tests/test_portfolio_summary_api.py \
	  tests/test_portfolio_performance_api.py \
	  tests/test_analytics_performance_metrics_api.py \
	  tests/test_analytics_asset_metrics_api.py \
	  tests/test_analytics_compare_api.py \
	  tests/test_transactions_api.py \
	  tests/test_csv_import_cash_preview.py \
	  -q
	cd $(FRONTEND_DIR) && npm test -- --run \
	  src/pages/Cash.test.jsx \
	  src/pages/Dashboard.test.jsx \
	  src/pages/Transactions.test.jsx \
	  src/pages/Compare.test.jsx \
	  src/components/TransactionModal.test.jsx \
	  src/components/metricSheet/metricSheet.test.jsx \
	  src/api.test.js

# Release confidence: full test suites + production build
test-all: test
	cd $(FRONTEND_DIR) && npm run build

sync-prices: setup-backend db migrate
	@set -a && [ -f .env ] && . ./.env; set +a; \
	cd $(BACKEND_DIR) && $(PYTHON) manage.py sync_prices

sync-benchmarks: setup-backend db migrate
	@set -a && [ -f .env ] && . ./.env; set +a; \
	cd $(BACKEND_DIR) && $(PYTHON) manage.py sync_benchmarks

sync-fx: setup-backend db migrate
	@set -a && [ -f .env ] && . ./.env; set +a; \
	cd $(BACKEND_DIR) && $(PYTHON) manage.py sync_fx_rates

sync-mutual-fund-navs: setup-backend db migrate
	@echo "==> Syncing mutual fund NAVs (cached HistoricalPrice, asset_type=MUTUAL_FUND)"
	@set -a && [ -f .env ] && . ./.env; set +a; \
	cd $(BACKEND_DIR) && $(PYTHON) manage.py sync_mutual_fund_navs

sync-market-data: setup-backend db migrate
	@echo "==> Syncing valuation cache: stock prices, benchmark indices, FX rates, mutual fund NAVs"
	@set -a && [ -f .env ] && . ./.env; set +a; \
	cd $(BACKEND_DIR) && $(PYTHON) manage.py sync_market_data

refresh: sync-market-data
	@echo "==> Refresh complete (stocks, benchmarks, FX, mutual fund NAVs)"

dev: setup-backend setup-frontend setup-docs db migrate
	@set -a && [ -f .env ] && . ./.env; set +a; \
	cd $(BACKEND_DIR) && $(PYTHON) manage.py runserver 0.0.0.0:$(BACKEND_PORT) & \
	cd $(BACKEND_DIR) && $(PYTHON) -m mkdocs serve -f ../mkdocs.yml -a 127.0.0.1:$(DOCS_PORT) & \
	cd $(FRONTEND_DIR) && npm run dev -- --host 0.0.0.0 --port $(FRONTEND_PORT)

graphify:
	graphify update .

ports:
	@echo "Port $(BACKEND_PORT) (backend):"
	@lsof -nP -iTCP:$(BACKEND_PORT) -sTCP:LISTEN 2>/dev/null || echo "  (none)"
	@echo ""
	@echo "Port $(FRONTEND_PORT) (frontend):"
	@lsof -nP -iTCP:$(FRONTEND_PORT) -sTCP:LISTEN 2>/dev/null || echo "  (none)"
	@echo ""
	@echo "Port $(DOCS_PORT) (docs):"
	@lsof -nP -iTCP:$(DOCS_PORT) -sTCP:LISTEN 2>/dev/null || echo "  (none)"

stop-backend:
	@for PID in $$(lsof -ti :$(BACKEND_PORT) 2>/dev/null); do \
		echo "Stopping backend PID $$PID on port $(BACKEND_PORT)"; \
		kill $$PID 2>/dev/null || true; \
	done

stop-frontend:
	@for PID in $$(lsof -ti :$(FRONTEND_PORT) 2>/dev/null); do \
		echo "Stopping frontend PID $$PID on port $(FRONTEND_PORT)"; \
		kill $$PID 2>/dev/null || true; \
	done

stop-docs:
	@for PID in $$(lsof -ti :$(DOCS_PORT) 2>/dev/null); do \
		echo "Stopping docs PID $$PID on port $(DOCS_PORT)"; \
		kill $$PID 2>/dev/null || true; \
	done

stop-dev: stop-backend stop-frontend stop-docs

stop-all: stop-dev
	docker compose stop postgres

clean-dev: stop-all
	@$(MAKE) ports
