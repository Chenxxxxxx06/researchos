# LLM Config Editing and Research Copilot Model Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add safe editing for saved project LLM configurations and let Research Copilot use a user-selected enabled configuration for the current page session.

**Architecture:** Give configuration creation and modification separate REST endpoints, carry an optional `llm_config_id` in the existing Agent Run context, and resolve that ID server-side with project and active-state checks. Keep Copilot selection in React component state, derive the default from the deterministically sorted configuration list, and preserve all existing callers by retaining the current default provider fallback when no ID is supplied.

**Tech Stack:** FastAPI, Pydantic v2, async SQLAlchemy, pytest, Next.js 15, React 19, TypeScript, TanStack Query, Vitest, Playwright.

## Global Constraints

- Use the approved ID-based approach; never route a selected model by mutable configuration name.
- Copilot selection lives only for the current mounted page; do not use localStorage, cookies, or a database preference.
- Default to the most recently updated enabled configuration.
- Show inactive configurations in Copilot but disable their options.
- An empty API Key on edit preserves the encrypted value already stored; a non-empty value replaces it after encryption.
- An explicitly selected missing, cross-project, or inactive configuration must fail; never silently switch to another model.
- Existing Agent callers that omit `llm_config_id` must keep the current default/environment/mock fallback behavior.
- Do not add a database migration or expose plaintext API keys.
- Preserve unrelated working-tree changes in `apps/api/researchos/agents/llm/openai_compatible.py`, `apps/api/tests/test_llm_protocol.py`, `AGENTS.md`, and `docs/test-reports/`.
- Every commit message must end with `Co-Authored-By: codex <noreply@anthropic.com>`.

## File Structure

- Create `apps/api/tests/test_llm_config.py`: integration coverage for create, ordered list, edit, secret preservation, authorization, and tenancy.
- Modify `apps/api/researchos/llm_config/schemas.py`: separate create and update request DTOs.
- Modify `apps/api/researchos/llm_config/router.py`: create-only POST, ID-based PATCH, deterministic list ordering, shared masked response conversion.
- Create `apps/api/tests/test_llm_provider_factory.py`: provider resolution coverage for explicit IDs and default selection.
- Modify `apps/api/researchos/agents/llm/factory.py`: optional explicit configuration resolution and provider construction.
- Modify `apps/api/researchos/agents/schemas.py`: add `llm_config_id` to validated run context.
- Modify `apps/api/researchos/agents/runtime/runtime.py`: pass the selected ID and persist typed resolution failures as failed runs.
- Modify `apps/api/tests/test_agents_api.py`: prove the selected ID is persisted in `input_json.context`.
- Modify `apps/api/tests/test_agent_runtime.py`: prove invalid explicit selections become durable failed runs.
- Modify `apps/web/lib/api/llmConfig.ts`: add the PATCH client and update input type.
- Modify `apps/web/lib/api/agents.ts`: type `llm_config_id` in Agent Run context.
- Create `apps/web/features/research/chat/modelSelection.ts`: pure default/fallback selection helpers.
- Create `apps/web/features/research/chat/modelSelection.test.ts`: DOM-free unit tests for selection behavior.
- Modify `apps/web/vitest.config.ts`: include feature-level pure unit tests.
- Modify `apps/web/features/management/SettingsPanel.tsx`: edit-mode form, optional edit key, and active toggle.
- Modify `apps/web/features/research/chat/ResearchChat.tsx`: selector UI, selection lifecycle, context merge, and no-enabled-config guard.
- Modify `apps/web/lib/i18n/dictionaries/zh-CN.ts`: Chinese edit and selector copy.
- Modify `apps/web/lib/i18n/dictionaries/en-US.ts`: matching English copy and dictionary key parity.
- Modify `apps/web/e2e/smoke.spec.ts`: assert the settings edit action and Copilot selector render.

---

### Task 1: Separate LLM Configuration Creation and Editing

**Files:**
- Create: `apps/api/tests/test_llm_config.py`
- Modify: `apps/api/researchos/llm_config/schemas.py`
- Modify: `apps/api/researchos/llm_config/router.py`

**Interfaces:**
- Consumes: existing `LLMProviderConfig`, `encrypt_secret`, `decrypt_secret`, `mask_secret`, `ProjectService.ensure_access`.
- Produces: `CreateLLMConfigRequest`, `UpdateLLMConfigRequest`, create-only `POST /projects/{project_id}/settings/llm`, and `PATCH /projects/{project_id}/settings/llm/{config_id}` returning `LLMConfigResponse`.

- [ ] **Step 1: Write failing create/edit integration tests**

Create `apps/api/tests/test_llm_config.py` with helpers that register a project owner and create configurations through the public API. Cover these exact behaviors:

```python
async def test_create_same_name_creates_distinct_rows(client) -> None:
    project_id = await _make_project(client, "llm-create@example.com")
    first = await _create_config(client, project_id, name="shared", model="model-a")
    second = await _create_config(client, project_id, name="shared", model="model-b")
    assert first.status_code == second.status_code == 200
    assert first.json()["id"] != second.json()["id"]


async def test_patch_updates_by_id_and_empty_key_preserves_secret(client, db_session) -> None:
    project_id = await _make_project(client, "llm-edit@example.com")
    created = await _create_config(client, project_id, api_key="original-secret")
    config_id = created.json()["id"]
    response = await client.patch(
        f"/projects/{project_id}/settings/llm/{config_id}",
        json={
            "name": "renamed",
            "provider_type": "openai_compatible",
            "base_url": "https://example.test/v1/",
            "model": "model-b",
            "api_key": "",
            "is_active": False,
            "description": "edited",
        },
        headers=csrf_headers(client),
    )
    assert response.status_code == 200
    assert response.json()["name"] == "renamed"
    assert response.json()["base_url"] == "https://example.test/v1"
    assert response.json()["is_active"] is False
    row = await db_session.get(LLMProviderConfig, uuid.UUID(config_id))
    assert decrypt_secret(row.api_key) == "original-secret"
```

Also add:

- `test_patch_non_empty_key_replaces_secret`
- `test_patch_cross_project_config_returns_404`
- `test_viewer_cannot_patch_config`
- `test_list_configs_orders_most_recently_updated_first`

Use the existing membership creation flow from `apps/api/tests/test_permissions.py` for the viewer case. Explicitly update `updated_at` and commit in the ordering test so it does not depend on clock timing.

- [ ] **Step 2: Run the new tests and verify the contract is missing**

Run:

```powershell
docker compose -f infra/docker/docker-compose.yml -f infra/docker/docker-compose.test.yml run --rm test sh -lc "uv pip install --system -e '.[dev]' >/dev/null && pytest tests/test_llm_config.py -q"
```

Expected: FAIL because PATCH returns 405 and the second same-name POST reuses the first row.

- [ ] **Step 3: Split request DTOs and implement the PATCH endpoint**

In `schemas.py`, replace the shared save DTO with explicit types:

```python
class CreateLLMConfigRequest(BaseModel):
    name: str = Field(default="default", max_length=100)
    provider_type: str = Field(default="openai_compatible", max_length=30)
    base_url: str = Field(default="https://api.openai.com/v1", max_length=1024)
    model: str = Field(default="gpt-4o", max_length=120)
    api_key: str = Field(default="", max_length=512)
    is_active: bool = True
    description: str | None = Field(default=None, max_length=500)


class UpdateLLMConfigRequest(CreateLLMConfigRequest):
    pass
```

In `router.py`:

- Add `_to_response(cfg: LLMProviderConfig) -> LLMConfigResponse` to keep masking identical across list/create/update.
- Sort list results with `.order_by(LLMProviderConfig.updated_at.desc(), LLMProviderConfig.id)`.
- Make POST always instantiate and add a new row; remove the name lookup.
- Add PATCH at `/{config_id}` and load the row with `cfg = await db.get(LLMProviderConfig, config_id)` plus the existing `cfg.project_id != project_id` guard.
- Apply `payload.base_url.rstrip("/")` consistently.
- Only assign `cfg.api_key = encrypt_secret(payload.api_key)` when `payload.api_key` is non-empty.
- Commit, refresh, and return `_to_response(cfg)`.

- [ ] **Step 4: Run focused API tests**

Run the Task 1 pytest command again.

Expected: all tests in `test_llm_config.py` PASS.

- [ ] **Step 5: Run formatting/static checks for touched backend files**

Run:

```powershell
docker compose -f infra/docker/docker-compose.yml -f infra/docker/docker-compose.test.yml run --rm test sh -lc "uv pip install --system -e '.[dev]' >/dev/null && ruff check researchos/llm_config tests/test_llm_config.py"
```

Expected: PASS with no lint errors.

- [ ] **Step 6: Commit the configuration API slice**

```powershell
git add apps/api/researchos/llm_config/schemas.py apps/api/researchos/llm_config/router.py apps/api/tests/test_llm_config.py
git commit -m "feat: add explicit LLM configuration editing" -m "Co-Authored-By: codex <noreply@anthropic.com>"
```

### Task 2: Carry the Selected Configuration Through Agent Runs

**Files:**
- Modify: `apps/api/researchos/agents/schemas.py`
- Modify: `apps/api/tests/test_agents_api.py`

**Interfaces:**
- Consumes: `CreateAgentRunRequest` and the existing JSON serialization in `agents/router.py`.
- Produces: `AgentRunContext.llm_config_id: uuid.UUID | None`, persisted as a JSON string under `input_json.context.llm_config_id`.

- [ ] **Step 1: Write a failing Agent API persistence test**

Append to `test_agents_api.py`:

```python
async def test_create_run_persists_llm_config_id(client) -> None:
    project_id = await _make_project(client, "agent-model@example.com")
    config_id = str(uuid.uuid4())
    response = await client.post(
        f"/projects/{project_id}/agents/runs",
        json={
            "agent_type": "research",
            "message": "use this model",
            "context": {"llm_config_id": config_id},
        },
        headers=csrf_headers(client),
    )
    assert response.status_code == 201
    detail = await client.get(
        f"/projects/{project_id}/agents/runs/{response.json()['agent_run_id']}"
    )
    assert detail.json()["input_json"]["context"]["llm_config_id"] == config_id
```

Import `uuid` at the top. Add a second assertion that a malformed ID returns 422.

- [ ] **Step 2: Run the two focused tests and verify failure**

Run:

```powershell
docker compose -f infra/docker/docker-compose.yml -f infra/docker/docker-compose.test.yml run --rm test sh -lc "uv pip install --system -e '.[dev]' >/dev/null && pytest tests/test_agents_api.py -q -k llm_config_id"
```

Expected: the valid request FAILS with 422 because the context field is not declared.

- [ ] **Step 3: Add the typed context field**

Add to `AgentRunContext`:

```python
llm_config_id: uuid.UUID | None = None
```

No router or database change is needed because `model_dump(mode="json", exclude_none=True)` already serializes UUIDs into the existing context JSON.

- [ ] **Step 4: Run the focused Agent API tests**

Run the Task 2 pytest command again.

Expected: both valid persistence and malformed-ID tests PASS.

- [ ] **Step 5: Commit the run-context contract**

```powershell
git add apps/api/researchos/agents/schemas.py apps/api/tests/test_agents_api.py
git commit -m "feat: persist selected LLM config on agent runs" -m "Co-Authored-By: codex <noreply@anthropic.com>"
```

### Task 3: Resolve Explicit Model Configurations Safely at Runtime

**Files:**
- Create: `apps/api/tests/test_llm_provider_factory.py`
- Modify: `apps/api/researchos/agents/llm/factory.py`
- Modify: `apps/api/researchos/agents/runtime/runtime.py`
- Modify: `apps/api/tests/test_agent_runtime.py`

**Interfaces:**
- Consumes: `get_llm_provider(project_id)` and `run.input_json.context.llm_config_id` from Task 2.
- Produces: `get_llm_provider(project_id: UUID | None = None, config_id: UUID | None = None) -> LLMProvider`; durable Agent Run failure for invalid explicit selections.

- [ ] **Step 1: Write failing factory tests**

Create `test_llm_provider_factory.py`. Insert real project rows and encrypted configurations through SQLAlchemy, then assert:

```python
async def test_explicit_config_id_selects_that_enabled_config(db_session) -> None:
    project, _user = await _setup_project(db_session, "factory-explicit@example.com")
    first = await _add_config(db_session, project.id, model="model-a", active=True)
    second = await _add_config(db_session, project.id, model="model-b", active=True)
    provider = await get_llm_provider(project.id, config_id=first.id)
    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.model == "model-a"
    assert second.id != first.id
```

Also add:

- `test_default_selection_uses_most_recent_enabled_config`
- `test_explicit_inactive_config_raises_validation_error`
- `test_explicit_cross_project_config_raises_not_found`
- `test_explicit_missing_config_raises_not_found`

Assert `provider.model` and `provider.base_url`, which are the public constructor-backed attributes exposed by `OpenAICompatibleProvider`; never assert or print decrypted database content.

- [ ] **Step 2: Run factory tests and verify the new argument is missing**

Run:

```powershell
docker compose -f infra/docker/docker-compose.yml -f infra/docker/docker-compose.test.yml run --rm test sh -lc "uv pip install --system -e '.[dev]' >/dev/null && pytest tests/test_llm_provider_factory.py -q"
```

Expected: FAIL with an unexpected `config_id` argument.

- [ ] **Step 3: Implement explicit factory resolution without changing fallback behavior**

Change the signature to:

```python
async def get_llm_provider(
    project_id: uuid.UUID | None = None,
    *,
    config_id: uuid.UUID | None = None,
) -> LLMProvider:
```

Extract provider construction into:

```python
def _provider_from_config(cfg: LLMProviderConfig) -> LLMProvider:
    if cfg.provider_type == "anthropic":
        from .anthropic import AnthropicProvider

        return AnthropicProvider(
            model=cfg.model or None,
            api_key=decrypt_secret(cfg.api_key) or None,
            base_url=cfg.base_url or None,
        )
    return OpenAICompatibleProvider(
        base_url=cfg.base_url,
        model=cfg.model,
        api_key=decrypt_secret(cfg.api_key),
    )
```

Resolution rules:

```python
if config_id is not None:
    if project_id is None:
        raise ValidationError("A project is required for an explicit LLM configuration.")
    cfg = await db.get(LLMProviderConfig, config_id)
    if cfg is None or cfg.project_id != project_id:
        raise NotFoundError("LLM config not found.")
    if not cfg.is_active:
        raise ValidationError("The selected LLM config is not active.")
    return _provider_from_config(cfg)
```

Leave the current active-project selection and environment/mock fallback unchanged when `config_id` is `None`.

- [ ] **Step 4: Run factory tests**

Run the Task 3 factory pytest command again.

Expected: all tests PASS.

- [ ] **Step 5: Write a failing durable-runtime-error test**

Append to `test_agent_runtime.py`:

```python
async def test_invalid_explicit_llm_config_fails_run_durably(db_session) -> None:
    run = await _research_run(db_session, "rt-llm-invalid@example.com")
    run.input_json = {
        "message": "use missing model",
        "context": {"llm_config_id": str(uuid.uuid4())},
    }
    await db_session.commit()
    await AgentRuntime(db_session).run(run.id)
    await db_session.refresh(run)
    assert run.status == AgentRunStatus.FAILED
    assert run.error_json["code"] == "not_found"
    assert "LLM config" in run.error_json["message"]
```

- [ ] **Step 6: Run the runtime test and verify the exception escapes**

Run:

```powershell
docker compose -f infra/docker/docker-compose.yml -f infra/docker/docker-compose.test.yml run --rm test sh -lc "uv pip install --system -e '.[dev]' >/dev/null && pytest tests/test_agent_runtime.py -q -k invalid_explicit_llm_config"
```

Expected: FAIL because provider resolution occurs before the runtime exception/finalization path.

- [ ] **Step 7: Resolve the selected provider inside a durable error boundary**

In `AgentRuntime.run`:

- Read `context = run.input_json.get("context", {})` before provider resolution.
- Parse `llm_config_id` with `uuid.UUID(str(value))` only when it exists; schema validation ensures newly created runs are valid, while the runtime conversion protects legacy/directly inserted JSON.
- Create the event emitter before resolution.
- Wrap explicit provider resolution in `try/except AppError` and call `_finalize_failed(run, emitter, exc.message, code=exc.code)` before returning.
- Preserve injected `self._llm` precedence for runtime unit tests.

The core call becomes:

```python
selected_config_id = context.get("llm_config_id")
try:
    llm = self._llm or await get_llm_provider(
        run.project_id,
        config_id=uuid.UUID(str(selected_config_id)) if selected_config_id else None,
    )
except (AppError, ValueError) as exc:
    code = exc.code if isinstance(exc, AppError) else "validation_error"
    await self._finalize_failed(run, emitter, str(exc), code=code)
    return run
```

- [ ] **Step 8: Run factory, runtime, and Agent API tests together**

Run:

```powershell
docker compose -f infra/docker/docker-compose.yml -f infra/docker/docker-compose.test.yml run --rm test sh -lc "uv pip install --system -e '.[dev]' >/dev/null && pytest tests/test_llm_provider_factory.py tests/test_agent_runtime.py tests/test_agents_api.py -q"
```

Expected: PASS.

- [ ] **Step 9: Commit runtime model selection**

```powershell
git add apps/api/researchos/agents/llm/factory.py apps/api/researchos/agents/runtime/runtime.py apps/api/tests/test_llm_provider_factory.py apps/api/tests/test_agent_runtime.py
git commit -m "feat: resolve selected LLM config for agent runs" -m "Co-Authored-By: codex <noreply@anthropic.com>"
```

### Task 4: Add Typed Frontend API Contracts and Selection Helpers

**Files:**
- Modify: `apps/web/lib/api/llmConfig.ts`
- Modify: `apps/web/lib/api/agents.ts`
- Create: `apps/web/features/research/chat/modelSelection.ts`
- Create: `apps/web/features/research/chat/modelSelection.test.ts`
- Modify: `apps/web/vitest.config.ts`

**Interfaces:**
- Consumes: Task 1 PATCH endpoint and Task 2 context field.
- Produces: `updateLLMConfig(projectId, configId, input)`, typed `AgentRunContext.llm_config_id`, `firstEnabledConfigId(configs)`, and `reconcileSelectedConfigId(configs, selectedId)`.

- [ ] **Step 1: Expand Vitest discovery and write failing pure selection tests**

Update `vitest.config.ts` include globs to:

```typescript
include: [
  'lib/**/*.test.ts',
  'components/**/*.test.ts',
  'features/**/*.test.ts',
],
```

Create `modelSelection.test.ts` with minimal `LLMConfig` fixtures and these assertions:

```typescript
it('selects the first enabled config from newest-first results', () => {
  expect(firstEnabledConfigId([inactive, newestEnabled, olderEnabled])).toBe(newestEnabled.id);
});

it('keeps a current selection while it remains enabled', () => {
  expect(reconcileSelectedConfigId([newestEnabled, olderEnabled], olderEnabled.id)).toBe(olderEnabled.id);
});

it('falls back when the selected config is removed or disabled', () => {
  expect(reconcileSelectedConfigId([newestEnabled, inactive], inactive.id)).toBe(newestEnabled.id);
});

it('returns an empty selection when no config is enabled', () => {
  expect(reconcileSelectedConfigId([inactive], inactive.id)).toBe('');
});
```

- [ ] **Step 2: Run the helper tests and verify missing exports**

Run:

```powershell
pnpm --filter web exec vitest run features/research/chat/modelSelection.test.ts
```

Expected: FAIL because `modelSelection.ts` does not exist.

- [ ] **Step 3: Implement the pure selection helpers**

Create:

```typescript
import type { LLMConfig } from '@/lib/api/llmConfig';

export function firstEnabledConfigId(configs: LLMConfig[]): string {
  return configs.find((config) => config.is_active)?.id ?? '';
}

export function reconcileSelectedConfigId(
  configs: LLMConfig[],
  selectedId: string,
): string {
  const selected = configs.find((config) => config.id === selectedId);
  return selected?.is_active ? selectedId : firstEnabledConfigId(configs);
}
```

- [ ] **Step 4: Add frontend request types**

In `llmConfig.ts`, add:

```typescript
export function updateLLMConfig(
  projectId: string,
  configId: string,
  input: SaveLLMConfigInput,
): Promise<LLMConfig> {
  return apiRequest(`/projects/${projectId}/settings/llm/${configId}`, {
    method: 'PATCH',
    body: input,
  });
}
```

Rename `SaveLLMConfigInput` to `LLMConfigInput` and use it for both create and update. Add to `AgentRunContext`:

```typescript
llm_config_id?: string;
```

- [ ] **Step 5: Run unit tests and typecheck**

Run:

```powershell
pnpm --filter web exec vitest run features/research/chat/modelSelection.test.ts
pnpm --filter web typecheck
```

Expected: PASS.

- [ ] **Step 6: Commit frontend contracts and pure behavior**

```powershell
git add apps/web/lib/api/llmConfig.ts apps/web/lib/api/agents.ts apps/web/features/research/chat/modelSelection.ts apps/web/features/research/chat/modelSelection.test.ts apps/web/vitest.config.ts
git commit -m "feat: add frontend model selection contracts" -m "Co-Authored-By: codex <noreply@anthropic.com>"
```

### Task 5: Add LLM Configuration Editing to Management Center

**Files:**
- Modify: `apps/web/features/management/SettingsPanel.tsx`
- Modify: `apps/web/lib/i18n/dictionaries/zh-CN.ts`
- Modify: `apps/web/lib/i18n/dictionaries/en-US.ts`

**Interfaces:**
- Consumes: `updateLLMConfig` and `LLMConfigInput` from Task 4.
- Produces: edit action and a shared add/edit form that never pre-fills plaintext API keys.

- [ ] **Step 1: Add the exact bilingual copy before wiring UI state**

Add matching dictionary keys:

```typescript
'settings.llmEdit': '修改',
'settings.llmEditTitle': '修改配置',
'settings.llmSaveChanges': '保存修改',
'settings.llmApiKeyHint': '留空则保留当前密钥',
'settings.llmActive': '启用',
```

and:

```typescript
'settings.llmEdit': 'Edit',
'settings.llmEditTitle': 'Edit configuration',
'settings.llmSaveChanges': 'Save changes',
'settings.llmApiKeyHint': 'Leave empty to keep the current key',
'settings.llmActive': 'Active',
```

Keep existing dictionary keys unique; replace the existing hint/active values rather than duplicating them.

- [ ] **Step 2: Introduce explicit form mode and prefill helpers**

In `SettingsPanel.tsx`:

- Add `editingId: string | null` state.
- Extend `emptyForm()` with `is_active: true`.
- Add `formForConfig(config: LLMConfig)` returning all editable non-secret fields with `api_key: ''`.
- Add an `update` mutation calling `updateLLMConfig(projectId, editingId, form)`.
- On either mutation success, close the form, clear `editingId`, reset the form, and invalidate `['llm-configs', projectId]`.
- On mutation error, leave the form open and unchanged.

- [ ] **Step 3: Add edit controls and safe secret behavior**

- Import `Pencil` from `lucide-react`.
- Add a labeled Edit button beside Test/Delete for every configuration.
- Clicking Add resets `editingId` to `null`; clicking Edit sets the ID, calls `formForConfig`, and opens the form.
- Make API Key `required` only in add mode. Render `settings.llmApiKeyHint` below the field in edit mode.
- Add a checkbox bound to `form.is_active`.
- Submit with `save.mutate(form)` in add mode or `update.mutate({ id: editingId, input: form })` in edit mode.
- Render `settings.llmSaveChanges` in edit mode and existing Save copy in add mode.
- Disable submit while either mutation is pending.

- [ ] **Step 4: Run frontend typecheck**

Run:

```powershell
pnpm --filter web typecheck
```

Expected: PASS with no dictionary-key or mutation-variable errors.

- [ ] **Step 5: Manually inspect add/edit state in the running UI**

Open `/projects/{projectId}/settings` and verify:

- Add shows an empty/new form and requires a key.
- Edit pre-fills all non-secret fields, leaves API Key blank, and shows the preservation hint.
- Cancel clears edit state.
- Saving a non-key field keeps the displayed key mask unchanged.
- Active can be toggled and reflected in the list badge.

- [ ] **Step 6: Commit management UI editing**

```powershell
git add apps/web/features/management/SettingsPanel.tsx apps/web/lib/i18n/dictionaries/zh-CN.ts apps/web/lib/i18n/dictionaries/en-US.ts
git commit -m "feat: edit LLM configs in management center" -m "Co-Authored-By: codex <noreply@anthropic.com>"
```

### Task 6: Add the Research Copilot Model Selector

**Files:**
- Modify: `apps/web/features/research/chat/ResearchChat.tsx`
- Modify: `apps/web/lib/i18n/dictionaries/zh-CN.ts`
- Modify: `apps/web/lib/i18n/dictionaries/en-US.ts`

**Interfaces:**
- Consumes: `reconcileSelectedConfigId`, sorted `listLLMConfigs`, and typed `AgentRunContext.llm_config_id`.
- Produces: page-local `selectedConfigId`, disabled inactive options, and selected ID merged into every research run request.

- [ ] **Step 1: Add exact bilingual selector and empty-state copy**

Add matching keys:

```typescript
'research.chat.model': '模型',
'research.chat.modelInactive': '未启用',
'research.chat.noActiveModel': '没有已启用的模型，请前往“管理中心 → 系统与模型”添加或启用配置。',
```

and:

```typescript
'research.chat.model': 'Model',
'research.chat.modelInactive': 'Inactive',
'research.chat.noActiveModel': 'No active model. Add or enable one in Management → System & models.',
```

- [ ] **Step 2: Add page-local selection lifecycle**

In `ResearchChat.tsx`:

```typescript
const [selectedConfigId, setSelectedConfigId] = useState('');
const configs = llm.data ?? [];
const activeConfigs = configs.filter((config) => config.is_active);
const hasRealLLM = activeConfigs.length > 0;

useEffect(() => {
  setSelectedConfigId((current) => reconcileSelectedConfigId(configs, current));
}, [configs]);
```

This keeps a valid manual choice during refetch, falls back if it disappears or becomes inactive, and naturally resets when the component unmounts on refresh/project navigation.

- [ ] **Step 3: Merge the selected ID with existing seed context**

Change the mutation body construction to preserve seed context:

```typescript
const body = seedToRequest(msg, s);
return createAgentRun(projectId, {
  agent_type: 'research',
  message: body.message,
  context: {
    ...body.context,
    llm_config_id: selectedConfigId,
  },
});
```

Change `submit()` and the submit button guard so an empty `selectedConfigId` cannot start a run.

- [ ] **Step 4: Render all configs while disabling inactive options**

Place a labeled native select above the message form:

```tsx
<select
  aria-label={t('research.chat.model')}
  value={selectedConfigId}
  onChange={(event) => setSelectedConfigId(event.target.value)}
  disabled={!hasRealLLM || mutation.isPending}
>
  {!selectedConfigId && <option value="">{t('research.chat.noActiveModel')}</option>}
  {configs.map((config) => (
    <option key={config.id} value={config.id} disabled={!config.is_active}>
      {config.name} · {config.model}
      {!config.is_active ? ` · ${t('research.chat.modelInactive')}` : ''}
    </option>
  ))}
</select>
```

When there is no enabled configuration, render the no-active-model message near the selector and keep the existing warning badge. Do not turn a list containing only inactive configurations into a “real LLM available” state.

- [ ] **Step 5: Run selection tests and typecheck**

Run:

```powershell
pnpm --filter web exec vitest run features/research/chat/modelSelection.test.ts
pnpm --filter web typecheck
```

Expected: PASS.

- [ ] **Step 6: Commit Copilot model selection**

```powershell
git add apps/web/features/research/chat/ResearchChat.tsx apps/web/lib/i18n/dictionaries/zh-CN.ts apps/web/lib/i18n/dictionaries/en-US.ts
git commit -m "feat: select models in Research Copilot" -m "Co-Authored-By: codex <noreply@anthropic.com>"
```

### Task 7: Add Browser Acceptance Coverage and Run Full Verification

**Files:**
- Modify: `apps/web/e2e/smoke.spec.ts`

**Interfaces:**
- Consumes: completed management and Copilot UI.
- Produces: smoke assertions for the new controls and final verification evidence.

- [ ] **Step 1: Add smoke assertions for both new controls**

On the Research Copilot page, add:

```typescript
await expect(page.getByLabel(/模型|Model/)).toBeVisible();
```

On the Settings page, locate the first saved LLM configuration. When one exists, assert its Edit button is visible and opens a form whose API Key input is empty:

```typescript
const editButton = page.getByRole('button', { name: /修改|Edit/ }).first();
if (await editButton.isVisible()) {
  await editButton.click();
  await expect(page.locator('input[type="password"]')).toHaveValue('');
  await expect(page.getByText(/保留当前密钥|keep the current key/i)).toBeVisible();
  await page.getByRole('button', { name: /取消|Cancel/ }).click();
}
```

- [ ] **Step 2: Run all focused backend tests**

Run:

```powershell
docker compose -f infra/docker/docker-compose.yml -f infra/docker/docker-compose.test.yml run --rm test sh -lc "uv pip install --system -e '.[dev]' >/dev/null && pytest tests/test_llm_config.py tests/test_llm_provider_factory.py tests/test_agents_api.py tests/test_agent_runtime.py tests/test_llm_protocol.py -q"
```

Expected: PASS. Including `test_llm_protocol.py` verifies the existing OpenAI-compatible tool-name fix remains intact.

- [ ] **Step 3: Run all frontend unit tests and typecheck**

Run:

```powershell
pnpm --filter web exec vitest run
pnpm --filter web typecheck
```

Expected: PASS.

- [ ] **Step 4: Run the frontend production build**

Run:

```powershell
pnpm --filter web build
```

Expected: PASS with a successful Next.js production build.

- [ ] **Step 5: Run Playwright smoke against the local stack**

Ensure the local API, worker, and web services are running, then run:

```powershell
pnpm --filter web test:e2e -- e2e/smoke.spec.ts
```

Expected: PASS, including visible model selector and edit-form secret behavior.

- [ ] **Step 6: Perform one minimal real-model end-to-end check**

Using an already configured, enabled test model:

1. Open Management → System & models.
2. Modify only the description and save with API Key blank.
3. Confirm connection testing still succeeds, proving the key was preserved.
4. Open Research Copilot, choose that configuration, and send one short prompt.
5. Read the resulting Agent Run detail and confirm `input_json.context.llm_config_id` equals the chosen ID.
6. Confirm the response completes through the chosen provider; do not repeat the paid call.

- [ ] **Step 7: Review the final diff for scope and secret safety**

Run:

```powershell
git status --short
git diff --check
git diff --stat HEAD~5..HEAD
rg -n "api_key.*(console|log|print)|decrypt_secret.*(log|print)" apps/api apps/web
```

Expected: no whitespace errors, no plaintext-secret logging, and no unrelated user files included in feature commits.

- [ ] **Step 8: Commit browser acceptance coverage**

```powershell
git add apps/web/e2e/smoke.spec.ts
git commit -m "test: cover LLM editing and Copilot model selection" -m "Co-Authored-By: codex <noreply@anthropic.com>"
```

## Completion Criteria

- Existing configurations can be edited by ID, including rename and active-state changes.
- Leaving the edit API Key empty preserves the original encrypted secret.
- Research Copilot lists every configuration, disables inactive entries, and defaults to the newest enabled configuration.
- A manual selection survives refetches for the current page only and is sent on every subsequent research run.
- Explicit invalid selections fail durably without switching providers.
- Existing Agent callers without a selection retain their previous behavior.
- Focused backend tests, all frontend unit tests, typecheck, production build, Playwright smoke, and one minimal real-provider call pass.
