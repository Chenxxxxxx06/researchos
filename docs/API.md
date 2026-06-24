# ResearchOS API Design

## 1. API Principles

- REST for durable resources.
- WebSocket for streaming and real-time state.
- Task handles for long-running work.
- Typed request and response schemas.
- Project-scoped permission checks on every endpoint.
- Idempotency keys for launch/install/compile operations.

## 2. Auth Flow

### Session Auth

- `POST /auth/login`
- `POST /auth/logout`
- `GET /auth/me`

### API Keys

- `GET /api-keys`
- `POST /api-keys`
- `DELETE /api-keys/{key_id}`

### Authorization

Roles:

- `owner`
- `admin`
- `researcher`
- `viewer`

Permissions are evaluated at organization, project, and resource level.

## 3. Project APIs

- `GET /projects`
- `POST /projects`
- `GET /projects/{project_id}`
- `PATCH /projects/{project_id}`
- `DELETE /projects/{project_id}`
- `GET /projects/{project_id}/activity`
- `GET /projects/{project_id}/memory-graph`

## 4. Research APIs

- `POST /projects/{project_id}/papers/search`
- `POST /projects/{project_id}/papers/import`
- `GET /projects/{project_id}/papers`
- `GET /projects/{project_id}/papers/{paper_id}`
- `POST /projects/{project_id}/papers/{paper_id}/summarize`
- `POST /projects/{project_id}/related-work/generate`
- `POST /projects/{project_id}/ideas`
- `GET /projects/{project_id}/ideas`
- `POST /projects/{project_id}/ideas/{idea_id}/critic-review`

## 5. Agent APIs

- `POST /projects/{project_id}/agents/runs`
- `GET /projects/{project_id}/agents/runs`
- `GET /projects/{project_id}/agents/runs/{run_id}`
- `POST /projects/{project_id}/agents/runs/{run_id}/cancel`
- `POST /projects/{project_id}/agents/runs/{run_id}/approve-tool-call`
- `GET /projects/{project_id}/agents/runs/{run_id}/trace`

Example request:

```json
{
  "agent_type": "critic",
  "message": "Review this idea for novelty and missing baselines.",
  "context": {
    "idea_id": "idea_123"
  },
  "skill_ids": ["cvpr-reviewer"]
}
```

## 6. IDE and Runtime APIs

- `GET /projects/{project_id}/files`
- `GET /projects/{project_id}/files/content?path=...`
- `POST /projects/{project_id}/files/patch`
- `GET /projects/{project_id}/git/status`
- `GET /projects/{project_id}/runtime/profiles`
- `POST /projects/{project_id}/runtime/profiles`
- `POST /projects/{project_id}/runtime/commands`
- `GET /projects/{project_id}/runtime/commands/{command_id}`
- `POST /projects/{project_id}/runtime/commands/{command_id}/cancel`

## 7. Experiment APIs

- `GET /projects/{project_id}/experiments`
- `POST /projects/{project_id}/experiments`
- `GET /projects/{project_id}/experiments/{experiment_id}`
- `POST /projects/{project_id}/experiments/{experiment_id}/runs`
- `GET /projects/{project_id}/experiment-runs`
- `GET /projects/{project_id}/experiment-runs/{run_id}`
- `GET /projects/{project_id}/experiment-runs/{run_id}/metrics`
- `GET /projects/{project_id}/experiment-runs/{run_id}/logs`
- `GET /projects/{project_id}/experiment-runs/{run_id}/artifacts`
- `POST /projects/{project_id}/experiment-runs/compare`
- `POST /projects/{project_id}/experiment-runs/{run_id}/paper-assets`

## 8. Paper Workspace APIs

- `GET /projects/{project_id}/latex-projects`
- `POST /projects/{project_id}/latex-projects`
- `GET /projects/{project_id}/latex-projects/{latex_project_id}/files`
- `PUT /projects/{project_id}/latex-projects/{latex_project_id}/files`
- `POST /projects/{project_id}/latex-projects/{latex_project_id}/compile`
- `GET /projects/{project_id}/latex-projects/{latex_project_id}/compile-jobs/{job_id}`
- `GET /projects/{project_id}/latex-projects/{latex_project_id}/citations`
- `POST /projects/{project_id}/latex-projects/{latex_project_id}/citations`

## 9. Skills APIs

- `GET /skills`
- `GET /skills/{skill_slug}`
- `GET /skills/{skill_slug}/versions`
- `POST /projects/{project_id}/skills/install`
- `GET /projects/{project_id}/skills`
- `PATCH /projects/{project_id}/skills/{installation_id}`
- `DELETE /projects/{project_id}/skills/{installation_id}`

## 10. Streaming APIs

Long-running endpoints return:

```json
{
  "task_id": "task_123",
  "status": "queued",
  "stream": "/ws?project_id=proj_123"
}
```

The client subscribes to WebSocket events for progress, logs, agent tokens, and completion.
