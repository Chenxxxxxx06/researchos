# Spec: Writing — Overleaf-grade LaTeX backend (selection ops, CAS versioning, anchors, compile fidelity, citations)

Workstream: **writing** (owner wishlist 8, realizes INNOVATION_IDEAS WS4-2 backend half, the backend halves of WS4-1/WS3-1 integration, and fixes Architecture Map weaknesses #31, #43, #44, #45).

Owned partition: `apps/api/researchos/documents/**`, `apps/api/researchos/agents/runtime/latex_agent.py`.

---

## Objective (user-visible outcome)

1. Selecting text in the paper editor and choosing Rewrite / Expand / Condense / Fix grammar / Continue produces a **tracked-change suggestion** (structured old→new spans) streamed live, which the user accepts or rejects — the AI never silently replaces text.
2. Two editors (or an editor plus a background refetch) can no longer clobber each other: saves are **compare-and-swap on a per-file version counter**; a stale save gets a 409 carrying the server content and a **three-way merge hint** so the client can merge instead of losing work.
3. One click inserts a result-anchor macro (`\ResBestAcc{}`) from the experiments workstream's macro service, with the `\input{results/anchors}` include maintained automatically.
4. Compile (still mock — no shell, honoring PHASE3/5) returns a **structural preview model** (sections/math/figures) plus a server-computed **diagnostics array** (unknown refs/cites, unclosed environments, duplicate labels), making `FAILED` reachable for genuinely broken documents.
5. Any library paper can be inserted as a citation: the backend generates its BibTeX entry into `refs.bib`, keeps keys deduplicated, and returns the `\cite{key}` snippet.

---

## Current state (concrete, file:line)

- **Save is last-write-wins**: `documents/service.py:124-152` `save_file` upserts by path, bumps `version` (`models.py:40`) with no expected-version check and no history — a background refetch clobbers unsaved edits (`ARCHITECTURE_MAP` §4 item 16, weakness #45). First save is check-then-insert → concurrent create races to IntegrityError 500 (`service.py:136-149`). `SaveFileRequest` (`schemas.py:45-47`) accepts unnormalized paths (`../` landmine).
- **Compile is a regex mock born SUCCEEDED**: `service.py:154-176` inserts a `LatexCompileJob` with `status=SUCCEEDED`, `engine='mock'`; `_mock_preview` (`service.py:47-62`) is line-oriented regex that breaks on nested braces (`\frac{a}{b}` → `a{b}`), ignores math/environments/`\input`/BibTeX (weaknesses #43, #44). Empty main file "succeeds". `QUEUED/RUNNING/FAILED` (`enums.py:8-12`) are unreachable. No `latex.compile.*` events are ever published despite the reserved family in `packages/shared-schemas/src/events.ts:42-46`.
- **LatexAgent is a side-chat**: `agents/runtime/latex_agent.py:21-45` — `allowed_tools=[]`, `response_schema=None`, prompt is two sentences; `finalize` returns `{"message": output_text}`. It has no document access and its output can never be inserted back (weakness #31). The runtime already registers it (`runtime/runtime.py:44`), already supports per-agent `response_schema` (read after `build_messages`, `runtime.py:148,166`), and already streams `agent.run.token` events over WS.
- **Mock provider** (`agents/llm/mock.py:66-95`) branches on `response_schema.properties`: `"files"` → coding patch, else critic object. A latex op schema would today get the critic object — the mock must gain a `"replacement"` branch (cross-partition).
- **No citation or anchor path exists**: `documents/router.py` exposes only list/create project, list/get/put files, compile, get job. `Paper` rows (`research/models.py:17-41`) have `authors_json/venue/published_at/url` — everything needed for BibTeX — but nothing renders them.
- **Prior constitution**: PHASE3-D2 (FS is source of truth) applies to the *code workspace*; LaTeX documents are DB-stored (`document_files`) and stay so. PHASE3/5 "no shell, no subprocess" for compile is **retained** — real latexmk/tectonic is explicitly out of scope here. No prior decision is superseded; the implicit last-write-wins `PUT /files` contract is tightened (see API changes) — the web workstream must start sending `expected_version`.

---

## Design (algorithms & data flow)

### D1. Selection ops are agent-run based (decision + justification)

**Decision: reuse the AgentRun/Celery/WS pipeline, not a synchronous endpoint.** Justification:
- The streaming requirement ("must stream if latency > a few seconds") is already solved: `agent.run.token` events flow worker → Redis pub/sub → WS relay. A sync endpoint would need brand-new SSE plumbing and would pin a FastAPI worker on LLM latency.
- Runs give persistence (suggestion ↔ `agent_run_id` traceability, replayable events), cooperative cancellation, and the existing per-user rate limit (`AgentRunService.create_run`, `agents/service.py:36-68`) for free.
- The mock provider path and all tests already flow through the runtime; a second LLM call-site would fork provider-resolution logic (factory 3-tier) for no benefit.
- Cost: one Celery hop (~100ms with a warm worker) — negligible against LLM latency; the mock provider completes in <1s end to end.

**Flow (numbered):**
1. Frontend flushes any pending autosave, then `POST /projects/{pid}/latex-projects/{lid}/selection-ops` with `{op, path, range, selection_text, expected_version, instruction?}`. `range` uses Monaco convention: 1-based `line`, 1-based `col`.
2. The documents router validates: project access (RESEARCHER), file exists, `op` in enum, `selection_text` ≤ 20 000 chars (empty allowed only for `continue_writing`), `instruction` ≤ 2 000 chars.
3. Server-side capture (in `documents/suggestions.py::prepare_op_context`): load the stored file; compute char offsets for `range` (lines split on `"\n"`); record `base_version = file.version`, `anchor_prefix` = 64 chars before the range start, `anchor_suffix` = 64 chars after the range end, `context_before` = previous 40 lines, `context_after` = next 20 lines. If `range`-extract of the stored content ≠ `selection_text` (client buffer ahead of store), keep the client's `selection_text` as authoritative and mark `anchor_mode='text'` (accept will re-anchor by text search only).
4. Router calls `AgentRunService(db).create_run(actor, pid, agent_type=AgentType.LATEX, message=instruction or op label, context={...all of step 3...})` (import only — no change to agents code) and returns 202 `{agent_run_id, stream}`.
5. Worker: `LatexAgent.build_messages` sees `context["op"]`, sets `self.response_schema = _SELECTION_OP_SCHEMA` (instance attribute — legal because the runtime reads `agent.response_schema` only after `build_messages`, `runtime.py:148,166`), and builds the per-op prompt (D2). Tokens stream to the WS as today.
6. `LatexAgent.finalize`: parse the JSON output → `{replacement, rationale}`. JSON parse failure → fallback `replacement = output_text.strip()`, `rationale = ""`, flag `unstructured: true` (the human review gate makes this safe — nothing applies without accept). Parsed JSON *without* a `replacement` key (e.g. an unextended mock returning the critic shape) → raise `ValueError` so the run is honestly `FAILED` (never persist an empty suggestion as success — lesson from weakness #28).
7. `compute_spans(old_text, new_text)` (D3) → `SuggestionService.create(...)` persists a `document_suggestions` row (status `proposed`). `output_json = {"message": rationale-or-summary, "suggestion_id", "path", "op", "unstructured"?}`.
8. Frontend receives `agent.run.completed`, fetches the run (`output_json.suggestion_id`), then `GET .../suggestions/{id}` and renders tracked changes from `spans`.
9. Accept: `POST .../suggestions/{id}/accept` → re-anchor + apply via the CAS save core (D4/D5) → returns updated file content+version; suggestion → `accepted`. Reject → `rejected`. Conflicted accepts return 409 but **leave status `proposed`** (a `last_error` field records why) — no terminal dead-end like patch `CONFLICT` (weakness #34).

### D2. LatexAgent selection-op prompt templates (strict output contract)

- Ops enum: `rewrite | expand | condense | fix_grammar | continue_writing | custom`.
- `_SELECTION_OP_SCHEMA = {"type":"object","properties":{"replacement":{"type":"string"},"rationale":{"type":"string"}},"required":["replacement","rationale"]}`.
- System prompt = shared preamble ("academic LaTeX writing assistant; output ONLY a JSON object matching the schema; preserve LaTeX commands, math, labels and citation keys verbatim unless the instruction targets them; never invent `\cite` keys") + a per-op directive table (rewrite: improve clarity/academic tone, same meaning & length ±20%; expand: elaborate with 2-4 sentences, mark speculative claims as assumptions; condense: ≤50% length, keep all citations; fix_grammar: grammar/spelling/spacing only, minimal edits; continue_writing: write the next 2-4 sentences continuing `context_before`, return them as `replacement`; custom: follow `instruction`).
- User message layout (order matters — the machine-readable line is what the mock parses):
  ```
  SELECTION_OP_INPUT: {"op":"rewrite","selection":"...","instruction":"..."}

  Context before:
  <context_before>
  Selection:
  <selection_text>
  Context after:
  <context_after>
  ```
- Chat mode (no `context["op"]`) keeps today's behavior verbatim (schema `None`, `{"message": output_text}` finalize) so the existing `PaperAssistant` keeps working.

### D3. Tracked-change spans (deterministic)

`documents/suggestions.py::compute_spans(old: str, new: str) -> list[Span]`:
1. Tokenize both strings with `re.split(r'(\s+)', s)` (words + whitespace preserved, lossless).
2. `difflib.SequenceMatcher(a=old_tokens, b=new_tokens, autojunk=False).get_opcodes()`.
3. Map opcodes → spans `{kind: 'equal'|'delete'|'insert'|'replace', old: str, new: str}` (joined token slices); merge adjacent spans of the same kind. `''.join(old parts) == old` and `''.join(new parts) == new` (round-trip invariant, unit-tested).
4. For `continue_writing`, `old=''` → single `insert` span.

### D4. CAS save + revisions + three-way merge hints

`save_file` becomes (in `documents/service.py`):
1. Normalize & validate `path` at the schema layer: must be relative, POSIX (`/`), no `..` segment, no leading `/`, no `\`, no NUL; pattern `^[A-Za-z0-9._][A-Za-z0-9._ /-]*$`, ≤512 chars. Reject with 422 otherwise (closes the `../` landmine).
2. If file missing → create (version 1) and insert revision row v1. Concurrent-create race: catch `IntegrityError` on the unique `(latex_project_id, path)` constraint, `rollback`, re-select and fall through to the update path (no more 500 — weakness pattern §4 item 8).
3. If file exists and `expected_version` is provided and `expected_version != file.version` → **409** `document_version_conflict` with details (see API section). Merge hint computation: `base = revision(expected_version).content` if retained; run `three_way_merge(base, server=file.content, client=payload.content)` (D5). If `base` is not retained → `base_available: false`, no merge object (client falls back to manual compare against `server_content`).
4. If `expected_version` is omitted → legacy force-save (backward compatible with the current frontend; the web workstream must adopt `expected_version` — cross-partition note).
5. On write: `content = new`, `version += 1`, insert `document_file_revisions` row `(file_id, new_version, content, updated_by)`, prune revisions older than the newest 50 per file, commit. All internal writers (suggestion accept, anchor include, citation insert) go through this same core (`_write_file_versioned`) so every mutation is versioned and revisioned.

### D5. Three-way merge (`documents/merge.py`)

`three_way_merge(base, server, client) -> MergeResult{merged: str|None, clean: bool, conflicts: list[Conflict]}` — a minimal line-level diff3:
1. Split all three into lines (`splitlines(keepends=True)`).
2. `get_opcodes()` base→server and base→client; convert each to a set of *change blocks* `{base_start, base_end, replacement_lines}` (equal opcodes skipped).
3. Sweep base line indices in order, interleaving blocks: a base region changed by only one side → take that side's replacement; changed identically by both → take once; changed differently by overlapping blocks → conflict `{base_start, base_end, base_text, server_text, client_text}`.
4. `clean = not conflicts`; `merged` is assembled only when clean (conflicting merges return `merged=None` — the client shows a conflict UI; we never auto-write merged content server-side).
Pure function, deterministic, stdlib-only, ~130 lines, exhaustively unit-testable without a DB.

### D6. Suggestion accept (re-anchoring)

1. Guard: suggestion status must be `proposed` (else 422 `suggestion_not_pending`); optional `expected_version` checked against the file (else 409 `document_version_conflict`, same payload as saves).
2. Anchor resolution against *current* stored content:
   a. If `file.version == suggestion.base_version` and `anchor_mode == 'range'`: apply at recorded offsets after verifying `content[start:end] == old_text` (belt-and-braces); on mismatch fall to (b).
   b. Text re-anchor: count occurrences of `old_text` (for `continue_writing`: of `anchor_prefix`, inserting after it). Exactly one → apply there. Zero → 409 `suggestion_conflict` `{reason:'anchor_not_found'}`; >1 → try `anchor_prefix + old_text + anchor_suffix` for disambiguation, still ambiguous → 409 `{reason:'ambiguous_anchor'}`. Status stays `proposed`; `last_error` recorded.
3. Apply = splice `new_text` over the anchored region → `_write_file_versioned` (D4 step 5) → suggestion `accepted`, `resolved_at/by` set, `applied_version = file.version`.
4. Response returns the full updated file `{path, content, version}` so the editor can swap its buffer atomically.

### D7. Compile preview model + diagnostics (`documents/latex_parse.py`)

Still mock (no shell — PHASE3/5 retained). New pure-Python structural pass over **all** project files:
1. `flatten(files: dict[str,str], main_path) -> list[SourceLine{file,line,text}]`: resolve `\input{x}` / `\include{x}` (append `.tex` if missing) against project files; unknown target → diagnostic `missing_input` (warning); cycle guard via visited-set + depth cap 10 (`input_cycle` error).
2. Single scan with a state machine over flattened lines (comments stripped with the existing `_COMMENT_RE` semantics):
   - environment stack from `\begin{name}` / `\end{name}`: mismatched name → `mismatched_environment` (error, reports both names+lines); non-empty stack at EOF → `unclosed_environment` (error) per frame; `\end` with empty stack → `unexpected_end` (error).
   - collect `\title{}`, `\(sub)*section{}` (level 1-3), `\label{}`, `\ref/\eqref/\autoref{}`, `\cite/\citep/\citet{}` (comma-split keys), display math (`\[ \]`, `$$`, `equation/align` envs), `figure`/`table`/`itemize`/`enumerate` envs, plain paragraphs.
   - `.bib` files in the project are parsed for keys via `documents/bibtex.py::parse_bib_keys` (regex `@\w+\s*\{\s*([^,\s]+)`).
3. Diagnostics: `undefined_reference` (ref target not in labels — warning), `undefined_citation` (cite key not in any project .bib — warning), `duplicate_label` (warning), `missing_end_document` (error), `missing_documentclass` (warning), `empty_document` (warning) plus the flatten/environment errors above. Every diagnostic: `{severity:'error'|'warning', code, message, file, line}`.
4. Preview model (JSONB): `{title, sections:[{level, number:"1.2", title, file, line, blocks:[{kind:'paragraph'|'math'|'list'|'figure'|'table', text, file, line}]}], labels:[...], bib_keys:[...], word_count}`. Block text uses an improved inline-command stripper: iterative innermost-brace reduction for `\textbf/\emph/\textit` (fixes the nested-brace corruption of `_CMD_RE`, weakness #43), math kept verbatim.
5. `DocumentService.compile`: run flatten+parse; `status = FAILED` iff any error-severity diagnostic (makes `FAILED` reachable; the default template stays clean → SUCCEEDED, so seeds/smoke keep passing); `error_summary` = first error message; plain-text `preview` regenerated from the preview model (headings + paragraph text — strictly better than today); persist `preview_model_json`, `diagnostics_json`. SHOULD: publish a `latex.compile.completed`/`latex.compile.failed` envelope (`EventEnvelope(resource_type='latex_compile', ...)` via `common.pubsub.publish_event`) — event strings and resource type already exist in both contracts; this is the first real producer for the family.

### D8. Result-anchor insertion (`documents/anchors.py`)

1. `POST .../anchors/insert {macro_name, target_path="main.tex", expected_version?, insert_at?}`. `macro_name` pattern `^[A-Za-z][A-Za-z]*$` (stored without backslash).
2. Validate the anchor via the experiments partition's `ResultAnchorService` (exact signature in Cross-partition requests). **Graceful degrade**: import inside `try/except ImportError` — if the module hasn't landed (parallel partition) or lookup raises, skip validation and use the conventional `anchors_file_path = "results/anchors.tex"`, flagging `"validated": false` in the response.
3. Ensure include: scan the target file for `\input{results/anchors}` (regex tolerant of an optional `.tex` suffix); if absent, insert the line immediately after `\begin{document}` (or prepend when absent) through `_write_file_versioned` with the caller's `expected_version` CAS (409 on staleness).
4. If `insert_at {line,col}` is provided (SHOULD), splice the usage snippet `\{macro_name}{}` into the target content at that position in the same versioned write; otherwise return the snippet for client-side cursor insertion.
5. Response: `{snippet: "\\ResBestAcc{}", include_added: bool, validated: bool, files: [{path, version}]}`.

### D9. Citation insertion (`documents/bibtex.py`)

1. `bib_key_for(paper) -> str`: first author's last whitespace-token (from `authors_json[0]`, NFKD-folded to ascii, lowercased, alnum only; fallback `"anon"`) + year (`published_at.year` or `"nd"`) + first title word ≥4 chars not in a small stopword set (fallback first word). E.g. `vaswani2017attention`. Collision with a *different* paper's existing entry → suffix `a`, `b`, ….
2. `bibtex_entry(paper, key) -> str`: `source == 'arxiv'` → `@misc{key, title={{...}}, author={A and B}, year={...}, eprint={external_id}, archivePrefix={arXiv}, url={...}}`; else `@article` with `journal={venue}`. Braces in fields escaped; deterministic field order (unit-testable string equality).
3. `GET .../citations` lists library papers (via `research.repository.PaperRepository.list_by_project` — import only) with computed `cite_key` and `in_bib` (key ∈ `parse_bib_keys(refs.bib)`), paginated.
4. `POST .../citations/insert {paper_id, bib_path="refs.bib", expected_bib_version?}`: create `refs.bib` if missing; if the key (for this paper) is absent, append the entry via `_write_file_versioned` (CAS on the bib file). Ensure a bibliography command: if the main file contains neither `\bibliography{` nor `\addbibresource{`, insert `\bibliographystyle{plain}` + `\bibliography{refs}` before `\end{document}` (force-save on main — SHOULD: CAS with separate `expected_main_version`). Return `{cite_key, snippet:"\\cite{key}", bib_file:{path,version}, entry_added, bibliography_command_added}`.

---

## API contract changes

All under `/projects/{project_id}/latex-projects/{latex_project_id}`; CSRF on non-GET; VIEWER for GETs, RESEARCHER for writes; non-membership 404 as everywhere.

1. **`PUT /files`** (changed) — request `{path, content, expected_version?: int}`.
   - 200: `DocumentFileResponse` (unchanged shape).
   - **409** `document_version_conflict`:
     ```json
     {"error": {"code": "document_version_conflict", "message": "Document changed since version 3.",
       "request_id": "…", "details": {
         "path": "main.tex", "expected_version": 3, "current_version": 5,
         "server_content": "…full current content…", "server_content_omitted": false,
         "base_available": true,
         "merge": {"clean": true, "merged_content": "…", "conflicts": []}}}}
     ```
     `server_content` omitted (flag true) when >512 KB. `merge.conflicts[]`: `{base_start, base_end, base_text, server_text, client_text}`; `merged_content` null when not clean. `merge` null when `base_available` false.
   - 422 `validation_error` for path traversal/absolute/backslash paths.

2. **`POST /selection-ops`** (new) — 202.
   Request: `{"op":"rewrite","path":"main.tex","range":{"start":{"line":12,"col":1},"end":{"line":14,"col":18}},"selection_text":"…","expected_version":5,"instruction":null}`
   Response: `{"agent_run_id":"…","stream":"/ws?project_id=…"}`
   Errors: 404 (project/file), 422 (`invalid_op`, empty selection for non-continue ops, selection >20 000 chars), 429 (agent run rate limit, from `create_run`).

3. **`GET /suggestions?status=proposed&path=main.tex&limit=50&offset=0`** (new) → `Page<SuggestionResponse>`.

4. **`GET /suggestions/{suggestion_id}`** (new) →
   ```json
   {"id":"…","path":"main.tex","op":"rewrite","status":"proposed","base_version":5,
    "range":{"start":{"line":12,"col":1},"end":{"line":14,"col":18}},
    "old_text":"…","new_text":"…","rationale":"…",
    "spans":[{"kind":"equal","old":"The ","new":"The "},{"kind":"replace","old":"results shows","new":"results show"}],
    "agent_run_id":"…","last_error":null,"created_at":"…","resolved_at":null}
   ```

5. **`POST /suggestions/{suggestion_id}/accept`** (new) — request `{"expected_version": 5}` (optional).
   - 200: `{"suggestion": …status accepted…, "file": {"path":"main.tex","content":"…","version":6}}`
   - 409 `suggestion_conflict` `{"details":{"reason":"anchor_not_found"|"ambiguous_anchor"}}` (status stays `proposed`); 409 `document_version_conflict` (same payload as PUT); 422 `suggestion_not_pending`.

6. **`POST /suggestions/{suggestion_id}/reject`** (new) → 200 suggestion (`rejected`). 422 if not `proposed`.

7. **`POST /compile`** (changed response) — `CompileJobResponse` gains `"diagnostics": [{"severity":"warning","code":"undefined_citation","message":"\\cite{foo2021} has no entry in refs.bib","file":"sections/intro.tex","line":12}]` and `"preview_model": {…D7 shape…}`. `status` may now be `"failed"` (structural errors), with `error_summary` set. `GET /compile-jobs/{id}` returns the same enriched shape.

8. **`POST /anchors/insert`** (new) — request/response per D8. Errors: 404 `anchor_not_found` (when validation ran and missed), 409 `document_version_conflict`, 422 bad macro name.

9. **`GET /citations?limit&offset`** (new) → `{"items":[{"paper_id":"…","title":"…","authors":["…"],"year":2017,"cite_key":"vaswani2017attention","in_bib":false}],"total":12,"limit":50,"offset":0}`.

10. **`POST /citations/insert`** (new) — per D9. Errors: 404 paper, 409 `document_version_conflict` on the bib CAS.

11. SHOULD — **`GET /files/history?path=&limit=20`** → `[{version, updated_by, created_at}]` and **`GET /files/revision?path=&version=`** → `DocumentFileResponse`-shaped content of that revision (404 if pruned).

## WS events

- Reused as-is: `agent.run.started|token|tool_call.*|completed|failed|cancelled` carry the selection-op stream; the run's `output_json.suggestion_id` is the join key (fetched via existing `GET /agents/runs/{run_id}`).
- SHOULD (first real producer of an already-contracted family): `latex.compile.completed` / `latex.compile.failed`, envelope `resource_type:"latex_compile"`, `resource_id:{job_id}`, payload `{"job_id":"…","status":"succeeded","engine":"mock","diagnostics_count":3,"error_summary":null}` — published from `DocumentService.compile` via `common.pubsub.publish_event`. Event strings already exist in `events.ts:42-46`; no contract change needed.
- STRETCH: `latex.suggestion.created` / `latex.suggestion.resolved` with `resource_type:"document_suggestion"` — requires contract additions (see Cross-partition).

## DB changes (for the migration consolidator — no alembic files authored here)

1. **New table `document_file_revisions`**: `id` UUID PK; `document_file_id` UUID FK → `document_files.id` ON DELETE CASCADE, indexed; `version` INTEGER NOT NULL; `content` TEXT NOT NULL; `updated_by` UUID NULL FK → `users.id` ON DELETE SET NULL; `created_at`/`updated_at` timestamptz (TimestampMixin). Constraint `UNIQUE(document_file_id, version)` (`uq_document_revision_file_version`). **Backfill**: `INSERT INTO document_file_revisions (id, document_file_id, version, content, updated_by, created_at, updated_at) SELECT gen_random_uuid(), id, version, content, updated_by, now(), now() FROM document_files;` (one revision per existing file at its current version).
2. **New table `document_suggestions`**: `id` UUID PK; `latex_project_id` FK → `latex_projects.id` CASCADE, indexed; `document_file_id` FK → `document_files.id` CASCADE, indexed; `agent_run_id` UUID NULL FK → `agent_runs.id` SET NULL, indexed; `op` native enum **`document_suggestion_op`** `('rewrite','expand','condense','fix_grammar','continue_writing','custom')`; `status` native enum **`document_suggestion_status`** `('proposed','accepted','rejected','superseded')` NOT NULL DEFAULT `'proposed'`; `base_version` INTEGER NOT NULL; `anchor_mode` VARCHAR(10) NOT NULL DEFAULT `'range'`; `range_json` JSONB NOT NULL (`{start,end,anchor_prefix,anchor_suffix,offset_start,offset_end}`); `old_text` TEXT NOT NULL DEFAULT `''`; `new_text` TEXT NOT NULL; `rationale` TEXT NOT NULL DEFAULT `''`; `spans_json` JSONB NOT NULL DEFAULT `'[]'`; `last_error` VARCHAR(50) NULL; `applied_version` INTEGER NULL; `created_by` FK → `users.id` RESTRICT; `resolved_by` UUID NULL FK SET NULL; `resolved_at` timestamptz NULL; timestamps. Composite index `(latex_project_id, status)`.
3. **`latex_compile_jobs`**: add `preview_model_json` JSONB NULL; add `diagnostics_json` JSONB NOT NULL DEFAULT `'[]'`. No backfill needed (old jobs keep NULL/[]).
4. Model registration: new models exported so `researchos/models.py` picks them up (documents models module already imported there via existing models — verify import list; if `models.py` enumerates classes, that one-line addition is a cross-partition request).

## shared-schemas additions (for the consolidator)

TypeScript types in `packages/shared-schemas/src/` (names exact):
- `type SelectionOp = 'rewrite'|'expand'|'condense'|'fix_grammar'|'continue_writing'|'custom'`
- `interface SuggestionSpan { kind: 'equal'|'delete'|'insert'|'replace'; old: string; new: string }`
- `interface DocumentSuggestion { id, path, op: SelectionOp, status: 'proposed'|'accepted'|'rejected'|'superseded', base_version: number, range: {start:{line,col}, end:{line,col}}, old_text, new_text, rationale, spans: SuggestionSpan[], agent_run_id: string|null, last_error: string|null, created_at, resolved_at: string|null }`
- `interface CompileDiagnostic { severity: 'error'|'warning'; code: string; message: string; file: string; line: number }`
- `interface DocumentVersionConflictDetails { path, expected_version, current_version, server_content?: string, server_content_omitted: boolean, base_available: boolean, merge: { clean: boolean, merged_content: string|null, conflicts: {base_start,base_end,base_text,server_text,client_text}[] } | null }`
- `CompileJobResponse` gains `diagnostics: CompileDiagnostic[]` and `preview_model: PreviewModel | null` (PreviewModel per D7).
- STRETCH only: event strings `latex.suggestion.created`, `latex.suggestion.resolved`; `ResourceType` += `'document_suggestion'` (mirror in `websocket/envelopes.py:15-22`).

## New dependencies

**None.** Everything uses stdlib (`difflib`, `re`, `unicodedata`) + existing SQLAlchemy/pydantic/httpx.

## File-by-file plan (owned partition)

| File | C/M | Change |
|---|---|---|
| `documents/enums.py` | M | Add `SuggestionOp`, `SuggestionStatus` StrEnums (~20 lines). |
| `documents/models.py` | M | Add `DocumentFileRevision`, `DocumentSuggestion`; add `preview_model_json`, `diagnostics_json` to `LatexCompileJob` (~80 lines). |
| `documents/schemas.py` | M | `SaveFileRequest.expected_version` + path field validator; `SelectionOpRequest`, `SuggestionResponse`, `AcceptSuggestionRequest`, `CitationItem`/`InsertCitationRequest`/`InsertCitationResponse`, `InsertAnchorRequest`/`InsertAnchorResponse`, `CompileJobResponse` diagnostics/preview_model, revision/history DTOs (~180 lines). |
| `documents/repository.py` | M | `DocumentRevisionRepository` (add/get_by_version/list_versions/prune), `SuggestionRepository` (add/get/list_by_project(status,path,paged)) (~90 lines). |
| `documents/service.py` | M | CAS `save_file` (+`_write_file_versioned` core, IntegrityError-safe create, 409 payload builder with merge hints); enriched `compile` (flatten+parse+diagnostics+status+optional WS publish); history/revision reads (~220 lines net). |
| `documents/merge.py` | C | `three_way_merge` diff3 (~130 lines). |
| `documents/latex_parse.py` | C | `flatten`, `parse_document` → preview model + diagnostics (~300 lines). |
| `documents/suggestions.py` | C | `compute_spans`, `prepare_op_context`, `SuggestionService` (create_from_run / accept with re-anchor / reject) (~220 lines). |
| `documents/bibtex.py` | C | `bib_key_for`, `bibtex_entry`, `parse_bib_keys`, `CitationService` (list/insert) (~170 lines). |
| `documents/anchors.py` | C | `AnchorInsertService` with ImportError-degrading experiments lookup (~90 lines). |
| `documents/router.py` | M | Endpoints 2-11 of the API section (~230 lines). |
| `agents/runtime/latex_agent.py` | M | Op prompt templates, dynamic `response_schema`, `SELECTION_OP_INPUT` message layout, finalize → spans + suggestion persistence via `SuggestionService` (mirrors `coding_agent.py`'s import of `PatchService`) (~170 lines). |
| `apps/api/tests/test_documents_*.py`, `test_latex_parse.py`, `test_merge.py`, `test_bibtex.py`, `test_suggestions.py` | C | See Test plan (tests live in the shared tests dir; if tests are partition-fenced, they ship inside this partition's PR anyway). |

Estimated ~1900 non-test lines + ~700 test lines; degrade path via MUST/SHOULD below.

## Cross-partition requests

1. **`apps/api/researchos/agents/llm/mock.py` (agents-core partition)** — extend the schema branch (after the existing `"files"` check, `mock.py:67-95`): when `response_schema.properties` contains `"replacement"`, locate the last user message line starting with `SELECTION_OP_INPUT: `, `json.loads` the remainder → `{op, selection, instruction}`, and emit `json.dumps({"replacement": _mock_op(op, selection, instruction), "rationale": f"Mock {op} suggestion (deterministic)."})` streamed in 24-char deltas. Exact `_mock_op` transforms (deterministic, offline):
   - `fix_grammar`: `re.sub(r'\s+',' ',selection).strip()`, first char uppercased, append `.` if no terminal punctuation.
   - `condense`: text up to and including the first `. ` (else first 15 whitespace-tokens + `.`).
   - `expand`: `selection + " Moreover, this observation holds under the additional settings considered."`
   - `rewrite`: `"This work shows that " + selection[:1].lower() + selection[1:]` (empty selection → the fixed sentence alone).
   - `continue_writing`: `"Building on the previous paragraph, we next describe the evaluation protocol."`
   - `custom`: `selection + " [addressed: " + (instruction or "")[:40] + "]"`.
   Missing/unparsable `SELECTION_OP_INPUT` line → fall back to `fix_grammar` over the whole last user message. (Hard constraint: mock must cover new agent modes.)
2. **Experiments-figures partition** — provide, importable as `from researchos.experiments.anchors import ResultAnchorService, ResultAnchorInfo`:
   ```python
   @dataclass
   class ResultAnchorInfo:
       macro_name: str              # without backslash, e.g. "ResBestAcc"
       anchors_file_path: str       # e.g. "results/anchors.tex" (path within the SAME latex project)
       formatted_value: str | None  # e.g. "92.41"
       experiment_id: uuid.UUID
       run_id: uuid.UUID | None

   class ResultAnchorService:
       def __init__(self, db: AsyncSession) -> None: ...
       async def get_anchor(self, project_id: uuid.UUID, latex_project_id: uuid.UUID,
                            macro_name: str) -> ResultAnchorInfo | None: ...
       async def list_anchors(self, project_id: uuid.UUID,
                              latex_project_id: uuid.UUID) -> list[ResultAnchorInfo]: ...
   ```
   Their regenerator must write the macros file at `anchors_file_path` **through `DocumentService.save_file`** (or `_write_file_versioned`) so anchor files are versioned like everything else.
3. **`packages/shared-schemas`** — type/event additions listed above (consolidator).
4. **`apps/api/researchos/models.py`** (if it enumerates model imports) — ensure `DocumentFileRevision`/`DocumentSuggestion` are imported; one line.
5. **`websocket/envelopes.py`** — STRETCH only: `ResourceType` += `'document_suggestion'`.
6. **Web paper-workspace partition (informational contract)** — must: send `expected_version` on every save; flush autosave before `POST /selection-ops`; render `spans` as decorations + accept/reject; on save-409 offer "merge" (use `merge.merged_content` when `clean`) or "review conflicts"; after accept, replace the buffer with the returned `file.content`/`version`.

## MUST / SHOULD / STRETCH breakdown

**MUST** (core, ~1500 lines): CAS save + 409 with `server_content`/`current_version` + revisions table & write path + path validation + IntegrityError-safe create; three-way merge hints (D5) in the 409; selection-ops endpoint + LatexAgent op templates/schema/finalize + `compute_spans` + suggestion persistence + accept (re-anchor)/reject endpoints; compile diagnostics + preview model + reachable FAILED; citations list + insert; anchors insert with ImportError degrade (snippet + include maintenance).
**SHOULD**: revision pruning (keep 50); history + revision endpoints; `latex.compile.completed|failed` WS publish; `insert_at` server-side splice for anchors; CAS (`expected_main_version`) on the bibliography-command insertion; suggestion `superseded` when a newer suggestion covers an overlapping range of the same file.
**STRETCH**: `latex.suggestion.*` events + `document_suggestion` resource type; `GET` diff between two revisions; biblatex (`\addbibresource`) preference detection; op-specific length guards on `replacement` (e.g. condense must be shorter) surfaced as suggestion warnings.

## Acceptance criteria (local gates + code review; runtime tests CI-deferred)

1. `ruff` + `mypy` clean over `apps/api` (new modules fully typed; no `Any` leaks in public signatures); `tsc`/`next build` unaffected (no web changes here).
2. Reading `documents/service.py`: `save_file` contains an `expected_version` comparison raising `ConflictError(code='document_version_conflict')` whose `details` include `current_version`, `server_content`, and a `merge` object; every content mutation path (suggestion accept, anchor include, citation insert) calls the shared `_write_file_versioned`, which inserts a `DocumentFileRevision` per write.
3. Reading `latex_agent.py`: per-op templates exist for all six ops; `response_schema` is set only when `context["op"]` present; finalize raises on schema-shaped-but-replacement-less output (no empty suggestion persisted as success) and creates a `DocumentSuggestion` with non-empty `spans_json` otherwise.
4. Reading `documents/latex_parse.py`: environment matching is stack-based; `\frac{a}{b}` survives block-text extraction intact (unit test asserts); the default `_DEFAULT_MAIN` template yields zero error-severity diagnostics (so existing seed/smoke flows still see SUCCEEDED).
5. Reading `documents/anchors.py`: the experiments import sits inside `try/except ImportError` and the endpoint still returns a valid snippet with `validated:false` offline.
6. `POST /selection-ops` never blocks on the LLM: the route handler only validates, captures context, and calls `AgentRunService.create_run` (202).
7. Suggestion accept conflicts return 409 while leaving `status='proposed'` (no dead-end state), verifiable by reading `suggestions.py`.
8. Mock-provider degradation: with the *unextended* mock, a selection-op run FAILS visibly (not silently empty); with the extended mock (cross-partition), the CI test asserts a deterministic `fix_grammar` suggestion round-trip.

## Test plan (authored now, run in CI — no external network anywhere)

- `test_latex_merge.py` (pure unit): identical edits, disjoint edits (clean merge content asserted), overlapping conflict (conflict record shape), one-side-only change, base==server, empty base.
- `test_latex_parse.py` (pure unit): flatten with `\input` + missing target + cycle; unclosed/mismatched env; undefined ref/cite; duplicate label; nested-brace text extraction; default template → no errors; preview-model section tree shape.
- `test_bibtex.py` (pure unit): key generation (unicode author fold, no year, stopword title), arXiv vs venue entry rendering (exact string equality), key parse, collision suffixing.
- `test_documents_versioning.py` (DB, CI): CAS happy path bumps version + revision row; stale save → 409 payload contract (details keys, merge.clean true/false paths); omitted expected_version force-saves; path traversal 422; concurrent-create IntegrityError path (monkeypatched flush) resolves to update; history/revision endpoints (SHOULD-gated with skipif).
- `test_document_suggestions.py` (DB, CI): `compute_spans` round-trip invariant + merge-adjacent behavior; full pipeline `AgentRuntime(db, llm=MockLLMProvider()).run(run_id)` for a `fix_grammar` op run (asserts suggestion row, spans, output_json.suggestion_id); accept at matching version; accept after an intervening edit elsewhere (text re-anchor succeeds); anchor_not_found and ambiguous_anchor 409s leaving status proposed; reject; unparsable-LLM-output fallback (`unstructured`); replacement-less JSON → run FAILED.
- `test_documents_citations.py` (DB, CI): citation list `in_bib` flags; insert creates refs.bib + bibliography command; second insert idempotent (`entry_added` false); CAS conflict on bib.
- `test_documents_anchors.py` (DB, CI): include inserted after `\begin{document}` exactly once (idempotent); monkeypatched ImportError → `validated:false` still 200; CAS staleness 409.
- `test_documents_compile.py` (DB, CI): compile persists diagnostics_json/preview_model_json; broken doc (unclosed env) → status FAILED + error_summary; default template SUCCEEDED; (SHOULD) compile publishes a `latex.compile.completed` envelope (capture via fake pubsub).

## Explicitly out of scope

- Real LaTeX compilation (latexmk/tectonic), PDF bytes, compile workers/queues — mock engine retained per PHASE3/5; the diagnostics/preview-model contract is designed so a real engine can later populate the same fields.
- All frontend work (Monaco decorations, tracked-changes UI, merge dialogs) — web partition.
- The macros/bindings regeneration service itself (`results/anchors.tex` content) — experiments-figures partition; we only consume its lookup signature and maintain the include.
- Workspace (FS) patches, git, collaborative/OT editing, document rename/delete endpoints, multi-user presence.
- Embedding-grounded writing (related-work weaver, WS4-4) and real-provider prompt-quality iteration.
