# Spec: frontend-paper — Overleaf-grade Writing & Experiment-Binding Frontend

Workstream: `frontend-paper` · Owner wishlist items: **7** (results flow into the paper, styled figures,
style settings) and **8** (write yourself OR AI floating assistant).
Realizes the frontend halves of INNOVATION_IDEAS **WS4-2** (floating selection assistant + tracked changes),
**WS4-3** (compile preview v2 + diagnostics), **WS3-1/WS3-3** (anchors + staleness UI), **WS3-4/WS3-6**
(figures + style presets + settings surface), and the save-safety fix for ARCHITECTURE_MAP §2#45/§4#16.

Owned partition:
- `apps/web/features/paper/**` (full rewrite + new components)
- `apps/web/features/system/**` (adds `PreferencesSection.tsx`; `SystemStatus.tsx` untouched)
- `apps/web/features/experiments/` — ONLY: `RunDetail.tsx` (modified), `CreateAnchorDialog.tsx` (new),
  `CreateFigureDialog.tsx` (new). `ExperimentsDashboard.tsx`, `MetricsChart.tsx`, `AnalysisPanel.tsx` untouched.
- `apps/web/lib/api/documents.ts`, `apps/web/lib/api/anchors.ts`, `apps/web/lib/api/figures.ts`,
  `apps/web/lib/api/preferences.ts` (all new)

---

## Objective (user-visible outcome)

1. **Floating AI assistant**: select text in the LaTeX Monaco editor → floating toolbar
   (Rewrite / Expand / Condense / Fix grammar / Continue / custom instruction) → the AI's suggestion renders
   as a **tracked change** (original struck through, replacement inline with word-level diff highlighting,
   rationale line, Accept / Reject per suggestion). Accepting applies through the writing spec's ops API so
   the server-side version chain stays intact. A docked assistant chat handles whole-document requests.
2. **Save safety**: saves carry `expected_version` (compare-and-swap). A concurrent edit produces a 409 →
   merge dialog with a Monaco diff (server vs mine) and explicit resolution. Dirty state is guarded
   (`beforeunload`), and a localStorage draft autosaves every 2 s so a crash never loses more than 2 s of work.
3. **Anchors & Figures panel**: browse the project's result anchors (`\ResBestAcc` macros) with live values
   and staleness badges, insert at cursor; browse figures with thumbnails, regenerate in any style preset,
   insert `\includegraphics` blocks. A banner warns when the open document references stale anchors, with
   one-click "Update all".
4. **Compile preview v2**: structural preview (headings/paragraphs/math/figures) instead of a `<pre>` dump,
   plus a Diagnostics tab; clicking a diagnostic jumps the editor to that line; diagnostics also render as
   Monaco markers (squiggles).
5. **Citation insert**: pick a paper from the project library / refs.bib and insert `\cite{key}`,
   adding the BibTeX entry when missing.
6. **Settings → Preferences**: theme (light/dark/system), default figure style preset with visual
   thumbnails, language — persisted via the preferences API.
7. **Experiments dashboard**: "Create anchor from this metric" and "Make figure from this run" entry points
   on the run detail page, closing the loop from run → paper.

Everything works with the deterministic mock LLM provider and with all external services offline.

---

## Current state (concrete, file:line)

- `apps/web/features/paper/PaperWorkspace.tsx:19` — uses `projects.data?.[0]` only; `:21` hardcodes
  `'main.tex'`; `:52` mounts Monaco with `language="plaintext"`; `:22` — `useEffect` re-sets `content` from
  `file.data` on every refetch, **clobbering unsaved local edits**; `:24` — save has no version handling
  (last-write-wins, matching backend `documents/service.py:124-152` which bumps `version` without any
  expected-version check); no dirty guard, no autosave, no draft.
- `apps/web/features/paper/PaperAssistant.tsx:22` — creates a latex agent run via the type-cast hack
  `agent_type: 'latex' as 'research'`; output renders into a `<pre>` (`:36`) and can never touch the editor;
  no history (only the single in-memory `runId`), no selection actions, no tracked changes.
- `apps/web/features/paper/PreviewPanel.tsx:31-35` — renders `job.preview` (the mock compiler's pseudo-
  Markdown string from `documents/service.py:47-62`) as a `<pre>`; no structure, no diagnostics, no editor
  integration. `CompileJob` type (`lib/api/paper.ts:25-35`) has only `log/preview/error_summary`.
- `apps/web/lib/api/paper.ts` — thin fetch wrappers; `saveFile` (`:46-47`) sends `{path, content}` only.
  Consumed exclusively by the two files above (verified by grep).
- `apps/web/features/experiments/RunDetail.tsx` — metrics/logs/artifacts/analysis cards; **zero** paper
  linkage; no per-metric actions. `MetricsChart.tsx:21` hardcodes colors (style presets don't reach it —
  out of scope here, WS7/WS3 backend concern).
- `apps/web/app/(workspace)/projects/[projectId]/settings/page.tsx:56-63` — Language card + LLM config card
  only; no theme, no figure style, no preferences API (none exists yet).
- `apps/web/features/system/SystemStatus.tsx` — readiness panel; untouched by this spec.
- WS contract: `packages/shared-schemas/src/events.ts:41-47` declares `latex.compile.*` with **no producers**
  and no payload types; no staleness/figure event families exist.
- `apps/web/lib/websocket/useProjectAgentEvents.ts:39` filters to `resource_type === 'agent_run'` only.
- i18n: `lib/i18n/index.tsx` — flat `DictKey` dictionaries; adding keys requires editing
  `lib/i18n/dictionaries/*` which this partition does not own (see Design step 0 for the workaround).
- `apps/web/package.json` — `@monaco-editor/react@^4.6.0`; no direct `monaco-editor` dependency (needed as a
  types-only devDependency for content widgets / view zones / markers).

### Relation to prior decisions
- **P3-D4 (whole-file patches, display-only hunks) is NOT superseded.** The workspace patch pipeline is
  untouched. Paper tracked changes are a *different* mechanism: interactive, user-mediated edits to
  `DocumentFile` rows where review happens inline *before* application, so routing them through
  `patch_proposals` would add indirection with no safety benefit. They apply through the documents ops API
  (cross-partition, backend-writing spec).
- **The documents last-write-wins behavior (ARCHITECTURE_MAP §2#45) is superseded** by version CAS. This
  frontend sends `expected_version` and handles 409; the server-side enforcement is a cross-partition
  request to the backend-writing spec.
- **P3-D13 (Monaco via CDN loader, `ssr:false`) is retained**; `monaco-editor` is added only for TypeScript
  types, never imported at runtime (`import type` only).

---

## Design (algorithms & data flow)

### 0. Local i18n module (unblocks everything else)

`DictKey` is a closed union derived from `dictionaries/zh-CN.ts`, which this partition cannot edit. To keep
tsc green without a cross-partition dependency, all new strings live in a **local, typed dictionary**:

1. `features/paper/i18n.ts` exports `PAPER_DICT: Record<'zh-CN'|'en-US', Record<PaperKey, string>>` and
   `usePaperT(): (k: PaperKey) => string` which reads `useI18n().locale`. Same pattern, zero central edits.
2. `features/experiments/CreateAnchorDialog.tsx` / `CreateFigureDialog.tsx` and
   `features/system/PreferencesSection.tsx` import from the same module (cross-feature import inside the
   owned partition). The full key list is in the i18n section below; folding them into the central
   dictionaries later is an optional cross-partition request (non-blocking).

### A. Save safety (CAS + dirty guard + draft)

Editor buffer state lives in `PaperWorkspace` (not zustand — single consumer):
`{ content: string, savedVersion: number, savedContent: string }`; `dirty = content !== savedContent`.

1. **Load**: `getFile` → set all three; **the refetch-clobber bug is fixed** by only syncing
   `content` from a refetch when `!dirty` (and updating `savedVersion/savedContent` always).
2. **Save** (button / Ctrl+S via `editor.addCommand(KeyMod.CtrlCmd | KeyCode.KeyS)`):
   `saveFile(pid, lid, { path, content, expected_version: savedVersion })`.
   - 200 → update `savedVersion/savedContent`, clear draft, flash "Saved · v{n}".
   - 409 `version_conflict` → open **MergeDialog**: header "This file changed on the server (v{mine} → v{server})";
     body = `MonacoDiff` original=`details.server_content`, modified=local buffer; actions:
     (a) **Keep mine** → re-`saveFile` with `expected_version = details.current_version`;
     (b) **Take server** → replace buffer + versions with server content (local text preserved in the draft
     slot under key suffix `:conflict-backup` for manual recovery);
     (c) **Cancel** → close, stay dirty. No automatic 3-way merge (out of scope).
3. **Draft autosave**: `features/paper/draft.ts` — `writeDraft(lid, path, {baseVersion, content, savedAt})`
   to localStorage key `ros-paper-draft:{lid}:{path}`, debounced 2 s while dirty; `clearDraft` on successful
   save. On mount after load: if a draft exists and `draft.content !== file.content`, render a restore bar
   above the editor ("Unsaved draft from {relative time} — Restore / Discard"); if
   `draft.baseVersion !== file.version` the bar carries a "server has newer changes" warning; Restore loads
   the draft into the buffer (dirty), Discard clears it.
4. **Dirty guard**: `beforeunload` listener registered while dirty (App Router exposes no client-side
   route-change event; the header shows a persistent amber "Unsaved" dot as the in-app affordance — this
   limitation is documented in code).

### B. Floating selection assistant + tracked changes

Components: `SelectionToolbar.tsx` (Monaco content widget), `suggestionStore.ts` (zustand),
`TrackedChanges.tsx` (decorations + view zones), `wordDiff.ts` (pure util).

1. **Toolbar**: on `onDidChangeCursorSelection`, a debounced (150 ms) handler shows a content widget
   anchored above the selection start. Non-empty selection → buttons `Rewrite · Expand · Condense · Fix ·
   More…` (More opens a one-line custom-instruction input, SHOULD). Empty selection → single `Continue`
   button at the cursor. Widget hides on scroll-away/blur/Escape.
2. **Request**: `createAgentRun(projectId, { agent_type: 'latex', message: JSON.stringify(payload) })` where
   `payload = { action: 'rewrite'|'expand'|'condense'|'fix'|'continue'|'custom', instruction?: string,
   selection_text, before_context /* prev ≤40 lines */, after_context /* next ≤20 lines */,
   file: path, range: {start_line, start_col, end_line, end_col}, latex_project_id }` (1-based, Monaco
   convention). Until the shared `AgentType` union gains `'latex'` (cross-partition), the existing
   `'latex' as 'research'` cast is kept behind a single `createLatexRun()` helper in `documents.ts`.
3. **Streaming**: the run is tracked via the existing `useProjectAgentEvents`; while running, the toolbar
   position shows a pulsing "AI…" chip. On `agent.run.completed`, parse `output` as JSON
   `{replacement, rationale}` (fallback: treat the whole text as `replacement`, empty rationale — keeps the
   mock/any provider working).
4. **Suggestion record** (zustand `suggestionStore.ts`):
   `EditSuggestion = { id, path, range, original, replacement, rationale, agentRunId,
   status: 'proposed'|'accepted'|'rejected'|'invalidated' }`. Store API: `add`, `resolve(id, status)`,
   `shiftAfter(range, lineDelta)`, `invalidateOverlapping(range)`, `clearForFile(path)`.
5. **Rendering** (`TrackedChanges.tsx`, given the editor instance): per proposed suggestion —
   `deltaDecorations` with class `ros-strike` (red strikethrough + faint red bg) over `range`
   (skip when `original === ''`, i.e. Continue), plus an `IViewZone` under `range.end_line` containing a
   React-rendered card (via `ReactDOM.createRoot` into the zone's DOM node): word-level diff of
   original→replacement (deleted words struck red, inserted words green — `wordDiff.ts`), the rationale
   line, and `Accept / Reject` buttons. Zone height = measured card height.
6. **`wordDiff(a, b)`**: tokenize on `/(\s+)/` keeping separators; LCS via DP capped at 400×400 tokens
   (beyond the cap, return one whole-block delete+insert pair); output
   `[{kind:'same'|'del'|'ins', text}]`. Pure, unit-testable.
7. **Accept** — two branches, deterministic:
   - buffer clean (`!dirty`): `applyOps(pid, lid, { path, expected_version: savedVersion, ops: [
     {kind:'replace_range', ...range, text: replacement}] })` → on 200 set
     `content/savedVersion/savedContent` from the returned file (server is authoritative); on 409 open the
     same MergeDialog as saves.
   - buffer dirty: `editor.executeEdits('ros-ai', [{range, text: replacement}])` (stays dirty; the normal
     CAS save persists it).
   Then: `resolve(id,'accepted')`; `shiftAfter(range, lineDelta)` where
   `lineDelta = lineCount(replacement) - lineCount(original)`; suggestions overlapping the edited range are
   `invalidated` (their decorations removed, card greyed with "outdated").
8. **Reject**: remove decorations/zone, `resolve(id,'rejected')`. **Continue** inserts render as pure
   insertion cards (green only) at the cursor; accept path identical with `original=''`.
9. **Docked assistant chat** (`AssistantDock.tsx`, replaces `PaperAssistant.tsx`): textarea + history.
   History = `listAgentRuns(projectId)` filtered client-side to latex runs whose
   `input_json.message` parses to `{latex_project_id === lid}`; live runs via `useProjectAgentEvents`.
   Whole-document requests send `{action:'document', instruction, document_text: first 400 lines}`.
   Responses render as markdown-ish text; fenced ```latex blocks get an "Insert at cursor" button
   (`executeEdits` at cursor). No tracked changes for whole-doc answers (bounded scope).

### C. Anchors panel + staleness banner

1. `AnchorsPanel.tsx` (right-rail tab): `useQuery(['anchors', lid], listResultBindings)` — rows:
   `\{macro_name}` (mono), formatted `last_value`, experiment/run chip (`run pinned` vs `latest`), amber
   `stale` badge when `stale`. Row actions: **Insert** (`executeEdits` inserts `\{macro_name}` at cursor +
   focus), **Delete** (confirm → `DELETE`), header actions: **Refresh values** (`POST .../regenerate`) and
   **Update all** (visible when any stale → `POST .../rebind-latest` then invalidate
   `['anchors']`,`['staleness']` and suggest recompile via a toast row in the panel).
2. **Staleness banner + gutter**: `useQuery(['staleness', lid], getStaleness, {refetchInterval: ws-fallback})`.
   Scan algorithm (memoized on `[content, staleMacroNames]`): build
   `new RegExp('\\\\(' + names.map(escapeRe).join('|') + ')\\b', 'g')`, run per line over the buffer →
   `[{line, macro}]`; apply gutter decorations (`ros-stale-gutter`, amber dot + hover message
   "{macro}: bound run {short} superseded by {short} ({delta_pct}%)"); when matches > 0 render a banner
   between toolbar and editor: "N stale result anchor(s) referenced — **Update all**". Empty stale set →
   nothing renders (zero-cost when unused).
3. Live refresh: `usePaperEvents` (D below) invalidates `['anchors']`/`['staleness']` on
   `paper.staleness.changed`; a 30 s `refetchInterval` on the staleness query is the WS-outage fallback.

### D. Figures panel + `usePaperEvents`

1. `FiguresPanel.tsx` (right-rail tab): cards per figure — thumbnail
   `<img src={assetUrl(pid, lid, f.thumbnail_path)}>` (plain `<img>` with `onError` placeholder box; the
   asset endpoint is cookie-authed same-origin-credentialed via `crossOrigin` not needed — plain GET with
   `credentials` handled by `<img>` only if same site; to be safe the URL is fetched via `apiRequest` →
   blob → `URL.createObjectURL`, cached in a `useAssetBlob(path)` hook), name, style preset chip, stale
   badge, `last_rendered_at`.
   Card actions: **style preset `<select>`** (options from `listFigureStyles()`, default value =
   `figure.style_slug`) + **Regenerate** (`POST /figures/{id}/render {style_slug}` → optimistic "rendering…"
   state until `figure.rendered` arrives or a 5 s poll refetch), **Insert** → `executeEdits` at cursor:
   ```
   % researchos:figure {figure.id}
   \begin{figure}[t]
     \centering
     \includegraphics[width=\linewidth]{{asset_path minus extension}}
     \caption{TODO: caption for {figure.name}}
     \label{fig:{slugified name}}
   \end{figure}
   ```
2. `usePaperEvents.ts` (features/paper): thin wrapper over `connectProjectEvents` (import-only from
   `lib/websocket/client.ts`) that dispatches `latex.compile.*`, `paper.staleness.changed`, and
   `figure.rendered` envelopes to handler callbacks; unknown/absent events are ignored so the UI works
   before the backend event producers land (polling fallbacks carry the feature).

### E. Compile preview v2 + diagnostics

1. `useCompileJob.ts`: `compile()` → if the returned job is terminal (mock engine returns SUCCEEDED
   synchronously today) use it directly; else (future async engine) subscribe via `usePaperEvents` for
   `latex.compile.completed|failed` on that job id and poll `GET /compile-jobs/{id}` every 2 s (max 60 s)
   as fallback. Exposes `{job, isCompiling, compile}`.
2. `PreviewPanel.tsx` rewrite — tabs **Preview | Diagnostics(n)**:
   - Preview renders `job.preview_model.blocks`: `heading` → `h1-h3` by `level`; `paragraph` → `<p>`;
     `math` → centered `<pre class="math">`; `figure` → thumbnail via `useAssetBlob` + caption; `list` →
     `<ul>`; unknown kinds → paragraph fallback. When `preview_model` is absent (older jobs), fall back to
     the legacy `<pre>{job.preview}</pre>`. Each block is clickable → `onJumpToLine(block.source_line)`.
   - Diagnostics tab: rows `severity icon · file:line · message`, errors first; row click →
     `onJumpToLine(line)` when `diag.file === openPath` (single-file v1).
3. **Editor markers**: `PaperWorkspace` effect on `job.diagnostics`: map diagnostics for the open path to
   `monaco.editor.setModelMarkers(model, 'latex-compile', [{startLineNumber: line, ...,
   severity: Error|Warning, message}])`; cleared on successful next compile.
4. `onJumpToLine(line)`: `editor.revealLineInCenter(line)` + `setPosition({lineNumber: line, column: 1})` +
   `focus()` — passed down from `PaperWorkspace`, which owns the editor ref (captured in `onMount`).

### F. Citation insert (SHOULD)

`CitePicker.tsx` (right-rail tab or toolbar popover): `useQuery(['bib', lid], getBibliography)`; text filter
over key/title/authors; row click → insert `\cite{key}` at cursor. Rows with `in_bib === false` (library
paper not yet in refs.bib) show **Add & cite** → `POST .../bibliography/entries {paper_id}` → insert
returned key, invalidate `['bib', lid]`.

### G. Preferences section + theme/language wiring

`features/system/PreferencesSection.tsx`, rendered by the settings page (one-line cross-partition request):

1. `useQuery(['preferences'], getMyPreferences)`; mutations `PUT /users/me/preferences` (partial body),
   optimistic update.
2. **Theme**: three radio tiles (Light/Dark/System, mini preview swatches). On change: PUT `{theme}`, AND
   apply locally — `localStorage.setItem('ros-theme', v)` +
   `document.documentElement.dataset.theme = resolved` — so the WS7 ThemeProvider (separate partition)
   picks it up when it lands; before WS7 lands the attribute is inert (harmless).
3. **Default figure style**: gallery of preset tiles from `listFigureStyles()`; each tile renders
   `FigureStyleThumb` (`features/paper/stylePreview.tsx`) — a deterministic inline **SVG** mini line-chart
   (2 series, 12 fixed points) drawn from the preset's `style` object (`palette`, `grid`, `font_family`,
   `legend_frame`) — no server rendering, works fully offline. Selected tile → PUT
   `{default_figure_style: slug}`. `FiguresPanel` and `CreateFigureDialog` read this preference as their
   default style.
4. **Language**: renders the existing `<LanguageSwitcher/>` (import-only) and an effect that PUTs
   `{language: locale}` when the locale changes (debounced 500 ms) so the preference follows the switcher.

### H. Experiments entry points

1. `RunDetail.tsx` (modified, ~+25 lines): Metrics card header gains two small buttons —
   **Create anchor** and **Make figure** — opening the dialogs; metric names for the pickers come from the
   already-fetched `['metrics', projectId, runId]` query (`listMetrics`, names deduped client-side).
2. `CreateAnchorDialog.tsx` (new): fields — target paper (`listLatexProjects`, auto-selected when exactly
   one), macro name (`Res` + PascalCase(metric) suggested; validated `^[A-Za-z]+$` with inline error),
   metric (select), aggregation (`final|best|min|max|mean`), format (`{:.2f}` default), bind mode radio
   (**Track latest run** → `run_id: null` / **Pin this run** → `run_id`). Submit →
   `createResultBinding` → success state shows `\{macro}` with an **Open paper** link
   (`/projects/{pid}/paper`); 409 `macro_name_taken` renders inline.
3. `CreateFigureDialog.tsx` (new): name (slugified, unique-per-project hint), metric multi-select
   (checkboxes), kind (`line` fixed v1), style preset select (default from preferences, thumbnails via
   `FigureStyleThumb`), submit → `createFigure` with
   `spec = {kind:'line', series: metrics.map(m => ({run_id, metric_name: m, label: m})), x:'step'}` →
   success links to the paper's Figures tab.
4. Both dialogs use `features/paper/Modal.tsx` (new, ~50 lines): portal, `role="dialog"` +
   `aria-modal`, Escape/backdrop close, initial-focus — reused by MergeDialog too.

---

## API contract changes

This partition ships **no backend code** — every route below is a consumption contract; implementation is
routed via Cross-partition requests to the named sibling spec. Shapes here are normative for the frontend.

### Documents (backend-writing spec)

`PUT /projects/{pid}/latex-projects/{lid}/files` — CAS save (change: adds `expected_version`)
```json
{ "path": "main.tex", "content": "\\documentclass...", "expected_version": 4 }
```
200 → `{ "id": "…", "path": "main.tex", "content": "…", "version": 5, "updated_at": "…" }`
409 → standard envelope with `"code": "version_conflict"`,
`"details": { "current_version": 6, "server_content": "…" }`.
`expected_version` omitted/null → legacy upsert (create path for new files).

`POST /projects/{pid}/latex-projects/{lid}/files/ops` — range ops (new)
```json
{ "path": "main.tex", "expected_version": 5, "ops": [
  { "kind": "replace_range", "start_line": 12, "start_col": 1, "end_line": 14, "end_col": 18, "text": "revised" },
  { "kind": "insert_at", "line": 30, "col": 1, "text": "\\ResBestAcc" } ] }
```
Positions 1-based (Monaco convention); server applies ops bottom-to-top.
200 → `{ "file": <DocFile>, "applied": 2 }` · 409 `version_conflict` (same details shape) ·
422 `op_out_of_range` with `details: { "op_index": 0, "reason": "end_line 999 > 120" }`.

`POST /projects/{pid}/latex-projects/{lid}/compile` and `GET .../compile-jobs/{job_id}` — response gains:
```json
{ "id": "…", "status": "succeeded", "engine": "mock", "log": "…", "preview": "legacy text",
  "preview_model": { "blocks": [
    { "kind": "heading", "level": 1, "text": "Introduction", "source_line": 7 },
    { "kind": "paragraph", "text": "…", "source_line": 9 },
    { "kind": "math", "text": "E = mc^2", "source_line": 12 },
    { "kind": "figure", "name": "figures/loss-curve", "caption": "…", "source_line": 20,
      "asset_path": "figures/loss-curve.png" },
    { "kind": "list", "items": ["a", "b"], "source_line": 25 } ] },
  "diagnostics": [
    { "file": "main.tex", "line": 33, "severity": "error", "message": "Undefined control sequence \\Foo" },
    { "file": "main.tex", "line": 40, "severity": "warning", "message": "stale anchor \\ResBestAcc: run 47 is newer" } ],
  "error_summary": null, "created_at": "…", "finished_at": "…" }
```
Both `preview_model` and `diagnostics` nullable — the frontend degrades to the legacy `<pre>` view.

`GET /projects/{pid}/latex-projects/{lid}/bibliography` (new) →
`{ "entries": [ { "key": "vaswani2017attention", "title": "…", "authors": "Vaswani et al.", "year": 2017,
"source": "library|bib", "paper_id": "uuid|null", "in_bib": true } ] }`
`POST .../bibliography/entries` `{ "paper_id": "uuid" }` → 201 `{ "key": "…", "bib_file_version": 3 }`
(409 `already_in_bib` treated as success-with-key).

### Anchors (backend experiment-binding spec, WS3-1/WS3-3)

`GET /projects/{pid}/latex-projects/{lid}/result-bindings` →
`{ "items": [ { "id": "…", "macro_name": "ResBestAcc", "experiment_id": "…", "experiment_name": "lr sweep",
"run_id": null, "metric_name": "accuracy", "aggregation": "best", "format_spec": "{:.2f}", "scale": 1.0,
"last_value": 92.41, "last_run_id": "…", "stale": false, "updated_at": "…" } ] }`

`POST` same path
`{ "macro_name": "ResBestAcc", "experiment_id": "…", "run_id": null, "metric_name": "accuracy",
"aggregation": "best", "format_spec": "{:.2f}", "scale": 1.0 }` → 201 binding ·
409 `macro_name_taken` · 422 `invalid_macro_name`.

`DELETE /projects/{pid}/latex-projects/{lid}/result-bindings/{binding_id}` → 204.
`POST .../result-bindings/regenerate` `{}` → `{ "regenerated": 4, "anchors_file_version": 7 }`.
`POST .../result-bindings/rebind-latest` `{ "binding_ids": null }` (null = all stale) → same shape.
`GET /projects/{pid}/latex-projects/{lid}/staleness` →
`{ "items": [ { "binding_id": "…", "macro_name": "ResBestAcc", "bound_run_id": "…", "latest_run_id": "…",
"bound_value": 91.1, "latest_value": 92.4, "delta_pct": 1.4 } ],
"figures": [ { "figure_id": "…", "name": "loss-curve", "reason": "newer_run" } ] }`

### Figures (backend experiment-binding spec, WS3-4/WS3-6)

`GET /projects/{pid}/latex-projects/{lid}/figures` →
`{ "items": [ { "id": "…", "name": "loss-curve", "spec_json": { "kind": "line", "series": [
{ "run_id": "…", "metric_name": "loss", "label": "loss" } ], "x": "step" },
"asset_path": "figures/loss-curve.pdf", "thumbnail_path": "figures/loss-curve.png",
"style_slug": "neurips-clean", "stale": false, "last_rendered_at": "…" } ] }`
`POST` same path `{ "name": "loss-curve", "spec": {…}, "style_slug": "neurips-clean" }` → 201 figure
(render async). `POST /figures/{figure_id}/render` `{ "style_slug": "ieee-mono" }` (null keeps current) →
202 `{ "figure_id": "…", "status": "queued" }`.
`GET /projects/{pid}/latex-projects/{lid}/assets/{path}` → raw bytes (`image/png` / `application/pdf`),
cookie-authed; fetched client-side into blob URLs.

### Preferences (backend platform spec)

`GET /users/me/preferences` →
`{ "theme": "system", "language": "zh-CN", "default_figure_style": "neurips-clean" }`
`PUT /users/me/preferences` — partial body, e.g. `{ "theme": "dark" }` → full updated object.
`GET /figure-styles` →
`{ "items": [ { "slug": "neurips-clean", "name": "NeurIPS Clean", "description": "…",
"style": { "palette": ["#4C72B0", "#DD8452", "#55A868", "#C44E52"], "font_family": "serif",
"grid": true, "legend_frame": false } } ] }` — `style` fields drive the client-side SVG thumbnails.

### Error cases (all routes)
Standard envelope `{"error":{code,message,request_id,details?}}`; 404 for non-membership (never 403);
CSRF header on non-GET via the existing `apiRequest`. Frontend-specific handling: 409 `version_conflict`
→ MergeDialog; 409 `macro_name_taken` / 422 `invalid_macro_name` → inline field errors; any 404 on
anchors/figures/preferences routes (backend spec not yet landed) → panel renders its empty/unavailable
state, never crashes (query `retry: false` + error boundary text).

## WS events (consumed; producers cross-partition)

- `latex.compile.started` — resource_type `latex_compile`, resource_id = job id, payload `{}`.
- `latex.compile.completed` — payload `{ "status": "succeeded", "diagnostics_count": 2 }` → refetch job.
- `latex.compile.failed` — payload `{ "status": "failed", "error_summary": "…" }`.
- `paper.staleness.changed` (NEW) — resource_type `latex_project`, resource_id = latex_project_id, payload
  `{ "latex_project_id": "…", "stale_binding_ids": ["…"], "stale_figure_ids": ["…"] }` → invalidate
  `['anchors']`, `['staleness']`, `['figures']`.
- `figure.rendered` (NEW) — resource_type `figure`, resource_id = figure_id, payload
  `{ "figure_id": "…", "status": "succeeded", "asset_path": "figures/x.pdf",
  "thumbnail_path": "figures/x.png" }` → invalidate `['figures']`, drop cached blob for that path.
- Existing `agent.run.*` unchanged (assistant streaming).
All handlers are optional-tolerant: the UI is fully functional on polling fallbacks alone.

## DB changes

**None** in this partition. Consumed tables (`result_bindings`, `figure_bindings`/`document_assets`,
`user_preferences`, `document_files.version` CAS semantics) are defined by the backend-writing,
experiment-binding, and platform specs; this spec adds no DDL.

## shared-schemas additions (routed to consolidation agent)

In `packages/shared-schemas/src/events.ts`:
1. New group `export const PAPER_EVENTS = ['paper.staleness.changed', 'figure.rendered'] as const;` folded
   into `EVENT_TYPES`.
2. `ResourceType` union += `'latex_project' | 'figure'`.
3. Payload interfaces + map entries: `LatexCompileCompletedPayload { status: 'succeeded'|'failed';
   diagnostics_count?: number }`, `LatexCompileFailedPayload { status: 'failed'; error_summary?: string }`,
   `PaperStalenessChangedPayload { latex_project_id: string; stale_binding_ids: string[];
   stale_figure_ids: string[] }`, `FigureRenderedPayload { figure_id: string;
   status: 'succeeded'|'failed'; asset_path?: string; thumbnail_path?: string }`.
4. `AgentType` union += `'latex'` (also mirrored in `apps/web/lib/api/agents.ts`, see Cross-partition).
Until these land, the frontend types WS payloads locally in `usePaperEvents.ts` (string event names,
`Record<string, unknown>` narrowing) so tsc never depends on the consolidation timing.

## New dependencies

- `apps/web/package.json` devDependencies: **`monaco-editor@^0.52.0`** — types only
  (`import type { editor, IRange } from 'monaco-editor'` etc. for content widgets, view zones, decorations,
  markers). Runtime still loads Monaco via the existing CDN loader (P3-D13 unchanged); no bundle impact
  (`next build` treeshakes type-only imports by definition).
- No new runtime JS deps (word diff, SVG thumbnails, modal are hand-rolled). No Python deps.

## File-by-file plan (≈2,350 changed/added lines total)

| File | Action | Contents | ≈LOC |
|---|---|---|---|
| `lib/api/documents.ts` | **create** | LatexProject/DocFile/CompileJob-v2/PreviewBlock/Diagnostic types; `listLatexProjects`, `createLatexProject`, `listFiles`, `getFile`, `saveFile` (CAS, throws `ApiError` — helper `isVersionConflict(e)` narrows `details`), `applyOps`, `compile`, `getCompileJob`, `getBibliography`, `addBibEntry`, `createLatexRun` (agent-type cast isolated here), `assetUrl` | 170 |
| `lib/api/anchors.ts` | **create** | `ResultBinding`/`StalenessReport` types; list/create/delete/regenerate/rebindLatest/getStaleness | 75 |
| `lib/api/figures.ts` | **create** | `PaperFigure`/`FigureSpec` types; list/create/render | 60 |
| `lib/api/preferences.ts` | **create** | `UserPreferences`/`FigureStyle` types; `getMyPreferences`, `updateMyPreferences`, `listFigureStyles` | 55 |
| `features/paper/PaperWorkspace.tsx` | **rewrite** | layout (assistant dock left, editor center, tabbed right rail), buffer/CAS state (Design A), editor `onMount` ref capture, Ctrl+S, draft restore bar, staleness banner + gutter (C.2), markers effect (E.3), `onJumpToLine`, mounts all child components | 300 |
| `features/paper/AssistantDock.tsx` | **create** (replaces `PaperAssistant.tsx`, deleted) | docked chat, history filter, whole-doc requests, insert-block button | 160 |
| `features/paper/PreviewPanel.tsx` | **rewrite** | Preview/Diagnostics tabs, block renderer, legacy fallback, jump-to-line | 190 |
| `features/paper/SelectionToolbar.tsx` | **create** | Monaco content widget lifecycle + action buttons + custom-instruction input | 140 |
| `features/paper/TrackedChanges.tsx` | **create** | decorations + view zones + suggestion cards, accept/reject wiring | 190 |
| `features/paper/suggestionStore.ts` | **create** | zustand store, `shiftAfter`, `invalidateOverlapping` | 90 |
| `features/paper/wordDiff.ts` | **create** | tokenizer + capped LCS + segments | 65 |
| `features/paper/MergeDialog.tsx` | **create** | MonacoDiff, keep-mine/take-server/cancel, conflict-backup draft write | 110 |
| `features/paper/AnchorsPanel.tsx` | **create** | binding list, insert/delete/refresh/update-all | 140 |
| `features/paper/FiguresPanel.tsx` | **create** | figure cards, style select, regenerate, insert block, `useAssetBlob` | 170 |
| `features/paper/CitePicker.tsx` | **create** (SHOULD) | bib list + filter + insert + add-and-cite | 110 |
| `features/paper/latexLanguage.ts` | **create** (SHOULD) | Monarch LaTeX tokenizer + language config, registered in editor `beforeMount` (idempotent guard) | 90 |
| `features/paper/usePaperEvents.ts` | **create** | WS wrapper with tolerant event dispatch | 70 |
| `features/paper/useCompileJob.ts` | **create** | compile + async-job await + poll fallback | 70 |
| `features/paper/stylePreview.tsx` | **create** | `FigureStyleThumb` deterministic SVG mini-chart | 80 |
| `features/paper/draft.ts` | **create** | localStorage draft read/write/clear | 45 |
| `features/paper/Modal.tsx` | **create** | portal dialog (a11y basics), reused by all dialogs | 55 |
| `features/paper/i18n.ts` | **create** | `PaperKey` union + zh-CN/en-US dicts + `usePaperT` | 130 |
| `features/paper/PaperAssistant.tsx` | **delete** | superseded by AssistantDock | -46 |
| `features/system/PreferencesSection.tsx` | **create** | theme tiles, figure-style gallery, language card wiring | 150 |
| `features/experiments/CreateAnchorDialog.tsx` | **create** | Design H.2 | 130 |
| `features/experiments/CreateFigureDialog.tsx` | **create** | Design H.3 | 130 |
| `features/experiments/RunDetail.tsx` | **modify** | two buttons in Metrics card header + dialog mounting | +25 |
| `apps/web/package.json` | **modify** | `monaco-editor` devDependency | +1 |
| `apps/web/e2e/paper.spec.ts` | **create** (file outside partition — flagged in Cross-partition) | Playwright coverage, see Test plan | 160 |

## Cross-partition requests

1. **backend-writing spec** (`apps/api/researchos/documents/**`, `agents/runtime/latex_agent.py`,
   `agents/llm/mock.py`):
   a. `PUT .../files` accepts optional `expected_version: int | None`; mismatch → 409
      `version_conflict` with `details {current_version, server_content}` (exact shapes above).
   b. `POST .../files/ops` per the contract above (1-based positions, bottom-to-top application,
      409/422 semantics).
   c. Compile job response gains nullable `preview_model` + `diagnostics` (shapes above) and publishes
      `latex.compile.started/completed/failed` envelopes.
   d. Bibliography endpoints (`GET .../bibliography`, `POST .../bibliography/entries`).
   e. Latex agent: parse the structured message JSON `{action, instruction?, selection_text,
      before_context, after_context, file, range, latex_project_id}`; respond with
      `response_schema {replacement: string, rationale: string}`.
   f. **Mock provider determinism** (required for e2e): for latex runs whose message parses to an action,
      mock must return exactly
      `{"replacement": "<selection_text> (AI <action>)", "rationale": "Deterministic mock suggestion."}`
      and for `action=continue`: `{"replacement": "This is a deterministic continuation.", "rationale": "Deterministic mock suggestion."}`.
2. **backend experiment-binding spec**: all Anchors/Figures/assets routes + `paper.staleness.changed` /
   `figure.rendered` event publication, exactly as specified above.
3. **backend platform spec**: `GET/PUT /users/me/preferences`, `GET /figure-styles` (with the `style`
   object fields `palette/font_family/grid/legend_frame`).
4. **app shell partition** — `app/(workspace)/projects/[projectId]/settings/page.tsx`: add
   `import { PreferencesSection } from '@/features/system/PreferencesSection';` and render
   `<PreferencesSection />` above the LLM card.
5. **app shell / api-client partition** — delete `apps/web/lib/api/paper.ts` (this spec migrates both of
   its only consumers to `documents.ts`); widen `AgentType` in `apps/web/lib/api/agents.ts` to include
   `'latex'` (until then the cast inside `createLatexRun` covers it — non-blocking).
6. **shared-schemas consolidation agent**: additions listed in the shared-schemas section.
7. **WS7 design-system partition** (informational): PreferencesSection writes `localStorage['ros-theme']`
   and `data-theme`; ThemeProvider should read the preferences API on session load to sync server-side
   preference → client theme.
8. **e2e ownership**: `apps/web/e2e/paper.spec.ts` is a new file with no current owner — route to this
   implementer (it exercises only this partition's UI).
9. **i18n partition (optional, non-blocking)**: fold the keys below into
   `lib/i18n/dictionaries/{zh-CN,en-US}.ts` and delete `features/paper/i18n.ts` in a later cleanup.

## MUST / SHOULD / STRETCH breakdown

**MUST** (core, ~1,800 LOC): `documents.ts`/`anchors.ts`/`figures.ts`/`preferences.ts`; PaperWorkspace
rewrite with CAS save + MergeDialog + dirty guard + draft autosave + refetch-clobber fix; SelectionToolbar +
suggestionStore + TrackedChanges + wordDiff (rewrite/expand/condense/fix/continue, accept via ops API /
local-edit branch); PreviewPanel v2 with diagnostics jump-to-line + editor markers; AnchorsPanel +
staleness banner/gutter; FiguresPanel (list, regenerate, style select, insert); PreferencesSection (theme,
figure style gallery with SVG thumbnails, language); CreateAnchorDialog + CreateFigureDialog + RunDetail
buttons; Modal; local i18n module; graceful 404-degradation for not-yet-landed backend routes.

**SHOULD** (~450 LOC): AssistantDock history + whole-document mode + insert-at-cursor (a minimal
send/stream dock is MUST since PaperAssistant.tsx is deleted); CitePicker; `latexLanguage.ts` Monarch
grammar (without it the editor stays `plaintext` — everything else still works); `usePaperEvents` live
invalidation (polling fallbacks are MUST and sufficient); custom-instruction toolbar input; draft
conflict-backup slot.

**STRETCH**: suggestion list chip in the left rail with pending count; per-suggestion Retry; `\Res…`
macro completion provider fed from the anchors query; Ctrl+Enter send in AssistantDock; figure-stale
"Re-render in new style" banner shortcut; preview scroll-position preservation across recompiles.

## Acceptance criteria (each verifiable via local gates or code/UI reading)

1. `pnpm -C apps/web typecheck` and `pnpm -C apps/web build` pass; `ruff`/`mypy` unaffected (no Python).
2. Grep gates: no file imports `@/lib/api/paper` under `features/paper/`; `monaco-editor` appears only in
   `import type` positions; no new runtime deps in `package.json` dependencies.
3. `PaperWorkspace.tsx` code review: refetch only overwrites `content` when `!dirty`; every `saveFile`
   call passes `expected_version`; 409 path opens MergeDialog (no silent overwrite path exists).
4. `TrackedChanges` accept path: clean-buffer branch calls `applyOps` and adopts the server-returned
   file verbatim; dirty branch uses `executeEdits`; overlapping suggestions are invalidated, not applied.
5. Diagnostics tab rows and preview blocks both call `onJumpToLine`; markers are set from
   `job.diagnostics` and cleared on the next successful compile (code-reviewable effect).
6. AnchorsPanel/FiguresPanel/PreferencesSection each render a designed empty/unavailable state on 404
   (queries use `retry: false`) — the paper page never white-screens when sibling backends are absent.
7. All user-facing strings in new/rewritten components come from `usePaperT`/`useI18n` (no hardcoded
   literals except LaTeX snippets); both locales present for every `PaperKey`.
8. `RunDetail.tsx` diff is ≤ ~30 lines and touches only the Metrics card header + dialog mounting.
9. Mock-LLM loop is deterministic end-to-end per the cross-partition mock contract (asserted in e2e).
10. Draft: localStorage write is debounced and keyed per `{lid}:{path}`; cleared on successful save
    (code review + e2e).

## Test plan (CI-run; no external network)

No owned backend ⇒ no pytest here (backend contract tests belong to the sibling specs).
**Playwright** `apps/web/e2e/paper.spec.ts` against the seeded demo stack with mock LLM:
1. *Save safety*: open Paper → create paper if empty → type text → Save → "Saved · v{n}" visible; simulate
   conflict via direct `PUT` (request API with stale then current version through `page.request`) → next
   save shows MergeDialog → "Keep mine" resolves and re-saves.
2. *Tracked change*: select a sentence → toolbar appears → click Rewrite → suggestion card shows
   `"<selection> (AI rewrite)"` (mock contract) → Accept → editor content contains the replacement,
   card gone → Save succeeds.
3. *Continue*: empty selection → Continue → insertion card with the deterministic continuation → Accept.
4. *Compile v2*: click Compile → Preview tab shows at least one heading block; Diagnostics tab renders
   (possibly empty); if a diagnostic row exists, click → cursor line changes (`test.skip` guard when
   the backend spec's diagnostics haven't landed: `preview_model == null`).
5. *Anchors/Figures/Preferences* (each wrapped in a `test.skip(response.status() === 404)` probe so the
   suite is green before/after sibling specs land): create anchor from RunDetail dialog → visible in
   AnchorsPanel → Insert places `\Res…` at cursor; Preferences: switch default figure style → persisted
   after reload (GET returns the slug).
6. *Draft*: type without saving → reload page → restore bar appears → Restore reinstates the text.
Unit-style checks (`wordDiff`, suggestion range shifting) are exercised through the e2e assertions;
no new unit-test infra is introduced (none exists in `apps/web`).

## Explicitly out of scope

- Multi-file tabs, outline panel, cite/ref completion providers (WS4-1 editor core beyond the Monarch
  grammar), and any `lib/ide/**` changes.
- Real PDF rendering (pdf.js) and the tectonic engine — preview v2 consumes the structural model; the PDF
  path is WS4-3 backend + a later preview tab.
- All backend implementation (documents CAS/ops/compile/bib, anchors, figures, preferences, WS producers,
  mock-provider extension) — contracts specified here, implementation cross-partitioned.
- Workspace patch pipeline, coding chat, RunInspector (WS2/WS7 partitions); theme token sweep and
  ThemeProvider (WS7); `MetricsChart` restyling; alembic migrations; central i18n dictionary edits;
  collaborative/multi-cursor editing; automatic 3-way merge; related-work weaver (WS4-4).
