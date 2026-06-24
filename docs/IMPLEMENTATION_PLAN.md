# ResearchOS Implementation Plan

This plan guides the phased implementation of ResearchOS. It intentionally
avoids building the whole product at once. Each phase must start with a design
review, then wait for confirmation before code is
written.

## Global Rules

- Read `docs/*.md` before each phase.
- Keep domain boundaries explicit.
- Prefer production-grade infrastructure over demo-only shortcuts.
- Add migrations for every database change.
- Keep API schemas, DTOs, services, repositories, and domain models separate.
- Put permission checks in service/runtime layers, not only in route handlers.
- Add tests where behavior, security, or data contracts can regress.
- Record phase decisions in `docs/PHASE_N_DECISIONS.md` when tradeoffs are made.
- Do not implement remote execution, LaTeX compilation, or third-party skill code
  execution without a sandbox and permission model.

## Phase 0: Engineering Infrastructure

Status: accepted.

### Goal

Create the monorepo foundation and a runnable local stack.

### Scope

- Monorepo layout.
- Next.js web app.
- FastAPI API app.
- Celery worker app.
- Docker Compose with PostgreSQL/pgvector, Redis, and MinIO.
- Typed configuration.
- Structured logging.
- Request ID propagation.
- Error envelope.
- Health and readiness endpoints.
- Basic API, worker, frontend, and shared schema test/typecheck setup.

### Acceptance Criteria

- `pytest` passes for API.
- `pytest` passes for worker.
- `pnpm -r typecheck` passes.
- Web production build passes.
- Docker Compose config is valid.
- Docker stack starts locally.
- API `/healthz` returns OK.
- API `/readyz` verifies PostgreSQL, Redis, and object storage.
- Web returns HTTP 200.
- Celery worker responds to `inspect ping`.

## Phase 1: Auth and Project Workspace

### Goal

Create the first real multi-tenant product loop: a user can sign in, create or
enter an organization/project, and view a project workspace shell.

### Backend

- Identity bounded context.
- Organizations bounded context.
- Projects bounded context.
- Users, organizations, projects, project memberships.
- Email/password auth for MVP.
- HTTP-only cookie session.
- CSRF protection for unsafe methods.
- Alembic migration.
- Router -> schema/DTO -> service -> repository -> ORM model flow.
- Permission checks in service layer.

### Frontend

- Login page.
- Project list page.
- Project overview page.
- Workspace layout shell.
- Project navigation.
- Typed API client for auth/projects.
- Loading, error, and empty states.

### Non-Goals

- OAuth.
- Billing.
- Research Copilot.
- AI agents.
- Experiments.
- LaTeX workspace.
- Skills runtime.

### Acceptance Criteria

- A user can register/sign in/sign out.
- Session cookie is HTTP-only.
- CSRF is enforced for unsafe authenticated requests.
- A user can create/list/read projects they belong to.
- A user cannot access another user's project.
- Migration creates all Phase 1 tables and indexes.
- Backend tests cover auth, session, CSRF, and project permissions.
- Frontend can sign in and load the project overview from the API.

## Phase 2: Research Copilot MVP

### Goal

Build the minimum research assistant workflow for paper search, idea capture,
and critic feedback.

### Backend

- Paper search provider abstraction.
- Paper library models and APIs.
- Idea model and APIs.
- Critic review data model.
- Agent run base model.
- WebSocket token/event streaming foundation.
- Research Agent and Critic Agent runtime interfaces.

### Frontend

- Research Chat UI.
- Paper library panel.
- Saved ideas panel.
- Critic result cards.
- Streaming response display.

### Non-Goals

- Full RAG quality optimization.
- Marketplace skills.
- Long-term memory graph automation.

## Phase 3: AI IDE Workspace MVP

### Goal

Build the coding workspace shell with safe local file operations and reviewable
AI patch proposals.

### Backend

- Workspace file read/write abstraction.
- File tree API.
- Git status abstraction.
- Coding Agent interface.
- Patch proposal model.
- Permission boundary for future SSH/runtime operations.

### Frontend

- IDE layout.
- File tree.
- Monaco editor.
- Terminal/log panel shell.
- AI assistant panel.
- Patch review UI.

### Non-Goals

- Unrestricted remote SSH execution.
- Automatic unreviewed writes.

## Phase 4: Experiment System MVP

### Goal

Track experiments, runs, metrics, logs, and artifacts in a way that can later
feed paper tables and figures.

### Backend

- Experiment, run, metric, and artifact models.
- Run status lifecycle.
- Metric ingestion API.
- Artifact metadata API.
- Experiment analysis agent interface.

### Frontend

- Experiment dashboard.
- Run list.
- Run detail.
- Logs view.
- Metrics chart.
- Artifact list.

### Non-Goals

- Automatic SSH metric collection.
- GPU scheduler.

## Phase 5: LaTeX Paper Workspace MVP

### Goal

Create the paper writing workspace with AI assistance, LaTeX editing, and PDF
preview.

### Backend

- LaTeX project model.
- Document file model.
- Compile job model.
- Compile API.
- Isolated worker execution path.
- LaTeX Agent interface.

### Frontend

- Three-column paper workspace:
  - AI assistant.
  - LaTeX editor.
  - PDF preview.
- Compile status and log drawer.
- File tabs.

### Safety Requirements

- No unsafe shell escape.
- No invented citations.
- Compile jobs run through an isolated worker path.

## Phase 6: Skills Runtime MVP

### Goal

Turn skills into a permissioned, first-party extension system that can inject
prompts, workflow steps, tools, and agent behavior.

### Backend

- Skill manifest schema.
- Skill registry.
- First-party skill installation.
- Project enabled skills.
- Prompt template loading.
- Tool permission declaration.
- Agent skill injection.

### Frontend

- Skills catalog.
- Installed skills.
- Skill detail.
- Permission display.
- Project enable/disable flow.

### Safety Requirements

- First-party skills only in MVP.
- No arbitrary third-party code execution.
- Every skill declares required permissions.
- Agent/tool injection is policy checked.

## Later Phases

- Team collaboration and audit logs.
- Advanced agent trace viewer.
- Remote SSH runtime implementation.
- LaTeX sandbox hardening.
- Third-party marketplace with signing and review.
- Enterprise SSO, billing, usage metering, and private deployment.
