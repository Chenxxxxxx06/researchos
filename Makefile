# ResearchOS developer commands.
# `make` is optional — every target has an equivalent in scripts/ or in the
# root package.json. See README.md.

COMPOSE := docker compose -f infra/docker/docker-compose.yml
PY_ENV  := researchos

.PHONY: help up down logs ps migrate test test-api test-worker lint fmt

help:
	@echo "ResearchOS — common commands"
	@echo "  make up        Start the full local stack (Docker)"
	@echo "  make down      Stop the stack"
	@echo "  make logs      Tail stack logs"
	@echo "  make migrate   Run Alembic migrations (empty baseline in Phase 0)"
	@echo "  make test      Run API + worker tests"
	@echo "  make lint      Ruff + mypy (Python), eslint + tsc (web)"
	@echo "  make fmt       Auto-format Python (ruff)"

up:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

ps:
	$(COMPOSE) ps

migrate:
	cd apps/api && conda run -n $(PY_ENV) alembic upgrade head

test: test-api test-worker

test-api:
	cd apps/api && conda run -n $(PY_ENV) pytest

test-worker:
	cd apps/worker && conda run -n $(PY_ENV) pytest

lint:
	cd apps/api && conda run -n $(PY_ENV) ruff check . && conda run -n $(PY_ENV) mypy researchos
	cd apps/worker && conda run -n $(PY_ENV) ruff check .
	pnpm -r typecheck

fmt:
	cd apps/api && conda run -n $(PY_ENV) ruff check --fix . && conda run -n $(PY_ENV) ruff format .
	cd apps/worker && conda run -n $(PY_ENV) ruff check --fix . && conda run -n $(PY_ENV) ruff format .
