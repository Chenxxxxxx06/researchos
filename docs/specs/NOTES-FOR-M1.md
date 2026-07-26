# Notes for M1 (consolidation partition)

Appended by Wave A partition implementers. Each bullet is a change M1 must make
in files outside the author's partition.

## From experiments-figures

- `researchos/main.py`: include routers `researchos.figures.router.router`,
  `researchos.preferences.router.me_router`,
  `researchos.preferences.router.project_router`,
  `researchos.experiments.ingest_router.router`.
- `researchos/models.py` (aggregator): import + `__all__` for `ResultAnchor`,
  `Figure`, `FigureAsset` (from `researchos.figures.models`), `UserPreference`
  (from `researchos.preferences.models`), `ExperimentIngestToken` (from
  `researchos.experiments.models`). Until this lands, the run-terminal staleness
  hook in `experiments/service.py` queries `result_anchors`/`figures`, so the
  experiments API tests need these tables created (aggregator import is what
  puts them on `Base.metadata` for the conftest `create_all`).
- `apps/worker/researchos_worker/app.py`: `include=` += `"researchos_worker.tasks.figures"`.
- `websocket/envelopes.py`: `ResourceType` += `"figure"` — figure WS events in
  `researchos/figures/events.py` auto-enable once the literal contains it
  (guarded by `get_args(ResourceType)`); no figures-partition change needed.
- `apps/api/tests/conftest.py` `_TABLES` += (children first): `"figure_assets"`,
  `"figures"`, `"result_anchors"`, `"experiment_ingest_tokens"`, `"user_preferences"`.
- shared-schemas: per the experiments-figures spec "shared-schemas additions"
  section (FIGURE_EVENTS, ANCHOR_EVENTS, ResourceType `'figure'`, payload
  interfaces, and the REST types `AnchorResponse`, `AnchorStalenessReport`,
  `FigureSpec`, `FigureResponse`, `StylePresetInfo`, `PreferencesResponse`,
  `IngestTokenResponse`). Note: style preset responses carry a `style` object
  `{palette, font_family, grid, legend_frame}` per CONSOLIDATION §5.
- `agents/runtime/experiment_agent.py` (runtime-llm applies): replace the
  `'loss'` heuristic via `researchos.experiments.directions.metric_direction`
  and `ExperimentService.get_metric_meta_for_run` (method now exists).
- `user_preferences` uniqueness is declared at the model level with
  `UniqueConstraint(..., postgresql_nulls_not_distinct=True)` (PG 16 in compose,
  per orchestrator confirmation) — the migration should mirror
  `UNIQUE NULLS NOT DISTINCT (user_id, project_id)`.

## From research

- `websocket/envelopes.py`: `ResourceType` += `"paper"`. Until then,
  `research/ingest.py`'s `paper.ingest.*` publishes fail EventEnvelope
  validation and are swallowed by its try/except (ingestion still completes);
  they auto-enable once the literal gains `"paper"`.
  `tests/test_paper_ingest.py::test_ingest_publishes_ws_events` asserts the
  envelopes and passes only after this lands.
- shared-schemas `events.ts`: `RESEARCH_EVENTS = ['paper.ingest.started',
  'paper.ingest.completed', 'paper.ingest.failed']` folded into `EVENT_TYPES`;
  `ResourceType` union gains `'paper'`; payload interfaces
  `PaperIngestCompletedPayload { paper_id: string; status: 'succeeded' |
  'abstract_only'; section_count: number }` and
  `PaperIngestFailedPayload { paper_id: string; error: string }`. Keep
  `test_ws_contract.py` vocabulary in sync.
- `researchos/models.py` (aggregator): import + `__all__` for `PaperSection`,
  `ResearchFeedPref` (from `researchos.research.models`).
- `apps/api/tests/conftest.py` `_TABLES` += (children first): `"paper_sections"`
  (before `"papers"`), `"research_feed_prefs"` (before `"projects"`). Both
  currently get truncated via CASCADE from `papers`/`projects`, so ordering is
  the only concern.
- `apps/worker/researchos_worker/app.py`: `include=` +=
  `"researchos_worker.tasks.ingestion"` (task `ingestion.paper_fulltext`,
  queue `ingestion`; file already exists) and re-export in `tasks/__init__.py`.
- Migration (per CONSOLIDATION §6.1d, already listed): new enums
  `paper_ingest_status`, `paper_section_kind`; `papers` +7 columns
  (`doi`, `arxiv_id`, `primary_category`, `citation_count`, `ingest_status`
  default `'pending'`, `ingested_at`, `ingest_error`) + indexes
  `ix_papers_project_doi (project_id, doi)`,
  `ix_papers_project_arxiv (project_id, arxiv_id)`; backfills
  `SET arxiv_id = external_id WHERE source='arxiv'` and
  `SET doi = lower(metadata_json->>'doi') WHERE metadata_json ? 'doi'`;
  `ideas` + `metadata_json JSONB NOT NULL DEFAULT '{}'`; new tables
  `paper_sections` (UNIQUE `(paper_id, seq)` as `uq_paper_section_seq`) and
  `research_feed_prefs` (PK `project_id`) — shapes exactly as declared in
  `researchos/research/models.py`.

## From coding-git

- `researchos/main.py`: include router `researchos.coding_chat.router.router`
  (prefix `/projects/{project_id}/coding-chat`; the coding-chat REST tests in
  `tests/test_coding_chat.py` 404 until this lands).
- `researchos/models.py` (aggregator): import + `__all__` for `ChatSession`,
  `ChatMessage` (from `researchos.coding_chat.models`) — required for the
  conftest `create_all` to create `chat_sessions`/`chat_messages` so the
  coding-chat and chat-linked coding-agent tests pass.
- `apps/api/tests/conftest.py` `_TABLES` += (children first): `"chat_messages"`,
  `"chat_sessions"` (today they are only cleaned via the `projects` CASCADE).
- Migration DDL (matches CONSOLIDATION §6.1(b), details in coding-git.md
  "DB changes"): `patch_files` +`base_content TEXT NULL`, +`edits_json JSONB
  NULL`; `patch_proposals` +`applied_commit_sha VARCHAR(64) NULL`,
  +`conflict_json JSONB NULL`, +`superseded_by UUID NULL REFERENCES
  patch_proposals(id) ON DELETE SET NULL`; new `chat_sessions` and
  `chat_messages` (UNIQUE `(session_id, seq)` named
  `uq_chat_message_session_seq`; `chat_sessions.agent_type` reuses the existing
  native `agent_type` enum — no new enum values anywhere in this partition).
- `infra/docker/python.Dockerfile`: install the git binary
  (`RUN apt-get update && apt-get install -y --no-install-recommends git &&
  rm -rf /var/lib/apt/lists/*`). Without it everything degrades to
  `provider="disabled"` (by design), but real deployments want history.
- shared-schemas: patch/git/chat REST types per coding-git.md "shared-schemas
  additions": `PatchEdit {search, replace}`; `PatchFileInput` gains
  `edits?: PatchEdit[]` and **drops** `hunks` (input-side breaking change —
  hunks are server-derived only now); `PatchFile` response +`base_content:
  string | null`, +`edits: PatchEdit[]`; `PatchProposal` +`applied_commit_sha:
  string | null`, +`conflicts: PatchConflict[]`, +`superseded_by: string |
  null`; `ApplyResult` +`applied_commit_sha: string | null` and
  +`skipped_paths: string[]` (file-granular partial apply, CONSOLIDATION §2);
  new `GitCommitEntry`, `GitCommitDiff`, `GitCommitDiffFile`,
  `GitRevertRequest`, `GitRevertResponse`, `ChatSession`, `ChatMessage`,
  `CreateChatMessageRequest`, `CreateChatMessageResponse`. No `events.ts`
  changes from this partition.
- FYI (no action): runtime-llm's CP-2/3/4 seams (Agent.max_tool_calls,
  prevalidate hook, ToolDenied→recoverable conversion, mock coding script) are
  verified present in the working tree; `ToolBroker.execute` still RAISES
  `ToolDenied` for unknown/denied tools per runtime-llm CP-2(c) while tool
  implementation failures return in-band `{"error": ...}` payloads.

## From runtime-llm

- `skills/manifest.py::ALLOWED_TOOLS` (outside this partition): extend with the
  new read-only tools now present in `TOOL_REGISTRY` — `"workspace.read"`,
  `"workspace.grep"`, `"paper.sections"` — so skills can declare them. The
  injection layer (`skills/service.py::list_enabled_for_runtime` filters by
  `ALLOWED_TOOLS`, then `runtime.py::_effective_tools` intersects with
  `TOOL_REGISTRY`) materializes them automatically once declared; no other code
  change needed.
- Migration reminder (already in CONSOLIDATION §6.1a, restated for ordering):
  the `tool_calls` renumber-dupes backfill (`ROW_NUMBER() OVER (PARTITION BY
  agent_run_id ORDER BY created_at, id) - 1`) must run BEFORE adding
  `uq_tool_call_run_seq`; the constraint is already declared on the `ToolCall`
  model. No other DB changes from runtime-llm (`agent_runs.skill_ids_json` /
  `cost_json` columns already exist and merely start being populated).
- shared-schemas `events.ts` (already in CONSOLIDATION §6.2): payload fields are
  live on the wire now — `AgentRunStartedPayload.skills:
  {slug, version}[]` (always present), `AgentRunFailedPayload.code: string`
  (always present; one of `timeout | structured_output_parse_error | llm_error |
  config_error | agent_error | tool_denied`), `AgentRunTokenPayload.seq: number`
  (monotone per run, always present). `tool_call.started` payloads additionally
  carry `granted_by: string` ("agent" or the granting skill slug).

## From writing

- `researchos/models.py` (aggregator): import + `__all__` for
  `DocumentFileRevision`, `DocumentSuggestion` (from
  `researchos.documents.models`). The module import already registers them on
  `Base.metadata`, so conftest `create_all` sees the tables today; the explicit
  aggregator entries are for consistency/Alembic clarity.
- `apps/api/tests/conftest.py` `_TABLES` += `"document_suggestions"`,
  `"document_file_revisions"` (place both BEFORE `"document_files"` /
  `"latex_projects"` — children first). Until then, `TRUNCATE ... CASCADE` on
  `document_files`/`latex_projects` already clears them transitively.
- Migration (already in CONSOLIDATION §6.1c, restated with the exact model
  shapes): `document_file_revisions` needs the backfill INSERT of one revision
  per existing `document_files` row at its current version;
  `document_suggestions` uses native enums `document_suggestion_op`
  (`rewrite,expand,condense,fix_grammar,continue_writing,custom`) and
  `document_suggestion_status` (`proposed,accepted,rejected,superseded`) plus
  composite index `(latex_project_id, status)`; `latex_compile_jobs` gains
  `preview_model_json` JSONB NULL and `diagnostics_json` JSONB NOT NULL
  DEFAULT `'[]'`.
- shared-schemas: writing REST types per writing.md "shared-schemas additions"
  (`SelectionOp`, `SuggestionSpan`, `DocumentSuggestion`, `CompileDiagnostic`,
  `DocumentVersionConflictDetails`; `CompileJobResponse` gains
  `diagnostics: CompileDiagnostic[]` and `preview_model: PreviewModel | null`).
- `latex.compile.completed|failed` now has a real producer
  (`documents/service.py::_publish_compile_event`, resource_type
  `latex_compile`) — event strings and the resource type already exist in both
  contracts; no shared-schemas change needed, just don't remove them.
- Frontend-paper (informational, per CONSOLIDATION §8): save conflicts use code
  `document_version_conflict`; suggestions/citations/anchors routes live under
  `/projects/{pid}/latex-projects/{lid}/...` exactly as in writing.md API §.
