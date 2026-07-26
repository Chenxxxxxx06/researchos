# Spec: runtime-llm — Real-LLM Agent Loop, Structured Output, Cancellation & Skill Injection

Workstream: `runtime-llm` · Realizes INNOVATION_IDEAS WS8-1 (skill runtime injection) and the
"Real-LLM path is broken end-to-end" cluster (ARCHITECTURE_MAP §4.11, inventory rows 21–25, 27, 28, 32, 33).

Partition (files this spec's implementer may touch):
`apps/api/researchos/agents/**` EXCEPT `agents/runtime/tools.py`, `agents/runtime/coding_agent.py`,
`agents/runtime/latex_agent.py`; plus `apps/api/researchos/skills/service.py` (read-path additions only)
and `apps/worker/**`. Everything else goes through Cross-partition requests.

---

## Objective (user-visible outcome)

A user who configures a real Anthropic or OpenAI-compatible provider in Settings gets working
multi-turn agents: the research agent actually searches then synthesizes, the critic returns a real
structured critique (or the run visibly FAILS — never a silent empty "success"), cancellation takes
effect within one loop iteration, runs cannot hang past `AGENT_RUN_TIMEOUT_SECONDS`, and enabled
project skills demonstrably change agent behavior (prompt fragments injected, extra tools granted,
active skills recorded on the run and shown in the started event). All of this remains fully
exercisable offline via an upgraded deterministic mock provider that emits realistic multi-turn
tool-use conversations and *validates* the message protocol like a real API would.

## Current state (concrete, file:line)

1. **Broken tool-loop message protocol** — `agents/runtime/runtime.py:181-194`: after executing a
   tool the runtime appends `LLMMessage(role="assistant", content="")` (line 184) with no record of
   the tool_use/tool_calls the model emitted, then a `role="tool"` message. Anthropic rejects a
   `tool_result` block whose `tool_use_id` has no matching `tool_use` block in the preceding
   assistant turn; OpenAI rejects a `role:"tool"` message not preceded by an assistant message with
   matching `tool_calls[].id`. `LLMMessage` (`agents/llm/base.py:18-23`) cannot even represent an
   assistant tool-call turn.
2. **text_buffer contamination** — `runtime.py:159,169,195`: `text_buffer` accumulates across ALL
   iterations, so any pre-tool-call prose (real models routinely emit "Let me search…") is prepended
   to the final JSON, breaking `json.loads` in finalize.
3. **Usage overwritten, not summed** — `runtime.py:173-177`: each iteration's `Usage` replaces the
   previous dict.
4. **response_schema never transmitted** — `agents/llm/anthropic.py:48-87` and
   `agents/llm/openai_compatible.py:42-139` both accept `response_schema` and ignore it.
5. **Anthropic adapter defects** — `anthropic.py:65` hardcodes `max_tokens=1024` (truncates JSON
   mid-stream); no request timeout; `_to_anthropic_messages` (`anthropic.py:90-110`) never
   reconstructs `tool_use` blocks and emits one `user`/`tool_result` message per tool result
   (Anthropic requires all results for one assistant turn in the single next user message);
   constructor reads only env settings (`anthropic.py:22-46`) — per-project DB model/key/base_url
   are dead (`agents/llm/factory.py:42-44`).
6. **OpenAI adapter defects** — `openai_compatible.py:34`: `api_key or settings.anthropic_api_key`
   leaks the Anthropic key as a Bearer token to ANY user-configured base_url; line 135 reads the
   stale loop variable `choice` after the loop (NameError if no chunk had `choices`); usage is
   always 0 because `stream_options: {include_usage}` is never sent; `_to_openai`
   (lines 142-159) drops assistant tool_calls entirely.
7. **Parse failure = empty success** — `critic_agent.py:74-77` falls back to `parsed = {}` and
   persists an empty critique on a COMPLETED run (same pattern in unowned `coding_agent.py:70-73`).
8. **Cancellation & timeout** — cancel flag checked only before (`runtime.py:76`) and after
   (`runtime.py:118`) the whole loop; `agent_run_timeout_seconds`
   (`common/config.py:104`) enforced nowhere.
9. **Seq races** — `agents/repository.py:51-55` `ToolCallRepository.next_seq` = `COUNT(*)`;
   `AgentRunEventRepository.next_seq` (`repository.py:73-77`) = `max+1`, and an IntegrityError in
   `EventEmitter.emit` (`runtime/events.py:34-43`) propagates and FAILS the run. `tool_calls` has no
   unique constraint on `(agent_run_id, seq)` (`agents/models.py:46-66`).
10. **Skills never injected** — `AgentRuntime.run` never reads `SkillInstallation`;
    `AgentRun.skill_ids_json` (`agents/models.py:41`) is always `[]`; manifests' `prompt_template` /
    `tool_permissions` / `workflow` (`skills/manifest.py:31-42`) are consumed by nothing.
11. **Mock is a placebo** — `agents/llm/mock.py:54-61` always calls `tools[0]` exactly once,
    performs no protocol validation, so the broken message shapes of (1) pass every test.
12. **Factory** — `factory.py:30-38` picks an arbitrary `is_active` row (`limit(1)`, no order);
    `get_llm_provider_sync` (`factory.py:68-78`) is an unused stub (grep: no callers outside
    factory itself).
13. **Hallucinated tool name fails the whole run** — `ToolBroker.execute` raises `ToolDenied`
    (`tools.py:153-159`, unowned) which propagates through `_run_loop` and marks the run FAILED.

### Prior-decision supersessions
- **P0/P2 "runtime message protocol is provider-neutral strings"** (implicit in
  `agents/llm/base.py`): superseded — `LLMMessage` gains a typed `tool_calls` field. Rationale: no
  provider-neutral encoding of a tool round-trip exists without it; both real APIs demand paired
  ids.
- **"Parse failure degrades to empty output"** (implicit behavior, MVP_STATUS honesty ledger):
  superseded — structured-output parse failure now FAILS the run with a typed error. Rationale:
  empty-success destroys trust and hides provider misconfiguration; the map calls this out as a
  top-severity issue (§4.11).
- No change to P3-D5 (agents never write files), P3-D6, or the citation whitelist mechanism.

---

## Design (algorithms & data flow)

### D1. Message protocol: typed tool turns

`agents/llm/base.py`:

```python
@dataclass
class LLMMessage:
    role: Role
    content: str
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[ToolCall] | None = None   # NEW: assistant tool-use turns
```

Protocol invariants (enforced by the strict mock, D8, and documented in the module docstring):
1. An assistant message with `tool_calls` is followed by exactly `len(tool_calls)` messages of
   `role="tool"`, in the same order, each with a `tool_call_id` matching one of the ids.
2. `role="tool"` messages appear nowhere else.
3. `system` messages appear only at the start of the list.

`LLMProvider.stream` signature gains one keyword:

```python
def stream(self, *, messages, tools=None, response_schema=None,
           force_structured: bool = False) -> AsyncIterator[StreamEvent]: ...
```

`force_structured=True` means "this call MUST produce the structured object now" (used by the
synthesis round, D3). All three providers accept it; mock and real adapters honor it as below.

### D2. The rewritten run loop (`runtime.py::_run_loop`)

Numbered algorithm (replaces lines 139-195):

1. `messages = await agent.build_prompt(actx)` (D6 — skill-augmented wrapper).
2. `effective_tools = self._effective_tools(agent, actx.skills)` (D6); build `llm_tools` from
   `TOOL_REGISTRY` for names in `effective_tools`, sorted by name for determinism.
3. Initialize `usage_total = {"input_tokens": 0, "output_tokens": 0}`, `tool_budget =
   agent.max_tool_calls or settings.agent_max_tool_calls`, `tool_count = 0`,
   `denied_count = 0`, `iteration = 0`, `synthesis = False`.
4. Loop (hard cap `iteration < tool_budget + 3` — safety against pathological providers):
   a. **Cancellation check**: `if await is_cancel_requested(run.id): raise AgentCancelledError`.
   b. `iter_text = ""`, `requested: list[ToolCall] = []` — **reset every iteration**.
   c. Stream `llm.stream(messages=messages, tools=([] if synthesis else llm_tools),
      response_schema=agent.response_schema, force_structured=synthesis and
      agent.response_schema is not None)`. Fold events: `TextDelta` → append to `iter_text` +
      `emitter.token(...)`; `ToolCall` → append to `requested`; `Usage` → **sum** into
      `usage_total`; `StreamDone` → record stop reason.
   d. If `requested` is empty or `synthesis` is True → **final iteration**: return
      `(iter_text, usage_total)`. (The final answer is the LAST iteration's text only — earlier
      prose lives inside prior assistant messages, not in the output.)
   e. Append ONE assistant message carrying this turn:
      `LLMMessage(role="assistant", content=iter_text, tool_calls=requested)`.
   f. For each `call` in `requested` (sequentially — the shared `AsyncSession` forbids concurrent
      DB use; parallel safety comes from the allocator in D7, not concurrent execution):
      - **Cancellation check** between calls (raise `AgentCancelledError`).
      - If `tool_count >= tool_budget`: result = `{"error": {"type": "tool_budget_exhausted",
        "message": "No tool calls remaining; produce your final answer."}}` (do NOT execute).
      - Else try `result = await broker.execute(call.name, call.arguments)`; on `ToolDenied` (and
        only `ToolDenied`), `denied_count += 1`; if `denied_count > 2` re-raise (fail run), else
        result = `{"error": {"type": "tool_not_available", "message": f"Tool '{call.name}' is not
        available. Available tools: {sorted(effective_tools)}"}}` — hallucinated tool names become
        a recoverable self-correction signal instead of failing the run (supersedes map row 27
        behavior from the runtime side without touching `tools.py`).
      - Other exceptions propagate (fail run) as today.
      - Append `LLMMessage(role="tool", name=call.name, tool_call_id=call.id,
        content=json.dumps(result))`. `tool_count += 1` (budget-exhausted stubs also count 0 —
        they consume no budget; only executed calls increment).
   g. If `tool_count >= tool_budget`: set `synthesis = True` and append
      `LLMMessage(role="user", content="You have used all available tool calls. Provide your final
      answer now using the information already gathered.")`.
   h. `continue`.

`run()` wraps the loop in the timeout + structured-output gate (D3, D5):

```python
try:
    async with asyncio.timeout(self.settings.agent_run_timeout_seconds):
        output_text, usage = await self._run_loop(...)
except TimeoutError:
    await self._recover_session()
    await self._finalize_failed(run, emitter, "Agent run timed out.", code="timeout")
    return run
except AgentCancelledError:
    await self._recover_session()
    await self._finalize_cancelled(run, emitter)
    return run
except Exception as exc:
    ...existing failure path, plus code=getattr(exc, "error_code", "agent_error")
```

`_recover_session()` = `await self.db.rollback()` then re-fetch the run via
`runs.get_unscoped(run_id)` so finalization writes onto a clean session (an `asyncio.timeout`
cancellation can interrupt a pending DB await). `AgentCancelledError` is a new exception in
`agents/runtime/runtime.py` (module-level, exported for tests).

### D3. Structured output: transmission, extraction, fail-on-parse

**Runtime gate** (in `run()`, before `agent.finalize`): if `agent.response_schema is not None`:

```python
try:
    parsed = extract_json(output_text)                    # D3a
    _check_required(parsed, agent.response_schema)        # top-level "required" keys present
except StructuredOutputError as exc:
    await self._finalize_failed(run, emitter, str(exc), code="structured_output_parse_error")
    return run
output_text = json.dumps(parsed)                          # normalized JSON into finalize
```

This guarantees the (unowned) `coding_agent.py` finalize's `json.loads(output_text)` always
succeeds when reached, and that a garbage LLM answer can never again persist an empty critique or
a COMPLETED run with no patch: the run FAILS with a visible typed error instead.
`critic_agent.py` (owned) drops its silent `parsed = {}` fallback and raises on `JSONDecodeError`
(defense in depth; unreachable via the runtime path).

**D3a. `extract_json(text) -> dict`** — new module `agents/llm/structured.py`:
1. `json.loads(text)` directly; accept only `dict` results.
2. Strip a single Markdown fence: regex ` ```(?:json)?\n(.*?)``` ` (DOTALL) → retry step 1 on the
   inner text.
3. Balanced-object scan: from the first `{`, walk chars tracking brace depth and JSON string/escape
   state; at depth 0 → `json.loads` that slice. Take the FIRST balanced object that parses.
4. Otherwise raise `StructuredOutputError("LLM did not return a parseable JSON object: <first 200
   chars>")`. `_check_required` raises `StructuredOutputError("missing required keys: ...")`.

**Anthropic transmission** (`anthropic.py`): when `response_schema` is not None, append a synthetic
tool `{"name": "emit_result", "description": "Submit your final structured answer. Call exactly
once when done.", "input_schema": response_schema}` to the tools array and append one line to the
system string: `"When you have your final answer, call the emit_result tool exactly once with it."`
When `force_structured=True`, send ONLY `emit_result` and `tool_choice={"type": "tool", "name":
"emit_result"}`. In the stream handler, a `tool_use` block named `emit_result` is NOT yielded as a
`ToolCall`; instead yield `TextDelta(json.dumps(block.input))` then treat stop as `"stop"` — the
runtime sees clean final JSON. `max_tokens` = `settings.llm_max_output_tokens` (cross-partition
config addition, default 8192); client constructed with
`timeout=settings.llm_request_timeout_seconds`.

**OpenAI transmission** (`openai_compatible.py`): when `response_schema` is not None, send
`"response_format": {"type": "json_schema", "json_schema": {"name": "agent_output", "schema":
response_schema, "strict": False}}`. Compatibility fallback: if the FIRST response is HTTP 4xx and
the error body mentions `response_format` (case-insensitive substring), retry the identical request
once without `response_format` (safe — no events were yielded yet). Also send
`"max_tokens": settings.llm_max_output_tokens` and `"stream_options": {"include_usage": true}`.
`force_structured=True` additionally omits `tools`.

### D4. Adapter round-trip fixes

**`_to_anthropic_messages`** (rewritten):
- `system` → skipped (joined separately, unchanged).
- assistant with `tool_calls` → `{"role": "assistant", "content": [
  *( [{"type": "text", "text": msg.content}] if msg.content.strip() else [] ),
  *[{"type": "tool_use", "id": c.id, "name": c.name, "input": c.arguments} for c in msg.tool_calls]
  ]}`.
- Consecutive `tool` messages are MERGED into one `{"role": "user", "content": [{"type":
  "tool_result", "tool_use_id": ..., "content": ...}, ...]}` (Anthropic requires all results in the
  single following user turn).
- assistant with empty content and no tool_calls → skipped (empty content blocks are rejected).
- other roles unchanged.

**`_to_openai`** (fixed): assistant with `tool_calls` →
`{"role": "assistant", "content": msg.content or None, "tool_calls": [{"id": c.id, "type":
"function", "function": {"name": c.name, "arguments": json.dumps(c.arguments)}} for c in
msg.tool_calls]}`; `tool` role unchanged.

**OpenAI stream loop fixes**: track `finish_reason: str | None` explicitly inside the chunk loop
(`finish_reason = choice.get("finish_reason") or finish_reason`), removing the stale-loop-variable
NameError at `openai_compatible.py:135`; hoist `import json as _json` to module top; request
timeout from `settings.llm_request_timeout_seconds`; constructor gains
`http_client: httpx.AsyncClient | None = None` for MockTransport-based tests (owned client is
created per-stream when None, as today).

**Key-leak fix**: `OpenAICompatibleProvider.__init__` becomes
`self.api_key = api_key or settings.openai_api_key` (NEW env `OPENAI_API_KEY`, cross-partition
config addition; empty default). The `anthropic_api_key` fallback is deleted. Error message
unchanged ("Set it in Settings → LLM Provider.").

**`AnthropicProvider.__init__`** gains `model: str | None = None, api_key: str | None = None,
base_url: str | None = None`; falls back to settings for each; validation errors unchanged but
computed against the resolved values. `AsyncAnthropic(api_key=..., base_url=... if provided,
timeout=settings.llm_request_timeout_seconds)`.

### D5. Factory (`factory.py`)

1. DB config pick becomes deterministic:
   `.order_by(LLMProviderConfig.updated_at.desc(), LLMProviderConfig.id).limit(1)`.
2. `provider_type == "anthropic"` now passes DB values through:
   `AnthropicProvider(model=cfg.model or None, api_key=cfg.api_key or None,
   base_url=cfg.base_url or None)` — empty strings fall back to env (matches the llm_config
   router's "empty api_key preserves stored key" convention: an empty stored key means "use env").
3. `get_llm_provider_sync` is DELETED (no callers; grep verified). Its export is removed from any
   `__init__` if present (it is not exported today).

### D6. Skill runtime injection

**New read-path in `skills/service.py`** (read-only addition, no auth check — internal runtime
path invoked by the worker on behalf of an already-authorized run):

```python
@dataclass
class RuntimeSkill:            # defined in skills/service.py (or schemas.py if preferred)
    slug: str
    name: str
    version: str
    prompt_template: str
    workflow: list[str]
    tool_permissions: list[str]
    settings: dict

class SkillService:
    async def list_enabled_for_runtime(
        self, project_id: uuid.UUID, module: SkillModule, *, cap: int = 5
    ) -> list[RuntimeSkill]: ...
```

Implementation: one query joining `SkillInstallation` (enabled, project) → `Skill` →
`SkillVersion` (the PINNED `skill_version_id`, NOT latest), filter
`module.value in manifest_json.get("modules", [])` in Python (manifest lists are short), order by
`SkillInstallation.created_at` asc, cap 5. `tool_permissions` are pre-filtered against
`skills.manifest.ALLOWED_TOOLS` here so the runtime never sees undeclarable names.

**New module `agents/runtime/skills_injection.py`**:

```python
_MODULE_BY_AGENT: dict[AgentType, SkillModule] = {
    AgentType.RESEARCH: SkillModule.RESEARCH,
    AgentType.CRITIC: SkillModule.RESEARCH,
    AgentType.CODING: SkillModule.IDE,
    AgentType.EXPERIMENT: SkillModule.EXPERIMENTS,
    AgentType.LATEX: SkillModule.PAPER,
}

async def load_skills(db, project_id, agent_type) -> list[RuntimeSkill]      # thin wrapper
def render_skill_block(skills: list[RuntimeSkill], *, char_budget: int = 8000) -> str
def skill_tool_grants(skills) -> dict[str, str]   # tool_name -> first granting slug
```

`render_skill_block` output (deterministic, injection-hardened — templates are treated as inert
text, `{{key}}` placeholders substituted from `settings` via plain `str.replace`, values coerced
with `str()`, unknown placeholders left as-is, NO eval/format):

```
## Active skills
### {name} v{version}
{substituted prompt_template}
Suggested workflow: 1) step; 2) step
```

Fragments are appended in order until `char_budget` is exceeded; the first over-budget fragment is
truncated with a trailing `"\n[truncated]"`, later skills are dropped (and logged).

**Prompt wiring — `agents/runtime/base.py`**: `AgentContext` gains
`skills: list[RuntimeSkill] = field(default_factory=list)`. `Agent` gains a CONCRETE method (so the
unowned `coding_agent.py`/`latex_agent.py`, which only override the still-abstract
`build_messages`, need no edits):

```python
class Agent(ABC):
    max_tool_calls: int | None = None        # NEW: per-agent budget override hook (D2 step 3)

    async def build_prompt(self, actx: AgentContext) -> list[LLMMessage]:
        messages = await self.build_messages(actx)
        block = render_skill_block(actx.skills)
        if block:
            if messages and messages[0].role == "system":
                messages[0] = LLMMessage(role="system",
                                         content=messages[0].content + "\n\n" + block)
            else:
                messages.insert(0, LLMMessage(role="system", content=block))
        return messages
```

**Runtime wiring** (`runtime.py::run`): after resolving the actor, before building `tool_ctx`:

```python
actx_skills = await load_skills(self.db, run.project_id, run.agent_type)
run.skill_ids_json = [{"slug": s.slug, "version": s.version} for s in actx_skills]
```

(committed together with the RUNNING transition at lines 85-87). `emitter.started` gains the skill
list (D9). Tool policy:

```python
def _effective_tools(agent, skills) -> set[str]:
    granted = set()
    for s in skills:
        granted |= set(s.tool_permissions)          # already ∩ ALLOWED_TOOLS (service side)
    return set(agent.allowed_tools) | (granted & set(TOOL_REGISTRY))
```

i.e. **skill grants = union of manifest `tool_permissions`, intersected with the platform
`ALLOWED_TOOLS` declaration allowlist AND the live `TOOL_REGISTRY`, then unioned with the agent's
own tools**. Declared-but-unregistered tools (e.g. `memory.read`, `experiment.read`) silently do
not materialize. `ToolContext.allowed_tools` receives `effective_tools`, and `llm_tools` (D2.2) is
built from it — a skill can therefore ADD read-only tools to an agent but can never exceed the
registry or the manifest allowlist. Per-skill attribution (`granted_by` stamping on tool events)
requires a `tools.py` change → Cross-partition request CP-2; until it lands, attribution is
recoverable from `skill_ids_json` + the grant map (logged at run start via structlog).

### D7. Seq allocation & event-persistence decoupling

**Tool calls** (`agents/repository.py::ToolCallRepository`): add an in-instance monotonic
allocator — `self._seq_next: dict[uuid.UUID, int]`. `next_seq(run_id)`: if cached, return and
increment; else seed from `select(func.max(ToolCall.seq))` + 1 (0 when None), cache, return.
`ToolBroker` already holds one repository instance per run (`tools.py:131-133`), so all calls in a
run share the cache; the COUNT(*) re-read race is gone even if tool execution is ever parallelized.
Backstop for zombie double-execution (acks_late redelivery): new
`UniqueConstraint("agent_run_id", "seq", name="uq_tool_call_run_seq")` on the `ToolCall` model
(DDL in DB changes). No retry logic needed in the (unowned) broker: a genuine duplicate executor
SHOULD fail loudly.

**Events** (`agents/repository.py::AgentRunEventRepository` + `runtime/events.py::EventEmitter`):
same in-instance allocator for `next_seq` (seeded from `max(seq)+1`; the existing
`uq_agent_run_event_run_seq` constraint stays the backstop). `EventEmitter.emit` decouples
persistence from the run: wrap the persist branch in `try/except IntegrityError`: rollback, re-seed
the allocator from DB (`repo.reset_seq_cache(run_id)`), retry the append ONCE; on second failure
log `event_persist_failed` and continue (the live publish still goes out; a lost persisted event
must never fail the run — supersedes map row 32 behavior).

### D8. Mock provider: realistic multi-turn + strict protocol validation (`llm/mock.py`)

Rewritten `MockLLMProvider(strict_protocol: bool = True)`:

1. **Protocol validation** (runs first when `strict_protocol`): walk `messages` and raise
   `ValueError("mock protocol violation: ...")` if (a) a `system` message appears after a
   non-system one; (b) a `tool` message is not part of a contiguous block immediately following an
   assistant message with `tool_calls`, with ids exactly matching in order; (c) an assistant
   message has `tool_calls` but the following block is missing/short. This makes the offline test
   suite reject the exact shapes real APIs reject — the load-bearing regression guard for D1/D2.
2. **Scripted multi-turn tool use**: let `called = {name of every ToolCall in prior assistant
   messages}`. If `tools` and `force_structured` is False: pick the first tool (in the order the
   runtime supplied, which is name-sorted) whose name is NOT in `called`; if found and
   `len(called) < 2`: yield `ToolCall(id=f"call_{len(called)+1}", name=..., arguments=...)`
   (arguments: `{"query": last_user_text, "limit": 5}` for `paper.search`, `{}` otherwise), then
   `Usage(12, 0)`, `StreamDone("tool_use")`, return. So a research run now exercises TWO tool
   iterations (`library.list` + `paper.search` in sorted order) and the full pairing round-trip.
3. **Final answer**: as today — structured object when `response_schema` (coding-style when
   `"files" in properties`, critic-style otherwise; `citations` from tool results), prose
   otherwise. Two additions: (a) if any system message contains `"## Active skills"`, prefix the
   prose answer with `"[skills-active] "` and add `"_skills_active": true` into structured objects
   — deterministic hook for injection tests; (b) when `force_structured=True`, ALWAYS emit the
   structured object (never prose, never tools). Usage `(20, max(1, len(text)//4))` per final
   iteration; totals are therefore exact and assertable after summing.
4. A test-only subclass hook stays possible because the class is small; tests needing bespoke
   behavior (garbage JSON, slow streams) subclass or wrap it and inject via
   `AgentRuntime(db, llm=...)` (existing injection point, `runtime.py:57,61`).

### D9. Events

No new event families. Additive payload changes:
- `agent.run.started` payload: `{"agent_type": ..., "skills": [{"slug": str, "version": str}]}`.
- `agent.run.failed` payload: `{"error": str, "code": str}` where code ∈
  `"timeout" | "structured_output_parse_error" | "llm_error" | "config_error" | "agent_error"`.
`EventEmitter.started(agent_type, skills)` and `.failed(error, code="agent_error")` signatures
updated (both callers are in `runtime.py`, owned).

### D10. Worker hardening (`apps/worker/**`)

`tasks/agents.py`: the task gains Celery limits derived from settings:
`@app.task(name="agents.run_agent", soft_time_limit=settings.agent_run_timeout_seconds + 60,
time_limit=settings.agent_run_timeout_seconds + 120)` — a backstop (prefork/Unix) behind the
authoritative in-loop `asyncio.timeout`; settings imported at module load (matches
`app.py:18-22` pattern). Docstring documents that the runtime's own timeout is primary and this
guard exists so a wedged event loop cannot poison the single-prefetch worker. No queue changes.

---

## API contract changes

None. No REST routes are added, removed, or reshaped. (Run cancellation, replay, and creation
endpoints are untouched; their behavior improves server-side only.)

Error-path behavior change (documented, not a schema change): agent runs that previously ended
COMPLETED with empty `output_json` on unparseable structured output now end
`status="failed"` with `error_json = {"message": ..., "code": "structured_output_parse_error"}`.

## WS events

- `agent.run.started` — payload gains `skills: [{slug: string, version: string}]` (always present,
  possibly empty array).
- `agent.run.failed` — payload gains `code: string` (always present; default `"agent_error"`).
- All other `agent.run.*` events unchanged. No new event type strings.

## DB changes

- `tool_calls`: add `UNIQUE (agent_run_id, seq)` as constraint `uq_tool_call_run_seq`
  (SQLAlchemy: add `__table_args__ = (UniqueConstraint("agent_run_id", "seq",
  name="uq_tool_call_run_seq"),)` to `ToolCall` in `agents/models.py`).
  Backfill note for the migration agent: duplicates are theoretically possible from the historical
  COUNT(*) race; before adding the constraint, renumber duplicates per run with
  `ROW_NUMBER() OVER (PARTITION BY agent_run_id ORDER BY created_at, id) - 1`.
- No new tables, columns, or enums. (`agent_runs.skill_ids_json` already exists and starts being
  populated.)

## shared-schemas additions

In `packages/shared-schemas/src/events.ts` (consolidated by the schemas agent):
- `AgentRunStartedPayload`: add `skills: { slug: string; version: string }[]`.
- `AgentRunFailedPayload`: add `code: string`.
- No changes to the `EVENT_TYPES` union.

## New dependencies

None. (`anthropic>=0.40` already exists as the `anthropic` optional extra in
`apps/api/pyproject.toml:28`; `httpx` already present. The mock path and all tests require neither.)

## File-by-file plan

| File | Action | Change |
|---|---|---|
| `apps/api/researchos/agents/llm/base.py` | modified | `LLMMessage.tool_calls: list[ToolCall] \| None = None`; `LLMProvider.stream` gains `force_structured: bool = False`; docstring documents the 3 protocol invariants (D1). |
| `apps/api/researchos/agents/llm/structured.py` | created | `StructuredOutputError`, `extract_json`, `_check_required` (D3a). Pure functions, no I/O. |
| `apps/api/researchos/agents/llm/anthropic.py` | modified | Constructor kwargs (model/api_key/base_url) + timeout; `max_tokens` from settings; `emit_result` schema transmission + `tool_choice` forcing under `force_structured`; `_to_anthropic_messages` rewrite (tool_use blocks, merged tool_result user turns, empty-turn skip) (D3, D4). |
| `apps/api/researchos/agents/llm/openai_compatible.py` | modified | Key-leak fix (`openai_api_key`, no anthropic fallback); `response_format` json_schema + single retry-without on 4xx mentioning it; `stream_options.include_usage`; `max_tokens`; finish_reason tracking fix; `_to_openai` tool_calls serialization; injectable `http_client`; module-top json import (D3, D4). |
| `apps/api/researchos/agents/llm/factory.py` | modified | Deterministic active-config ordering; Anthropic DB config pass-through; delete `get_llm_provider_sync` (D5). |
| `apps/api/researchos/agents/llm/mock.py` | modified | Strict protocol validation, scripted 2-iteration multi-tool conversations, `force_structured`, skills-active marker, per-iteration usage (D8). |
| `apps/api/researchos/agents/llm/__init__.py` | modified | Export `structured` helpers if convenient; no removals except none needed (`get_llm_provider_sync` was never exported). |
| `apps/api/researchos/agents/runtime/runtime.py` | modified | Rewritten `_run_loop` (D2); `asyncio.timeout` + `AgentCancelledError` + `_recover_session` (D2/D5); structured-output gate before finalize (D3); skill loading + `skill_ids_json` + effective-tools computation (D6); usage summing; ToolDenied-recoverable handling. |
| `apps/api/researchos/agents/runtime/base.py` | modified | `AgentContext.skills` field; concrete `Agent.build_prompt`; `Agent.max_tool_calls: int \| None = None` (D6, D2). `build_messages` stays abstract and untouched for subclasses. |
| `apps/api/researchos/agents/runtime/skills_injection.py` | created | `_MODULE_BY_AGENT`, `load_skills`, `render_skill_block`, `skill_tool_grants` (D6). |
| `apps/api/researchos/agents/runtime/events.py` | modified | `started(agent_type, skills)`; `failed(error, code)`; IntegrityError-tolerant persist with one retry + never-fail semantics (D7, D9). |
| `apps/api/researchos/agents/runtime/critic_agent.py` | modified | Remove silent `parsed = {}` fallback — raise on JSONDecodeError (defense in depth under D3 gate). |
| `apps/api/researchos/agents/runtime/research_agent.py` | modified | No functional change required; docstring note that final text = last iteration only. |
| `apps/api/researchos/agents/runtime/experiment_agent.py` | modified | No structural change (deterministic summary retained); comment updated: LLM text still streamed for UX, deterministic result persisted — unchanged by design this session. |
| `apps/api/researchos/agents/models.py` | modified | `ToolCall.__table_args__` unique constraint (DB changes). |
| `apps/api/researchos/agents/repository.py` | modified | In-instance monotonic seq allocators for `ToolCallRepository.next_seq` and `AgentRunEventRepository.next_seq` + `reset_seq_cache` (D7). |
| `apps/api/researchos/skills/service.py` | modified (read-path only) | `RuntimeSkill` dataclass + `list_enabled_for_runtime` (D6). No existing method touched. |
| `apps/worker/researchos_worker/tasks/agents.py` | modified | soft/hard time limits from settings (D10). |
| `apps/api/tests/test_llm_protocol.py` | created | See Test plan. |
| `apps/api/tests/test_structured_output.py` | created | See Test plan. |
| `apps/api/tests/test_skill_injection.py` | created | See Test plan. |
| `apps/api/tests/test_agent_runtime.py` | modified | Multi-turn, cancellation, timeout, usage-sum, failure-code assertions. |
| `apps/worker/tests/test_health_task.py` | untouched | — |

Estimated delta: ~1400 changed/added lines including tests — within budget.

## Cross-partition requests

- **CP-1 → common/config owner**: add to `Settings` (`apps/api/researchos/common/config.py`, LLM
  section): `llm_max_output_tokens: int = 8192` (env `LLM_MAX_OUTPUT_TOKENS`),
  `llm_request_timeout_seconds: float = 120.0` (env `LLM_REQUEST_TIMEOUT_SECONDS`),
  `openai_api_key: str = ""` (env `OPENAI_API_KEY`). Until merged, the adapters read them via
  `getattr(settings, "llm_max_output_tokens", 8192)`-style guards so this partition builds alone.
- **CP-2 → coding-git (owner of `agents/runtime/tools.py`)**: (a) keep the module-level names
  `TOOL_REGISTRY: dict[str, ToolSpec]` and `ToolSpec(name, description, parameters, impl)` stable
  — the runtime and skill broker key off them; (b) add field
  `granted_by: dict[str, str] = field(default_factory=dict)` to `ToolContext` (tool name →
  `"agent"` or granting skill slug; the runtime will populate it) and include
  `"granted_by": ctx.granted_by.get(tool_name, "agent")` in the `tool_call_started` event payload;
  (c) `ToolBroker` must continue to raise `ToolDenied` (not a generic error) for
  unknown/unpermitted tools — the runtime now converts it into a recoverable tool-result message
  (D2.f) and this contract is what makes that safe.
- **CP-3 → coding-git (owner of `coding_agent.py`)**: `Agent.max_tool_calls` override hook now
  exists (set e.g. `max_tool_calls = 25` per WS2-1); the runtime guarantees `output_text` passed to
  finalize is normalized valid JSON when `response_schema` is set, so the silent-drop
  `json.loads → {}` fallback in `coding_agent.py:70-73` is dead code they may remove.
- **CP-4 → skills partition owner (manifest/seed)**: when new read-only tools register (e.g.
  `workspace.read`), extend `skills/manifest.py::ALLOWED_TOOLS` accordingly; the injection layer
  automatically materializes any declared tool that appears in `TOOL_REGISTRY`.
- **CP-5 → shared-schemas consolidator**: the two payload additions listed above.

## MUST / SHOULD / STRETCH

**MUST**
1. `LLMMessage.tool_calls` + rewritten `_run_loop` with per-iteration text reset, proper
   assistant/tool pairing, usage summing, last-iteration final answer (D1, D2).
2. Both adapters round-trip tool turns correctly (`_to_anthropic_messages`, `_to_openai`) (D4).
3. `response_schema` transmitted by both adapters; `extract_json`; runtime FAILS the run with
   `structured_output_parse_error` on unparseable/incomplete structured output (D3).
4. Anthropic `max_tokens` raised via settings; request timeouts on both adapters (D4, CP-1 guard).
5. OpenAI adapter: anthropic-key bearer fallback removed; finish_reason fix; include_usage (D4).
6. Factory: Anthropic DB config pass-through + deterministic active-row pick (D5).
7. Cancellation checked per iteration and between tool calls; `asyncio.timeout` enforcement with
   clean session recovery (D2, D5).
8. Skill injection: `list_enabled_for_runtime`, `render_skill_block`, prompt append via
   `build_prompt`, tool-grant union∩allowlist∩registry, `skill_ids_json` populated, `started`
   event carries skills (D6, D9).
9. Mock provider: strict protocol validation + 2-iteration scripted tool use + `force_structured`
   + skills marker (D8).
10. Seq allocators + `uq_tool_call_run_seq` + event-persist decoupling (never fails the run) (D7).

**SHOULD**
11. Synthesis round on budget exhaustion (`tool_budget_exhausted` stub results + forced final
    iteration with `force_structured`) (D2.g).
12. ToolDenied → recoverable self-correction message, bounded at 2 (D2.f).
13. OpenAI `response_format` 4xx retry-without fallback (D3).
14. Worker soft/hard time limits (D10).
15. `agent.run.failed` `code` field end-to-end (D9).

**STRETCH**
16. Populate `AgentRun.cost_json` with `{"estimated": true, input_tokens, output_tokens}` derived
    from summed usage (no pricing tables — counts only).
17. `skills_injection` char-budget truncation emits a structlog warning with the dropped slugs.
18. Per-skill grant logging surfaced in `tool_call_started` payload once CP-2 lands.

Degradation rule: items 11-18 can each be dropped independently; MUST items cannot. If item 8's
tool-grant half is at risk, ship prompt injection + `skill_ids_json` alone (grants default to
`agent.allowed_tools` exactly as today).

## Acceptance criteria (verifiable via local gates + code reading; DB tests deferred to CI)

1. `ruff check` and `mypy` pass over `apps/api` and `apps/worker` (all new/changed code typed;
   `LLMProvider` protocol updated consistently — mypy will catch any adapter missing
   `force_structured`).
2. Reading `runtime.py`: no `LLMMessage(role="assistant", content="")` remains; `iter_text` is
   reset inside the loop; `usage_total` uses `+=`; `is_cancel_requested` awaited inside the loop
   body and inside the per-call loop; `asyncio.timeout(settings.agent_run_timeout_seconds)` wraps
   the loop; when `agent.response_schema` is set, a failed `extract_json` leads to
   `_finalize_failed(..., code="structured_output_parse_error")` and `finalize` is not called.
3. Reading `anthropic.py`: `"max_tokens": 1024` is gone; `emit_result` tool present when
   `response_schema`; `_to_anthropic_messages` emits `tool_use` blocks and merges consecutive tool
   results into one user turn.
4. Reading `openai_compatible.py`: `anthropic_api_key` does not appear; `stream_options`,
   `response_format`, and explicit finish_reason tracking do.
5. Reading `factory.py`: anthropic branch passes `cfg.model/api_key/base_url`;
   `order_by(...updated_at.desc()...)` present; `get_llm_provider_sync` absent from the codebase
   (grep clean).
6. Reading `mock.py`: a malformed history (assistant tool_calls without paired tool messages)
   raises; the same test asserts the real runtime shape passes.
7. Reading `agents/models.py`: `uq_tool_call_run_seq` constraint declared. Reading
   `repository.py`: no `func.count()` in `next_seq`.
8. Reading `skills/service.py` diff: only additions; pinned `skill_version_id` (not
   `latest_version`) is joined.
9. `pytest` suite (CI): all tests below green; existing `test_agent_runtime.py`,
   `test_coding_agent.py`, `test_ws_contract.py` still green (ws contract needs no change — no new
   event types).

## Test plan (authored now, run in CI; no network, mock provider only)

`apps/api/tests/test_llm_protocol.py` (pure, no DB):
- `_to_anthropic_messages`: assistant+tool_calls → text block + tool_use blocks; two consecutive
  tool msgs → ONE user turn with two tool_result blocks in order; empty assistant filler skipped;
  system excluded.
- `_to_openai`: tool_calls serialized with `json.dumps` arguments; `content: None` when empty.
- `extract_json`: direct object; fenced ```json; prose-wrapped balanced object; nested braces in
  strings; list input rejected; garbage raises `StructuredOutputError`; `_check_required` missing
  key raises.
- Mock strict validation: runtime-shaped history passes; empty-assistant-before-tool history (the
  OLD bug shape) raises `ValueError`.

`apps/api/tests/test_structured_output.py` (DB, mock/injected providers):
- Critic run with a provider stub yielding non-JSON text → run FAILED,
  `error_json["code"] == "structured_output_parse_error"`, no `ResearchCritique` row, failed event
  has the code.
- Critic run via standard mock → COMPLETED; `output_json` parses; citations filtered as before.
- `force_structured` path: provider stub that only emits valid JSON when `force_structured=True`,
  budget 0 via a `max_tool_calls = 0` test agent → synthesis round produces COMPLETED run (SHOULD
  item 11; marked xfail-safe if 11 is dropped).

`apps/api/tests/test_skill_injection.py` (DB):
- Install + enable a custom skill (module `research`, `prompt_template` with `{{tone}}`,
  `tool_permissions: ["library.list"]`) via `SkillService`; run a research agent; assert
  `run.skill_ids_json == [{"slug": ..., "version": "1.0.0"}]`, started event payload contains the
  skill, and mock's `[skills-active]` marker appears in `output_json["message"]`.
- Disabled installation injects nothing; `skill_ids_json == []`.
- `list_enabled_for_runtime` returns the PINNED version after a newer version is published;
  tool_permissions filtered to `ALLOWED_TOOLS`; cap 5 respected.
- `_effective_tools`: skill granting `paper.search` to `CriticAgent` widens the set; a declared
  tool absent from `TOOL_REGISTRY` does not.

`apps/api/tests/test_agent_runtime.py` (extended):
- Research run now records ≥2 tool calls (`library.list` + `paper.search`), tool_calls seq strictly
  0..N-1, events monotonic; usage equals the summed per-iteration mock values.
- Mid-loop cancellation: provider stub sets the cancel flag from inside its second `stream` call →
  run CANCELLED, `agent.run.cancelled` event persisted, no completed event.
- Timeout: provider stub with `await asyncio.sleep(...)` + settings override
  (`agent_run_timeout_seconds=0`… use monkeypatched Settings) → run FAILED with `code == "timeout"`.
- ToolDenied recovery: stub requests a fake tool name then answers → run COMPLETED, one failed
  tool_call row persisted (SHOULD item 12; skip-marked if dropped).

`apps/worker/tests`: `test_agents_task_limits.py` — import the task object, assert
`soft_time_limit`/`time_limit` computed from settings (pure import test, no broker).

No Playwright changes (no UI surface in this partition).

## Explicitly out of scope

- `tools.py`, `coding_agent.py`, `latex_agent.py` internals (coding-git partition) — including new
  tools (`workspace.read`/`grep`), read-before-write enforcement, and per-hunk patches.
- Alembic migration authoring (DDL described above; consolidated by the migration agent).
- LLM API-key encryption at rest, provider health checks/fallback chains, per-agent-type model
  routing, embeddings (`embed()` — WS1-4 partition).
- New WS event families (experiment/latex/skill lifecycle events), WS reconnect/replay client work.
- Skill uninstall/search endpoints, manifest `config_schema` JSON-Schema validation, marketplace
  usage counters (STRETCH 16-18 aside), and the project-level tool kill-switch policy table
  (WS8-1 sketch step 5) — deferred; the injection layer is written so a policy set can be one more
  intersection term.
- Prompt-quality iteration against real models (mock verifies plumbing, not prose quality).
