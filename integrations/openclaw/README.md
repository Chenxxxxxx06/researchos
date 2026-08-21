# OpenClaw integration

ResearchOS exposes its durable Mission DAG through the `researchos orchestration` CLI commands. OpenClaw is installed on this development machine and can consume `SKILL.md` as the bounded worker policy.

## Current local connection

```powershell
$ROS = 'G:\code\code_vscode\aireasearch\scripts\openclaw-researchos.cmd'
& $ROS --json doctor
& $ROS --json adapters doctor
```

The CLI stores its authenticated session and active project under the user's private ResearchOS home directory. Secrets are not placed in this repository.

## Supported operations

- inspect or bootstrap a Mission DAG
- reconcile Coordinator state
- dispatch a built-in ResearchOS Agent
- lease work to OpenClaw or another external worker
- heartbeat an active lease
- submit output with hashed artifacts
- present approval gates for an explicit human decision

OpenClaw does not receive an unrestricted database token and cannot bypass ResearchOS approval gates.
