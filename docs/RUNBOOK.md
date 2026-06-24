# ResearchOS Runbook

## Prerequisites

- Docker Desktop (or Docker Engine + Compose v2)
- Node.js >= 20 (for local frontend dev; not required if using Docker web image)
- pnpm >= 9 (via corepack: `corepack enable`)

## Quick start (one command)

```bash
pnpm stack:full
```

This runs: `down` → `up --build` → `migrate` → `seed`. After it finishes the
stack is live and the demo account is ready.

If `pnpm` is not available, use the equivalent docker compose commands directly
(see below).

## Step-by-step commands

```bash
# 1. Start all services (postgres, redis, minio, api, worker, web)
docker compose -f infra/docker/docker-compose.yml up -d --build
# or: pnpm stack:up

# 2. Apply database migrations
docker compose -f infra/docker/docker-compose.yml exec -T api alembic upgrade head
# or: pnpm stack:migrate

# 3. Seed demo data (idempotent -- safe to re-run)
docker compose -f infra/docker/docker-compose.yml exec -T api python -m researchos.seed.demo
# or: pnpm stack:seed
```

## Access the application

- Web: <http://localhost:3000>
- API docs: <http://localhost:8000/docs>
- MinIO console: <http://localhost:9001> (researchos / researchos)

## Demo account

| Field | Value |
|---|---|
| Email | `demo@researchos.dev` |
| Password | `demo-password-123` |
| Project | ResearchOS Demo |

## Core page URLs

| Page | URL pattern |
|---|---|
| Login | <http://localhost:3000/login> |
| Project list | <http://localhost:3000/projects> |
| Overview | `/projects/{projectId}/overview` |
| Research Copilot | `/projects/{projectId}/research` |
| AI IDE | `/projects/{projectId}/ide` |
| Experiments | `/projects/{projectId}/experiments` |
| Paper Workspace | `/projects/{projectId}/paper` |
| Skills Marketplace | `/projects/{projectId}/skills` |
| Skill Builder | `/projects/{projectId}/skills/builder` |
| Settings | `/projects/{projectId}/settings` |

Get your project ID from the project list page or run:

```bash
curl -s -c /tmp/c.txt -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@researchos.dev","password":"demo-password-123"}' >/dev/null && \
curl -s -b /tmp/c.txt http://localhost:8000/organizations | \
  python3 -c "import sys,json;d=json.load(sys.stdin);print('org:',d[0]['id'])" && \
ORG=$(curl -s -b /tmp/c.txt http://localhost:8000/organizations | python3 -c "import sys,json;print(json.load(sys.stdin)[0]['id'])") && \
curl -s -b /tmp/c.txt "http://localhost:8000/projects?organization_id=$ORG" | \
  python3 -c "import sys,json;d=json.load(sys.stdin);print('project:',d['items'][0]['id'])"
```

## Language switching

The UI defaults to **Chinese (zh-CN)**. Switch to English via the dropdown in the
top-right corner of any page (or the login page). The choice is persisted in
`localStorage`.

## How to configure a real LLM

1. Log in and open **Settings** → **LLM** section.
2. Click **Add config**.
3. Fill: provider type (`openai_compatible` or `anthropic`), base URL, model
   name, and your API key.
4. Save. All AI panels (Research Copilot, Critic, Coding Agent, Paper
   Assistant, Experiment Analysis) will use this configuration instead of the
   mock provider.
5. API keys are stored **per project** in the database and are **never exposed
   to the frontend** (the UI only shows a masked version, e.g. `****1234`).

Without a saved LLM config, all agents run on the built-in mock provider, which
returns deterministic answers and never makes external calls or spends money.

## Running tests

```bash
# All backend tests (inside the compose network)
docker compose -f infra/docker/docker-compose.yml -f infra/docker/docker-compose.test.yml run --rm test
# or: pnpm stack:test

# Lint + typecheck (backend)
docker compose -f infra/docker/docker-compose.yml exec -T api ruff check .
docker compose -f infra/docker/docker-compose.yml exec -T api mypy .

# Lint + typecheck + build (frontend)
pnpm -r typecheck
pnpm --filter web build
```

## API smoke test (PowerShell)

```powershell
.\scripts\smoke_api.ps1
```

This logs in as the demo user and hits every core API endpoint, reporting
pass/fail for each.

## Stopping

```bash
docker compose -f infra/docker/docker-compose.yml down
# or: pnpm stack:down
```

To also remove volumes (destroys all local data):

```bash
docker compose -f infra/docker/docker-compose.yml down -v
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| "port is already allocated" (5432/6379) | A local PostgreSQL or Redis is running. Stop it, or change ports in `infra/docker/docker-compose.yml`. |
| skills catalog is empty after startup | The first-party skill catalog is seeded during API startup *after* migrations run. `docker compose restart api` to re-trigger, or run `pnpm stack:seed`. |
| /readyz reports postgres down | Wait a few seconds; the PostgreSQL container may still be initialising. |
| web page redirects to /login on every refresh | Session cookies require `credentials: "include"`. Make sure you are accessing from the same origin or CORS is configured. |
| "Event loop is closed" in worker logs | This is the Phase 2 fix (`asyncio_runner`). If it recurs, ensure `DB_USE_NULLPOOL=true` in the worker env. |
| outbound arXiv search returns 0 | The container may not have internet access. The arXiv provider is tested via a recorded fixture. |
