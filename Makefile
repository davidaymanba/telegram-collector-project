# TUC — common tasks (macOS). The project path may contain spaces, so paths are quoted.
SHELL := /bin/bash
UV ?= uv
PY := $(UV) run python

.PHONY: help install dev dev-api dev-web test test-backend test-frontend lint format typecheck \
        build-frontend migrate seed serve health launchd-install launchd-uninstall launchd-status

help:
	@grep -E '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install: ## Install system deps (brew), Python deps (uv) and frontend deps (npm)
	./scripts/install_macos.sh
	$(UV) sync
	cd frontend && npm install

dev: ## Run API (reload) and Vite dev server together
	@trap 'kill 0' INT TERM; \
	  $(PY) -m app.cli serve --reload --port 8000 & \
	  (cd frontend && npm run dev) & \
	  wait

dev-api: ## API only, with auto-reload
	$(PY) -m app.cli serve --reload --port 8000

dev-web: ## Vite dev server only (proxies /api to :8000)
	cd frontend && npm run dev

test: test-backend test-frontend ## All tests

test-backend: ## pytest against the MySQL *_test database
	$(UV) run pytest

test-frontend: ## Vitest unit tests
	cd frontend && npm test -- --run

lint: ## ruff + mypy + eslint/tsc
	$(UV) run ruff check .
	$(UV) run mypy app
	cd frontend && npm run typecheck

format: ## Auto-format Python
	$(UV) run ruff check --fix .
	$(UV) run ruff format app tests

typecheck:
	$(UV) run mypy app

build-frontend: ## Production build served by FastAPI
	cd frontend && npm install && npm run build

migrate: ## Apply database migrations
	$(PY) -m app.cli init-db --no-import-config

seed: ## Demo data
	$(PY) -m app.cli seed-demo

serve: ## Run the dashboard on 127.0.0.1:8000
	$(PY) -m app.cli serve --host 127.0.0.1 --port 8000

health: ## Health check
	$(PY) -m app.cli health-check

launchd-install: ## Install background LaunchAgents
	$(PY) -m app.cli launchd install

launchd-uninstall: ## Remove background LaunchAgents
	$(PY) -m app.cli launchd uninstall

launchd-status:
	$(PY) -m app.cli launchd status
