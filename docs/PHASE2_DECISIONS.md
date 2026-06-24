# ResearchOS — Phase 2 Architecture Decisions

Status: **Accepted**.
Scope: Phase 2 — Research Copilot MVP (paper search, library, ideas, critic
review, agent runtime, WebSocket streaming).
Builds on `docs/PHASE0_DECISIONS.md` and `docs/PHASE1_DECISIONS.md`.

---

## 1. Decision Log

| # | Topic | Decision | Notes |
|---|-------|----------|-------|
| P2-D1 | Agent execution | AgentRun is persisted (`queued`), dispatched to the **Celery `agents` queue**, executed in the worker; events fan out via **Redis pub/sub → WebSocket**. | Survives client disconnect; reuses the existing worker/queue. The API dispatches by task name (`agents.run_agent`) and never imports worker code. |
| P2-D2 | LLM provider | `LLMProvider` abstraction with a **mock provider as the default**. Anthropic adapter is enabled only via `LLM_PROVIDER=anthropic` + `ANTHROPIC_API_KEY`. | The model id comes **only** from `LLM_MODEL` (default placeholder `mock-model`); no vendor model id is hardcoded. All tests run on the mock provider with zero external keys / zero paid calls. |
| P2-D3 | Paper provider | `PaperSearchProvider` abstraction; **arXiv only** in Phase 2 (no API key). HTTP client is injectable for tests. | Semantic Scholar / OpenAlex are future providers. |
| P2-D4 | Chat persistence | Research Chat is **derived from `agent_runs`** (input = user message, output = assistant message). No `research_threads` / `research_messages` tables yet. | Multi-turn thread management is a later phase. |
| P2-D5 | Event persistence | Persist **coarse** events (`started`, `tool_call.started`, `tool_call.completed`, `completed`, `failed`, `cancelled`) to `agent_run_events`; **token events are live-only** (pub/sub, not stored). `seq` is monotonic and supports REST replay (`GET /events?after_seq=`). | Avoids row explosion from token streams. |
| P2-D6 | RAG / vectors | Deferred. No `paper_chunks` table, no embedding pipeline in Phase 2. | Interfaces will be introduced when RAG lands. |
| P2-D7 | Citation integrity | Hard rule: only papers returned by tools or already in the project library may be cited. Unbacked citations are dropped (`filter_citations`). | Enforced in the runtime/agents; tested directly and via the critic path. |
| P2-D8 | Tool broker | All tools execute through a `ToolBroker` that checks the per-agent allowlist, records `tool_calls`, and emits events. | This is the extension point for Phase 6 skill permission policy. |
| P2-D9 | Native enums | Continued (`idea_status`, `agent_type`, `agent_run_status`, `tool_call_status`); same migration-risk exit path as Phase 1. | |
| P2-D10 | Org member endpoint | `POST /organizations/{id}/members` (added in Phase 1 build) remains the way to grow project membership. | |

## 2. Worker event-loop safety (runtime fix)

**Problem.** Celery prefork workers run each task synchronously; we drive async
code with `asyncio.run`, which creates and closes a **new event loop per task**.
The process-global async SQLAlchemy engine/sessionmaker and async Redis client
are bound to the loop that created them. Reusing them from a later task on a
different loop raised `RuntimeError: Event loop is closed` and
`RuntimeError: got Future attached to a different loop`, so the **second** agent
run stalled in `queued`.

**Fix.**

1. `researchos.common.asyncio_runner.run_async_task(factory)` runs the coroutine
   in a fresh loop and, in a `finally`, calls `dispose_engine()` and
   `close_redis()` **inside that same loop** before it closes.
2. `dispose_engine()` resets **both** `_engine` and `_sessionmaker` (a stale
   sessionmaker bound to a disposed engine was part of the bug).
3. The worker runs with `DB_USE_NULLPOOL=true` so no pooled connection outlives
   its loop.
4. Both worker tasks (`agents.run_agent`, `health.check_dependencies`) use
   `run_async_task`; `health.check_dependencies` now runs both probes in a
   single loop instead of three separate `asyncio.run` calls.

A synchronous regression test
(`tests/test_worker_loop_regression.py`) drives two consecutive
`run_async_task(run_agent_run(...))` invocations and asserts both reach
`completed`, guarding against re-introducing the leak (e.g. if the
sessionmaker reset is removed).

## 3. Phase 2 non-goals

No AI IDE, experiments, LaTeX, skills runtime, SSH, full RAG, memory graph,
research threads/messages, or non-arXiv providers.

## 4. Known limitations

- WebSocket client has no auto-reconnect (MVP); `GET /events?after_seq=` is the
  fallback.
- Rate limiting is a simple Redis fixed window; LLM spend quotas are a stub.
- The Anthropic adapter is not exercised by tests (by design — no key).
- Outbound internet to arXiv may be unavailable in some environments; the
  provider is verified via a recorded fixture and the agent pipeline via the
  offline critic path (library.list tool).
