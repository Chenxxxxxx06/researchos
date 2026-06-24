# ResearchOS

AI-native research operating system — a full-stack MVP that connects research
discovery, code editing, experiment tracking, paper writing, and reusable skills
in one workspace.

> Tech: FastAPI + Next.js + PostgreSQL (pgvector) + Redis + Celery + Docker

## Quick start

```bash
pnpm stack:full
```

This runs `down` → `up --build` → `migrate` → `seed`. Then open
<http://localhost:3000> and log in with the demo account.

**Demo account**: `demo@researchos.dev` / `demo-password-123`

See [`docs/RUNBOOK.md`](docs/RUNBOOK.md) for step-by-step commands and
troubleshooting.

## What's inside (MVP)

| Module | What it does |
|---|---|
| **Research Copilot** | Paper search (arXiv), library, ideas, LLM-powered chat, critic review with source-grounded citations |
| **AI IDE Workspace** | File tree, Monaco editor, terminal shell, coding agent that proposes reviewable patches |
| **Experiment Dashboard** | Experiments, runs, Recharts metrics curves, logs, artifacts, AI analysis |
| **Paper Workspace** | Three-pane LaTeX editor, AI writing assistant, mock-compile preview |
| **Skills Marketplace** | First-party skill catalog, install/enable per project, Skill Builder for custom skills |
| **Settings** | Language (zh-CN / en-US), per-project LLM provider configuration (OpenAI-compatible / Anthropic) |

## Commands

```bash
pnpm stack:up       # Start all services
pnpm stack:down     # Stop
pnpm stack:migrate  # Apply database migrations
pnpm stack:seed     # Seed demo data (idempotent)
pnpm stack:full     # Full reset: down → up → migrate → seed
pnpm stack:test     # Run all backend tests
pnpm typecheck      # TypeScript type checking
pnpm build:web      # Next.js production build
pnpm smoke:api      # API smoke test (PowerShell)
```

## Stack

- **Backend**: FastAPI, SQLAlchemy 2.0 (async), Pydantic v2, Alembic, Celery
- **Frontend**: Next.js 15 App Router, TypeScript, TailwindCSS, TanStack Query, Zustand, Monaco Editor, Recharts
- **Infra**: PostgreSQL (pgvector), Redis, MinIO, Docker Compose

## Docs

- [`docs/RUNBOOK.md`](docs/RUNBOOK.md) — operations guide
- [`docs/MVP_STATUS.md`](docs/MVP_STATUS.md) — what's real, what's mock, what's next
- [`docs/`](docs/) — architecture, product, database, API design
- [`docs/PHASE0_DECISIONS.md`](docs/PHASE0_DECISIONS.md) through [`docs/PHASE3_DECISIONS.md`](docs/PHASE3_DECISIONS.md) — per-phase decisions
- [`docs/SKILL_BUILDER.md`](docs/SKILL_BUILDER.md) — skill architecture

## CI

GitHub Actions runs `ruff` + `mypy` + `pytest` + `typecheck` + `build` on
push and PR.
