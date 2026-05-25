.PHONY: db db-stop db-logs db-shell db-reset backend frontend migrate seed bootstrap test test-backend test-frontend dev setup-backend setup-frontend sync-prices sync-benchmarks sync-fx sync-market-data refresh graphify ports stop-backend stop-frontend stop-dev stop-all clean-dev

BACKEND_DIR := backend
FRONTEND_DIR := frontend
VENV := $(BACKEND_DIR)/.venv
PYTHON := .venv/bin/python3
PIP := .venv/bin/pip

BACKEND_PORT ?= 8000
FRONTEND_PORT ?= 5173

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
	cd backend && .venv/bin/python manage.py sync_prices
	cd backend && .venv/bin/python manage.py sync_benchmarks
	cd backend && .venv/bin/python manage.py sync_fx_rates

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
