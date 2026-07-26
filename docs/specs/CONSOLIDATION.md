# CONSOLIDATION — binding cross-partition resolutions

> Authored by the orchestrator after reading all nine specs. **On any conflict between a
> partition spec and this file, THIS FILE WINS.** Implementers read their own spec fully,
> then this file, then start.

## 0. Partitions and wave plan

| Wave | Partition | Owns (summary) | Spec |
|---|---|---|---|
| A (parallel) | `runtime-llm` | `agents/llm/**`, `agents/runtime/{runtime,base,events,citations,critic_agent,research_agent,experiment_agent}.py`, new `agents/runtime/skills_injection.py`, `agents/{models,repository}.py`, `skills/service.py` (read-path add), `apps/worker/researchos_worker/tasks/agents.py` | runtime-llm.md |
| A | `coding-git` | `agents/runtime/{tools,coding_agent}.py`, `patches/**`, `git/**`, `workspace/**`, `common/paths.py`, new `coding_chat/**` | coding-git.md |
| A | `writing` | `documents/**`, `agents/runtime/latex_agent.py` | writing.md |
| A | `research` | `research/**`, new `apps/worker/researchos_worker/tasks/ingestion.py` | research.md |
| A | `experiments-figures` | `experiments/**`, new `figures/**`, new `preferences/**`, new `apps/worker/researchos_worker/tasks/figures.py` | experiments-figures.md |
| A-post | `M1` (consolidated) | single alembic migration, `packages/shared-schemas/**`, `researchos/main.py`, `researchos/models.py`, `websocket/{envelopes.py,gateway ping-pong}`, `apps/worker/researchos_worker/app.py` + `tasks/__init__.py`, `apps/api/tests/conftest.py` `_TABLES`, auth hardening | this file §6 |
| B1 (first) | `frontend-design-system` | `apps/web/app/**`, `components/**`, `features/workspace/**`, `lib/{theme,shortcuts,command}/**`, `lib/i18n/**` | frontend-design-system.md |
| B2 (parallel) | `frontend-ide` | `features/ide/**`, `lib/websocket/**`, `lib/api/{codingAgent,patches,git,workspace,agents}.ts`, `lib/ide/**`, `lib/store/ide.ts` (delete) | frontend-ide.md |
| B2 | `frontend-research` | `features/research/**`, `lib/api/{papers,ideas,research}.ts` | frontend-research.md |
| B2 | `frontend-paper` | `features/paper/**`, `features/system/**`, `features/experiments/{RunDetail.tsx,CreateAnchorDialog.tsx,CreateFigureDialog.tsx,MetricsChart.tsx}`, `lib/api/{documents,anchors,figures,preferences}.ts`, `e2e/paper.spec.ts` | frontend-paper.md |

**M0 (already applied by the orchestrator before Wave A):** `common/config.py` Settings
fields, dependency additions (`selectolax`, `matplotlib`, `lucide-react`, `monaco-editor`
devDep, `vitest` devDep), Dockerfile git install.

Gates: ruff/mypy/tsc/build run **after M1** (Wave A) and after each Wave B stage — not per
partition mid-wave (cross-partition imports may be temporarily unresolved). pytest is
CI-only (no local PG).

## 1. Coding chat (coding-git ⇄ frontend-ide) — BINDING

- Paths: **`/projects/{project_id}/coding-chat/sessions`** (backend spec wins; frontend's
  assumed `/coding-agent/sessions` is wrong — update `lib/api/codingAgent.ts`).
- Message model: backend's role-based `chat_messages` wins. `GET /sessions/{sid}` returns
  session + `messages: [{id, seq, role: "user"|"assistant", content, agent_run_id,
  patch_id, created_at}]`. Frontend renders messages directly; a "turn" = user message +
  the assistant message sharing its `agent_run_id`. No `/turns` route.
- ADD to coding-git (from frontend spec): `POST /sessions/{sid}/messages` returns **409
  `{"error":{"code":"session_busy"}}`** while the session's latest run is queued/running.
- Frontend fallback behavior (list route 404 → implicit session over agent runs) stays.

## 2. Patch review & apply — BINDING

- Patch detail: `files[]` carry `base_content` (nullable) + `edits[]` + server-computed
  real `hunks[]` (coding-git shapes win; they match what frontend-ide needs).
- **Partial apply is FILE-granularity, not hunk-granularity** (scope control):
  `POST .../apply` optional body `{"paths": ["src/a.py"]}` — omitted = apply all
  (today's semantics). Response gains `"skipped_paths": [...]`. SHOULD-tier for
  coding-git. Frontend: per-file checkboxes; hunk checkboxes are display-only this
  session (render hunks, select files). If apply-with-body returns 422, hide checkboxes.
- Apply success response: `{"patch_id", "status", "conflicts", "applied_commit_sha"}`.
- Reject legal from `pending` **and** `conflict`.

## 3. Git surface — BINDING (producer shapes win; frontend maps)

- `GET /git/log?path=&limit=&skip=` → `{"entries":[{sha, author_name, author_email,
  authored_at, summary, patch_id, agent_run_id, reverts_sha}]}`. No `total`; frontend
  infers has-more from page fill; `short_sha` derived client-side.
- `GET /git/commits/{sha}/diff` → coding-git's shape (`omitted` flag, no `parent_sha`).
- `POST /git/revert {"sha"}` → 200 `{"commit_sha", "reverted_sha"}`.
- Git-disabled degradation: status `provider:"disabled"`, log `{"entries":[]}`; frontend
  shows timeline empty state.
- ADD to coding-git (from frontend spec): REST **`GET /projects/{id}/workspace/grep`**
  `?query=&regex=false&limit=100` → `{"matches":[{path, line, preview}], "truncated"}`
  (router glue over the already-specced service function; 400 invalid regex).

## 4. WS / realtime — BINDING

- `agent.run.started` payload gains `skills`, `agent.run.failed` gains `code`
  (runtime-llm). `agent.run.token` payload gains **`seq`** (monotone per run) — assigned
  to runtime-llm (owner of `events.py`), MUST-tier (frontend ordering depends on it;
  trivial where events already get seqs).
- `patch.created` / `patch.status_changed` / `git.commit.created` / `text_snapshot` /
  `research.feed.updated` / figure & anchor events: **DEFERRED** (every consumer has a
  refetch fallback; do not implement producers this session). Event *type strings* for
  `paper.ingest.*` DO ship (research owns producers).
- Ping/pong: client sends `{"type":"ping","ts"}`; the gateway must read client frames and
  reply `{"type":"pong","ts"}`, ignoring anything else → **M1** (websocket gateway).
- `websocket/envelopes.py` `ResourceType` += `"paper"` → M1.

## 5. Preferences, anchors, figures (experiments-figures ⇄ design-system, paper) — BINDING

- Preferences: producer shapes win. `GET/PUT /users/me/preferences` with
  `{"effective": {...}, "global": {...}|null}`; PUT is **full replace** of the global row
  `{theme, language, figure_style_slug, extra}`. Consumers read `.effective`, merge
  client-side before PUT. Field is `language` (not `locale`), `figure_style_slug` (not
  `default_figure_style`). Project-scoped preferences routes ship as specced.
- Style presets: **`GET /projects/{id}/figures/style-presets`** (project-scoped; no
  global `/figure-styles`). ADD to preset response a `style` object
  `{palette: string[], font_family: "serif"|"sans", grid: bool, legend_frame: bool}`
  (drives frontend SVG thumbnails).
- Anchors & figures are **project-scoped** (`/projects/{id}/anchors`, `/figures`) — the
  frontend-paper spec's `/latex-projects/{lid}/result-bindings` paths are wrong; its
  panels consume the producer routes (`AnchorResponse` uses `decimals/scale/suffix`, not
  `format_spec`). Staleness via polling `GET /anchors/staleness`; no staleness WS event.
- Figure assets: fetched as bytes from `GET /figures/{fid}/assets/{svg|png}` (ETag) into
  blob URLs. Insert-into-paper writes an `\includegraphics{figures/<name>.png}` block
  into the buffer + `PATCH /figures/{fid}` `{latex_project_id, usage_path}`. Materializing
  actual image files into the LaTeX workspace is deferred (mock compile doesn't read
  them).
- Anchor↔document bridge (writing CP-2): experiments-figures ADDS a facade
  `researchos/figures/anchor_service.py::ResultAnchorService` with
  `get_anchor(project_id, latex_project_id, macro_name)` / `list_anchors(...)` returning
  `ResultAnchorInfo{macro_name ("ROS"+name, no backslash), anchors_file_path
  (fixed "results/anchors.tex"), formatted_value, experiment_id, run_id}` — thin adapter
  over `AnchorRepository` + the macro renderer. The writing partition owns writing the
  macros content into the document (via `DocumentService.save_file`) on insert/regenerate,
  calling `render_macros_tex`.

## 6. M1 worklist (consolidated partition; runs after Wave A partitions merge)

1. **One alembic migration** (hand-written, single revision on current head), in order:
   (a) `tool_calls` renumber-dupes backfill then `uq_tool_call_run_seq` UNIQUE;
   (b) `patch_files` +`base_content`,+`edits_json`; `patch_proposals`
   +`applied_commit_sha`,+`conflict_json`,+`superseded_by`; new `chat_sessions`,
   `chat_messages`;
   (c) new `document_file_revisions` (+backfill from `document_files`), new enums
   `document_suggestion_op/status`, new `document_suggestions`; `latex_compile_jobs`
   +`preview_model_json`,+`diagnostics_json`;
   (d) new enums `paper_ingest_status`,`paper_section_kind`; `papers` +7 columns
   +2 indexes +backfills; `ideas` +`metadata_json`; new `paper_sections`,
   `research_feed_prefs`;
   (e) `experiments` +`metric_meta_json`; `experiment_runs` +`log_next_seq` (+backfill);
   `experiment_logs` resequence-backfill then UNIQUE `(run_id, seq)`; new enums
   `anchor_aggregation`,`figure_render_status`; new `result_anchors`, `figures`,
   `figure_assets`, `user_preferences`, `experiment_ingest_tokens`.
   `user_preferences` uniqueness: use **two partial unique indexes** (`WHERE project_id
   IS NULL` / `IS NOT NULL`) instead of `NULLS NOT DISTINCT` unless the compose PG image
   is ≥15 (verify `infra/docker/docker-compose.yml`).
2. **shared-schemas**: `preferences.ts` (ThemePreference, UserPreferences w/ `language`);
   `events.ts`: `AgentRunStartedPayload.skills`, `AgentRunFailedPayload.code`,
   `AgentRunTokenPayload.seq?`, `RESEARCH_EVENTS = paper.ingest.{started,completed,failed}`
   into `EVENT_TYPES`, `ResourceType` += `'paper'`, ingest payload interfaces
   (producer field names: `status: 'succeeded'|'abstract_only'`, `section_count`); patch/
   git/chat/anchor/figure **REST types** per the producer specs (PatchEdit, GitCommitEntry,
   ChatSession/ChatMessage, AnchorResponse, FigureResponse, StylePresetInfo,
   PreferencesResponse, DocumentSuggestion, SuggestionSpan, CompileDiagnostic,
   DocumentVersionConflictDetails). Keep `test_ws_contract.py` and `envelopes.py`
   vocabulary in sync (that's why M1 owns both sides).
3. `researchos/main.py`: include routers `coding_chat`, `figures`, `preferences.me_router`,
   `preferences.project_router`, `experiments.ingest_router`.
4. `researchos/models.py`: aggregator imports for all new models (chat, revisions,
   suggestions, sections, feed prefs, anchors, figures, assets, preferences, ingest
   tokens).
5. `websocket`: gateway ping/pong + envelopes `ResourceType` += `'paper'`.
6. Worker: `app.py` `include=` += `tasks.figures`, `tasks.ingestion`; `tasks/__init__.py`.
7. `apps/api/tests/conftest.py` `_TABLES` += (children first): `figure_assets`, `figures`,
   `result_anchors`, `experiment_ingest_tokens`, `user_preferences`, `chat_messages`,
   `chat_sessions`, `document_suggestions`, `document_file_revisions`, `paper_sections`,
   `research_feed_prefs`.
8. **Auth hardening**: apply the existing rate-limit dependency to `/auth/login` and
   `/auth/register`; align register-conflict response to defeat enumeration (generic
   message, same status/timing as success path where feasible — keep small).

## 7. Research surface (research ⇄ frontend-research) — BINDING

- Search: producer request wins — `filters` object contains `categories, date_from,
  date_to, author, title, abstract, sort, offset`. Per-request `sources` filter is NOT
  implemented; frontend hides that control. Response is `{results, provider_status}`;
  frontend derives `provider_errors` display from `provider_status`, computes `has_more`
  from page fill, and computes `in_library` client-side against the library list.
  Provenance = `extra.sources`.
- Import: reference-based `{"papers":[{source, external_id}]}` →
  `{imported: PaperResponse[], skipped:[{source, external_id, reason}]}`.
- Sections: `GET /papers/{paper_id}/sections`; vocabulary is the producer's
  (`ingest_status: pending|running|succeeded|abstract_only|failed`; kinds `introduction`,
  `related_work`, `background`, `results`, …). Re-ingest = `POST /papers/{id}/ingest`.
  Frontend maps labels; no `full_text` string anywhere.
- Feed: producer routes `GET /papers/feed?cursor=&limit=` and
  `GET|PUT /papers/feed/categories`. No per-item dismiss/import routes: import uses the
  normal refs-based import; dismiss is client-side (localStorage) this session.
  `research.feed.updated` event dropped.
- Ideas: **synchronous** `POST /ideas/generate` → `201 {ideas, gaps_considered,
  papers_used}` (409 `library_too_small` <5 papers). No `ideate` AgentType anywhere.
  Gap fields live in `IdeaResponse.metadata` (`gap_type`, `supporting_paper_keys`).
  `GET /ideas/gap-matrix` does NOT exist; the matrix heat view is deferred — list view
  only.
- "Explain this section": frontend seeds the research chat with `context.paper_id` +
  `section_seqs`; **runtime-llm partition** (owner of `research_agent.py`) implements:
  inject referenced section bodies into the prompt via
  `PaperService.sections_for_agent` and set `allowed_tools = ["paper.search",
  "library.list", "paper.sections"]`. The `paper.sections` TOOL registration in
  `tools.py` is implemented by **coding-git** (owner of tools.py) using research's CP-2
  snippet verbatim.

## 8. Documents surface (writing ⇄ frontend-paper) — BINDING

- Save conflict: code is **`document_version_conflict`** with writing's full details
  payload (`current_version`, `server_content`, `merge` hints). Frontend's assumed
  `version_conflict` code is wrong; adapt `isVersionConflict`.
- **No `POST /files/ops` route.** Insert-at-cursor (anchors, citations, figure blocks)
  edits the local buffer + CAS-saves, or uses writing's dedicated
  `POST /anchors/insert` / `POST /citations/insert` endpoints.
- Tracked changes are **server-side suggestions** (writing's model wins): frontend
  hydrates `GET /suggestions?status=proposed&path=`, accepts via
  `POST /suggestions/{id}/accept` (response carries updated file content+version →
  replace buffer), rejects via `/reject`. The zustand `suggestionStore` becomes a cache
  of server suggestions, not the source of truth.
- Selection ops: `POST /selection-ops` → 202 `{agent_run_id, stream}`; completion via
  `agent.run.completed` (or run polling), then refetch suggestions.
- Bibliography: writing's `GET /citations` + `POST /citations/insert` win (no
  `/bibliography` routes). Response `{items:[{paper_id, title, authors: string[], year,
  cite_key, in_bib}], total, limit, offset}`.
- Compile: `preview_model` + `diagnostics` per writing's D7 (its spec is normative —
  frontend implementer reads writing.md §D7 for block shapes). `latex.compile.*` events
  SHOULD; frontend keeps polling fallback.
- Mock latex provider: writing's `_mock_op` transform table (its CP-1) is the single
  deterministic contract. Frontend e2e asserts on structure (a suggestion appears with
  non-empty replacement), NOT exact text.

## 9. Frontend internals — BINDING

- Themed Monaco: design-system's `components/editor/monaco.tsx` is canonical.
  frontend-ide's `lib/ide/monaco.tsx` becomes a thin re-export; its `theme.ts` hook
  consumes `@/lib/theme`. Import swaps in EditorPane/PatchDiff/PaperWorkspace happen in
  the owning feature partitions (B2 wave), not in design-system.
- `features/experiments/MetricsChart.tsx` `useChartTheme` swap → **frontend-paper**
  partition (it already owns experiments-feature files).
- Route pages (`ide/page.tsx`, `research/page.tsx`, `research/read/[paperId]/page.tsx`,
  settings page Appearance card): owned by **design-system** (app/** owner) — it applies
  the thin-wrapper bodies requested by ide/research specs (import from feature roots;
  those components exist by the time B2 merges; design-system lands first with the OLD
  bodies retokened, then each feature partition's CP is applied by that partition itself
  editing ONLY its feature files + the consolidator note: since app/** belongs to
  design-system, the feature partitions MAY edit exactly their one route page file as
  listed here — this is the single sanctioned overlap, sequenced by the wave order
  (design-system finishes before B2 starts).)
- `lib/api/agents.ts`: owned by frontend-ide; apply frontend-research's CP-2 (context
  fields, pagination opts). No `'ideate'` in any AgentType union.
- i18n keys: each feature partition adds its own keys to the two dictionaries
  (`lib/i18n/dictionaries/*` is design-system-owned, but key additions are append-only
  and wave-sequenced: design-system lands its ~45 keys in B1; feature partitions append
  their sections in B2 — append-only edits to distinct key namespaces are conflict-free).

## 10. Risk register (implementer-actionable)

1. Parallel Wave A agents must not touch files outside their partition — anything extra
   goes in a `NOTES-FOR-M1.md` appended note, not code.
2. Cross-partition imports during Wave A may not resolve until all A partitions land —
   use lazy imports where the target module is another partition's NEW file
   (writing→figures facade already designed so; experiment_agent→directions likewise).
3. Native-enum additions require careful `values_callable` parity with existing models —
   copy the existing pattern exactly (see `experiment_run_status`).
4. The migration's UNIQUE constraints need their backfills to run FIRST in the same
   revision (tool_calls seq, experiment_logs seq).
5. Frontend builds must never depend on M1's shared-schemas timing — each spec already
   mandates local type fallbacks; keep them.
6. Monaco stays CDN-loaded (P3-D13); `monaco-editor` is types-only devDep — any runtime
   import of it breaks the build.
7. The mock LLM provider MUST cover: multi-turn coding tool-use script (coding-git CP-4),
   selection ops `_mock_op` (writing CP-1), gap ideas (research CP-4), section-grounded
   explain (research CP-5f) — all live in `agents/llm/mock.py` owned by runtime-llm;
   runtime-llm implements ALL FOUR mock scripts (collect exact behaviors from those
   specs' CP sections before starting).
8. `agents/runtime/tools.py` single-writer: coding-git implements its own tools PLUS
   research's `paper.sections` registration (CP-2 verbatim) PLUS runtime-llm's
   `granted_by` ToolContext field (CP-2b) — three inputs, one owner.
9. Frontend partitions must treat every not-yet-landed backend route's 404/422 as a
   designed degraded state (each spec lists them) — never a crash.
10. After M1, run the full gate (`ruff`, `mypy`, `pnpm -r typecheck`, `pnpm --filter web
    build`); a dedicated fixer agent resolves cross-partition seams before Wave B starts.
