.PHONY: db db-stop db-logs db-shell db-reset backup-db db-safety-check backend frontend migrate seed bootstrap test test-backend test-frontend dev setup-backend setup-frontend sync-prices sync-benchmarks sync-fx sync-market-data refresh graphify ports stop-backend stop-frontend stop-dev stop-all clean-dev

BACKEND_DIR := backend
FRONTEND_DIR := frontend
VENV := $(BACKEND_DIR)/.venv
PYTHON := .venv/bin/python3
PIP := .venv/bin/pip

BACKEND_PORT ?= 8000
FRONTEND_PORT ?= 5173
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

backend: setup-backend db
	@set -a && [ -f .env ] && . ./.env; set +a; \
	cd $(BACKEND_DIR) && $(PYTHON) manage.py runserver 0.0.0.0:$(BACKEND_PORT)

frontend: setup-frontend
	cd $(FRONTEND_DIR) && npm run dev -- --port $(FRONTEND_PORT)

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
	cd $(FRONTEND_DIR) && npm test

sync-prices: setup-backend db migrate
	@set -a && [ -f .env ] && . ./.env; set +a; \
	cd $(BACKEND_DIR) && $(PYTHON) manage.py sync_prices

sync-benchmarks: setup-backend db migrate
	@set -a && [ -f .env ] && . ./.env; set +a; \
	cd $(BACKEND_DIR) && $(PYTHON) manage.py sync_benchmarks

sync-fx: setup-backend db migrate
	@set -a && [ -f .env ] && . ./.env; set +a; \
	cd $(BACKEND_DIR) && $(PYTHON) manage.py sync_fx_rates

sync-market-data: setup-backend db migrate
	@set -a && [ -f .env ] && . ./.env; set +a; \
	cd $(BACKEND_DIR) && $(PYTHON) manage.py sync_market_data

dev: setup-backend setup-frontend db migrate
	@set -a && [ -f .env ] && . ./.env; set +a; \
	cd $(BACKEND_DIR) && $(PYTHON) manage.py runserver 0.0.0.0:$(BACKEND_PORT) & \
	cd $(FRONTEND_DIR) && npm run dev -- --port $(FRONTEND_PORT)

refresh: sync-market-data

sync-market-data:
	cd backend && .venv/bin/python manage.py sync_market_data

sync-prices:
	cd backend && .venv/bin/python manage.py sync_prices

sync-benchmarks:
	cd backend && .venv/bin/python manage.py sync_benchmarks

sync-fx:
	cd backend && .venv/bin/python manage.py sync_fx_rates

graphify:
	graphify .

ports:
	@echo "Port $(BACKEND_PORT) (backend):"
	@lsof -nP -iTCP:$(BACKEND_PORT) -sTCP:LISTEN 2>/dev/null || echo "  (none)"
	@echo ""
	@echo "Port $(FRONTEND_PORT) (frontend):"
	@lsof -nP -iTCP:$(FRONTEND_PORT) -sTCP:LISTEN 2>/dev/null || echo "  (none)"

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

stop-dev: stop-backend stop-frontend

stop-all: stop-dev
	docker compose stop postgres

clean-dev: stop-all
	@$(MAKE) ports
