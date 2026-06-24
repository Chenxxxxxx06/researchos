# ResearchOS — Phase 0 Architecture Decisions

Status: **Accepted** (confirmed before any code was written).
Scope: Phase 0 only — engineering infrastructure. No business modules.

This document is the single source of truth for the technical choices made for
Phase 0. Later phases may revisit individual decisions, but each change must be
recorded here (or in a successor `PHASE_N_DECISIONS.md`).

---

## 1. Decision Log

| # | Topic | Decision | Rationale |
|---|-------|----------|-----------|
| D1 | Vector storage | Use **pgvector** on the shared PostgreSQL instance for the MVP. Keep a vector-store abstraction so it can be swapped for Qdrant / a dedicated vector DB later. | One fewer infra component; abstraction prevents lock-in. |
| D2 | ORM / DTO | **SQLAlchemy 2.0 (async) + asyncpg** for persistence; **Pydantic v2** for DTOs/schemas. **No SQLModel.** | SQLModel has rough edges with complex relations and Alembic; explicit separation of ORM models and API DTOs is more production-grade. |
| D3 | Frontend state | **TanStack Query** for server state; **Zustand** for UI/local workspace state. | Clear separation of concerns; both are lightweight. |
| D4 | Python packaging | **uv** for dependency management and locking. | Fast, reproducible, CI-friendly. |
| D5 | Charts | **Recharts** for the MVP. | Sufficient for experiment curves; revisit ECharts if many-series/large-data needs appear. |
| D6 | WebSocket | Embedded inside the **FastAPI** process for Phase 0/1, with **Redis pub/sub** fan-out. Extract a standalone WS gateway later. | Avoids premature distributed complexity; follows the documented extraction path. |
| D7 | Workers | A **single Celery worker** process with **multiple queue routing** (`agents`, `ingestion`, `runtime`, `latex`, `experiments`, `skills`) for Phase 0. Split into per-queue containers in production later. | Routing code is written now; container split is a deployment-only change with zero rework. |
| D8 | Packages | Phase 0 creates **only `packages/shared-schemas`**. `agent-protocol` and `skill-sdk` are deferred to their owning phases (Phase 2 / Phase 6). | Avoid empty-shell maintenance burden. |
| D9 | High-risk surfaces | **SSH runtime, LaTeX sandbox, and third-party skill execution keep architectural boundaries only** in Phase 0 — no real high-risk capability is implemented. | Security-first; these are the highest-risk surfaces and are gated behind later phases with explicit review. |

## 2. Resolved "A or B" choices from the docs

- ORM: SQLAlchemy 2.0 (not SQLModel) — see D2.
- Frontend state: Zustand (not Redux) — see D3.
- Python package manager: uv (not Poetry) — see D4.
- Charts: Recharts (not ECharts) for MVP — see D5.
- Vector DB: pgvector (not a separate vector service) for MVP — see D1.

## 3. Phase 0 technology stack

Backend (apps/api, apps/worker):

- Python 3.13 (isolated in a dedicated environment)
- FastAPI + Uvicorn
- SQLAlchemy 2.0 (async) + asyncpg
- Alembic (env configured; **empty baseline — no business tables in Phase 0**)
- Pydantic v2 + pydantic-settings
- Celery (Redis broker/result backend)
- structlog (structured JSON logging)
- redis (async client) + httpx (object-storage health probe)
- pytest + pytest-asyncio, ruff, mypy

Frontend (apps/web):

- Next.js (App Router) + TypeScript
- TailwindCSS + shadcn-compatible structure
- TanStack Query + Zustand
- Recharts (declared for later use)

Infrastructure (infra/docker):

- PostgreSQL with the `pgvector` extension image
- Redis
- MinIO (S3-compatible object storage)
- Docker Compose for the local stack

Tooling:

- pnpm workspace (JS/TS), uv (Python)
- JavaScript dependencies are pinned in `pnpm-lock.yaml`.
- Python dependencies currently use version ranges in `pyproject.toml`; add a
  committed `uv.lock` before production or CI release gating.
- Makefile **and** root npm scripts + shell scripts, so the stack runs even
  without `make` installed.

## 4. Environment isolation

Python work runs in a dedicated environment named **`researchos`** (created with
`conda create -n researchos -c conda-forge python=3.13` because the default
Anaconda channel is restricted in this setup). Dependencies are installed into
that environment via `uv pip` / `pip`. The environment is per-developer and is
never committed.

## 5. Explicit Phase 0 non-goals

- No business domain tables (no users / organizations / projects / papers /
  experiments / documents / skills records).
- No authentication or authorization logic.
- No agent, research, experiment, LaTeX, or skills business endpoints.
- No real SSH execution, no real LaTeX compilation, no third-party code loading.

Phase 0 delivers: monorepo layout, three runnable apps, Docker Compose stack,
configuration system, structured logging, health/readiness checks, a test
framework, and verified frontend↔backend connectivity.
