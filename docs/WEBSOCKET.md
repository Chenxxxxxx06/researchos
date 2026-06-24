# ResearchOS WebSocket Design

## 1. Purpose

WebSocket powers real-time ResearchOS workflows:

- Agent token streaming
- Agent tool-call updates
- Remote command logs
- Experiment metrics
- LaTeX compile status
- Runtime connection status
- Skill install progress
- Project activity feed

## 2. Connection

Endpoint:

```text
GET /ws?project_id={project_id}
```

Authentication:

- Browser session cookie or short-lived WebSocket token.
- Server validates user project membership.
- Server subscribes connection to project-scoped channels.

## 3. Event Envelope

```json
{
  "event_id": "evt_123",
  "event_type": "agent.run.token",
  "project_id": "proj_123",
  "resource_type": "agent_run",
  "resource_id": "run_123",
  "timestamp": "2026-01-01T00:00:00Z",
  "payload": {}
}
```

## 4. Event Types

### Agent Events

- `agent.run.started`
- `agent.run.token`
- `agent.run.tool_call.started`
- `agent.run.tool_call.completed`
- `agent.run.approval_required`
- `agent.run.completed`
- `agent.run.failed`
- `agent.run.cancelled`

### Experiment Events

- `experiment.run.queued`
- `experiment.run.started`
- `experiment.metric.recorded`
- `experiment.log.appended`
- `experiment.artifact.created`
- `experiment.run.completed`
- `experiment.run.failed`

### Runtime Events

- `runtime.ssh.connected`
- `runtime.ssh.disconnected`
- `runtime.command.started`
- `runtime.command.output`
- `runtime.command.completed`
- `runtime.command.failed`

### LaTeX Events

- `latex.compile.queued`
- `latex.compile.started`
- `latex.compile.log`
- `latex.compile.completed`
- `latex.compile.failed`

### Skill Events

- `skill.install.started`
- `skill.install.validated`
- `skill.install.completed`
- `skill.install.failed`

## 5. Client Subscriptions

The MVP can subscribe by project. Later versions should support targeted subscriptions:

- `project:{project_id}`
- `agent_run:{run_id}`
- `experiment_run:{run_id}`
- `latex_compile:{job_id}`
- `runtime_command:{command_id}`

## 6. Reliability

- Each event has a unique `event_id`.
- Persist audit-critical events in PostgreSQL.
- Redis pub/sub or streams can fan out live updates.
- Client should reconnect with last seen timestamp or event ID.
- Server should provide REST fallback to fetch current task state.

## 7. Backpressure

- Batch high-frequency metric updates.
- Truncate or chunk large log messages.
- Apply per-connection send buffers.
- Drop non-critical activity events before critical status events.

## 8. Security

- Never send events across project boundaries.
- Redact secrets from logs before event emission.
- Validate event payloads against typed schemas.
- Enforce connection limits and idle timeouts.
