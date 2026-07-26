# Spec: coding-git — NL-to-code core + git traceability

Workstream: WS2 (owner wishlist items 5 & 6). Realizes INNOVATION_IDEAS WS2-1 (agent eyes +
read-before-write), WS2-2 (diff-native patches), WS2-3 (git-backed workspace), plus the
brief's atomic-apply, CONFLICT-unstick, multi-turn chat, and `base_sha` hole fixes.

Partition (files this spec's implementer owns):
`apps/api/researchos/agents/runtime/tools.py`, `apps/api/researchos/agents/runtime/coding_agent.py`,
`apps/api/researchos/patches/**`, `apps/api/researchos/git/**`, `apps/api/researchos/workspace/**`,
`apps/api/researchos/common/paths.py`, plus NEW module `apps/api/researchos/coding_chat/**`
(claimed here; registration in unowned files is a cross-partition request) and new test files
under `apps/api/tests/`.

---

## Objective (user-visible outcome)

1. The coding agent can actually **see** the workspace: it reads files (line-ranged, budgeted)
   and greps before proposing changes, so "modify" patches are grounded in real content instead
   of hallucinated whole-file rewrites.
2. Patches become **diff-native**: the agent emits Aider-style SEARCH/REPLACE edit blocks; the
   server resolves them against a snapshotted base, materializes the new content, and renders
   real per-hunk diffs in review. Whole-file content remains for create; delete needs neither.
3. Applying a patch is **atomic** (temp + fsync + rename, full rollback on any failure) and
   produces a **real git commit** in the project workspace (author = acting user, trailers link
   patch/run, `Co-Authored-By: codex <noreply@anthropic.com>` per project convention).
4. The IDE gets real **git history**: per-file and global log, per-commit diff, one-click
   safe revert (never history rewrite), and a real `git status` (porcelain parsing) replacing
   the stub. Everything degrades gracefully when the `git` binary is absent.
5. CONFLICT patches are no longer a dead end: they can be rejected, and (SHOULD) re-proposed
   via an agent re-run seeded with the conflict details.
6. Coding becomes a **conversation**: chat sessions persist message history; each new message
   spawns a coding run that sees prior turns.

## Superseded prior decisions

- **P3-D4** ("whole-file replacement; `patch_hunks` display-only") — superseded. Patches may
  now carry SEARCH/REPLACE edits; the server *materializes* `new_content` at proposal time, so
  the apply path remains whole-file guarded by `base_sha` (the safe part of P3-D4 is retained),
  and `patch_hunks` become real server-derived unified-diff hunks. Rationale: whole-file LLM
  output is the single largest source of corrupted patches and token waste (INNOVATION WS2-2).
- **P3-D10** ("git = read-only stub, reserved interface") — superseded. Real git with
  lazy per-workspace init, auto-commit on apply, log/diff/revert. The non-negotiable core of
  P3-D10 is retained: **no destructive operations ever** — no reset/rebase/force/checkout of
  history; revert is an additive inverse commit.
- **PHASE3 "Known limitations" #1** (mid-write partial apply) — resolved by atomic apply.
- **P3-D5 (AI never writes) is NOT superseded**: the agent still only proposes; apply remains
  a user-initiated, CSRF-protected, role-checked action. Git commits happen only inside that
  user-initiated apply (and revert), never from the worker.
- **P3-D14** (sync FS I/O) retained; git subprocess calls are wrapped in `asyncio.to_thread`.

---

## Current state (concrete, file:line)

- `agents/runtime/coding_agent.py:52` — `allowed_tools = ["workspace.tree"]`; the agent cannot
  read file contents. `_SYSTEM` (lines 20–26) demands whole-file `new_content` and a guessed
  `base_sha`. `finalize` (61–109) silently drops invalid entries (`continue` at 85 and 90) and
  a JSON parse failure yields a COMPLETED run with no patch and no error (71–73).
- `agents/runtime/tools.py:99-125` — registry has exactly 3 read-only tools; no file read, no
  grep. `ToolBroker.execute` (135–191) **raises** on unknown/denied tool (153–159) and on any
  tool exception (163–169), which fails the whole run (ARCHITECTURE_MAP §2 #27).
- `agents/runtime/runtime.py:181` — global `settings.agent_max_tool_calls` (=4,
  `common/config.py:103`) applies to all agent types; multi-file work is impossible.
  (runtime.py is owned by the runtime-llm spec — hooks requested below.)
- `patches/service.py:117-147` — conflict scan compares `current != f.base_sha`; for MODIFY
  with `base_sha=None` and a missing file, `None == None` passes and **silently creates** the
  file (the "None==None hole"). DELETE of an already-deleted file conflicts (132: `current
  (None) != base_sha`). Lines 149–158: apply loops `fs.write_file` per file — non-atomic, no
  rollback, no backup; `write_file` itself (`workspace/fs.py:120-127`) is a bare
  `write_bytes` with no temp/rename. `PatchStatus.CONFLICT` is terminal-in-practice:
  `apply_patch`/`reject_patch` both require PENDING (114, 168–169).
- `patches/models.py:55-56` — `PatchFile` stores only `base_sha` + `new_content`; no base
  content snapshot. `PatchHunk` (64–79) exists but nothing populates it ("display-only", dead).
- `git/provider.py:23-29,44-45` — `StubGitStatusProvider` always returns clean/`main`;
  `ReadOnlyGitStatusProvider.status` raises `NotImplementedError`. `git/service.py` and
  `git/router.py` expose only `GET /projects/{id}/git/status`.
- `common/paths.py:33` — `DENY_DIR_NAMES = {".git"}` already hides git internals from the
  tree and from patch paths (kept; git access goes through subprocess `cwd`, never through
  `resolve_in_workspace`).
- `workspace/fs.py:72-110` — `read_file` reads whole files (1 MB cap), no line ranges; no grep
  anywhere. `workspace/service.py:27-30` wraps it with VIEWER auth.
- `coding_agent/router.py` (NOT owned) — one-shot `POST /projects/{id}/coding-agent/runs`
  with `context={}`; no conversation persistence anywhere.
- `agents/llm/mock.py:68-83` (NOT owned) — mock coding output is a `create` of
  `AGENT_NOTES.md` with `new_content`; it never modifies, so it remains valid under the new
  validation rules unmodified (extension requested cross-partition to exercise the new path).
- `infra/docker/python.Dockerfile` — `python:3.13-slim` base; **no git binary installed**.

---

## Design (algorithms & data flow)

### D1. Agent eyes: `workspace.read` + `workspace.grep` + budgets (tools.py, workspace/fs.py)

**ToolContext additions** (`tools.py`):

```python
@dataclass
class ToolContext:
    ...existing fields...
    read_paths: dict[str, str] = field(default_factory=dict)   # rel path -> full-file sha at read time
    read_bytes_used: int = 0                                   # budget accounting
```

**`workspace.read`** — params `{path: str, start_line?: int, end_line?: int}` (1-based,
inclusive). Implementation `_workspace_read(ctx, args)`:

1. VIEWER access is already implied (the run's actor passed project auth); call a new
   `fs.read_file_range(project_id, path, start_line, end_line, max_lines)`:
   - resolves via `resolve_in_workspace` (403 on denied/escape),
   - reads full raw bytes (existing 1 MB / binary checks from `fs.read_file` reused),
   - computes `sha = sha256_hex(raw)` over the **whole file** (this is the value the
     `base_sha` guard compares, so ranged reads still record the correct sha),
   - slices `[start_line-1 : end_line]`, clamped to `settings.workspace_read_max_lines`
     (default 400) lines per call; sets `truncated=True` when clamped or when the requested
     window exceeded the cap.
2. Budget: before returning, `ctx.read_bytes_used += len(content_bytes)`. If the *pre-call*
   `read_bytes_used >= settings.workspace_read_budget_bytes` (default 262_144), do not read;
   return `{"error": {"code": "read_budget_exhausted", "message": "..."}}`.
3. Success result:
   `{path, content, start_line, end_line, total_lines, sha, truncated}`.
4. Record `ctx.read_paths[path] = sha` (overwrites on re-read — last read wins).
5. Binary / too-large files return `{"error": {"code": "unreadable_file", "message": ...}}`
   (not a raised exception).

**`workspace.grep`** — params `{pattern: str, glob?: str, max_results?: int,
ignore_case?: bool}`. Implementation `_workspace_grep` → new `fs.grep_files(project_id,
pattern, glob, max_results, ignore_case)`:

1. `re.compile(pattern, re.IGNORECASE if ignore_case else 0)`; `re.error` →
   `{"error": {"code": "invalid_pattern", "message": str(exc)}}`.
2. Walk the workspace with `os.walk`, applying `is_denied` per relative path (skips `.git`,
   `.ros-staging`, deny-listed files), honoring `glob` via `fnmatch` on the relative posix
   path.
3. Bounds (all deterministic): max 2000 files scanned; skip files whose size >
   `settings.workspace_grep_max_file_bytes` (default 200_000) or whose first 8 KB contain
   NUL; per matched line, emit at most 300 chars; stop at
   `min(max_results, settings.workspace_grep_max_results)` (default cap 50) matches.
4. Result: `{"matches": [{"path", "line_no", "line"}], "truncated": bool,
   "files_scanned": int}`.

**Registry entries** (JSON-schema `parameters` mirroring the arg shapes above) are added to
`TOOL_REGISTRY` as `"workspace.read"` and `"workspace.grep"`.

**ToolBroker becomes non-fatal** (fixes ARCHITECTURE_MAP §2 #27 for every agent):
`execute()` never raises for tool-level problems. Three cases now return a structured error
payload `{"error": {"code", "message"}}` while persisting the ToolCall row as FAILED and
emitting `tool_call.completed(status="failed")`:
- unknown tool name → code `"unknown_tool"`,
- tool not in `ctx.allowed_tools` → code `"tool_denied"`,
- implementation raised → code `"tool_failed"`, message `str(exc)` (the exception is logged;
  `WorkspaceAccessError` and `AppError` subclasses use their own `code`).
`ToolDenied` stays defined (imports elsewhere keep working) but is no longer raised from
`execute`. `result_summary` becomes content-aware: `"N match(es)"` for grep, `"N line(s)"`
for read, `"N result(s)"` otherwise, `"error: <code>"` for error payloads. The citation
whitelist growth loop is unchanged (error payloads have no `results` key).

Runtime impact: `runtime.py:183` already just forwards `broker.execute`'s return value into a
`role="tool"` message — the agent sees the error JSON and can retry; no runtime change
required for this to work.

**Per-agent tool budget**: `CodingAgent.max_tool_calls = 25` (new class attribute; see
cross-partition request CP-2/CP-3 for `base.py`/`runtime.py` honoring it). Without the
runtime change the system still works at the global budget of 4 (degraded but functional).

### D2. Read-before-write enforcement (coding_agent.py)

New `_SYSTEM` prompt (exact intent, implementer words it):
- tools available: `workspace.tree`, `workspace.read`, `workspace.grep`;
- **read any file before modifying or deleting it**; take `base_sha` verbatim from the
  `workspace.read` result;
- respond with JSON `{summary, files: [{path, change_type, base_sha, new_content?, edits?}]}`;
- for `modify` prefer `edits`: a list of `{search, replace}` blocks where `search` is copied
  **verbatim** from the file with at least 3 lines of surrounding context and must be unique
  in the file; for `create` use `new_content`; for `delete` provide neither.

`_SCHEMA` gains `edits: {"type": ["array","null"], items: {search: string,
replace: string}}` on file items.

`finalize` algorithm (replaces silent dropping):

1. Lenient JSON extraction: try `json.loads(output_text)`; on failure, retry on the substring
   from the first `{` to the last `}` (real providers wrap JSON in prose/fences); on failure
   → `output_json = {"message": "", "patch_id": None, "file_count": 0,
   "error": "parse_failure"}` and return (run COMPLETED but the error is now *visible*).
2. Per file entry, collect `violations: list[{path, reason, detail?}]` instead of dropping:
   - Pydantic/`resolve_in_workspace` failure → reason `invalid_path` / `workspace_denied`.
   - `change_type in (modify, delete)` and `path not in actx.tool_ctx.read_paths` → reason
     `unread_file` ("read the file with workspace.read before modifying it").
   - For read paths, **the server overrides `base_sha` with the recorded read sha**
     (`tool_ctx.read_paths[path]`) — the agent's echo is advisory; the sha the broker served
     is authoritative. (Kills a whole class of copy-error conflicts.)
   - `modify` with neither `new_content` nor `edits`, or with both → reason `invalid_change`.
   - `create` with `edits` or without `new_content` → `invalid_change`; `create` gets
     `base_sha=None` forced.
3. Call `PatchService.create_proposal` with the surviving files. Per-file edit-resolution
   failures (see D3) are returned by the service as structured
   `EditResolutionFailure(path, index, reason)` — folded into `violations`, and the proposal
   is created from the files that resolved cleanly (patch is all-or-nothing per *file*, not
   per proposal). Zero surviving files → no patch.
4. `output_json = {"message": summary, "patch_id", "file_count",
   "rejected_files": violations}` — rejected files are now first-class, user-visible output.
5. Chat integration (D7): if `actx.context.get("chat_session_id")`, insert an assistant
   `ChatMessage` (content = summary or the parse/violation error text, `agent_run_id`,
   `patch_id`).

SHOULD — self-repair round (needs CP-3 `prevalidate` hook): implement
`async def prevalidate(self, actx, output_text) -> str | None` on `CodingAgent` returning a
feedback string listing violations/resolution failures when any exist (else `None`); the
runtime appends it as a `role="user"` message and re-streams **once**. Finalize then runs on
the corrected output. Without the hook, step 2–4 behavior stands alone.

### D3. Diff-native patches: SEARCH/REPLACE resolution + base snapshots (patches/**)

**New pure module `patches/resolution.py`** (no DB, fully unit-testable):

```python
@dataclass(frozen=True)
class EditBlock:
    search: str
    replace: str

@dataclass(frozen=True)
class EditFailure:
    index: int
    reason: Literal["empty_search", "not_found", "ambiguous"]

class EditResolutionError(Exception):
    def __init__(self, failures: list[EditFailure]): ...

def resolve_edits(base: str, edits: list[EditBlock]) -> str: ...
def compute_hunks(base: str, new: str, n: int = 3) -> list[HunkData]: ...
```

`resolve_edits` applies blocks **sequentially** to the evolving text. Per block:
1. `search == ""` → `EditFailure(empty_search)`.
2. **Exact match**: `text.count(search)`; 1 → `text.replace(search, replace, 1)`;
   \>1 → `ambiguous`; 0 → step 3.
3. **Whitespace-fuzzy line match**: split text and `search` into lines (trailing empty line
   of `search` trimmed). Slide a window of `len(search_lines)` over the text lines; a window
   matches iff `text_line.strip() == search_line.strip()` for every pair. Exactly one
   matching window required (0 → `not_found`, >1 → `ambiguous`). On match, compute the
   indent delta between the window's first line and the search's first line
   (`len(indent(text_first)) - len(indent(search_first))`) and apply that constant shift to
   every non-empty `replace` line, then splice the window.
4. All failures are collected across blocks (resolution continues past a failed block on the
   text-so-far so the agent gets the full failure list) and raised together as
   `EditResolutionError` if any occurred.
5. STRETCH: level-3 fallback via `difflib.SequenceMatcher` best window with ratio ≥ 0.9.

`compute_hunks` runs `difflib.unified_diff(base_lines, new_lines, n=3)` and parses `@@ -a,b
+c,d @@` headers into `HunkData(header, old_start, old_lines, new_start, new_lines, content)`
where `content` is the hunk's body (context + -/+ lines, `\n`-joined).

**Schema changes** (`patches/schemas.py`):
- New `PatchEditInput {search: str, replace: str}` (search `min_length=1`).
- `PatchFileInput`: `+ edits: list[PatchEditInput] | None = None`; **remove**
  `hunks: list[PatchHunkInput]` from the input (hunks are now server-derived only —
  `PatchHunkInput` deleted; breaking change flagged for shared-schemas). Model validator:
  - `create` → `new_content` required, `edits` and `base_sha` must be absent/None;
  - `modify` → exactly one of `new_content` / `edits`; `base_sha` **required** (closes the
    None==None hole at the schema boundary);
  - `delete` → no `new_content`, no `edits` (`base_sha` optional; filled from live at
    creation).
- `PatchFileResponse`: `+ base_content: str | None`, `+ edits: list[PatchEditResponse]`
  (echo of `edits_json`).
- `PatchResponse`: `+ applied_commit_sha: str | None`, `+ conflicts: list[PatchConflict]`
  (from `conflict_json`, empty unless status is/was CONFLICT), `+ superseded_by: uuid | None`.
- `ApplyResultResponse`: `+ applied_commit_sha: str | None = None`.

**`PatchService.create_proposal`** (service.py) new algorithm:

1. Path-guard all files (existing `_validate_paths`).
2. Per file:
   - `modify`: `data = fs.read_file(project_id, path)`. If missing → per-file failure
     `base_missing`. If binary/too-large: `edits`-based → per-file failure
     `unpatchable_binary`; whole-file `new_content` → allowed, `base_content=None`
     (degraded, as today). Else `base_content = data["content"]`, `live_sha = data["sha"]`.
     - If `edits` present: require `live_sha == base_sha` (the agent read moments ago;
       mismatch = concurrent edit) → else per-file failure `base_changed`. Then
       `new_content = resolve_edits(base_content, edits)`; `EditResolutionError` → per-file
       failures surfaced. Store `edits_json`.
     - If `new_content` present (UI path): store as given; if the caller's `base_sha` is
       stale vs live, keep it — the apply-time guard reports the conflict (unchanged
       optimistic-concurrency semantics).
     - Compute hunks: `compute_hunks(base_content, new_content)` → `PatchHunk` rows.
   - `delete`: read live file; missing → per-file failure `base_missing`; else snapshot
     `base_content`, fill `base_sha = live_sha` when the caller sent None.
   - `create`: if a live file exists → per-file failure `already_exists` (early, instead of
     a guaranteed later conflict). `base_content = None`.
3. Files with failures are excluded from the proposal; the failure list is returned to the
   caller (`create_proposal` returns `tuple[PatchProposal | None, list[FileFailure]]`;
   `create_patch` — the human REST path — raises `ValidationError` with
   `details={"files": failures}` if *any* file fails, keeping the human API strict, while
   the agent path folds failures into `rejected_files`).
4. Proposal + files + hunks flushed as today.

### D4. Atomic apply + fixed conflict semantics (patches/service.py, workspace/fs.py)

**Conflict scan** (replaces service.py:117-147):
- CREATE: `current is not None` → conflict `"file already exists"`.
- MODIFY: `current is None` → conflict `"file missing"`; `current != base_sha` → conflict
  `"base content changed"`. (`base_sha` is non-null by schema, so `None==None` cannot pass.)
- DELETE: `current is None` → **satisfied no-op** (idempotent delete — fixes ARCH §2 #34's
  already-deleted dead end); else `current != base_sha` → conflict.
- On conflicts: `status=CONFLICT`, `conflict_json = [conflict.model_dump()...]` persisted
  (needed for D6 re-propose and for the UI after refresh), commit, return.

**`fs.apply_files_atomic(project_id, ops: list[FileOp]) -> dict[str, str]`** where
`FileOp = (path, action: "write"|"delete", content: str | None)`:

1. Staging dir `<root>/.ros-staging/<uuid4hex>/` (same filesystem as targets ⇒ `os.replace`
   is atomic). `.ros-staging` joins `DENY_DIR_NAMES` in `common/paths.py` so it is invisible
   to the tree, unreachable by patches/reads, and skipped by grep. Best-effort cleanup of
   stale `.ros-staging/*` entries older than 24 h runs at the start of each apply.
2. **Phase A (prepare — nothing user-visible touched):** for each write op `i`: write
   `staging/stage-{i}` with the UTF-8 content, `flush` + `os.fsync(fd)`. Resolve and guard
   every target path. Any failure → `shutil.rmtree(staging)`, raise; workspace untouched.
3. **Phase B (commit — journaled renames):** for each op in order, appending a journal entry
   after each successful step:
   - `modify`/`delete`: `os.replace(target, staging/backup-{i})` (the original is moved
     aside, not copied — restorable byte-identically).
   - `write` (create/modify): `target.parent.mkdir(parents=True, exist_ok=True)`, then
     `os.replace(staging/stage-{i}, target)`.
4. **Rollback on any Phase B exception:** walk the journal in reverse — placed files are
   moved back to staging (or unlinked for creates), backups are restored via
   `os.replace(backup → target)`. Then raise `WorkspaceApplyError(rolled_back=True)`. If a
   rollback step itself fails, keep restoring the rest, then raise
   `WorkspaceApplyError(rolled_back=False)` (logged critical; patch stays PENDING and
   `base_content` snapshots + git make manual recovery possible).
5. Success: fsync parent dirs where supported (POSIX; `try/except OSError` for Windows),
   `shutil.rmtree(staging, ignore_errors=True)`, return `{path: sha256_hex(content)}` for
   writes.

`fs.write_file` / `fs.delete_file` remain for non-patch callers but `apply_patch` no longer
uses them.

**`apply_patch` phase 2** becomes: build ops from proposal files (skipping satisfied
deletes) → `apply_files_atomic` → on `WorkspaceApplyError` raise `AppError`
(`code="apply_failed"`, http 500, message states whether rollback succeeded); patch stays
PENDING and can be retried. On success → git auto-commit (D5) → `status=APPLIED`,
`applied_at`, `applied_commit_sha` persisted → single commit → response includes
`applied_commit_sha`.

**Reject from CONFLICT** (D6 part 1): `reject_patch` precondition becomes
`status in (PENDING, CONFLICT)`.

### D5. Real git (git/**)

**New `git/runner.py`:**

```python
_SHA_RE = re.compile(r"^[0-9a-f]{7,64}$")

@lru_cache(maxsize=1)
def git_available() -> bool:            # settings.git_enabled and shutil.which("git")
class GitError(AppError): code="git_error"; http_status=500
class GitDisabled(AppError): code="git_disabled"; http_status=409

def run_git(root: Path, *args: str, timeout: float | None = None,
            check: bool = True) -> subprocess.CompletedProcess[str]
```

`run_git` executes `["git", "-C", str(root), *args]` with `capture_output=True, text=True,
encoding="utf-8", errors="replace"`, `timeout=settings.git_timeout_seconds` (default 10.0),
env overrides `GIT_TERMINAL_PROMPT=0`, `GIT_CONFIG_NOSYSTEM=1`. Injection safety: no shell;
user-supplied shas must match `_SHA_RE`; user-supplied paths go through
`resolve_in_workspace` first and are passed after a literal `--`. `check=True` raises
`GitError` embedding a truncated stderr. Async call sites wrap in `asyncio.to_thread`.

**`git/service.py` (GitService) methods** (all take `actor` and call `ensure_access`;
per-project `asyncio.Lock` around mutating ops — apply-commit and revert both run in the API
process, and git's own `index.lock` covers any cross-process race by turning it into a
logged commit failure):

- `ensure_repo(project_id) -> bool`: `fs.ensure_workspace`; False when `not
  git_available()`. If `<root>/.git` missing: `git init`, `git symbolic-ref HEAD
  refs/heads/main`, `git config user.name "ResearchOS"`, `git config user.email
  "bot@researchos.local"`, `git commit --allow-empty -m "researchos: initialize workspace"`.
  Idempotent.
- `status(actor, project_id)`: delegates to the provider (below). Does **not** init a repo
  (read path stays side-effect free); an uninitialized workspace reports
  `provider="git", branch="main", clean=True, files=[]`.
- `log(actor, project_id, *, path=None, limit=50, skip=0)`: VIEWER. No repo / disabled →
  `[]`. `git log --format=%H%x1f%an%x1f%ae%x1f%aI%x1f%s%x1f%b%x1e -n {limit} --skip {skip}
  [-- {rel_path}]`. Parse records on `\x1e`, fields on `\x1f`; extract trailers `Patch:`,
  `Agent-Run:`, `Reverts:` from the body via `^(Patch|Agent-Run|Reverts):\s*(\S+)$`
  multiline regex. Returns `GitCommitEntry` list.
- `commit_diff(actor, project_id, sha)`: VIEWER. Validate sha. `git show --format=%H%x1f%an%x1f%aI%x1f%s
  --name-status {sha}` → per file `A/M/D/R###` with path(s). For each file:
  `old_content = git show {sha}^:{path}` (omitted for A and for root commits — detect via
  `git rev-parse --verify {sha}^` failure), `new_content = git show {sha}:{path}` (omitted
  for D). Contents larger than `workspace_max_file_bytes` or containing NUL are returned as
  `omitted=True` with `size`. Deny-listed paths (`is_denied`) are omitted entirely.
- `commit_applied_patch(project_id, *, summary, patch_id, agent_run_id, author_name,
  author_email, paths) -> str | None`: `ensure_repo`; False → None. `git add -A --
  {*rel_paths}`; commit message:

  ```
  {summary first line, ≤72 chars, fallback "Apply patch"}

  Patch: {patch_id}
  Agent-Run: {agent_run_id or "-"}

  Co-Authored-By: codex <noreply@anthropic.com>
  ```

  with `--author "{author_name} <{author_email}>"`. Returns `git rev-parse HEAD`. **Any git
  failure here logs a warning and returns None — it never fails the apply** (git is
  traceability, feature-flagged; the FS apply already succeeded).
- `revert(actor, project_id, sha) -> GitRevertResponse`: RESEARCHER. `GitDisabled` when git
  unavailable. Preconditions: repo exists; working tree clean (`git status --porcelain`
  empty) else `ValidationError("workspace has uncommitted changes")`. Run `git revert
  --no-commit --no-edit {sha}`; on failure `git revert --abort` (best-effort) and raise
  `ValidationError` with the stderr snippet (typical cause: revert conflicts). Then commit
  with author = acting user, message `Revert "{original summary}"` + trailers `Reverts:
  {sha}` and the Co-Authored-By line. Returns `{commit_sha, reverted_sha}`.

**`git/provider.py`:** `StubGitStatusProvider` is replaced by:
- `RealGitStatusProvider` — `git status --porcelain=v1 --branch --untracked-files=all`.
  Header `## <branch>...` (also handles `## No commits yet on main` and detached HEAD) →
  `branch`, `[ahead N, behind M]` → ahead/behind. Entry mapping from the XY code:
  `??`→untracked, first-significant-of-XY `A`→added, `M`→modified, `D`→deleted,
  `R`→renamed (path taken from the `old -> new` right side). `clean = no entries`.
  Missing repo → pristine response as above.
- `DisabledGitStatusProvider` — `provider="disabled", branch="", clean=True, files=[]`.
- `get_git_provider()` returns Real iff `git_available()` else Disabled. The
  `ReadOnlyGitStatusProvider` placeholder class is deleted.

Degradation matrix (git absent or `GIT_ENABLED=false`): status shows `provider="disabled"`;
log returns `[]`; diff/revert return 409 `git_disabled`; patch apply skips the commit
(`applied_commit_sha=None`) and everything else works. No code path requires git for core
function.

### D6. Unsticking CONFLICT patches

1. (MUST) `reject_patch` accepts CONFLICT (D4). `conflict_json` persisted at conflict time.
2. (SHOULD) `POST /patches/{patch_id}/repropose` (`patches/router.py` + service):
   - Preconditions: status == CONFLICT, `agent_run_id` is not None (agent-authored),
     RESEARCHER + CSRF.
   - Loads the originating run's `input_json` (message + context). Creates a new coding
     `AgentRun` via `AgentRunService.create_run` with the same message and
     `context = {**old_context, "repropose_of": str(patch_id)}` (keeps
     `chat_session_id` when present).
   - Sets `old.superseded_by = <new patch id>` later: `CodingAgent.finalize` checks
     `context["repropose_of"]`, and after creating the new proposal updates the old
     proposal's `superseded_by` and flips its status to REJECTED (terminal, auditable).
   - `CodingAgent.build_messages` with `repropose_of` present appends a system-message
     appendix: the old proposal's summary, per-file `conflict_json` entries, and each
     conflicted file's *stored* `base_content` vs a note that the live file changed —
     with the instruction "re-read every conflicted file with workspace.read and re-anchor
     your edits to the current content".
   - Response: `CreateAgentRunResponse` (same shape as coding runs).

### D7. Multi-turn coding conversations (new module `coding_chat/`)

Decision: a dedicated `chat_sessions` + `chat_messages` model (not an agent-run chain) —
runs stay single-shot and stateless (P3-D6 intact); the session is a UI/persistence object
that *feeds context into* runs via `input_json.context.chat_session_id`, so **no `agent_runs`
column is needed** (avoids a cross-partition model change).

Models (`coding_chat/models.py`):

```python
class ChatSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "chat_sessions"
    project_id: FK projects CASCADE, index
    created_by: FK users RESTRICT
    agent_type: _enum(AgentType) default CODING     # reuses the existing native enum
    title: String(200) default ""                   # first user message, truncated

class ChatMessage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "chat_messages"
    __table_args__ = (UniqueConstraint("session_id", "seq"),)
    session_id: FK chat_sessions CASCADE, index
    seq: int
    role: String(20)                                # "user" | "assistant"
    content: Text
    agent_run_id: FK agent_runs SET NULL, nullable
    patch_id: FK patch_proposals SET NULL, nullable
```

`seq` = `max(seq)+1` inside the request transaction with one retry on `IntegrityError`
(unique constraint is the safety net; sessions are single-user UI surfaces).

Service (`coding_chat/service.py`): `create_session` (RESEARCHER), `list_sessions`
(VIEWER, paginated, newest first), `get_session` (VIEWER, includes messages ordered by seq),
`post_message` (RESEARCHER):
1. insert user `ChatMessage`; set session title if it is the first message; commit.
2. `AgentRunService.create_run(actor, project_id, agent_type=CODING, message=payload.message,
   context={"chat_session_id": str(session_id)})` (rate limiting + Celery dispatch reused).
3. patch `user_message.agent_run_id = run.id`; commit.
4. return `{message_id, agent_run_id, stream}`.

Agent side (`coding_agent.py::build_messages`): when `actx.context.get("chat_session_id")`
is set, load the last 20 messages (excluding the just-inserted current user message, matched
by `agent_run_id == actx.run.id`) and prepend them as alternating
`LLMMessage(role="user"/"assistant")` turns between the system prompt and the current user
message. Cap total injected history at ~8_000 chars (drop oldest first). The worker resolves
this through its own DB session (`actx.db`), no API involvement.

The assistant reply is persisted by `finalize` (D2 step 5), so history survives reconnects
and the chat pane can be rebuilt entirely from REST (`get_session`) — live streaming still
rides the existing `agent.run.*` WS events keyed by `agent_run_id`.

### D8. `base_sha` None==None hole — summary of the three-layer fix

1. Schema: `modify` requires `base_sha` (D3).
2. Creation: `create` of an existing file and `modify`/`delete` of a missing file fail at
   proposal time (D3), and agent-side `base_sha` is overwritten by the broker-recorded read
   sha (D2).
3. Apply: MODIFY with `current is None` conflicts (`"file missing"`); DELETE of an absent
   file is a satisfied no-op (D4).

---

## API contract changes

All under the existing error envelope / CSRF / role conventions (P3-D9: reads VIEWER+,
mutations RESEARCHER+ with CSRF; non-membership 404).

### Changed: `POST /projects/{id}/workspace/patches` (create)
Request `files[]` items now accept `edits` and reject client-supplied hunks:
```json
{"summary": "Fix off-by-one",
 "files": [{"path": "src/util.py", "change_type": "modify",
            "base_sha": "9f2c...64hex",
            "edits": [{"search": "    for i in range(n - 1):\n        emit(i)\n",
                       "replace": "    for i in range(n):\n        emit(i)\n"}]}]}
```
Errors: 422 (schema: modify without base_sha, create with edits, both/neither content forms);
400 `validation_error` with `details.files=[{path, index?, reason}]` when any file fails
resolution (`not_found` | `ambiguous` | `empty_search` | `base_changed` | `base_missing` |
`already_exists` | `unpatchable_binary`); 403 `workspace_forbidden` (path guard).

### Changed: `GET .../patches/{patch_id}` / list
`files[]` gain `base_content` (nullable) and `edits[]`; `hunks[]` are now real. Proposal
gains `applied_commit_sha`, `conflicts[]`, `superseded_by`.

### Changed: `POST .../patches/{patch_id}/apply`
Success `200`:
```json
{"patch_id": "…", "status": "applied", "conflicts": [], "applied_commit_sha": "a1b2c3…"}
```
Conflict `200` (unchanged shape + persisted): `{"status": "conflict", "conflicts": [{"path":
"src/util.py", "expected_sha": "9f2c…", "actual_sha": "77aa…", "reason": "base content
changed"}], "applied_commit_sha": null}`. New error: 500 `apply_failed` when the atomic
apply rolled back (patch remains `pending`, retryable).

### Changed: `POST .../patches/{patch_id}/reject`
Now legal from `conflict` as well as `pending` (400 otherwise).

### New (SHOULD): `POST .../patches/{patch_id}/repropose`
`201` → `{"agent_run_id": "…", "status": "queued", "stream": "/ws?project_id=…"}`.
Errors: 400 (status not `conflict` / not agent-authored), 429 (agent run rate limit).

### Changed: `GET /projects/{id}/git/status`
Same schema; now real: `{"provider": "git", "branch": "main", "clean": false, "ahead": 0,
"behind": 0, "files": [{"path": "src/util.py", "state": "modified"}]}`. Git-less deployment:
`{"provider": "disabled", "branch": "", "clean": true, "files": []}`.

### New: `GET /projects/{id}/git/log?path=&limit=&skip=`
`limit` 1..100 default 50; optional workspace-relative `path` (guarded). `200`:
```json
{"entries": [{"sha": "a1b2…", "author_name": "Demo User",
              "author_email": "demo@researchos.dev",
              "authored_at": "2026-07-26T12:00:00+00:00",
              "summary": "Add retry to fetcher",
              "patch_id": "uuid-or-null", "agent_run_id": "uuid-or-null",
              "reverts_sha": null}]}
```
Git disabled / no repo → `{"entries": []}`.

### New: `GET /projects/{id}/git/commits/{sha}/diff`
`sha` must match `^[0-9a-f]{7,64}$` (422 otherwise). `200`:
```json
{"sha": "a1b2…", "summary": "Add retry to fetcher",
 "author_name": "Demo User", "authored_at": "…",
 "files": [{"path": "src/fetch.py", "change_type": "modified",
            "old_path": null, "old_content": "…", "new_content": "…",
            "omitted": false, "size": 1421}]}
```
Errors: 404 (unknown sha), 409 `git_disabled`.

### New: `POST /projects/{id}/git/revert` (CSRF, RESEARCHER)
Request `{"sha": "a1b2…"}`. `200` → `{"commit_sha": "d4e5…", "reverted_sha": "a1b2…"}`.
Errors: 400 `validation_error` (dirty tree, revert conflict — message carries git stderr
snippet), 404 (unknown sha), 409 `git_disabled`.

### New: coding chat (`coding_chat/router.py`, prefix `/projects/{project_id}/coding-chat`)
- `POST /sessions` (CSRF, RESEARCHER) `{"title": ""}` → `201`
  `{"id": "…", "project_id": "…", "title": "", "agent_type": "coding", "created_at": "…"}`
- `GET /sessions?limit=&offset=` → `Page[ChatSessionResponse]` (newest first).
- `GET /sessions/{session_id}` → session + `messages: [{"id", "seq", "role", "content",
  "agent_run_id", "patch_id", "created_at"}]` ordered by seq.
- `POST /sessions/{session_id}/messages` (CSRF, RESEARCHER)
  `{"message": "rename foo to bar in utils"}` → `201`
  `{"message_id": "…", "agent_run_id": "…", "status": "queued",
    "stream": "/ws?project_id=…"}`. Errors: 404 (session), 429 (agent run rate limit).

The legacy `POST /projects/{id}/coding-agent/runs` (unowned) keeps working unchanged
(sessionless one-shot runs).

## WS events

**No new event types.** The chat/patch UX rides the existing persisted `agent.run.*` family
(`agent.run.completed.payload.output` plus `output_json.patch_id` fetched over REST). A
`patch.applied` event would need a non-`agent_run` envelope builder in
`websocket/envelopes.py` (unowned) — deliberately deferred; noted as available follow-up for
the realtime workstream.

## DB changes (for the consolidating migration agent — no alembic files authored here)

- `patch_files`:
  - `ADD COLUMN base_content TEXT NULL` — full pre-image snapshot for modify/delete of text
    files ≤ `workspace_max_file_bytes`; NULL for create/binary/legacy rows.
  - `ADD COLUMN edits_json JSONB NULL` — raw `[{search, replace}]` blocks as proposed.
- `patch_proposals`:
  - `ADD COLUMN applied_commit_sha VARCHAR(64) NULL`
  - `ADD COLUMN conflict_json JSONB NULL`
  - `ADD COLUMN superseded_by UUID NULL REFERENCES patch_proposals(id) ON DELETE SET NULL`
- New table `chat_sessions`: `id UUID PK`, `project_id UUID NOT NULL REFERENCES projects(id)
  ON DELETE CASCADE` (index), `created_by UUID NOT NULL REFERENCES users(id) ON DELETE
  RESTRICT`, `agent_type agent_type NOT NULL DEFAULT 'coding'` (reuses existing native
  enum), `title VARCHAR(200) NOT NULL DEFAULT ''`, `created_at/updated_at TIMESTAMPTZ`.
- New table `chat_messages`: `id UUID PK`, `session_id UUID NOT NULL REFERENCES
  chat_sessions(id) ON DELETE CASCADE` (index), `seq INTEGER NOT NULL`, `role VARCHAR(20)
  NOT NULL`, `content TEXT NOT NULL`, `agent_run_id UUID NULL REFERENCES agent_runs(id) ON
  DELETE SET NULL`, `patch_id UUID NULL REFERENCES patch_proposals(id) ON DELETE SET NULL`,
  `created_at/updated_at`, `UNIQUE (session_id, seq)`.
- Backfill: none required. All new columns nullable; legacy patches simply lack
  `base_content` (review diff falls back to live-vs-new; revert still available via git).
- No `agent_runs` changes (session linkage lives in `input_json.context` +
  `chat_messages.agent_run_id`).

## shared-schemas additions (for the consolidating agent)

Types (`src/`): `PatchEdit {search, replace}`; `PatchFileInput` gains `edits?: PatchEdit[]`
and **drops** `hunks` (breaking — input only); `PatchFile` response gains
`base_content: string | null`, `edits: PatchEdit[]`; `PatchProposal` gains
`applied_commit_sha: string | null`, `conflicts: PatchConflict[]`,
`superseded_by: string | null`; `ApplyResult` gains `applied_commit_sha: string | null`.
New: `GitCommitEntry`, `GitCommitDiff`, `GitCommitDiffFile`, `GitRevertRequest`,
`GitRevertResponse`, `ChatSession`, `ChatMessage`, `CreateChatMessageRequest`,
`CreateChatMessageResponse`, tool result shapes `WorkspaceReadResult`,
`WorkspaceGrepResult` (optional, for the run inspector). No `events.ts` changes.

## New dependencies

**None.** Git via the system `git` binary behind a feature flag (subprocess, stdlib);
diffing via `difflib`; everything else stdlib. (Deliberate: dulwich from INNOVATION WS2-3
is rejected — the brief specifies porcelain parsing + binary feature-flag, and zero-dep wins.)

## File-by-file plan

| File | Action | Contents |
|---|---|---|
| `agents/runtime/tools.py` | modify | `ToolContext.read_paths/read_bytes_used`; `_workspace_read`, `_workspace_grep`; registry entries; broker structured-error results (never raise for tool-level failures); content-aware `result_summary`. (~150 lines) |
| `agents/runtime/coding_agent.py` | modify | new `_SYSTEM`/`_SCHEMA` (edits); `max_tool_calls = 25`; chat-history + repropose context in `build_messages`; finalize: lenient parse, violations, sha override, chat message insert, repropose supersede; (SHOULD) `prevalidate`. (~200) |
| `patches/resolution.py` | **create** | `EditBlock`, `EditFailure`, `EditResolutionError`, `resolve_edits`, `compute_hunks`, `HunkData`. Pure functions. (~170) |
| `patches/schemas.py` | modify | `PatchEditInput`, input validators per change_type, drop `PatchHunkInput`, response additions. (~80 delta) |
| `patches/models.py` | modify | `PatchFile.base_content/edits_json`; `PatchProposal.applied_commit_sha/conflict_json/superseded_by`. (~25 delta) |
| `patches/service.py` | modify | create_proposal resolution pipeline + snapshots + hunk derivation + per-file failures; apply: new conflict rules, `apply_files_atomic`, git commit, `conflict_json`; reject-from-conflict; (SHOULD) `repropose`. (~250 delta) |
| `patches/router.py` | modify | (SHOULD) `POST /{patch_id}/repropose`. (~30) |
| `patches/repository.py` | modify | eager-load unchanged; helper to update `superseded_by`. (~10) |
| `patches/enums.py` | unchanged | status vocabulary unchanged (no new enum values — native-enum ALTER avoided). |
| `git/runner.py` | **create** | `git_available`, `run_git`, `GitError`, `GitDisabled`, sha validation. (~90) |
| `git/provider.py` | modify | `RealGitStatusProvider` (porcelain v1 parse), `DisabledGitStatusProvider`, selection; delete `ReadOnlyGitStatusProvider` + stub. (~120) |
| `git/service.py` | modify | `ensure_repo`, `log`, `commit_diff`, `commit_applied_patch`, `revert`, per-project lock, `asyncio.to_thread` wrappers. (~220) |
| `git/schemas.py` | modify | `GitCommitEntry`, `GitLogResponse`, `GitCommitDiff(File)`, `GitRevertRequest/Response`. (~60) |
| `git/router.py` | modify | `GET /log`, `GET /commits/{sha}/diff`, `POST /revert` (CSRF). (~60) |
| `workspace/fs.py` | modify | `read_file_range`, `grep_files`, `apply_files_atomic` (+ `WorkspaceApplyError`, staging cleanup). (~220 delta) |
| `workspace/service.py` | modify | thin authorized wrappers `read_file_range`/`grep` for tool use. (~25) |
| `workspace/schemas.py` | modify | optional DTOs for ranged read (REST surface unchanged). (~15) |
| `common/paths.py` | modify | add `".ros-staging"` to `DENY_DIR_NAMES`. (2) |
| `coding_chat/__init__.py`, `models.py`, `schemas.py`, `service.py`, `router.py` | **create** | D7 as specified. (~300) |
| `apps/api/tests/test_patch_resolution.py` | **create** | see Test plan. |
| `apps/api/tests/test_atomic_apply.py` | **create** | |
| `apps/api/tests/test_workspace_tools.py` | **create** | |
| `apps/api/tests/test_git_service.py` | **create** | |
| `apps/api/tests/test_coding_chat.py` | **create** | |
| `apps/api/tests/test_patches.py`, `test_coding_agent.py` | modify | update to new validation rules (modify requires base_sha; rejected_files visible). |

Estimated ~1,750 production + ~700 test lines. Degrade via SHOULD/STRETCH if over budget.

## Cross-partition requests

- **CP-1 `common/config.py` (Settings)** — add fields (defaults shown):
  `git_enabled: bool = True`; `git_timeout_seconds: float = 10.0`;
  `workspace_read_max_lines: int = 400`; `workspace_read_budget_bytes: int = 262_144`;
  `workspace_grep_max_results: int = 50`; `workspace_grep_max_file_bytes: int = 200_000`.
- **CP-2 `agents/runtime/base.py` (runtime-llm)** — add
  `max_tool_calls: ClassVar[int | None] = None` to `Agent`.
- **CP-3 `agents/runtime/runtime.py` (runtime-llm)** — (a) tool budget:
  `limit = agent.max_tool_calls or self.settings.agent_max_tool_calls` at line 181;
  (b) note: `ToolBroker.execute` no longer raises for tool-level failures — it returns
  `{"error": {...}}` payloads; keep forwarding results into `role="tool"` messages;
  (c) SHOULD hook: after the loop and before `finalize`, call
  `feedback = await agent.prevalidate(actx, output_text)` (default returns None); if a
  non-None string and no retry has happened yet, append
  `LLMMessage(role="user", content=feedback)` and re-run the stream loop exactly once.
- **CP-4 `agents/llm/mock.py` (runtime-llm)** — deterministic script covering the new coding
  mode: pass 1 → `ToolCall(workspace.tree)`; pass 2 (tree result present, non-empty) →
  `ToolCall(workspace.read, {"path": <first file path in tree result>})`; pass 3 (read
  result present) → emit `{"summary": "Mock edit", "files": [{"path": <read path>,
  "change_type": "modify", "base_sha": <sha from the read result>, "edits": [{"search":
  <first line of read content + "\n">, "replace": <same line + "\n"> }]}]}` — a no-op-safe
  unique-first-line replace; empty-tree fallback → current `AGENT_NOTES.md` create block
  (which remains valid under the new schema).
- **CP-5 `researchos/main.py`** — `app.include_router(coding_chat_router)`.
- **CP-6 `researchos/models.py`** — `from researchos.coding_chat import models  # noqa`.
- **CP-7 `infra/docker/python.Dockerfile`** — install git:
  `RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*`.
- **CP-8 web (IDE workstream)** — `PatchDiff.tsx` should diff `base_content` (when non-null)
  against `new_content` instead of the live file; surface `rejected_files`,
  `applied_commit_sha`, git history panel, chat sessions UI. Informational, not blocking.
- **CP-9 migration agent** — DDL per "DB changes"; **CP-10 shared-schemas agent** — types per
  "shared-schemas additions".

## MUST / SHOULD / STRETCH

**MUST**
1. `workspace.read` (line-ranged, size-capped, sha-recording) + `workspace.grep` (bounded)
   + read budgets + broker structured-error results (D1).
2. Read-before-write enforcement with visible `rejected_files` + server-side sha override +
   lenient JSON extraction (D2, minus prevalidate).
3. SEARCH/REPLACE edits with exact + whitespace-fuzzy resolution, server-materialized
   `new_content`, `base_content` snapshots, real derived `patch_hunks`, schema validators
   closing the `base_sha` hole (D3, D8).
4. Atomic apply with staging/fsync/rename + journaled rollback; idempotent delete; persisted
   `conflict_json`; reject-from-CONFLICT (D4, D6.1).
5. Real git: runner, lazy init, auto-commit on apply (author=user, Patch/Agent-Run trailers,
   Co-Authored-By), real porcelain status, log (global + per-file), commit diff, safe
   revert, full disabled-mode degradation (D5).
6. Coding chat sessions: models, endpoints, history injection, assistant-message persistence
   (D7).
7. Tests for all of the above.

**SHOULD** (in order)
8. `POST /patches/{id}/repropose` conflict-seeded re-run + `superseded_by` linkage (D6.2).
9. `prevalidate` self-repair round (needs CP-3c) and mock extension (CP-4).
10. Stale-staging cleanup scheduling niceties; `git log` `skip` pagination param.

**STRETCH**
11. Per-hunk selective apply (`selections` body on apply + re-materialization).
12. Level-3 fuzzy edit matching (difflib ratio ≥ 0.9).
13. `patch.applied` WS event (needs generic envelope builder, unowned).

## Acceptance criteria (local gates + code review + CI-deferred tests)

1. `ruff check` + `mypy` pass on `apps/api` (local gate).
2. Code review: `TOOL_REGISTRY` contains `workspace.read`/`workspace.grep`; `CodingAgent.
   allowed_tools == ["workspace.tree", "workspace.read", "workspace.grep"]`;
   `max_tool_calls == 25`.
3. Code review: `ToolBroker.execute` has no `raise ToolDenied()` path; unknown/denied/failed
   tools produce `{"error": ...}` results and FAILED ToolCall rows.
4. Code review: `PatchFileInput` validator rejects `modify` without `base_sha`;
   `apply_patch` conflicts on MODIFY-with-missing-file and no-ops DELETE-of-missing-file.
5. Code review: `apply_patch` performs no direct `fs.write_file` calls; all writes go
   through `apply_files_atomic`; failure path leaves status PENDING.
6. Code review: every `run_git` call site passes validated shas (`_SHA_RE`) and `--`-guarded
   paths; no `shell=True` anywhere; revert path contains no `reset`/`rebase`/`push`.
7. Code review: commit message construction includes `Patch:`/`Agent-Run:` trailers and
   `Co-Authored-By: codex <noreply@anthropic.com>`; `--author` uses the acting user's
   `display_name`/`email`.
8. Grep gate: `rg "git_available" apps/api/researchos/git` shows every mutating entry point
   guarded; `rg "\.ros-staging" apps/api/researchos/common/paths.py` hits `DENY_DIR_NAMES`.
9. CI: full pytest suite green (including new tests below) with `LLM_PROVIDER=mock` and no
   external network.

## Test plan (pytest, CI-run; no network; mock provider; git tests skip when binary absent)

- `test_patch_resolution.py` (pure, no DB): exact single/multiple-occurrence (ambiguous),
  not-found, empty-search; whitespace-fuzzy match with indent-shift reconstruction; unique-
  window requirement; sequential edits on evolving text; aggregated failure lists;
  `compute_hunks` header/offsets vs known diffs; round-trip `resolve_edits` →
  `compute_hunks` consistency.
- `test_atomic_apply.py` (tmp workspace via `workspace_root` monkeypatch, no DB): success
  writes+deletes+creates; Phase-A failure leaves workspace untouched; Phase-B mid-journal
  failure (monkeypatched `os.replace` failing on the Nth call) restores byte-identical
  originals and removes created files; staging dir invisible to `build_tree` and denied by
  `resolve_in_workspace`; stale-staging cleanup.
- `test_workspace_tools.py` (DB fixtures from existing conftest): ranged read clamps at
  `workspace_read_max_lines` and sets `truncated`; whole-file sha recorded in
  `ctx.read_paths` for ranged reads; budget exhaustion returns `read_budget_exhausted`
  error payload and a FAILED ToolCall without failing the run; grep bounds (max results,
  binary skip, invalid regex error payload, deny-list exclusion); unknown/denied tool →
  error payload (regression for ARCH #27).
- `test_patches.py` (extend): modify-without-base_sha 422; edits-based create_proposal
  materializes `new_content`, snapshots `base_content`, derives hunks; `base_changed` /
  `ambiguous` per-file failures; apply conflict on missing file (None==None regression);
  idempotent delete; conflict persists `conflict_json`; reject from CONFLICT; apply
  response carries `applied_commit_sha` (None when git disabled via `GIT_ENABLED=false`).
- `test_coding_agent.py` (extend, scripted `llm=` injection into `AgentRuntime`): run whose
  script reads a file then emits edits → patch created with server-recorded sha; script
  that modifies an unread path → no patch file, violation in `output_json.rejected_files`;
  parse-failure → `output_json.error == "parse_failure"`; mock-provider default flow still
  produces the `AGENT_NOTES.md` create patch.
- `test_git_service.py` (`pytest.mark.skipif(shutil.which("git") is None)`; tmp workspace):
  lazy init idempotency (branch `main`, bot identity, empty root commit); apply→commit
  captures author/trailers (`git log` parse asserts `Patch:`/`Agent-Run:`/Co-Authored-By);
  porcelain status parse (modified/untracked/deleted/renamed fixtures — parser additionally
  unit-tested from literal porcelain strings without git); per-file log filtering; commit
  diff old/new content incl. create/delete edges and root commit; revert happy path +
  dirty-tree rejection + conflict abort; disabled mode (setting off): status
  `provider="disabled"`, log `[]`, revert 409, apply still succeeds with
  `applied_commit_sha=None`.
- `test_coding_chat.py`: session CRUD + pagination + 404 isolation (non-member);
  post_message inserts user row, creates queued coding run with
  `context.chat_session_id`, links `agent_run_id`; after a runtime run (scripted provider)
  the assistant message exists with `patch_id`; `build_messages` injects prior turns in
  order and caps history; seq uniqueness under the retry path.
- Playwright: none here (IDE chat/git UI belongs to the web partition; CP-8).

## Explicitly out of scope

- Frontend changes (CodingChat pane, DiffCards, git timeline UI, PatchDiff base_content
  rendering) — web/IDE partition (CP-8).
- Repo map (WS2-5) and self-verifying patches (WS2-6) — future workstreams; the tool/broker
  surfaces here are designed not to preclude them.
- Branch-per-agent-session and merge flows (INNOVATION WS2-3 branch model) — commits land on
  `main`; branches deferred until the runner/pipeline workstreams need them.
- Per-hunk selective apply beyond STRETCH #11; partial-proposal editing.
- Remote git (push/pull/remotes), git-based document (LaTeX) versioning, `ExperimentRun.
  git_commit` stamping (experiments partition can call `GitService` later).
- Any change to `runtime.py`/`base.py`/`llm/**` themselves (requested via CP-2/3/4 only).
- Encryption/secret handling, session administration, and other cross-cutting fixes listed
  in ARCHITECTURE_MAP §4 not touched by these flows.
