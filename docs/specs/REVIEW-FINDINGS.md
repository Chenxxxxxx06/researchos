# Orchestrator inline review findings (pre-final-review)

Findings I verified myself by reading Wave A code while Wave B runs. Each is to be
re-verified adversarially and fixed in Phase 4.

## F1 — git revert permanently blocked on pre-existing workspaces (correctness/UX) — FIXED
`git/service.py::_ensure_repo_sync` lazily inits the repo with only an
`--allow-empty` initial commit; it never stages the files that already exist in
the workspace (created via `fs.write_file` before git existed). Those files stay
**untracked**. `revert()` (`_revert_sync`) rejects when `git status --porcelain`
is non-empty, and untracked files (`?? path`) count as dirty → **every revert on
a project that had files before its first applied patch fails** with
"Workspace has uncommitted changes".
Fix: at init, stage+commit the existing tree:
`git add -A` then a real (non-empty-only) initial commit, before returning True.
Verify: after ensure_repo on a non-empty workspace, `git status --porcelain` is
empty.

## Phase 4 adversarial review — adjudication (10 findings, orchestrator-verified)

Six-dimension parallel review; each finding re-read and adjudicated against the cited code.

| # | Sev | Finding | Verdict | Action |
|---|-----|---------|---------|--------|
| 1 | CRITICAL | Platform LLM key leaks to attacker `base_url` (anthropic + openai adapters fall back to env key even for a custom endpoint) | CONFIRMED | **FIXED** — both adapters: env-key fallback only when `base_url` is the canonical host; a custom base_url requires an explicit api_key or raises config_error |
| 2 | HIGH | `AgentRunContext` drops `paper_id`/`section_seqs` → research "Explain section" silently dead | CONFIRMED | **FIXED** — added both fields to `agents/schemas.py::AgentRunContext` |
| 3 | HIGH | `PaperWorkspace` refetch-after-save clobbers unsaved buffer (data loss) | CONFIRMED | **FIXED** — `loadedLidRef` guard: init only on first doc load; refetch never overwrites the live buffer |
| 4 | MED | Accept-suggestion while dirty discards unsaved edits | CONFIRMED | **FIXED** — accept blocked while dirty (saveFirst toast), mirroring selection-ops |
| 5 | MED | Section-numbering regex `[0-9IVXLCA-Z]` eats real first words ("BERT"→"") | CONFIRMED | **FIXED** — restricted to dotted-decimal / Roman / single-capital |
| 6 | MED | Document CAS non-atomic → concurrent save 500 not 409 | CONFIRMED | **FIXED** — update+revision staged in a savepoint; IntegrityError → 409 merge hint |
| 7 | LOW | Tracked-change decorations drift after edits (dead shift methods) | CONFIRMED | **FIXED** — overlay hidden while dirty (only shown on the saved buffer it was computed against) |
| 8 | LOW | Reconnect token backfill dropped by live-advanced `lastTokenSeq` (transient text gap) | PLAUSIBLE | **DEFERRED** — self-heals on `agent.run.completed` (full output); a correct fix means reworking the token-accumulation hot path, which cannot be runtime-tested here → blind-edit risk > transient display gap. Documented limitation. |
| 9 | LOW | User `suffix` unescaped into `\newcommand` value (LaTeX injection) | CONFIRMED | **FIXED** — `_escape_suffix` escapes unescaped `{ } % # & $ _` (preserves intended `\%`, `\times`) |
| 10 | LOW | `user_preferences` NULLS NOT DISTINCT needs PG≥15 | REFUTED | No action — compose pins pgvector:pg16; model+migration agree |

Result: 8 fixed, 1 deferred (documented), 1 refuted. All gates green after fixes
(ruff, mypy 190 files, tsc, next build).

## Modules verified CLEAN by inline read (grounding for final review)
- `agents/llm/anthropic.py` — emit_result synthetic tool + tool_choice forcing;
  tool_use/tool_result pairing correct; empty-assistant skip; per-iter usage. OK.
- `agents/llm/openai_compatible.py` — anthropic-key leak removed (openai_api_key
  only); response_format json_schema + 4xx retry-without; finish_reason preserved;
  tool_calls delta accumulation; correct message serialization. OK.
- `agents/runtime/runtime.py` — per-iteration text reset, proper assistant/tool
  pairing, usage summing, asyncio.timeout, per-iter + per-call cancel checks,
  structured-output gate FAILS on unparseable (no more empty-success),
  budget→synthesis nudge, ToolDenied→recoverable (bounded 2). OK.
- `patches/resolution.py` — exact match first (byte-exact, rejects >1 as ambiguous),
  indent-aware single-window fuzzy fallback, failures collected, difflib hunks. OK.
- `workspace/fs.py::apply_files_atomic` — staging+fsync, journaled renames with
  reverse rollback distinguishing full vs partial rollback, parent-dir fsync,
  delete via backup-without-place. Genuinely atomic. OK.
- `research/providers/federated.py` — union-find over DOI/arxiv-id/title + fuzzy
  pass gated on author-or-year, RRF ranking, source-priority field merge with full
  provenance, one-provider-failure tolerant. OK.
- `agents/runtime/coding_agent.py` — read-before-write ENFORCED (modify/delete of an
  unread file → `unread_file` violation); base_sha overridden with the broker-served
  sha (agent echo advisory; closes the base_sha=None hole); SEARCH/REPLACE edits with
  proposal-time dry-run; one-turn self-repair via prevalidate; repropose re-anchor. OK.
- `experiments/service.py::list_runs` — IDOR fixed: verifies experiment ∈ project
  (404 otherwise) before listing runs. OK.
- `agents/llm/openai_compatible.py` + `anthropic.py` — Anthropic-key bearer leak
  removed (openai_api_key only). Security fix confirmed. OK.
