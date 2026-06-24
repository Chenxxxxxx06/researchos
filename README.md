# ResearchOS

AI-native research operating system. Monorepo containing the web app, API,
worker, shared packages, and infrastructure.

> **Status: Phase 0 — engineering infrastructure only.** No business modules
> (no users / projects / papers / experiments). See `docs/PHASE0_DECISIONS.md`
> for the architecture decisions and `docs/` for the full product/architecture
> design.

## Repository layout

```text
researchos/
  apps/
    web/      Next.js (App Router, TS, Tailwind, TanStack Query, Zustand)
    api/      FastAPI (config, logging, errors, health, Alembic)
    worker/   Celery (queue routing + health tasks; reuses api.common.*)
  packages/
    shared-schemas/   Shared TS contracts (WebSocket events)
  infra/docker/       Dockerfiles + docker-compose (postgres/redis/minio)
  docs/               Product + architecture documentation
  scripts/            Dev helper scripts
```

## Prerequisites

- Docker (for the one-command stack)
- For local non-Docker dev: a Python 3.13 environment, `uv`, Node 20+, and
  `pnpm` (via `corepack`).

This repo was developed against a dedicated Python environment named
`researchos` (see `docs/PHASE0_DECISIONS.md` §4).

## Quick start (Docker)

```bash
# from the repository root
docker compose -f infra/docker/docker-compose.yml up -d --build
# or: pnpm stack:up   |   make up   |   bash scripts/dev_up.sh
```

Then open:

- Web: <http://localhost:3000> — shows live backend health
- API docs: <http://localhost:8000/docs>
- API readiness: <http://localhost:8000/readyz>
- MinIO console: <http://localhost:9001> (researchos / researchos)

Stop the stack:

```bash
docker compose -f infra/docker/docker-compose.yml down   # or: make down
```

## Local development (without Docker)

Start PostgreSQL, Redis, and MinIO (e.g. via the compose file), then:

```bash
# API
cd apps/api
uv pip install -e ".[dev]"          # into your researchos environment
uvicorn researchos.main:app --reload --port 8000

# Worker (separate shell)
cd apps/worker
uv pip install -e ".[dev]"
celery -A researchos_worker.app worker --loglevel=info \
  --queues=agents,ingestion,runtime,latex,experiments,skills,default

# Web (separate shell)
pnpm install
pnpm --filter web dev
```

## Testing

```bash
cd apps/api    && pytest      # health endpoints, error envelope, request id
cd apps/worker && pytest      # celery wiring + health tasks
pnpm -r typecheck             # TypeScript typecheck across web + packages
# or: make test
```

## Database migrations

Alembic is configured (URL injected from settings). Phase 0 has an **empty
baseline** — no business tables yet.

```bash
cd apps/api
alembic upgrade head           # no-op in Phase 0
alembic revision -m "message"  # used from Phase 1 onward
```

## What Phase 0 delivers

- Monorepo with three runnable apps and one shared package.
- Docker Compose stack: PostgreSQL (pgvector), Redis, MinIO, api, worker, web.
- Typed configuration (`pydantic-settings`) shared by api + worker.
- Structured JSON logging with request-id propagation.
- `/healthz` liveness and `/readyz` readiness (probes PG/Redis/object storage).
- Consistent typed error envelope.
- Test framework for api and worker; typecheck for web.
- Verified frontend ↔ backend connectivity (home page renders live readiness).
