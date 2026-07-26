# Spec: experiments-figures — Experiment→Paper Binding, Named Result Anchors, Figure Pipeline, User Preferences

Workstream: WS3 (owner wishlist 7). Realizes INNOVATION_IDEAS WS3-1 (Named Result
Anchors), WS3-3 (Staleness sentinel), WS3-4 (Figure worker), WS3-6 (Style presets +
settings surface), WS3-2 (NDJSON telemetry ingest, per-project-token variant), plus the
two audited experiments bugs (IDOR, best-metric direction).

Owned partition:
- `apps/api/researchos/experiments/**` (modified)
- `apps/api/researchos/figures/**` (NEW)
- `apps/api/researchos/preferences/**` (NEW)
- `apps/worker/researchos_worker/tasks/figures.py` (NEW — figure rendering task only)

---

## Objective (user-visible outcome)

1. Numbers in the paper stop rotting: a researcher binds `\ROSBestAcc` to
   "best `val_acc` of experiment *lr-sweep*", pastes `\input{macros.tex}`-style content
   fetched from `GET /projects/{id}/anchors/macros.tex` into their LaTeX project, and the
   number regenerates with two decimals and a `\%` suffix. When run 52 beats run 47, the
   anchor is flagged **stale** and a staleness report says exactly which macro is out of
   date and by how much.
2. Publication figures render server-side: a FigureSpec (runs + metrics + chart type +
   style preset) renders via matplotlib to SVG+PNG, is stored and linked as a run
   artifact, is re-renderable on demand, and degrades to a capped synchronous render when
   the Celery worker is down.
3. 4–5 built-in, versioned figure style presets (`clean-serif`, `ieee`, `nature`,
   `dark`, `minimal-gray`) selectable per user / per project via a new generic
   preferences surface (`/users/me/preferences`, `/projects/{id}/preferences`) that also
   carries theme and language — the backend the frontend settings page consumes.
4. A GPU training script can `POST` NDJSON metric/log/status lines with a per-project
   ingest token — no browser cookies, no CSRF (SHOULD).
5. Two audited security/correctness bugs are fixed: the experiments list-runs IDOR and
   the `'loss'`-substring best-metric direction heuristic.

---

## Current state (concrete, file:line)

- **IDOR**: `apps/api/researchos/experiments/service.py:116-120` — `list_runs` calls
  `ensure_access(project_id)` but then `self.runs.list_for_experiment(experiment_id)`
  (`repository.py:54-60` filters only on `experiment_id`). Any member of *any* project
  can enumerate another project's runs by guessing/knowing an experiment UUID and
  supplying their own project id in the path. (ARCHITECTURE_MAP §4 Security #5.)
- **Best-metric direction bug**:
  `apps/api/researchos/agents/runtime/experiment_agent.py:35` —
  `best[name] = min(values) if "loss" in name.lower() else max(values)`. Misclassifies
  perplexity/WER/error-rate/latency as higher-is-better. No per-metric metadata exists
  anywhere (`experiments/models.py:17-29` has no metric metadata column).
- **Log seq race**: `experiments/repository.py:91-95` — `next_seq` is
  `SELECT COUNT(*)`; concurrent appends produce duplicate `seq`; no unique constraint
  (`models.py:76-87`). (Map §4 #9, weakness #41.)
- **Run lifecycle**: `service.py:133-143` — `update_run_status` accepts any transition;
  entering `RUNNING` never sets `started_at`; `CANCELLED` never sets `finished_at`
  (only COMPLETED/FAILED at line 139). `create_run` (`service.py:92-97`) likewise skips
  `finished_at` for CANCELLED. (Weakness #40.)
- **Metric duplicates**: `service.py:146-158` inserts row-per-point with no dedup on
  `(run, name, step)` (weakness #42) — any consumer that reduces a series must
  de-duplicate.
- **No programmatic ingestion**: every write route in `experiments/router.py` requires
  session cookie + `require_csrf` (`router.py:129-142` etc.); no token path
  (Map §3.3).
- **No figures / anchors / preferences code exists**: `grep` for anchor/figure/preference
  under `apps/api/researchos` returns nothing; `ExperimentArtifact.uri`
  (`models.py:101`) is a dead string; `common/storage.py:1-8` is a reachability probe
  only; the `experiments` Celery queue has zero registered tasks
  (`apps/worker/researchos_worker/queues.py:26-33`, `app.py:24`).
- **Events**: backend publishes only `agent.run.*`
  (`websocket/envelopes.py:25-33`); `EXPERIMENT_EVENTS` exist in
  `packages/shared-schemas/src/events.ts:22-30` with no producers.
- **Settings surface**: the only per-project settings router is
  `llm_config/router.py` (upsert pattern at lines 48-86); there is no per-user settings
  model at all (`identity/` has no preferences).

### Prior-decision supersessions (explicit)

- **WS3-1 sketch** proposed writing anchors into a `results/anchors.tex` DocumentFile
  via a Celery hook. **Superseded**: macros are served from
  `GET /projects/{id}/anchors/macros.tex` and never written into `document_files`.
  Rationale: the documents store is last-write-wins with no optimistic concurrency
  (Map weakness #45) — a background writer would clobber user edits; and
  `documents/**` is another partition. The paper references the endpoint output (copy
  or fetch); the documents partition may later add an "import from anchors" action.
- **WS3-4 sketch** proposed MinIO + a `document_assets` table. **Superseded**: rendered
  figure bytes live in a new `figure_assets` DB table (bytea, capped 4 MB, latest render
  per format only) and are *linked* as `experiment_artifacts` rows. Rationale: no
  storage abstraction exists (`common/storage.py` is a probe), no Docker/MinIO on the
  dev machine, and DB-stored assets are CI-testable. This does NOT touch the
  "filesystem is source of truth for **workspaces**" decision (P3-D2) — figures are
  project resources, not workspace files. A later `storage_key` column migration is the
  MinIO escape hatch.
- **WS3-6 sketch** proposed presets as marketplace skills (`SkillModule.FIGURE_STYLE`).
  **Superseded for now**: presets are a code registry (`figures/presets.py`) of
  versioned, allowlisted rcParams dicts — "versioned like skills" via a semver string
  per preset; bumping a preset version marks dependent figures stale. Marketplace
  packaging is deferred (skills partition), the preference key is a plain slug so the
  swap is non-breaking.
- **Phase 0 note in `common/storage.py`** ("actual storage abstraction introduced when a
  phase needs to persist artifacts") — deliberately NOT triggered by this spec (see
  above).

---

## Design (algorithms & data flow)

### D1. Metric direction metadata (fixes the `'loss'` heuristic)

1. `Experiment` gains `metric_meta_json: JSONB` — a mapping
   `{"<metric_name>": {"direction": "min"|"max", "unit": str?, "display_name": str?}}`.
   Editable via new `PATCH /projects/{id}/experiments/{eid}` (RESEARCHER).
2. New pure module `experiments/directions.py`:
   ```python
   Direction = Literal["min", "max"]
   _MIN_HINTS = ("loss", "error", "err_", "_err", "perplexity", "ppl", "wer", "cer",
                 "mae", "mse", "rmse", "regret", "latency")

   def metric_direction(name: str, metric_meta: Mapping[str, Any] | None) -> Direction:
       """Explicit metadata wins; else expanded substring heuristic; else 'max'."""

   def dedupe_points(rows: Sequence[ExperimentMetric]) -> list[tuple[int, float]]:
       """Collapse duplicate (name-scoped) steps keeping the latest row
       (max created_at, then max id); returns step-sorted (step, value)."""

   def reduce_series(points: Sequence[tuple[int, float]], *, aggregation: AnchorAggregation,
                     direction: Direction) -> float | None:
       """final=value at max step; best=min/max per direction; min/max/mean literal.
       None for empty series."""
   ```
3. `ExperimentService` gains
   `async def get_metric_meta_for_run(self, actor, project_id, run_id) -> dict`
   (loads run → experiment → returns `metric_meta_json`) so the experiment agent can
   consume it with a one-line change (see Cross-partition requests).
4. Everything in this spec that reduces a series (anchors, figures artifact naming,
   agent summary) routes through `directions.py`. Single source of truth.

### D2. IDOR + lifecycle hardening (experiments service)

1. `list_runs`: after `ensure_access`, load
   `await self.experiments.get(project_id, experiment_id)`; `None` → `NotFoundError`
   (404, matching the 404-hides-existence convention). Same guard added to any future
   experiment-scoped path.
2. Transition table in `enums.py`:
   ```python
   TERMINAL = {COMPLETED, FAILED, CANCELLED}
   ALLOWED_TRANSITIONS = {QUEUED: {RUNNING, COMPLETED, FAILED, CANCELLED},
                          RUNNING: {COMPLETED, FAILED, CANCELLED},
                          COMPLETED: set(), FAILED: set(), CANCELLED: set()}
   ```
   `update_run_status` raises `ConflictError(code="invalid_transition")` on violation;
   sets `started_at` when entering RUNNING (if unset); sets `finished_at` on any
   terminal status (CANCELLED included). `create_run` sets `finished_at` for CANCELLED
   too. Idempotent same-status PATCH is a no-op 200.
3. On transition into a terminal status, the service fires the post-completion hook
   (lazy import to avoid cycles):
   `AnchorService(db).mark_stale_for_experiment(run.experiment_id)` and
   `FigureService(db).mark_stale_for_run(run)` — pure UPDATEs, same transaction, then
   (SHOULD) publishes `experiment.run.completed|failed` + `anchor.values.updated` WS
   events after commit.
4. Atomic log seq: `ExperimentRun.log_next_seq: int NOT NULL DEFAULT 0`;
   `RunRepository.allocate_log_seqs(run_id, n) -> int` executes
   `UPDATE experiment_runs SET log_next_seq = log_next_seq + :n WHERE id = :rid
   RETURNING log_next_seq` and returns `returned - n` (first seq of the reserved
   block). `append_log` and the NDJSON ingest both use it. `LogRepository.next_seq` is
   deleted. Unique constraint `(run_id, seq)` added on `experiment_logs`.

### D3. Named Result Anchors

Data model — `result_anchors` (see DB changes):
`{name, project_id, experiment_id, run_id|None (None = latest COMPLETED run),
metric_name, aggregation, decimals, scale, suffix, captured_value, captured_run_id,
captured_at, stale}`. Macro identity: rendered name is `\ROS{name}`; `name` validated
`^[A-Za-z]{1,48}$` (LaTeX control words are letters-only), unique per project.

**Resolution algorithm** (`AnchorService._resolve(anchor) -> ResolvedAnchor`):
1. Source run: `anchor.run_id` if pinned, else newest COMPLETED run of
   `anchor.experiment_id` ordered by `finished_at DESC NULLS LAST, created_at DESC`
   (`RunRepository.latest_completed(experiment_id)`).
2. Load `(run, metric_name)` series; `dedupe_points`; `reduce_series` with
   `metric_direction(metric_name, experiment.metric_meta_json)`.
3. `None` (no run / no points) → unresolved marker; never an exception.
4. Formatted value: `f"{value * scale:.{decimals}f}" + suffix` (suffix rendered
   verbatim, e.g. `\%`; `scale=100, suffix='\\%'` gives percents).

**Capture / staleness**:
- `POST /projects/{id}/anchors/refresh` (and `GET macros.tex?refresh=true`, the
  default) resolves every anchor, writes `captured_value/captured_run_id/captured_at`,
  clears `stale`, and returns the report.
- `mark_stale_for_experiment(experiment_id)` (run-completion hook) sets `stale=true`
  where: pinned anchors — a COMPLETED run newer than `captured_run_id` exists; latest
  anchors — cheap re-resolution shows `resolved_run != captured_run_id` or
  `resolved_value != captured_value`. Anchors never captured are left `stale=false`
  (nothing to be stale against).
- `GET /projects/{id}/anchors/staleness` recomputes live and returns
  `{anchor, captured_*, latest_run_id, latest_value, delta, delta_pct, stale}` per
  anchor without mutating state.

**macros.tex generation** (`figures/macros.py`, pure function over resolved anchors):
```latex
% Auto-generated by ResearchOS. Do not edit. Regenerate: GET /projects/{id}/anchors/macros.tex
% generated_at=2026-07-26T12:00:00Z project=3f2a...
% \ROSBestAcc <- experiment "lr-sweep" run "run-47" metric val_acc agg=best
\newcommand{\ROSBestAcc}{94.21\%}
% \ROSFinalLoss <- experiment "lr-sweep" run latest metric train_loss agg=final [UNRESOLVED]
\newcommand{\ROSFinalLoss}{\textbf{??}}
```
Unresolved anchors emit `\textbf{??}` plus a comment — the file always compiles.
Deterministic ordering (by name) for testability.

### D4. Figure pipeline

**FigureSpec** (pydantic, stored as `figures.spec_json`, `figures/spec.py`):
```json
{
  "chart": "line",                       // line | bar | scatter
  "series": [
    {"source": {"kind": "run_metric", "run_id": "…", "metric_name": "val_acc"},
     "label": "baseline", "smoothing_window": 5},
    {"source": {"kind": "run_metric", "experiment_id": "…", "metric_name": "val_acc"},
     "label": "latest run"},              // experiment_id w/o run_id = latest COMPLETED
    {"source": {"kind": "inline", "points": [[0, 0.1], [1, 0.4]]}, "label": "ref"}
  ],
  "title": "Validation accuracy", "x_label": "step", "y_label": "acc",
  "legend": true, "y_scale": "linear",   // linear | log
  "style_slug": null                      // null = resolve from preferences
}
```
Caps enforced by the pydantic model: 1–8 series; inline series ≤ 2000 points;
smoothing_window 1–500; labels ≤ 120 chars. Discriminated union on `source.kind`.
Service-level validation at create/update/render: every referenced run/experiment must
belong to the figure's project (404 otherwise — same IDOR discipline as D2).

**Data resolution** (`FigureService._resolve_series`): per run_metric series load the
(possibly latest-run) metric rows, `dedupe_points`, apply centered rolling-mean
smoothing if requested, uniformly downsample to ≤ 1000 points per series for render.
Records the concrete run ids used into `figures.source_run_ids`.

**Style resolution**: `spec.style_slug` → creator's project-scoped
`figure_style_slug` preference → creator's global preference → `"clean-serif"`.
Unknown slug at render time → fall back to default + warning in `last_error`-free log.

**Render core** (`figures/render.py`, pure, lazy-imports matplotlib, `Agg` backend,
no DB/network):
```python
def render_figure_bytes(chart, series_data, labels, opts, preset) -> dict[str, bytes]:
    # returns {"svg": ..., "png": ...}
```
`mpl.rc_context(preset.rcparams)`; per-chart: line → `ax.plot`, bar → grouped
`ax.bar` over categorical x, scatter → `ax.scatter`; palette cycled from
`preset.palette`. Determinism: `rcParams["svg.hashsalt"]="researchos"`,
`savefig(..., metadata={"Date": None})` for SVG; PNG at `preset.dpi` (default 200).
Fonts restricted to generic families (`serif`/`sans-serif` → DejaVu, always bundled
with matplotlib) so CI renders identically.

**Persistence**: upsert `figure_assets` rows keyed `(figure_id, format)` — only the
latest render is kept (no unbounded growth); reject assets > 4 MB
(`ValidationError`). Stamp `figures.rendered_style_slug/rendered_style_version/
last_rendered_at/source_run_ids`, `status='rendered'`, `stale=false`.

**Run-artifact linking**: for each distinct source run, upsert an
`ExperimentArtifact` (`artifact_type="figure"`, `name=f"{figure.name}.svg"`,
`uri=f"/projects/{pid}/figures/{fid}/assets/svg"`,
`metadata_json={"figure_id": str(fid), "formats": ["svg", "png"]}`); upsert = scan the
run's artifacts for matching `metadata_json.figure_id`, update in place else insert.

**Async path** (SHOULD): `figures/dispatch.py` calls
`get_celery_client().send_task("experiments.render_figure", args=[str(figure_id)],
queue="experiments")` — task name rides the existing `experiments.*` route
(`queues.py:31`), so `queues.py` is untouched. Worker task
(`apps/worker/researchos_worker/tasks/figures.py`) is a thin shell mirroring
`tasks/agents.py`: `run_async_task(lambda: run_figure_render(figure_id))` where
`run_figure_render` lives in `figures/render_job.py` (API package): load figure →
`status='rendering'` (+ WS started event) → resolve data → `asyncio.to_thread(render_figure_bytes, …)`
→ persist → WS completed event; on exception `status='failed'`, `last_error=str(exc)[:2000]`,
WS failed event. Idempotent under acks-late redelivery (re-render overwrites).

**Degraded sync path** (MUST): `POST …/render {"mode": "sync"}` renders in-request via
`asyncio.wait_for(asyncio.to_thread(...), timeout=15)`; guarded by caps — ≤ 4 series
and ≤ 2000 total resolved points (`ValidationError code="figure_too_large_for_sync"`
otherwise) — and `enforce_rate_limit(f"figure_sync:{user.id}", limit=10)`.
`mode="async"` (default): if the broker publish raises (`OperationalError`/
`ConnectionError`), fall back to sync when within caps, else
`DependencyError(code="worker_unavailable")` (503).

**Figure staleness**: `mark_stale_for_run(run)` sets `stale=true` on figures whose
spec references `run.experiment_id` with latest-run sources, or (for pinned sources)
where a newer COMPLETED run exists in the same experiment. Preset version bumps: a
startup-free check in `list_figures`/`get_figure` compares `rendered_style_version`
against the current registry version and reports `style_outdated: true` in responses
(no writes on GET).

### D5. Style presets (`figures/presets.py`)

```python
@dataclass(frozen=True)
class StylePreset:
    slug: str; version: str; name: str; description: str
    rcparams: Mapping[str, Any]; palette: tuple[str, ...]; dpi: int = 200
PRESETS: dict[str, StylePreset]
```
Built-ins (all version `"1.0.0"`):
- `clean-serif` — serif (DejaVu Serif), thin spines, no top/right spine, muted 6-color
  palette, subtle y-grid.
- `ieee` — small sans fonts (8pt), grayscale-safe palette + distinct linestyles,
  compact figsize (3.5, 2.4), tight margins.
- `nature` — sans, Okabe–Ito colorblind-safe palette, compact, boxed axes off.
- `dark` — dark background (#111318 axes/figure), light text, vivid palette (slides).
- `minimal-gray` — grayscale only, markers differentiate series.
rcParams are hand-written allowlisted keys only (fonts, sizes, spines, grid, legend,
figure size/dpi, prop_cycle) — no arbitrary keys, no code. `GET …/figures/style-presets`
serializes the registry (never the rcparams internals — slug/version/name/description/
palette only).

### D6. Preferences (generic user-settings surface)

`user_preferences` row per `(user_id, project_id)`, with `project_id NULL` = the
user's global row (unique NULLS NOT DISTINCT). Fields: `theme`
(`system|light|dark|NULL`), `language` (`en|zh-CN|NULL`), `figure_style_slug`
(known preset slug or NULL), `extra_json` (flat `str -> str|int|float|bool`, ≤ 8 KB —
forward-compatible bucket for frontend-only settings). `NULL` field = "no opinion at
this scope".

Effective resolution (`PreferenceService.effective(user, project_id|None)`):
per field, project row → global row → defaults
`{"theme": "system", "language": "zh-CN", "figure_style_slug": "clean-serif",
"extra": {}}` (zh-CN matches the frontend's current default locale). `PUT` is a
full replacement of that scope's row (omitted field ⇒ NULL ⇒ no override); rows are
personal — any project member (VIEWER+) manages their own project-scoped row; no
cross-user access exists by construction (queries always filter `user_id = actor.id`).

### D7. NDJSON ingest + per-project tokens (SHOULD)

1. Token issue (browser, CSRF'd): `POST /projects/{id}/experiments/ingest-tokens`
   (RESEARCHER) → generates `rosit_` + `secrets.token_hex(20)`; stores only
   `sha256(token)` (`token_hash`, unique) + `token_prefix` (first 12 chars for
   display); plaintext returned exactly once. List (masked) + revoke
   (`revoked_at`) endpoints.
2. Ingest (script, no cookie/CSRF): `POST /ingest/experiment-runs/{run_id}` with
   `Authorization: Bearer rosit_…`, body `application/x-ndjson`, caps: ≤ 1 MB body,
   ≤ 1000 lines. Auth dependency (`experiments/ingest.py`): hash presented token →
   lookup non-revoked row → 401 on miss; then load run and require
   `run.project_id == token.project_id` (404 otherwise); update `last_used_at`
   (best-effort); `enforce_rate_limit(f"ingest:{token.id}", limit=120)`.
3. Line contract (discriminated union on `"t"`, pydantic `TypeAdapter`):
   - `{"t":"metric","name":"loss","step":10,"value":0.5}`
   - `{"t":"log","level":"info","msg":"epoch 3 done"}`
   - `{"t":"status","status":"completed"}`
4. Processing: parse all lines first (invalid lines collected as
   `{line, error}`, valid ones proceed — partial acceptance); bulk-insert metrics
   (`MetricRepository.bulk_add`, single `add_all` + one commit); logs get a
   block-allocated seq (D2.4); status lines go through the guarded transition
   (invalid transition ⇒ rejected line, not request failure) and fire the
   D2.3 completion hook. Response `{"accepted": N, "rejected": [...],
   "run_status": "..."}`. WS `experiment.metric.recorded` / `experiment.log.appended`
   published per batch (counts, not per line).

### D8. WS events (SHOULD — all fire after commit, best-effort, never fail the request)

Producers use `EventEnvelope` from `websocket/envelopes.py` (import-only) via a small
builder in `figures/events.py` / inline in experiments service. See "WS events" for
exact shapes. Figure events need `ResourceType` to gain `"figure"`
(cross-partition request #4); until it lands, figure events are withheld (the feature
is poll-complete via `GET /figures/{fid}`).

---

## API contract changes

All routes follow existing conventions: session cookie auth, `X-CSRF-Token` on
non-GET (except the bearer-token ingest route), error envelope
`{"error": {code, message, request_id}}`, non-membership → 404.

### Experiments (modified)

- `GET /projects/{id}/experiments/{eid}/runs` — **behavior change**: 404 when the
  experiment does not belong to `{id}` (IDOR fix). Response shape unchanged.
- `PATCH /projects/{id}/experiments/{eid}` — **NEW** (RESEARCHER).
  Request: `{"name"?, "description"?, "goal"?, "metric_meta"?: {"val_acc": {"direction": "max", "unit": "%"}}}`
  → 200 `ExperimentResponse` (now includes `"metric_meta": {...}`).
  Errors: 404; 422 invalid direction (`direction` must be `"min"|"max"`, ≤ 200 keys).
- `PATCH /projects/{id}/experiment-runs/{run_id}` — **behavior change**: illegal
  transitions → 409 `{"error":{"code":"invalid_transition","message":"Cannot move run from completed to running."}}`;
  RUNNING sets `started_at`, terminal statuses set `finished_at`.
- `POST /projects/{id}/experiment-runs/{run_id}/logs` — unchanged shape; `seq` now
  atomically allocated.

### Ingest tokens (NEW, SHOULD)

- `POST /projects/{id}/experiments/ingest-tokens` (RESEARCHER, CSRF)
  Request `{"name": "gpu-box-1"}` → 201
  `{"id": "…", "name": "gpu-box-1", "token": "rosit_9f2c…40hex", "token_prefix": "rosit_9f2c…", "created_at": "…"}`
  (`token` present only in this response).
- `GET /projects/{id}/experiments/ingest-tokens` → 200
  `[{"id", "name", "token_prefix", "created_at", "last_used_at", "revoked_at"}]`
- `DELETE /projects/{id}/experiments/ingest-tokens/{token_id}` (RESEARCHER) → 204
  (sets `revoked_at`; idempotent).

### NDJSON ingest (NEW, SHOULD — bearer auth, no cookie, no CSRF)

- `POST /ingest/experiment-runs/{run_id}`
  Headers: `Authorization: Bearer rosit_…`, `Content-Type: application/x-ndjson`.
  Body: one JSON object per line (contract in D7.3).
  → 200 `{"accepted": 128, "rejected": [{"line": 7, "error": "value: not a number"}], "run_status": "running"}`
  Errors: 401 `invalid_token` (missing/unknown/revoked); 404 run not in token's
  project; 413 `payload_too_large` (> 1 MB or > 1000 lines); 429 rate limited.

### Result anchors (NEW)

- `POST /projects/{id}/anchors` (RESEARCHER, CSRF)
  Request:
  ```json
  {"name": "BestAcc", "experiment_id": "…", "run_id": null,
   "metric_name": "val_acc", "aggregation": "best",
   "decimals": 2, "scale": 100.0, "suffix": "\\%"}
  ```
  → 201 `AnchorResponse`:
  ```json
  {"id": "…", "name": "BestAcc", "macro": "\\ROSBestAcc", "experiment_id": "…",
   "run_id": null, "metric_name": "val_acc", "aggregation": "best",
   "decimals": 2, "scale": 100.0, "suffix": "\\%",
   "captured_value": null, "captured_run_id": null, "captured_at": null,
   "stale": false, "created_at": "…"}
  ```
  Errors: 409 `conflict` duplicate name; 404 experiment/run not in project;
  422 name not `^[A-Za-z]{1,48}$` / bad aggregation / decimals ∉ 0..10.
- `GET /projects/{id}/anchors` (VIEWER) → 200 `[AnchorResponse]` (ordered by name).
- `GET /projects/{id}/anchors/{anchor_id}` → 200 / 404.
- `PATCH /projects/{id}/anchors/{anchor_id}` (RESEARCHER) — any create field;
  changing source fields resets `captured_*` to null and `stale` to false. → 200.
- `DELETE /projects/{id}/anchors/{anchor_id}` (RESEARCHER) → 204.
- `POST /projects/{id}/anchors/refresh` (RESEARCHER, CSRF) → 200
  ```json
  {"refreshed": 5, "unresolved": 1,
   "anchors": [{"id": "…", "name": "BestAcc", "value": 0.9421,
                "formatted": "94.21\\%", "run_id": "…", "resolved": true}]}
  ```
- `GET /projects/{id}/anchors/staleness` (VIEWER) → 200
  ```json
  {"stale_count": 1, "items": [
     {"anchor_id": "…", "name": "BestAcc", "stale": true,
      "captured_run_id": "…47", "captured_value": 0.9421,
      "latest_run_id": "…52", "latest_value": 0.9533,
      "delta": 0.0112, "delta_pct": 1.19}]}
  ```
- `GET /projects/{id}/anchors/macros.tex?refresh=true` (VIEWER) → 200, content-type
  `application/x-tex; charset=utf-8`, body per D3. `refresh=true` (default) captures
  snapshots as a side effect (documented); `refresh=false` renders from stored
  snapshots only.

### Figures (NEW)

- `POST /projects/{id}/figures` (RESEARCHER, CSRF)
  `{"name": "lr-ablation", "spec": {FigureSpec}}` → 201 `FigureResponse`:
  ```json
  {"id": "…", "name": "lr-ablation", "spec": {…}, "status": "pending",
   "stale": false, "style_outdated": false, "last_error": null,
   "rendered_style_slug": null, "rendered_style_version": null,
   "source_run_ids": [], "last_rendered_at": null,
   "latex_project_id": null, "usage_path": null, "created_at": "…"}
  ```
  Errors: 409 duplicate name; 404 referenced run/experiment not in project; 422 spec
  invalid (caps in D4).
- `GET /projects/{id}/figures` (VIEWER) → 200 `[FigureResponse]`.
- `GET /projects/{id}/figures/{fid}` → 200 / 404.
- `PATCH /projects/{id}/figures/{fid}` (RESEARCHER) — `{"name"?, "spec"?,
  "latex_project_id"?, "usage_path"?}`; spec change ⇒ `status='pending'`,
  `stale=false`. → 200.
- `DELETE /projects/{id}/figures/{fid}` (RESEARCHER) → 204 (cascades assets; linked
  `experiment_artifacts` rows remain but their `uri` 404s — acceptable, documented).
- `POST /projects/{id}/figures/{fid}/render` (RESEARCHER, CSRF)
  `{"mode": "sync"}` → 200
  `{"figure_id": "…", "status": "rendered", "assets": [{"format": "svg", "size_bytes": 18234, "sha256": "…"}, {"format": "png", "size_bytes": 90211, "sha256": "…"}]}`
  `{"mode": "async"}` (default) → 202 `{"figure_id": "…", "status": "pending"}`.
  Errors: 422 `figure_too_large_for_sync`; 429 sync rate limit; 503
  `worker_unavailable` (async dispatch failed and sync caps exceeded); 409
  `conflict` if already `rendering` (async only).
- `GET /projects/{id}/figures/{fid}/assets/{fmt}` (VIEWER; `fmt` ∈ `svg|png`) → 200
  bytes (`image/svg+xml` / `image/png`), `ETag: "<sha256>"`, honors
  `If-None-Match` → 304. 404 if never rendered.
- `GET /projects/{id}/figures/style-presets` (VIEWER) → 200
  `[{"slug": "clean-serif", "version": "1.0.0", "name": "Clean serif",
     "description": "…", "palette": ["#4C72B0", …]}]`

### Preferences (NEW)

- `GET /users/me/preferences` → 200
  ```json
  {"effective": {"theme": "system", "language": "zh-CN",
                 "figure_style_slug": "clean-serif", "extra": {}},
   "global": {"theme": "dark", "language": null, "figure_style_slug": null, "extra": {}}}
  ```
  (`global` is `null` when no row exists.)
- `PUT /users/me/preferences` (CSRF) — full replace of the global row:
  `{"theme": "dark", "language": null, "figure_style_slug": null, "extra": {}}` → 200
  (same shape as GET). 422: unknown theme/language/preset slug; `extra` non-flat or
  > 8 KB.
- `GET /projects/{id}/preferences` (VIEWER) → 200
  `{"effective": {…}, "project": {…}|null, "global": {…}|null}` — effective merges
  project → global → defaults per field.
- `PUT /projects/{id}/preferences` (VIEWER — personal setting, CSRF) — full replace of
  the caller's project-scoped row. → 200 (same shape as GET).

---

## WS events

All SHOULD-tier; envelope = existing `EventEnvelope`. Exact strings/payloads:

Existing contract strings (`events.ts:22-30`), finally given producers
(resource_type `"experiment_run"`, resource_id = run id):
- `experiment.run.queued` — `{run_id, experiment_id, status: "queued"}` (create_run)
- `experiment.run.started` — `{run_id, experiment_id, status: "running"}`
- `experiment.run.completed` — `{run_id, experiment_id, status: "completed"}`
- `experiment.run.failed` — `{run_id, experiment_id, status: "failed"|"cancelled"}`
- `experiment.metric.recorded` — `{run_id, count, names: ["loss", "val_acc"]}` (per
  batch: cookie route and NDJSON ingest)
- `experiment.log.appended` — `{run_id, count, last_seq}` (per batch)

New strings (shared-schemas additions required; resource_type `"figure"`, resource_id
= figure id — blocked on cross-partition request #4):
- `figure.render.queued` — `{figure_id, name}`
- `figure.render.started` — `{figure_id, name}`
- `figure.render.completed` — `{figure_id, name, formats: ["svg","png"], style_slug, style_version, source_run_ids}`
- `figure.render.failed` — `{figure_id, name, error}`

New string (resource_type `"project"`, resource_id = project id):
- `anchor.values.updated` — `{updated_count, stale_count, anchor_ids: [...]}` (fired
  by refresh and by the run-completion staleness hook)

---

## DB changes (DDL-level; migration authored by the consolidation agent)

Modified tables:
1. `experiments` — ADD COLUMN `metric_meta_json JSONB NOT NULL DEFAULT '{}'::jsonb`.
   No backfill.
2. `experiment_runs` — ADD COLUMN `log_next_seq INTEGER NOT NULL DEFAULT 0`.
   Backfill: `UPDATE experiment_runs r SET log_next_seq = COALESCE((SELECT MAX(l.seq) + 1 FROM experiment_logs l WHERE l.run_id = r.id), 0);`
3. `experiment_logs` — ADD CONSTRAINT `uq_experiment_logs_run_seq UNIQUE (run_id, seq)`.
   Backfill BEFORE the constraint (COUNT(*)-era duplicates exist): resequence per run
   ordered by `(created_at, id)` via a window-function UPDATE.

New enums (native PG, `values_callable` lowercase like `experiment_run_status`):
- `anchor_aggregation`: `final | best | min | max | mean`
- `figure_render_status`: `pending | rendering | rendered | failed`

New tables:
4. `result_anchors`
   - `id UUID PK`; `created_at/updated_at timestamptz` (house mixins)
   - `project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE` (indexed)
   - `name VARCHAR(64) NOT NULL`; `UNIQUE (project_id, name)`
   - `experiment_id UUID NOT NULL REFERENCES experiments(id) ON DELETE CASCADE` (indexed)
   - `run_id UUID NULL REFERENCES experiment_runs(id) ON DELETE SET NULL`
   - `metric_name VARCHAR(120) NOT NULL`
   - `aggregation anchor_aggregation NOT NULL DEFAULT 'final'`
   - `decimals INTEGER NOT NULL DEFAULT 2`; `scale FLOAT NOT NULL DEFAULT 1.0`;
     `suffix VARCHAR(16) NOT NULL DEFAULT ''`
   - `captured_value FLOAT NULL`;
     `captured_run_id UUID NULL REFERENCES experiment_runs(id) ON DELETE SET NULL`;
     `captured_at timestamptz NULL`
   - `stale BOOLEAN NOT NULL DEFAULT FALSE`
   - `created_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT`
5. `figures`
   - `id UUID PK`; timestamps
   - `project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE` (indexed)
   - `name VARCHAR(120) NOT NULL`; `UNIQUE (project_id, name)`
   - `spec_json JSONB NOT NULL`
   - `status figure_render_status NOT NULL DEFAULT 'pending'`
   - `last_error TEXT NULL`
   - `rendered_style_slug VARCHAR(64) NULL`; `rendered_style_version VARCHAR(16) NULL`
   - `source_run_ids JSONB NOT NULL DEFAULT '[]'::jsonb`
   - `stale BOOLEAN NOT NULL DEFAULT FALSE`
   - `last_rendered_at timestamptz NULL`
   - `latex_project_id UUID NULL REFERENCES latex_projects(id) ON DELETE SET NULL`
   - `usage_path VARCHAR(512) NULL`
   - `created_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT`
6. `figure_assets`
   - `id UUID PK`; timestamps
   - `figure_id UUID NOT NULL REFERENCES figures(id) ON DELETE CASCADE` (indexed)
   - `format VARCHAR(8) NOT NULL` (app-validated `svg|png`); `UNIQUE (figure_id, format)`
   - `content BYTEA NOT NULL` (SQLAlchemy `LargeBinary`; app cap 4 MB)
   - `sha256 CHAR(64) NOT NULL`; `size_bytes INTEGER NOT NULL`;
     `rendered_at timestamptz NOT NULL`
7. `user_preferences`
   - `id UUID PK`; timestamps
   - `user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE` (indexed)
   - `project_id UUID NULL REFERENCES projects(id) ON DELETE CASCADE`
   - `theme VARCHAR(16) NULL`; `language VARCHAR(16) NULL`;
     `figure_style_slug VARCHAR(64) NULL`
   - `extra_json JSONB NOT NULL DEFAULT '{}'::jsonb`
   - `UNIQUE NULLS NOT DISTINCT (user_id, project_id)` (PG15+; SQLAlchemy
     `UniqueConstraint(..., postgresql_nulls_not_distinct=True)`)
8. `experiment_ingest_tokens`
   - `id UUID PK`; timestamps
   - `project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE` (indexed)
   - `name VARCHAR(120) NOT NULL`
   - `token_hash CHAR(64) NOT NULL UNIQUE`; `token_prefix VARCHAR(12) NOT NULL`
   - `created_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT`
   - `last_used_at timestamptz NULL`; `revoked_at timestamptz NULL`

---

## shared-schemas additions (consolidator applies)

`packages/shared-schemas/src/events.ts`:
- `export const FIGURE_EVENTS = ['figure.render.queued','figure.render.started','figure.render.completed','figure.render.failed'] as const;`
- `export const ANCHOR_EVENTS = ['anchor.values.updated'] as const;`
- Append both to `EVENT_TYPES`.
- `ResourceType` union: add `'figure'`.
- Payload interfaces: `FigureRenderCompletedPayload {figure_id: string; name: string; formats: string[]; style_slug: string; style_version: string; source_run_ids: string[]}`,
  `FigureRenderFailedPayload {figure_id: string; name: string; error: string}`,
  `AnchorValuesUpdatedPayload {updated_count: number; stale_count: number; anchor_ids: string[]}`,
  `ExperimentMetricRecordedPayload {run_id: string; count: number; names: string[]}`,
  `ExperimentLogAppendedPayload {run_id: string; count: number; last_seq: number}`,
  `ExperimentRunStatusPayload {run_id: string; experiment_id: string; status: string}`.

New API types (for the web partition; TS mirrors of the JSON in "API contract
changes"): `AnchorResponse`, `AnchorStalenessReport`, `FigureSpec`, `FigureResponse`,
`StylePresetInfo`, `PreferencesResponse`, `IngestTokenResponse`.

---

## New dependencies

- `apps/api/pyproject.toml`: `matplotlib>=3.9` (render core + sync fallback live in the
  API package; imported lazily inside functions so API startup cost is zero).
- `apps/worker/pyproject.toml`: `matplotlib>=3.9` (explicit, though also transitive via
  the editable `researchos-api` dep — the worker task imports it).
- No new JS dependencies.

---

## File-by-file plan

`apps/api/researchos/experiments/` (all modified unless marked NEW):
- `enums.py` — add `TERMINAL_STATUSES`, `ALLOWED_TRANSITIONS`.
- `models.py` — `Experiment.metric_meta_json`, `ExperimentRun.log_next_seq`,
  `ExperimentLog.__table_args__` unique `(run_id, seq)`, new model
  `ExperimentIngestToken`.
- `schemas.py` — `UpdateExperimentRequest` (+`metric_meta` validation),
  `ExperimentResponse.metric_meta`, ingest-token DTOs, NDJSON line models
  (`MetricLine|LogLine|StatusLine` discriminated union), `IngestResult`.
- `repository.py` — delete `LogRepository.next_seq`; add
  `RunRepository.allocate_log_seqs`, `RunRepository.latest_completed(experiment_id)`,
  `MetricRepository.bulk_add(rows)`,
  `MetricRepository.series(run_id, name)`; `IngestTokenRepository`.
- `service.py` — IDOR fix in `list_runs`; transition guard + timestamps in
  `update_run_status`/`create_run`; `update_experiment`; `get_metric_meta_for_run`;
  atomic log seq in `append_log`; terminal-transition hook → anchors/figures staleness
  (lazy imports); WS publishing (SHOULD); ingest-token issue/list/revoke.
- `router.py` — `PATCH /experiments/{eid}`; ingest-token routes.
- NEW `directions.py` — `metric_direction`, `dedupe_points`, `reduce_series` (pure).
- NEW `ingest.py` — token generate/hash/verify, NDJSON parsing, `IngestService`.
- NEW `ingest_router.py` — bearer-auth `POST /ingest/experiment-runs/{run_id}` (own
  APIRouter, no cookie deps, no CSRF).

`apps/api/researchos/figures/` (all NEW):
- `__init__.py`; `enums.py` (`AnchorAggregation`, `FigureRenderStatus`);
- `models.py` — `ResultAnchor`, `Figure`, `FigureAsset`;
- `presets.py` — `StylePreset` + `PRESETS` registry (D5);
- `spec.py` — `FigureSpecModel` + series/source models + caps;
- `macros.py` — `render_macros_tex(resolved: list[ResolvedAnchor], *, project_id, generated_at) -> str` (pure, deterministic);
- `schemas.py` — anchor/figure/staleness/preset DTOs;
- `repository.py` — `AnchorRepository`, `FigureRepository`, `FigureAssetRepository`
  (asset upsert by `(figure_id, format)`);
- `anchor_service.py` — CRUD, `_resolve`, `refresh_all`, `staleness_report`,
  `mark_stale_for_experiment`, macros endpoint logic;
- `figure_service.py` — CRUD, `_resolve_series`, sync render, async dispatch +
  broker-failure fallback, asset read (ETag), run-artifact upsert,
  `mark_stale_for_run`, `style_outdated` computation;
- `render.py` — `render_figure_bytes` (pure matplotlib, lazy import, Agg);
- `render_job.py` — `run_figure_render(figure_id)` async job (worker entry body);
- `dispatch.py` — `dispatch_figure_render(figure_id)` via
  `common.celery_app.get_celery_client().send_task("experiments.render_figure", …, queue="experiments")`;
- `events.py` — envelope builders (SHOULD);
- `router.py` — anchors + figures + style-presets routes
  (prefix `/projects/{project_id}`, tags `["figures"]`).

`apps/api/researchos/preferences/` (all NEW):
- `__init__.py`; `models.py` (`UserPreference`); `schemas.py` (scope DTO +
  validation of theme/language/slug/extra); `service.py` (`effective`, `get_scope`,
  `put_scope` upsert); `router.py` — two routers: `me_router`
  (prefix `/users/me/preferences`) and `project_router`
  (prefix `/projects/{project_id}/preferences`).

`apps/worker/researchos_worker/tasks/`:
- NEW `figures.py` — `@app.task(name="experiments.render_figure")` thin wrapper:
  `run_async_task(lambda: run_figure_render(figure_id))`, mirroring `tasks/agents.py:18-24`.

`apps/api/tests/` (NEW files; see Test plan): `test_experiment_directions.py`,
`test_experiments_hardening.py`, `test_anchors.py`, `test_figures.py`,
`test_figure_render_unit.py`, `test_preferences.py`, `test_ingest.py`.

---

## Cross-partition requests

1. **`apps/api/researchos/main.py`** (app owner/consolidator): add imports and
   `app.include_router(...)` for: `researchos.figures.router.router`,
   `researchos.preferences.router.me_router`,
   `researchos.preferences.router.project_router`,
   `researchos.experiments.ingest_router.router`.
2. **`apps/api/researchos/models.py`** (aggregator): import + `__all__` for
   `ResultAnchor`, `Figure`, `FigureAsset` (from `researchos.figures.models`),
   `UserPreference` (from `researchos.preferences.models`),
   `ExperimentIngestToken` (from `researchos.experiments.models`).
3. **`apps/worker/researchos_worker/app.py`** (runtime-llm spec): extend `include=`
   list (line 24) with `"researchos_worker.tasks.figures"`.
4. **`apps/api/researchos/websocket/envelopes.py`** (realtime owner): extend
   `ResourceType` literal (line 15) with `"figure"`. Figure WS events ship only after
   this lands; everything else is independent.
5. **`apps/api/researchos/agents/runtime/experiment_agent.py`** (runtime-llm spec):
   replace the direction heuristic. Desired change: `_summarize` gains a
   `metric_meta: dict` parameter; line 35 becomes
   `direction = metric_direction(name, metric_meta)` /
   `best[name] = min(values) if direction == "min" else max(values)` with
   `from researchos.experiments.directions import metric_direction`; both call sites
   obtain meta via
   `await ExperimentService(actx.db).get_metric_meta_for_run(actx.actor, actx.project_id, uuid.UUID(str(run_id)))`
   (method provided by this spec). No mock-provider change is required (no new agent
   mode; ExperimentAgent's deterministic summary path is unchanged in shape).
6. **`apps/api/tests/conftest.py`** (test-infra owner/consolidator): extend `_TABLES`
   truncation list (children first):
   `"figure_assets", "figures", "result_anchors", "experiment_ingest_tokens", "user_preferences"`.
7. **shared-schemas** — see "shared-schemas additions" (consolidated by the dedicated
   agent).

---

## MUST / SHOULD / STRETCH breakdown

**MUST** (core, self-contained, no cross-partition blockers except #1/#2/#6):
- IDOR fix (`list_runs`), transition guard + `started_at`/`finished_at` fixes,
  atomic log seq (`log_next_seq` + unique constraint), `PATCH /experiments/{eid}` +
  `metric_meta_json`, `directions.py`, `get_metric_meta_for_run`.
- Result anchors: model, CRUD, resolution, refresh, staleness report,
  run-completion staleness hook, `macros.tex` endpoint.
- Figures: model + spec validation, presets registry, `render.py`, **sync** render
  path with caps + rate limit, asset storage + `GET assets/{fmt}` with ETag,
  run-artifact linking, figure staleness hook, style-presets endpoint.
- Preferences: model + both GET/PUT surfaces + effective resolution.
- `matplotlib` dependency entries.

**SHOULD**:
- Celery async render (`dispatch.py`, `render_job.py`, worker `tasks/figures.py`,
  broker-failure sync fallback; cross-partition #3).
- WS events: experiment run/metric/log producers (existing contract strings) +
  `anchor.values.updated`; figure events once #4 lands.
- NDJSON ingest + per-project ingest tokens (D7).
- `style_outdated` reporting on figure responses.

**STRETCH**:
- Per-preset preview render endpoint (fixture dataset → PNG, cached in
  `figure_assets`-style rows keyed by preset slug).
- `GET /projects/{id}/figures/{fid}/latex` — canned `\begin{figure}` snippet with
  `% researchos:figure {id}` provenance comment for manual paste.
- Downsampling density parameter + per-series linestyle overrides in FigureSpec.
- Ingest client shim example script (docs-only; `scripts/` is outside this partition).

Degradation is clean: SHOULD items are additive routers/tasks/events; nothing in MUST
imports them.

---

## Acceptance criteria (each verifiable via local gates or code reading)

1. `ruff check` + `mypy` pass on `apps/api` and `apps/worker`; `tsc`/`next build`
   unaffected (no owned JS changes).
2. Code reading: `experiments/service.py::list_runs` loads the experiment scoped by
   `project_id` and raises `NotFoundError` before listing runs.
3. Code reading: no `COUNT(*)`-based seq remains in `experiments/repository.py`;
   `allocate_log_seqs` uses a single `UPDATE … RETURNING`; `ExperimentLog` declares
   the `(run_id, seq)` unique constraint.
4. Code reading: `directions.py` is pure (no DB/network imports); explicit
   `metric_meta` direction takes precedence over the heuristic; `"perplexity"`,
   `"wer"` map to `min` by default.
5. Code reading: `render.py` imports matplotlib only inside functions, sets Agg, and
   is called from exactly two places (sync endpoint via `to_thread`, `render_job.py`).
6. Code reading: sync render enforces ≤ 4 series / ≤ 2000 points / rate limit before
   rendering; asset writes reject > 4 MB; assets are upserted (no growth per re-render).
7. Code reading: ingest router has no cookie/CSRF dependency; tokens stored as sha256
   hex only; plaintext token appears solely in the create response.
8. Code reading: `macros.tex` output is deterministic (sorted by name), always emits a
   `\newcommand` per anchor, and never raises for unresolved anchors.
9. Code reading: preferences queries always filter `user_id = actor.id`; effective
   resolution is field-wise project → global → defaults.
10. CI: the pytest suite below passes (no external network; matplotlib renders
    offline; NDJSON tests use in-process ASGI client).

## Test plan (CI-run pytest; follows `apps/api/tests/conftest.py` conventions)

- `test_experiment_directions.py` (pure, no DB): direction precedence
  (explicit min beats accuracy-heuristic; `perplexity`/`wer`/`rmse` → min;
  `accuracy` → max), `dedupe_points` keeps latest duplicate step, `reduce_series` for
  all five aggregations incl. empty series → None.
- `test_experiments_hardening.py` (DB): IDOR — user B (member of project 2 only)
  gets 404 for `GET /projects/{p2}/experiments/{exp_in_p1}/runs`; terminal→RUNNING
  PATCH → 409 `invalid_transition`; QUEUED→RUNNING sets `started_at`; →CANCELLED sets
  `finished_at`; 20 concurrent `append_log` calls (asyncio.gather) yield unique seqs;
  `PATCH /experiments/{eid}` persists `metric_meta` and rejects bad directions (422).
- `test_anchors.py` (DB): CRUD + duplicate-name 409 + macro-name validation 422;
  resolution — pinned run vs latest-completed; `best` respects metric_meta direction;
  formatting `decimals/scale/suffix`; `macros.tex` golden-string comparison incl.
  unresolved anchor; staleness — complete a newer better run → hook flips `stale`,
  staleness report shows delta; refresh clears stale and captures.
- `test_figure_render_unit.py` (pure, no DB): `render_figure_bytes` over inline data
  for line/bar/scatter × two presets returns non-empty SVG starting `<?xml`/`<svg` and
  PNG with `\x89PNG` magic; same input twice → identical SVG bytes (determinism);
  preset registry invariants (unique slugs, semver strings, palette non-empty,
  rcparams keys within the documented allowlist).
- `test_figures.py` (DB): create with cross-project run id → 404; spec caps → 422;
  sync render persists both assets, sets status/`source_run_ids`/style stamps, links
  a run artifact with `metadata_json.figure_id`; asset GET returns correct
  content-type + ETag and 304 on If-None-Match; oversized sync spec → 422
  `figure_too_large_for_sync`; run completion flips figure `stale`.
- `test_preferences.py` (DB): defaults when empty; global PUT then project PUT —
  effective merges field-wise; PUT full-replace clears omitted fields; unknown
  theme/slug → 422; user A's rows invisible to user B.
- `test_ingest.py` (DB, SHOULD scope): token create returns plaintext once, list is
  masked; ingest with valid token inserts metrics/logs (seqs contiguous) without any
  cookie; mixed batch → partial `accepted`/`rejected` with line numbers; revoked
  token → 401; token from another project → 404; status line `completed` transitions
  the run and triggers anchor staleness; > 1000 lines → 413.
- Worker task registration smoke (extends `apps/worker/tests` pattern): importing
  `researchos_worker.tasks.figures` registers task name `experiments.render_figure`
  routed to the `experiments` queue.

## Explicitly out of scope

- All frontend work (settings page consumption, figure gallery UI, staleness gutter
  badges, Recharts restyling) — web partition.
- MinIO/object-storage abstraction; artifact byte upload for arbitrary artifacts
  (`{"t":"artifact"}` NDJSON lines are rejected as unknown-type lines).
- Writing anchors/figures into `document_files` or any `\begin{figure}` auto-insertion
  (documents partition; superseded design noted above).
- Run-comparison LaTeX table generator + paper-asset inbox (WS3-5) and the provenance
  graph (WS8-2).
- Per-run tokens and the pip-installable client shim package.
- Real experiment execution, heartbeats/zombie detection, metric pagination/
  downsampling on the existing list endpoints, and the seeded demo data updates
  (`seed/demo.py` is outside this partition).
