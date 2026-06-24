# ResearchOS Backend Design

## 1. Stack

- FastAPI
- PostgreSQL
- Redis
- Celery
- WebSocket gateway
- SQLAlchemy or SQLModel
- Alembic migrations
- Object storage compatible with S3
- Vector database through a provider abstraction

## 2. Backend Modules

```text
apps/api/
  researchos/
    identity/
    organizations/
    projects/
    research/
    agents/
    skills/
    experiments/
    documents/
    runtime/
    websocket/
    billing/
    audit/
    common/
```

## 3. Domain Boundaries

### Identity

Owns users, sessions, API keys, auth providers, organizations, roles, and memberships.

### Projects

Owns project metadata, membership, project settings, context packs, and cross-module navigation.

### Research

Owns papers, paper search, paper ingestion, summaries, ideas, datasets, baselines, related work, and novelty records.

### Agents

Owns agent definitions, agent runs, tool calls, traces, approval gates, memory operations, and orchestration state.

### Skills

Owns skill packages, installation, enablement, permissions, versions, marketplace metadata, and runtime policies.

### Experiments

Owns experiment definitions, runs, metrics, logs, artifacts, comparisons, and paper asset candidates.

### Documents

Owns LaTeX projects, files, versions, BibTeX, compile jobs, PDF artifacts, and paper sections.

### Runtime

Owns SSH profiles, remote servers, command execution, job lifecycle, sandbox policy, and runtime logs.

## 4. Request Lifecycle

1. Validate auth/session.
2. Resolve organization, project, and permissions.
3. Validate request with Pydantic schemas.
4. Execute synchronous domain operation or enqueue async task.
5. Persist domain event.
6. Emit WebSocket event when user-visible state changes.
7. Return typed response or task handle.

## 5. Async Work

Use Celery queues by workload:

- `agents`: LLM calls, tool orchestration, memory writes.
- `ingestion`: papers, PDFs, embeddings, GitHub metadata.
- `runtime`: SSH execution, log streaming, remote metrics.
- `latex`: compile jobs, PDF generation, compile diagnostics.
- `experiments`: metric ingestion, artifact processing, analysis.
- `skills`: install, validate, package scanning, compatibility checks.

## 6. Error Handling

Errors should be typed:

- Validation errors
- Permission errors
- Provider errors
- Runtime errors
- Agent planning errors
- Tool execution errors
- Retryable worker errors
- User-action-required errors

Long-running errors must be persisted on the relevant task/job/run record and emitted as WebSocket events.

## 7. Observability

Capture:

- API request latency and status
- WebSocket connection counts
- Queue depth and task duration
- LLM provider latency, cost, tokens, and errors
- Agent tool-call traces
- Remote runtime session lifecycle
- LaTeX compile duration and failure categories
- Experiment metric ingestion lag

## 8. Configuration

Backend settings should include:

- Database URL
- Redis URL
- Object storage credentials
- Vector provider configuration
- LLM provider credentials
- Allowed SSH encryption key provider
- Feature flags
- Queue routing
- Rate limits
- CORS and cookie settings

## 9. Multi-Tenancy

All user-owned domain records must be scoped by `organization_id` and usually `project_id`. Permission checks must happen at service boundaries, not only in route handlers.

Tenant isolation rules:

- Users can only access projects where they are members.
- Skills can only access projects where they are enabled.
- Agents inherit the permissions of the triggering user plus skill policy constraints.
- Remote runtime credentials are organization/project scoped.

## 10. Production Readiness

- Database migrations are required for all schema changes.
- All background jobs must be idempotent or have safe retry behavior.
- External provider calls need timeouts and circuit breakers.
- Tool calls must be auditable.
- Secrets must never be logged.
- File uploads must be size-limited and scanned before processing when possible.
