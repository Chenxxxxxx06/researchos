# ResearchOS Monorepo Design

## 1. Goal

The monorepo should keep frontend, backend, workers, shared schemas, infrastructure, and documentation together while preserving clear ownership boundaries.

## 2. Proposed Structure

```text
researchos/
  apps/
    web/
    api/
    worker/
  packages/
    shared-schemas/
    ui/
    agent-protocol/
    skill-sdk/
  infra/
    docker/
    kubernetes/
    terraform/
  docs/
  scripts/
  tests/
```

## 3. Apps

### apps/web

Next.js frontend with product modules, UI components, WebSocket client, and Monaco integrations.

### apps/api

FastAPI backend serving REST APIs, auth, domain services, and WebSocket gateway.

### apps/worker

Celery workers for agents, ingestion, runtime, LaTeX, experiments, and skills.

## 4. Packages

### shared-schemas

JSON Schema, OpenAPI generated types, event schemas, and shared constants.

### ui

Shared UI primitives and ResearchOS-specific components.

### agent-protocol

Agent run schemas, tool-call schemas, memory interfaces, and trace models.

### skill-sdk

Skill manifest types, validators, packaging utilities, and local test harness.

## 5. Dependency Rules

- `apps/web` depends on `packages/ui` and generated API/event types.
- `apps/api` owns domain logic and database models.
- `apps/worker` uses backend services but should keep task code separated by queue.
- Shared packages must not depend on app code.
- Skills communicate through SDK/protocol boundaries, not internal service imports.

## 6. Tooling

- TypeScript package manager: pnpm.
- Python package manager: uv or Poetry.
- API schema generation from FastAPI OpenAPI.
- Alembic for migrations.
- Ruff and mypy for Python.
- ESLint and TypeScript checks for frontend.
- Docker Compose for local development.

## 7. Local Development

Local stack:

- Web app
- API app
- Worker
- PostgreSQL
- Redis
- Object storage emulator
- Vector database or local embedding index

Common commands should cover:

- Start stack
- Run migrations
- Seed first-party skills
- Run frontend
- Run API
- Run workers
- Run tests

## 8. Testing Strategy

- Unit tests for domain services and skill validators.
- API tests for permission and resource behavior.
- Worker tests for idempotent task behavior.
- Frontend component tests for major workspace panels.
- Contract tests for WebSocket event schemas.
- End-to-end tests for MVP closed loop.
