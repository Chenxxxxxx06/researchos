---
name: researchos-control-plane
description: Control a ResearchOS Mission DAG through the authenticated CLI lease protocol. Use when the user asks OpenClaw to inspect, execute, monitor, or submit ResearchOS Agent tasks.
---

# ResearchOS Control Plane

ResearchOS is authoritative for task state, approval gates, permissions, artifacts, and provenance. OpenClaw acts as a bounded external worker. It must not edit the ResearchOS database or invent completion state.

## Preconditions

Use the repository-owned wrapper on this machine:

```powershell
$ROS = 'G:\code\code_vscode\aireasearch\scripts\openclaw-researchos.cmd'
```

Run authentication once under direct user control:

```powershell
& $ROS login --email <email>
& $ROS use <project-id>
& $ROS --json doctor
```

Never request or print the user's password, Zotero key, LLM key, SSH key, or ResearchOS cookie.

## Inspect the graph

```powershell
& $ROS --json orchestration graph <mission-id>
& $ROS --json orchestration tick <mission-id>
```

Read `status`, `role`, `agent_type`, `acceptance_json`, `permissions_json`, dependencies, gates, and prior artifacts before doing work.

## Lease one task

```powershell
& $ROS --json orchestration lease --owner openclaw --role <role> --lease-seconds 120
```

A 404 means no task is currently runnable. Do not bypass dependencies or approval gates.

## Heartbeat

For work longer than one minute, extend the lease before it expires:

```powershell
& $ROS --json orchestration heartbeat <lease-token> --running --lease-seconds 120
```

Stop immediately when the lease expires or ResearchOS rejects the heartbeat.

## Submit verifiable output

Every standard task requires at least one artifact with a real SHA-256 digest. Write output and artifact metadata to JSON files, then submit:

```powershell
& $ROS --json orchestration submit <lease-token> `
  --output-json @output.json `
  --artifacts-json @artifacts.json
```

Artifact example:

```json
[
  {
    "schema_name": "researchos.external-result/v1",
    "schema_version": 1,
    "content_hash": "<64 lowercase hex SHA-256>",
    "uri": "relative/path/to/artifact.json",
    "metadata": {"producer": "openclaw", "summary": "what was actually produced"},
    "input_artifact_versions": [],
    "visibility": "team"
  }
]
```

Never submit a placeholder hash, fabricated result, or artifact that cannot be opened.

## Built-in Agent dispatch

If the task has an `agent_type` and should run through the ResearchOS LLM runtime instead of OpenClaw:

```powershell
& $ROS --json orchestration dispatch <task-id> "<bounded instruction>" --context-json @context.json
```

## Approval gates

OpenClaw may display a pending gate but must not approve scope, repository import, patch application, paid compute, or release without the user's explicit decision. After the user decides:

```powershell
& $ROS --json orchestration gate <gate-id> approve --note "Approved by the user"
```

## Failure behavior

- Do not retry terminal failures silently.
- Do not start a second worker for an active lease.
- Keep negative experiment results.
- Record missing evidence as a gap rather than filling it with model output.
- Re-read the graph after submit because downstream tasks may have been promoted.
