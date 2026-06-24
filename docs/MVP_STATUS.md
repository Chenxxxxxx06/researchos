# ResearchOS MVP Status

Last updated: 2026-06-25

## Completed modules (real, working)

| Module | Status | Notes |
|---|---|---|
| Auth (register/login/logout/me) | [OK] | Email/password, Redis sessions, CSRF |
| Organizations + Projects | [OK] | M:N membership, soft-delete, role ladder |
| Research Copilot | [OK] | Paper search (arXiv provider), library, ideas, critic review, agent runtime |
| AI IDE | [OK] | File tree, Monaco editor, patch proposals, patch apply (base_sha guard), coding agent |
| Experiment Dashboard | [OK] | Experiments, runs, metrics (Recharts), logs, artifacts, analysis agent |
| Paper Workspace (LaTeX) | [OK] | Three-pane, Monaco LaTeX editor, mock compile (safe text transform), writing assistant |
| Skills Marketplace | [OK] | 5 first-party skills, install/enable/disable, detail panel |
| Skill Builder | [OK] | Form, validate, preview manifest, save & install custom skill |
| i18n (zh-CN / en-US) | [OK] | Full coverage, language switcher, persisted |
| WebSocket | [OK] | Agent run streaming via Redis pub/sub, REST events fallback |
| Celery workers | [OK] | agents.run_agent task, queue routing |
| Settings / LLM config | [OK] | Per-project provider configs, OpenAI-compatible adapter |
| Demo seed | [OK] | Idempotent, safe to re-run |
| CI | [OK] | GitHub Actions: ruff, mypy, pytest, typecheck, build |

## Modules with mock / stub components

| Module | What is mock | Impact |
|---|---|---|
| LLM providers | **MockLLMProvider** is the default when no API key is configured | All agent runs produce deterministic, no-cost output. Configure a real key in Settings to use real LLM. |
| LaTeX compile | **Mock compiler** — pure Python text transform, no shell, no PDF | Preview is a plain-text rendering. Real LaTeX (isolated container, `latexmk`) is deferred. |
| Git status | **Stub provider** — always reports clean | Real `git status --porcelain` can be enabled later. |
| Terminal | **UI shell only** — no command execution | Real shell access is deferred for security. |
| SSH runtime | **Interface only** — no remote connection | Real SSH execution is deferred. |

## Known risks

| Risk | Severity | Mitigation |
|---|---|---|
| Worker event-loop cleanup | Medium | `asyncio_runner` disposes engine/redis after each task. Regression test in place. |
| API must start *after* migrations | Low | `docker compose restart api` if the skills table was missing at startup. |
| Skills seed runs at API startup | Low | Idempotent; also can be triggered explicitly via `python -m researchos.seed.demo`. |
| No outbound arXiv from containers | Low | Provider verified via recorded fixture. Research copilot uses library tool when offline. |
| SQLAlchemy native enums | Low | Adding new enum values requires `ALTER TYPE … ADD VALUE` (PG12+); removing values requires more work. Documented exit path in PHASE1_DECISIONS. |

## Next steps toward production

1. **Real LaTeX compilation** — isolated container, `latexmk`, no shell-escape
2. **Real SSH execution** — credential encryption, approval gates, audit
3. **Skill runtime injection** — prompt/workflow loading into agents
4. **Email verification + password reset**
5. **Rate limiting hardening** — token bucket vs. fixed window
6. **API key encryption at rest**
7. **OpenTelemetry tracing** — API → worker → LLM spans
8. **Kubernetes deployment** — per-queue worker scaling
