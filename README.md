# ResearchOS

AI-native research operating system -- full-stack MVP connecting research
discovery, code editing, experiment tracking, paper writing, and reusable skills
in one workspace.

> Stack: FastAPI + Next.js + PostgreSQL (pgvector) + Redis + Celery + Docker

## Quick start

### If you have pnpm

```bash
pnpm stack:full     # down -> up -> migrate -> seed
```

### If you don't have pnpm (Windows PowerShell)

```powershell
.\scripts\dev.ps1 full
```

### Manual (any OS)

```bash
docker compose -f infra/docker/docker-compose.yml up -d --build
docker compose -f infra/docker/docker-compose.yml exec -T api alembic upgrade head
docker compose -f infra/docker/docker-compose.yml exec -T api python -m researchos.seed.demo
```

Then open <http://localhost:3000>.

## Demo account

| Field | Value |
|---|---|
| Email | `demo@researchos.dev` |
| Password | `demo-password-123` |
| Project | ResearchOS Demo |

## What's inside

| Module | What it does |
|---|---|
| Research Copilot | Paper search (arXiv), library, ideas, LLM-powered chat, critic reviews |
| AI IDE Workspace | File tree, Monaco editor, coding agent, reviewable patches |
| Experiment Dashboard | Experiments, runs, Recharts metrics curves, logs, artifacts, AI analysis |
| Paper Workspace | Three-pane LaTeX editor, AI writing assistant, mock-compile preview |
| Skills Marketplace | 5 first-party skills, install/enable, Skill Builder for custom skills |
| Settings | Language (zh-CN / en-US), per-project LLM config (OpenAI-compatible / Anthropic) |

## Commands

```bash
pnpm stack:full    # Full reset: down -> up -> migrate -> seed
pnpm stack:up      # Start all services
pnpm stack:down    # Stop all services
pnpm stack:migrate # Apply database migrations
pnpm stack:seed    # Seed demo data (idempotent, safe to re-run)
pnpm stack:logs    # Tail combined container logs
pnpm test          # Backend pytest (in-network)
pnpm check         # Full quality gate: backend test + frontend typecheck + build
pnpm check:web     # TypeScript typecheck + Next.js build
pnpm smoke:api     # API smoke test (PowerShell, 16 endpoints)
pnpm smoke:e2e     # Playwright browser E2E (10 pages + language switch)
pnpm build:web     # Next.js production build
```

Or use `.\scripts\dev.ps1 <command>` on Windows (same commands as above).

## What's currently mock/stub

| Feature | Status |
|---|---|
| LLM (when no API key is configured) | Mock provider (deterministic, no-cost). Configure a real key in Settings -> LLM to use Anthropic / OpenAI. |
| LaTeX compile | Mock text transform (no shell, no PDF). Real isolated latexmk compilation is deferred. |
| Terminal panel | UI shell only (no command execution). |
| Git status | Stub (always reports clean). Read-only `git status --porcelain` implementation deferred. |
| SSH runtime | Interface + permission model only (no remote connection). |
| Skill runtime injection | Skills can be installed/enabled but the agent runtime does not yet inject skill prompts/workflows. |

## Docs

- [`docs/RUNBOOK.md`](docs/RUNBOOK.md) -- operations guide & troubleshooting
- [`docs/MVP_STATUS.md`](docs/MVP_STATUS.md) -- what's real, what's mock, what's next
- [`docs/`](docs/) -- architecture, product, database, API design
- [`docs/SKILL_BUILDER.md`](docs/SKILL_BUILDER.md) -- skill architecture

## Quality / CI

| Check | Command |
|---|---|
| Backend test | `pnpm test` |
| Backend lint | `pnpm check:api:test` (runs ruff + mypy + pytest in-network) |
| Frontend typecheck | `pnpm -r typecheck` |
| Frontend build | `pnpm --filter web build` |
| API smoke | `pnpm smoke:api` |
| Browser E2E | `pnpm smoke:e2e` (requires stack running: `pnpm stack:full` first) |
| Full gate | `pnpm check` |

GitHub Actions CI runs `ruff` + `mypy` + `pytest` + `typecheck` + `build` on push/PR.
