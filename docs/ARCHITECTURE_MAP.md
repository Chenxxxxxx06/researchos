# ResearchOS Architecture Map

> **Historical architecture snapshot.** This document describes the repository before
> the `5ee2354` Harness/CLI update and is retained as audit evidence. Some statements
> about the terminal, routes, Skills UI, and product surface are no longer current.
> Use [README.md](../README.md) and [TODO_ZH.md](TODO_ZH.md) for the current capability
> ledger; regenerate this map before using it for implementation decisions.

Synthesized from parallel subsystem readings of the full monorepo (2026-07). Covers: `apps/api` (FastAPI backend, 14 routers), `apps/worker` (Celery), `apps/web` (Next.js 15 / React 19 client-only frontend), `packages/shared-schemas`, `infra/docker`, `scripts/`, `docs/`.

---

## 1. System Overview

### 1.1 Topology

```
┌─────────────────────────────── Browser ────────────────────────────────┐
│  Next.js 15 App Router (all pages 'use client', no SSR data fetching)  │
│  TanStack Query + Zustand (org id, IDE tabs/buffers) + hand-rolled i18n│
│  Monaco (CDN-loaded) editors: IDE, LaTeX, patch diffs                  │
└──────┬──────────────────────────────────────────────┬──────────────────┘
       │ REST: fetch w/ credentials:'include'          │ WS: ws(s)://api/ws?project_id=
       │ cookies: ros_session (HttpOnly)               │ (session cookie on handshake,
       │          ros_csrf → X-CSRF-Token on non-GET   │  push-only relay, no reconnect)
       ▼                                               ▼
┌──────────────────────────── FastAPI API (:8000) ───────────────────────┐
│ RequestContextMiddleware (X-Request-ID) → routers:                     │
│  health / auth / organizations / projects / research / agents /        │
│  coding-agent / workspace / patches / git(stub) / experiments /        │
│  documents(latex) / skills / llm_config / websocket                    │
│ Authz: ProjectService.ensure_access (404-hides non-members)            │
│ Error envelope: {"error":{code,message,request_id,details?}}           │
└──┬──────────────┬───────────────┬──────────────┬───────────────────────┘
   │ asyncpg      │ Redis         │ Celery       │ Local FS
   ▼              ▼               │ send_task    ▼
┌──────────┐ ┌──────────────┐    │ by name    <workspace_root>/<project_id>
│ Postgres │ │ Redis        │    │ 'agents.    (path-guarded; patches are the
│ pgvector │ │ - sessions   │    │  run_agent'  only write path)
│ /pg16    │ │ - rate limits│    ▼
│ (JSONB,  │ │ - cancel flag│ ┌────────────── Celery Worker ────────────┐
│  native  │ │ - pub/sub    │ │ queues: agents + 6 empty (ingestion,    │
│  enums)  │ │   ws:project:│ │ runtime, latex, experiments, skills,    │
└──────────┘ │   {id}       │ │ default) — only agents.run_agent +      │
             └──────▲───────┘ │ health.* registered                     │
                    │ publish │ AgentRuntime → LLM provider →           │
                    └─────────│ ToolBroker (3 read-only tools)          │
                              └───────┬─────────────────────────────────┘
                                      │ outbound HTTP
                    ┌─────────────────┼───────────────────────┐
                    ▼                 ▼                       ▼
            arXiv Atom API     Anthropic API /        MinIO (reachability
            (http://export.    OpenAI-compatible      probe only — no real
            arxiv.org)         endpoints (default:    storage abstraction)
                               MOCK provider)
```

Key structural facts:
- The **API never imports worker code**; Celery dispatch is stringly-typed by task name (`agents.run_agent`, queue `agents`). The worker depends on the full API package (editable path dep) and must wrap every async task in `run_async_task` (fresh event loop, engine/Redis disposal per task).
- The **WebSocket gateway is a dumb relay**: it authenticates once at connect, then forwards Redis pub/sub envelopes verbatim. Only `agent.run.*` events are ever published; experiment/latex/skill/runtime event families exist only in the TypeScript contract.
- The **default LLM provider is a deterministic mock** (`LLM_PROVIDER=mock`); every AI feature works end-to-end while producing canned output. Real-provider multi-turn tool loops are broken by message-shape bugs (see §4).
- **Git, terminal, SSH runtime, LaTeX compilation, and object storage are all stubs** (see §3).

### 1.2 Request lifecycles

**(a) Paper search / ingestion**
1. `POST /projects/{id}/papers/search` → CSRF + session check → `ensure_access(VIEWER)` → Redis fixed-window rate limit (`paper_search:{user_id}`, 60/min).
2. `ArxivProvider.search`: builds `all:{raw query}` (no escaping), GET `http://export.arxiv.org/api/query` (fresh httpx client, 10s timeout, page 0 only), feedparser → normalized `PaperResult[]` (id normalization strips version by splitting on first `v` — corrupts old-style IDs). **Nothing is persisted.**
3. Client displays results; user selects → `POST /projects/{id}/papers/import` **echoes the full client-supplied PaperResult objects back** (trusted wholesale, `ensure_access(RESEARCHER)`); per-item check-then-insert dedup on `(project_id, source, external_id)` (N+1, race → 500), single commit.
4. No PDF download, no full-text, no summarization ever happens; `pdf_url` and `Paper.summary` are stored but unused.

**(b) Agent chat → code edit**
1. `POST /projects/{id}/coding-agent/runs {message}` → `AgentRunService.create_run` (RESEARCHER, 30/min rate limit) inserts `AgentRun(QUEUED)`, commits, `send_task('agents.run_agent', [run_id])`.
2. Frontend receives `{agent_run_id, stream:'/ws?project_id=…'}`; opens/reuses WS; `useProjectAgentEvents` folds `agent.run.token/tool_call.*/completed/failed` into a live bubble (events between POST and WS subscribe are lost; REST replay endpoint exists but is never called).
3. Worker: `AgentRuntime.run` resolves provider (per-project `llm_provider_configs` row → env → mock), sets RUNNING, `_run_loop`: stream LLM → collect ToolCalls → `ToolBroker.execute` (allowlist: coding agent gets **only `workspace.tree`** — no file-read tool) → append empty assistant msg + `role:tool` msg → re-stream (max 4 tool calls). Cancellation checked only before/after the whole loop.
4. `CodingAgent.finalize`: `json.loads` full text buffer → validate each file via `PatchFileInput` + `resolve_in_workspace` (bad entries silently dropped) → `PatchService.create_proposal` inserts PENDING `PatchProposal` + `PatchFile` rows (whole-file `new_content`, `base_sha`). Parse failure = COMPLETED run with no patch, no error.
5. UI: `CodingAssistant` fires 5 hardcoded setTimeout invalidations; `PatchReviewPanel` polls every 5s; `PatchDiff` renders Monaco diff of **live file vs new_content** (not the recorded base).
6. Human clicks Apply → `POST /patches/{id}/apply` (RESEARCHER + CSRF): phase 1 re-guards paths and compares live sha256 vs `base_sha` (any mismatch → status CONFLICT, nothing written, **permanently stuck** — apply/reject both require PENDING); phase 2 writes every file whole (non-atomic, no temp+rename, no backup — no rollback exists anywhere).

**(c) Experiment run**
1. There is **no execution**: `POST /experiments` then `POST /experiments/{id}/runs` create purely client-reported records (`command` is stored, never run; SSH runtime is an interface-only stub imported by nothing).
2. Client PATCHes status (no state machine — any transition accepted) and POSTs metric batches (≤5000 points, row-per-point, no dedup on `(run,name,step)`), single log lines (seq = `COUNT(*)` — races), and artifact **metadata only** (no bytes, no storage backend). All writes require browser cookie + CSRF — no API-key path for a training script on a GPU box.
3. `POST /experiment-runs/{run_id}/analyze` → EXPERIMENT agent run via the same Celery path. `ExperimentAgent` computes a deterministic final/best summary (best = min iff name contains `'loss'`, else max), streams LLM tokens to the WS, then **discards the LLM output** in finalize and persists the deterministic text. Frontend `AnalysisPanel` shows the stream; the result is never re-displayable after unmount.

**(d) Paper (LaTeX) editing**
1. `PaperWorkspace` uses `projects[0]` only, hardcoded `main.tex`, Monaco in `plaintext` mode. Save = `PUT /latex-projects/{id}/files` — whole-file upsert, version counter bump, **no optimistic concurrency** (last-write-wins; concurrent editors clobber each other; a background refetch clobbers unsaved local edits).
2. Compile = `POST /compile`: runs **synchronously in-request**, `_mock_preview` regex-transforms main.tex to pseudo-Markdown, inserts a `LatexCompileJob` born SUCCEEDED (engine='mock'). No PDF, no worker, no `latex.compile.*` events; QUEUED/RUNNING/FAILED states are unreachable.
3. `PaperAssistant` sidebar creates a `latex` agent run (type cast to `'research'` client-side); the agent has no tools — it cannot read the document; output is never inserted back.

---

## 2. Current Algorithm Inventory

| # | Area | Algorithm / heuristic | Key weakness |
|---|------|----------------------|--------------|
| 1 | auth | Redis opaque sessions, sliding 7d TTL (`common/session.py`) | No absolute lifetime; no per-user index → no revoke-all; `last_seen` never updated; GET+EXPIRE non-atomic |
| 2 | auth | CSRF double-submit, itsdangerous-signed session id (`common/csrf.py`) | Collapses if default `SECRET_KEY` ships to prod (no boot guard); no in-session rotation |
| 3 | auth | Login timing-equalization + generic 401 (`identity/service.py:43-63`) | Defeated by register 409 + member-add 404/409 email enumeration; **no rate limit on login/register** |
| 4 | auth | argon2id via pwdlib (`common/security.py`) | No tuning knobs, no rehash-on-verify, no pepper |
| 5 | tenancy | Role ladders + implicit org-admin→project-admin (`common/roles.py`, `projects/service.py`) | No last-owner protection (ADMIN can demote/remove OWNER); org membership immutable; coarse roles |
| 6 | tenancy | 404-hiding of non-membership (`projects/service.py:61-73`) | Convention-only — nothing forces new routers to call `ensure_access`; 403 still confirms existence |
| 7 | infra | Fixed-window rate limiter INCR+EXPIRE (`common/rate_limit.py`) | Non-atomic (crash → TTL-less permanent 429); 2× burst at boundaries; not on auth endpoints; no Retry-After |
| 8 | infra | Unique slug w/ retry (`organizations/service.py:30-39`) | Check-then-insert TOCTOU → 500; ASCII-only (non-Latin names → 'org'); slugs decorative |
| 9 | infra | Workspace path guard (`common/paths.py:63-83`) | Basename-only deny-list (`prod.env`, `.ssh/config`, `*.p12`, `token.txt` pass); case-sensitive fnmatch; TOCTOU |
| 10 | infra | Offset pagination Page[T] (`common/pagination.py`) | COUNT+OFFSET; non-unique sort key duplicates rows; member lists unpaginated |
| 11 | infra | Request-id propagation (`common/middleware.py`) | Inbound X-Request-ID trusted verbatim → log spoofing; BaseHTTPMiddleware edge cases |
| 12 | infra | Readiness aggregation (`health/router.py:41-60`) | Sequential; `detail=str(exc)` leaks internals to unauthenticated callers; Celery liveness unprobed |
| 13 | infra | Celery loop-per-task bridge (`common/asyncio_runner.py`) | Full engine/pool teardown+rebuild per task; dispatch-by-name fails only at runtime |
| 14 | infra | Idempotent demo seeder (`seed/demo.py`) | Cannot bootstrap empty DB; reads `.id` before flush → NOT NULL crash on fresh experiments seed; name-keyed idempotency |
| 15 | research | arXiv query construction (`providers/arxiv.py:76-95`) | Raw user string into arXiv query language (operator injection); page 0 only; no retry/backoff/caching; bozo feeds → silent empty list |
| 16 | research | arXiv external-id normalization (`arxiv.py:40-43`) | Splits on first `v` → corrupts old-style IDs (`solv-int/9701001`→`sol`); version info lost; dedup-key collisions |
| 17 | research | Metadata-only extraction (`arxiv.py:104-110`) | Abstract keeps hard wraps + raw LaTeX; venue hardcoded 'arXiv'; journal_ref/DOI/category dropped; no PDF/full-text ever |
| 18 | research | Import dedup by (project,source,ext_id) (`research/service.py:48-78`) | N+1 sequential selects; race → IntegrityError 500; no DOI/fuzzy matching; no metadata refresh |
| 19 | research | Client-trusted import provenance (`schemas.py:25-26`) | Server never re-verifies — fabricated papers importable; no length limits vs DB columns → 500 |
| 20 | research | Search ranking | None — arXiv relevance order passthrough; `list_ids_for_project` (already-in-library marker) is dead code |
| 21 | llm | Provider selection 3-tier (`llm/factory.py`) | Anthropic DB config ignores stored model/key/base_url; multiple `is_active` rows → arbitrary `limit(1)` pick; no fallback/health check; one model for all 5 agents |
| 22 | llm | Agent orchestration loop (`runtime/runtime.py:139-195`) | Empty assistant msg w/o tool_calls → real OpenAI/Anthropic APIs reject round 2; text_buffer accumulates across iterations (breaks JSON finalize); usage overwritten not summed; timeout setting unenforced; no mid-loop cancel |
| 23 | llm | Mock provider script (`llm/mock.py`) | Deployment default is a placebo: always calls tools[0], canned critique/patch identical for every input; masks broken real path |
| 24 | llm | Anthropic adapter (`llm/anthropic.py`) | max_tokens=1024 hardcoded (truncates JSON mid-stream); response_schema ignored; never reconstructs tool_use blocks → API rejects tool loops; no timeout |
| 25 | llm | OpenAI-compatible SSE adapter (`llm/openai_compatible.py`) | Usage always 0 (no `stream_options`); stale loop-var `finish_reason` (line 135, NameError edge); `anthropic_api_key` as fallback bearer to arbitrary base_urls; drops assistant tool_calls |
| 26 | agents | Citation whitelist (`runtime/citations.py`, `tools.py`) | Paper-existence-level only, not claim-level; research agent cites everything retrieved; critic citations silently all dropped if `library.list` never called |
| 27 | agents | ToolBroker execute (`runtime/tools.py`) | Hallucinated tool name → whole run FAILS (no recoverable error payload); seq via `count(*)` races; only 3 read-only tools |
| 28 | agents | Critic structured review (`critic_agent.py`) | Schema never transmitted to real providers; JSON parse failure → empty critique persisted as SUCCESS; sees titles only, no abstracts |
| 29 | agents | Coding patch proposal (`coding_agent.py`) | No file-read tool → blind whole-file rewrites with guessed base_sha; invalid entries silently dropped; parse failure → completed run, no patch |
| 30 | agents | Experiment summarizer (`experiment_agent.py:24-43`) | `'loss'`-substring direction heuristic misclassifies perplexity/error/WER; LLM output streamed then discarded (theater) |
| 31 | agents | LaTeX assistant (`latex_agent.py`) | No document access, no tools, no structured edits — pure side-chat |
| 32 | agents | Event stream + persistence (`runtime/events.py`) | Tokens live-only (reconnect loses text); `max(seq)+1` races → IntegrityError fails run; per-event commits entangle run state |
| 33 | agents | Cooperative cancel (`cancellation.py`) | Checked only before/after loop — cancel doesn't interrupt in-flight LLM/tools; 1h flag TTL vs longer queues |
| 34 | patches | base_sha optimistic concurrency (`patches/service.py:117-147`) | TOCTOU scan→write; CONFLICT is a terminal dead end (no retry/rebase/dismiss); `None==None` hole silently creates files; exact-sha delete conflicts on already-deleted |
| 35 | patches | All-or-nothing apply (`service.py:149-159`) | Not atomic: mid-loop I/O error → FS/DB divergence; non-atomic `write_file`; **no rollback/undo anywhere** (base content never stored) |
| 36 | patches | Diff display (client, `PatchDiff.tsx`) | Diff vs live file, not recorded base → stale patches show misleading diffs; PatchHunk table is dead weight |
| 37 | workspace | Tree building (`workspace/fs.py:29-69`) | Silent truncation at 5000 entries/depth 12 (no flag); rebuilt per request; sync I/O on event loop; full tree fed to LLM |
| 38 | workspace | Binary/size detection (`fs.py:72-110`) | >1MB → sha=null → unpatchable from UI; `errors='replace'` decode permanently corrupts non-UTF-8 on round-trip; NUL-in-8KB heuristic |
| 39 | git | Status provider (`git/provider.py:44-45`) | Hardwired stub: always clean/'main'; workspaces aren't git repos; applied patches un-versioned |
| 40 | experiments | Run lifecycle timestamps (`experiments/service.py:92-143`) | No state machine; QUEUED→RUNNING never sets started_at; CANCELLED never finished_at; no heartbeat → zombie RUNNING |
| 41 | experiments | Log seq = COUNT(*) (`repository.py:91-95`) | Race → duplicate seq, no unique constraint; one HTTP round-trip per line |
| 42 | experiments | Metric record/list (`service.py:146-158`) | No upsert → duplicates skew analysis; no pagination/downsampling; scalars only |
| 43 | documents | Mock LaTeX preview (`documents/service.py:47-62`) | Line-oriented regex; nested braces break (`\frac{a}{b}`→`a{b}`); no math/env/\input/BibTeX handling |
| 44 | documents | Sync always-succeed compile (`service.py:154-176`) | 3 of 4 enum states unreachable; empty main file 'succeeds'; no events, no PDF |
| 45 | documents | Save/version upsert (`service.py:124-152`) | Last-write-wins, no expected-version; create TOCTOU → 500; version counter has no history to diff; path accepted unnormalized (`../` landmine) |
| 46 | skills | Manifest validation (`skills/manifest.py:45-60`) | config_schema never validated as JSON Schema; settings_json never checked/used; prompt_template unscreened (injection surface); enforcement broker doesn't exist |
| 47 | skills | Latest-version by created_at (`repository.py:21-26`) | Not semver — publishing 0.9.0 after 1.0.0 makes 0.9.0 'latest' |
| 48 | skills | Install/toggle/global slug (`service.py:97-161`) | No uninstall; re-install = only upgrade path; global slug namespace leaks cross-tenant skill existence |
| 49 | skills | First-party seeding (`seed.py:89-124`) | Slug-existence idempotency only — code edits never propagate; multi-worker startup race crashes lifespan |
| 50 | ws | Auth handshake (`websocket/router.py:34-66`) | Close-before-accept → app close codes (4400/4401/4403) likely never reach the client; membership checked once — revocation doesn't disconnect |
| 51 | ws | Redis relay loop (`router.py:69-79`) | Push-only, no ping — dead sockets + one Redis conn per tab leak indefinitely; at-most-once, no replay for non-agent events; no backpressure |
| 52 | ws | Envelope construction (`envelopes.py:36-62`) | `event_type` unvalidated str; `approval_required` missing from backend vocabulary; payloads dict-by-convention |
| 53 | web | Chat history/live merge (`ResearchChat.tsx`) | Depends on undocumented newest-first order; first page only; live bubble shows 'Processing…' not the user's prompt; swap flicker |
| 54 | web | Live event accumulator (`useProjectAgentEvents.ts`) | No seq ordering/dedup → out-of-order corrupts text; subscribe-after-create race loses events; REST replay never used; unbounded run map; one socket per consuming component |
| 55 | web | Editor propose-patch (`EditorPane.tsx:27-33`) | Only 'modify' reachable; buffer not cleared after propose (duplicate proposals); base_sha can be stale/null |
| 56 | web | Coding-agent discovery (`CodingAssistant.tsx:20`) | 5 hardcoded setTimeouts instead of WS completion; timers not cleaned up; run failures invisible |
| 57 | web | Critic completion detection (`IdeaPanel.tsx`) | Critique-count-growth polling; server failure → 'Reviewing…' forever; idea-switch mid-review compares wrong baseline |
| 58 | web | Metrics pivot (`MetricsChart.tsx`) | Single run only; dup (name,step) overwrite; one shared y-axis; no live refresh for running runs |
| 59 | web | Mock-LLM badge heuristic (3 components) | `configs.length > 0` equated with working LLM — no validation; logic duplicated 3× |
| 60 | web | Paper workspace model (`PaperWorkspace.tsx`) | `projects[0]` + hardcoded main.tex + plaintext mode; refetch effect clobbers unsaved edits |
| 61 | web-infra | Route guard (`middleware.ts`) | Cookie-presence-only; stale cookie → **infinite /login↔/projects redirect loop**; non-401 /auth/me failure → permanent blank page |
| 62 | web-infra | API client (`lib/api/client.ts`) | No timeout/AbortController; empty-2xx body → raw SyntaxError; no 401 interceptor/429 handling; blind casts, zero zod validation |
| 63 | web-infra | WS client (`lib/websocket/client.ts`) | No reconnect/backoff/heartbeat/onerror — dropped socket silently freezes all live UI; cookie-on-handshake breaks cross-domain |
| 64 | web-infra | i18n hydration (`lib/i18n`) | zh-CN flash before localStorage read; `<html lang="en">` hardcoded vs zh-CN default; no interpolation; partial coverage |
| 65 | web-infra | IDE tab/buffer store (`lib/store/ide.ts`) | Close tab silently discards unsaved buffer; no persistence; panel-resize fields have no setters |
| 66 | web-infra | Org defaulting (`OrgSwitcher.tsx`, projects page) | Stale/foreign persisted org id never validated; zero-org user → infinite skeleton |
| 67 | ops | Stack orchestration (`scripts/dev.ps1`, compose) | `Start-Sleep 8` readiness race; hardcoded researchos/researchos creds; no SECRET_KEY in main compose; dev-only web image; single worker |
| 68 | ops | E2E/smoke strategy (`e2e/smoke.spec.ts`, `smoke_api.ps1`) | Brittle seed-string couplings; hard sleeps; happy-path GET-only; zero unit/component tests in web |

---

## 3. Stub & Gap Inventory

### 3.1 AI / LLM (the product's core is mostly mock)
- **Default provider is a deterministic mock** — all five agents produce canned output out of the box (`apps/api/researchos/agents/llm/mock.py`; `common/config.py:82`).
- Real-provider tool loops unimplemented: empty assistant turn w/o tool_calls/tool_use (`agents/runtime/runtime.py:184`); adapters reject round-2 messages (`llm/anthropic.py:90-110`, `llm/openai_compatible.py:142-159`).
- `response_schema` accepted but never sent by either real adapter (`openai_compatible.py:47`, `anthropic.py:53`); Anthropic `max_tokens` hardcoded 1024 (`anthropic.py:65`); OpenAI usage always 0 (`openai_compatible.py:49-53`).
- Anthropic per-project DB config dead — env-only (`llm/factory.py:42-44`); `get_llm_provider_sync` explicit stub (`factory.py:68-78`).
- `agent_run_timeout_seconds=120` defined, enforced nowhere (`common/config.py:104`); `cost_json`/`skill_ids_json` never populated (`agents/models.py:40-41`).
- Tool registry: 3 read-only tools only — no file-read, paper-fetch/abstract, experiment tools, write tools; "Phase 6 skill permission policy" plug-in point empty (`agents/runtime/tools.py:5-7`); `library.list` hardcoded limit=50 (`tools.py:83-85`).
- LaTeX agent self-labeled "(mock)", no document access (`runtime/latex_agent.py:1`); experiment agent discards LLM output (`experiment_agent.py:69-80`).
- LLM API keys plaintext at rest, acknowledged MVP (`llm_config/models.py:5,32`); hardcoded defaults gpt-4o / api.openai.com (`models.py:29-31`).

### 3.2 Research pipeline
- arXiv is the only provider; any other config → 500 (`research/providers/registry.py:19-24`). No Semantic Scholar/OpenAlex/PubMed, no fan-out.
- `PaperSearchFilters` (year range) fully dead plumbing (`providers/base.py:16-18`, `arxiv.py:81`, `service.py:46`, `schemas.py:16-18`).
- No PDF/full-text ingestion anywhere; `pdf_url` stored, never fetched (`arxiv.py:110`, `models.py:36`). `Paper.summary` never written (`models.py:37`); `Idea.novelty_score` never written (`models.py:58`).
- `list_ids_for_project` dead code (`repository.py:55-61`); provider pagination hardcoded start=0 (`arxiv.py:85`); no paper PATCH/bulk-delete/library search (`research/router.py`); feedparser bozo/error feeds unchecked (`arxiv.py:96-98`).

### 3.3 Execution / experiments / git / terminal
- **SSH remote runtime is interface-only**: `UnavailableRuntimeProvider.execute` raises NotImplementedError; module imported by nothing (`runtime/ssh/interface.py:1-70`).
- 6 of 7 Celery queues have zero registered tasks (`worker/queues.py:26-33`, `app.py:24`).
- `ExperimentRun.command` stored, never executed (`experiments/schemas.py:34`, `models.py:52`); no cancellation/heartbeat mechanism (`enums.py:13`); artifacts metadata-only, no bytes/storage (`schemas.py:90-95`); no programmatic ingestion (cookie+CSRF only — no API keys) (`router.py:129-194`); no DELETE endpoints, no pagination (`experiments/router.py`); `default_config_json` dead column (`models.py:26`).
- **Git is fictional**: stub always clean/'main' (`git/provider.py:23-29,44-45`); `ReadOnlyGitStatusProvider` = NotImplementedError (`provider.py:32-41`).
- Terminal is a static mock (`apps/web/features/ide/TerminalPanel.tsx:3-16`).

### 3.4 Documents / LaTeX
- Compilation is an explicit regex mock, no PDF (`documents/service.py:1-6,47-62,154-176`); QUEUED/RUNNING/FAILED unreachable (`enums.py:8-12`); engine default 'mock' (`models.py:60`).
- Missing endpoints: delete/rename file, delete project, change main_file_path, history/diff (`documents/router.py`).
- Frontend: preview is `<pre>` text (`PreviewPanel.tsx:31-35`); no tex/bib Monaco mapping (`lib/ide/language.ts:3-18`); single-file, `projects[0]` only (`PaperWorkspace.tsx:21,52`).

### 3.5 Skills
- **No execution engine**: manifests/tool_permissions/installations consumed by nothing — marketplace is UI-only; "platform tool broker" doesn't exist (`skills/*`, `manifest.py:17-18`).
- 5 first-party skills are 2-3 sentence prompt stubs (`seed.py:15-86`); `config_schema`/`settings_json` stored, never validated/applied, no edit endpoint (`manifest.py:42`, `models.py:72`); no uninstall/delete/search (`skills/router.py`).

### 3.6 Realtime / events
- Backend implements only `agent.run.*`; `experiment.*`, `runtime.*`, `latex.compile.*`, `skill.install.*` families and `agent.run.approval_required` have no producers (`websocket/envelopes.py:25-33` vs `packages/shared-schemas/src/events.ts:16-54`).
- No client→server protocol, no resume cursor, no ping; token deltas unrecoverable on reconnect (`websocket/router.py`); frontend never calls the REST replay endpoint (`lib/websocket/useProjectAgentEvents.ts`, `lib/api/agents.ts:60-66`).

### 3.7 Identity / tenancy / platform
- Object storage = reachability probe only; no upload/download/presign (`common/storage.py:1-8`) while seeds reference `s3://` URIs (`seed/demo.py:231`).
- No profile update, password change/reset, email verification, deactivation surface (`identity/router.py`, `models.py:19-20`).
- Orgs create/read-only: no member removal/role change/leave/rename/delete (`organizations/router.py:20-84`); `plan='free'` unenforced (`organizations/models.py:19`).
- `Project.settings_json` never read/written (`projects/models.py:30`); no unarchive (`projects/router.py:88-95`).
- Rate limiting absent on auth endpoints (`common/config.py:105-107`); no session administration (`common/session.py`).
- Demo seeder can't bootstrap empty DB and pre-blocks demo email registration (`seed/demo.py:34-56`).

### 3.8 Frontend / DX / infra
- OpenAPI→TS generation is an echo placeholder; all API types hand-written (`scripts/gen_api_types.sh:4-11`; `packages/shared-schemas/package.json:4`).
- No `error.tsx`/`not-found.tsx`/`loading.tsx` anywhere (`apps/web/app/`); UI kit = 5 primitives, no dialog/toast/select/tabs (`components/ui/`); dark mode disabled (`globals.css:15-17`).
- Pagination UI absent everywhere despite `Page<T>` (`ProjectList.tsx:14-17`, `PaperLibrary.tsx:10-13`, `ResearchChat.tsx:25-28`, `PatchReviewPanel.tsx:16`, `lib/api/projects.ts:24-28`).
- No frontend project-role helpers (only org ladder) → can't gate researcher-only actions (`lib/permissions/roles.ts`).
- Dev-only web Docker image, no production build (`infra/docker/web.Dockerfile`); `packages/ui`/`agent-protocol`/`skill-sdk`, k8s/terraform absent vs MONOREPO.md.
- Placeholder stores: `ui.ts:5-7` sidebar; `ide.ts:9-10` resize fields w/o setters; register page not i18n'd (`app/(auth)/register/page.tsx:10-16`).
- Web test suite = 1 Playwright smoke spec; zero unit/component tests (`apps/web/e2e`).
- Missing FE affordances: no file create/rename/delete/upload in IDE (`FileTree.tsx`); no run create/cancel UI in experiments dashboard; analysis results ephemeral (`AnalysisPanel.tsx`); patch UI can't create/delete files (`EditorPane.tsx`).

---

## 4. Cross-Cutting Quality Issues

### Security
1. **Email enumeration** by any authenticated user via member-add 404-vs-409 (`organizations/service.py:102-106`, `projects/service.py:190-198`) and register 409 (`identity/service.py:30-31`) — defeats the login timing-equalization effort.
2. **No brute-force protection on /auth/login|register** — rate limiter exists but is never wired there.
3. **Default `SECRET_KEY` (`dev-insecure-secret-change-me`) has no production boot guard** (`common/config.py:51`); main docker-compose sets no SECRET_KEY (`infra/docker/docker-compose.yml:58-64`) and hardcodes pg/minio creds.
4. **Plaintext LLM API keys in DB** (`llm_config/models.py:32`); **Anthropic key leaked as bearer fallback to arbitrary user-configured base_urls** (`openai_compatible.py:34`).
5. **IDOR: cross-project experiment-run enumeration** — `list_runs` never verifies the experiment belongs to the checked project (`experiments/service.py:116-120`).
6. Path deny-list basename-only + case-sensitive (`common/paths.py:20-33`); document file paths unnormalized `../` accepted (`documents/schemas.py:45-46`); `/readyz` leaks `str(exc)` to unauthenticated callers (`health/router.py:55`); X-Request-ID unvalidated (`middleware.py:26`); hardcoded demo creds in source (`seed/demo.py:19-21`); global skill-slug namespace leaks cross-tenant existence (`skills/service.py:160-161`).
7. WS authorization checked once at connect — revoked members keep streaming (`websocket/router.py:58-79`); cookie-on-handshake + SameSite=Lax breaks (silently) on any cross-domain deployment.

### Concurrency / races (systemic pattern: check-then-insert, count-based seq, no upsert)
8. Unhandled IntegrityError → 500 on concurrent: register (`identity/service.py:30-37`), org slug (`organizations/service.py:30-39`), membership adds, paper import (`research/service.py:48-78`), document first-save (`documents/service.py:136-149`), skill seeding (`skills/seed.py:93-95`). No global IntegrityError→409 handler (`common/errors.py`).
9. Seq allocation races: tool_calls `count(*)` (`agents/repository.py:51-55`), agent events `max+1` → IntegrityError **fails the run** (`repository.py:73-77`), experiment logs `count(*)` w/ no unique constraint (`experiments/repository.py:91-95`).
10. Patch apply TOCTOU + non-atomic multi-file writes → FS/DB divergence (`patches/service.py:117-158`); non-atomic `write_file` (`workspace/fs.py:120-127`); rate limiter INCR/EXPIRE non-atomic (`common/rate_limit.py:26-27`).

### Real-LLM path is broken end-to-end
11. Runtime message shape rejected by both real providers on any tool round-trip (`runtime.py:184`, `anthropic.py:90-110`, `openai_compatible.py:142-159`); text_buffer contamination breaks JSON finalize (`runtime.py:159-195`); Anthropic 1024-token truncation + silent `json.loads` fallback → **empty critique/patch persisted as a SUCCESSFUL run** (`critic_agent.py:74-77`, `coding_agent.py:70-73`); hallucinated tool name fails the whole run (`tools.py:153-159`); usage under-counted (`runtime.py:174-177`); stale `finish_reason` loop-var bug (`openai_compatible.py:135`).

### Silent failure swallowing (systemic)
12. Malformed WS frames dropped without logging (`lib/websocket/client.ts`); invalid skill config JSON silently `{}` (`SkillBuilder.tsx:32`); dropped patch files never reported (`coding_agent.py:84-91`); empty compile 'succeeds' (`documents/service.py:160-161`); tree truncation unflagged (`fs.py:29-69`); bozo arXiv feeds → empty list (`arxiv.py:96-98`); UTF-8 `errors='replace'` corruption round-trips cleanly (`fs.py:102`).

### State-machine / lifecycle absence
13. Experiment status transitions unconstrained; zombie RUNNING runs (`experiments/service.py:133-143`). CONFLICT patches permanently stuck (`patches/enums.py:14-16`). QUEUED agent runs orphaned forever if broker drops message — no reconciliation (`common/celery_app.py:28`). No last-owner protection (`projects/service.py:204-225`). Session TTL sliding-only, no absolute expiry.

### Frontend fragility
14. **Stale-cookie infinite redirect loop** login↔projects (`middleware.ts:27-31` + `(workspace)/layout.tsx:17-21`); blank page on non-401 session failure (`layout.tsx:32-34`).
15. **WS has no reconnect** — one blip freezes all live UI (`lib/websocket/client.ts:15-28`); token frames unordered/undeduped (`useProjectAgentEvents.ts:63-66`); 2-3 sockets per page.
16. Data-loss paths: refetch clobbers unsaved LaTeX (`PaperWorkspace.tsx:22`), tab close discards buffers (`lib/store/ide.ts:31-41`), no dirty confirmation anywhere.
17. Misleading review diff vs live file (`PatchDiff.tsx:12-17`); polling-and-timers instead of the existing WS events (`PatchReviewPanel.tsx:16`, `CodingAssistant.tsx:20`, `IdeaPanel.tsx:26-36`); Monaco from CDN breaks offline/air-gapped (`lib/ide/monaco.tsx:5-7`); a11y gaps (hand-rolled modal, span-onClick close buttons); `<html lang="en">` vs zh-CN default.

### Performance / scale
18. N+1 patterns: paper import, skills catalog (`skills/service.py:43-64`); unpaginated member/metric/log lists; per-task engine rebuild; one Redis pubsub conn per browser tab; per-request httpx clients; sync FS I/O on the event loop (`fs.py`, P3-D14); full workspace tree JSON into LLM context per tool call.

---

## 5. Contracts

### 5.1 REST API surface (all under FastAPI :8000; error envelope `{"error":{code,message,request_id,details?}}`; CSRF header `X-CSRF-Token` on all non-GET)

| Area | Routes |
|------|--------|
| Health | `GET /healthz`, `GET /readyz` |
| Auth | `POST /auth/register`, `POST /auth/login`, `POST /auth/logout`, `GET /auth/me` (re-issues CSRF cookie) |
| Orgs | `GET/POST /organizations`, `GET /organizations/{org_id}`, `GET/POST /organizations/{org_id}/members` |
| Projects | `GET /projects?organization_id=` (paginated), `POST /projects`, `GET/PATCH/DELETE(=archive) /projects/{id}`, `GET/POST/PATCH/DELETE /projects/{id}/members` |
| Research | `/projects/{id}/papers/search`, `/papers/import`, `GET /papers`, `GET/DELETE /papers/{paper_id}`, ideas CRUD `/ideas…`, `POST /ideas/{idea_id}/critic-review`, `GET /ideas/{idea_id}/critiques` |
| Agents | `POST/GET /projects/{id}/agents/runs`, `GET /runs/{run_id}`, `GET /runs/{run_id}/events?after_seq=`, `POST /runs/{run_id}/cancel` |
| Coding | `POST /projects/{id}/coding-agent/runs` |
| Workspace | `GET /projects/{id}/workspace/tree`, `GET /workspace/files?path=` (returns `{content, sha, binary}`) |
| Patches | `POST/GET /projects/{id}/workspace/patches`, `GET /{patch_id}`, `POST /{patch_id}/apply`, `POST /{patch_id}/reject` |
| Git | `GET /projects/{id}/git/status` (stub) |
| Experiments | `/projects/{id}/experiments` CRUD-lite, `/experiments/{id}/runs`, `/experiment-runs/{run_id}` PATCH, `/metrics`, `/logs`, `/artifacts`, `POST /experiment-runs/{run_id}/analyze` |
| Documents | `/projects/{id}/latex-projects` list/create, `/files` list, `GET /files?path=`, `PUT /files` (upsert), `POST /compile`, `GET /compile-jobs/{id}` |
| Skills | `/projects/{id}/skills/catalog`, `/installed`, `/allowed-tools`, `POST /validate`, custom create/update, `GET /{slug}`, `POST /{slug}/install`, `POST /{slug}/toggle` |
| LLM config | `GET/POST /projects/{id}/settings/llm` (upsert by `(project_id,name)`; empty api_key preserves stored key), `DELETE /settings/llm/{config_id}` |

Role gates: VIEWER = reads; RESEARCHER = writes/runs/patch apply; ADMIN = LLM config write, member management; non-membership always 404 (never 403).

### 5.2 WebSocket protocol
- Endpoint: `GET /ws?project_id=<uuid>`; auth = `ros_session` cookie on handshake; app close codes 4400/4401/4403 (likely lost pre-accept); push-only.
- Redis channel: `ws:project:{project_id}` via `common/pubsub`.
- Envelope: `{event_id:'evt_'+hex, event_type, project_id, resource_type, resource_id, timestamp:ISO-8601, payload}`.
- Implemented events (agent_run only): `agent.run.started`, `agent.run.token {delta}` (live-only), `agent.run.tool_call.started {seq,tool_name,arguments}`, `agent.run.tool_call.completed {seq,tool_name,status,result_summary}`, `agent.run.completed {output,citations,usage}`, `agent.run.failed {error}`, `agent.run.cancelled`. Coarse events also persisted → REST replay `?after_seq=`.
- Canonical TS contract: `packages/shared-schemas/src/events.ts` (contract test `apps/api/tests/test_ws_contract.py`); experiment/runtime/latex/skill families + `approval_required` are contract-only.
- Citation key convention: `'<source>:<external_id>'` (e.g. `arxiv:2401.12345`).

### 5.3 Environment variables
Backend (`common/config.py`, UPPER_SNAKE, `.env` supported): `POSTGRES_DSN`, `REDIS_URL`, `CELERY_BROKER_URL`/`CELERY_RESULT_BACKEND` (default REDIS_URL), `SECRET_KEY`, `CORS_ORIGINS`, `ENVIRONMENT` (local|staging|production), `SESSION_TTL_SECONDS` (7d), `SESSION_COOKIE_SECURE`, `COOKIE_SAMESITE`/`COOKIE_DOMAIN`, `S3_ENDPOINT_URL`/`S3_REGION`/`S3_ACCESS_KEY`/`S3_SECRET_KEY`/`S3_BUCKET`, `LLM_PROVIDER` (mock|anthropic|openai_compatible, default **mock**), `LLM_MODEL`, `ANTHROPIC_API_KEY`, `PAPER_PROVIDER` (arxiv), `ARXIV_API_BASE`, `ARXIV_TIMEOUT_SECONDS`, `PAPER_SEARCH_MAX_RESULTS` (25), `WORKSPACE_ROOT` (/data/workspaces), `WORKSPACE_MAX_FILE_BYTES` (1MB), `WORKSPACE_MAX_TREE_ENTRIES` (5000), `WORKSPACE_MAX_TREE_DEPTH` (12), `AGENT_MAX_TOOL_CALLS` (4), `AGENT_RUN_TIMEOUT_SECONDS` (120, unenforced), `RATE_LIMIT_AGENT_RUNS_PER_MINUTE` (30), `RATE_LIMIT_PAPER_SEARCH_PER_MINUTE` (60), `DB_USE_NULLPOOL` (true for worker), `LOG_LEVEL`/`LOG_JSON`.
Frontend: `NEXT_PUBLIC_API_BASE_URL` (default http://localhost:8000; WS URL derived by http→ws replace).

### 5.4 Database models (Alembic revisions 0001–0005; UUID PKs app-side, server-clock timestamps, Postgres-only JSONB/native enums; every model must be imported in `researchos/models.py`)
- 0001 identity/tenancy: `User`, `Organization`, `OrganizationMembership`, `Project`, `ProjectMembership`
- 0002 research/agents: `Paper`, `Idea`, `ResearchCritique`, `AgentRun`, `ToolCall`, `AgentRunEvent`
- 0003 IDE: `PatchProposal`, `PatchFile`, `PatchHunk` (unused)
- 0004: `Experiment`, `ExperimentRun`, `ExperimentMetric`, `ExperimentLog`, `ExperimentArtifact`, `LatexProject`, `DocumentFile`, `LatexCompileJob`, `Skill`, `SkillVersion`, `SkillInstallation`
- 0005: `LLMProviderConfig`

### 5.5 Frontend routes
`/` → redirect `/projects`; `/login`, `/register`; `/projects`; `/projects/[projectId]/{overview, research, ide, experiments, paper, skills, skills/builder, settings}`. Middleware matcher: `/projects/:path*`, `/login`, `/register` (cookie-presence only). Cookies: `ros_session` (HttpOnly, SameSite=Lax), `ros_csrf` (JS-readable). Demo account: `demo@researchos.dev` / `demo-password-123` (hardcoded across README/RUNBOOK/smoke/e2e).

### 5.6 Celery / worker contract
Task `agents.run_agent(run_id)` on queue `agents` — the only real task; dispatch by name only; `task_acks_late=True`, prefetch 1 (tasks must be idempotent under redelivery); every task body via `run_async_task` (fresh loop + engine/Redis disposal). Queues declared: agents, ingestion, runtime, latex, experiments, skills, default (last six empty). Prefix routing `'<area>.*' → <area>` queue.

### 5.7 Standing design decisions (docs/PHASE0-3_DECISIONS.md — treat as constitution or explicitly supersede)
pgvector; SQLAlchemy 2 async (no SQLModel); TanStack Query + Zustand; uv; Recharts; embedded WS gateway over Redis pub/sub; whole-file patch apply guarded by `base_sha`; **agents never write files** (patch review is the only write path); workspace path deny-list; filesystem as source of truth for workspaces (nothing cached in DB); no destructive git ops ever. `docs/MVP_STATUS.md` + README mock table are the honest real-vs-mock ledger; `docs/API.md`/`DATABASE.md`/`AGENTS.md` contain aspirational surface (planner agent, memory graph, api-keys, paper_chunks) with no implementation.
