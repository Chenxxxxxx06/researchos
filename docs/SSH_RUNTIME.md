# ResearchOS SSH Runtime

## 1. Purpose

The SSH runtime lets researchers run experiments on remote GPU servers while ResearchOS tracks commands, logs, metrics, artifacts, and provenance.

## 2. Core Concepts

- Runtime profile: saved server connection and execution settings.
- Remote workspace: project directory on the remote machine.
- Command: a single shell command or script invocation.
- Training job: a tracked experiment run launched through a runtime profile.
- Artifact sync: upload of logs, metrics, checkpoints, figures, and result files.

## 3. Runtime Profile

Fields:

- `name`
- `host`
- `port`
- `username`
- `auth_type`
- `encrypted_key_ref`
- `default_workdir`
- `python_env`
- `gpu_selector`
- `max_concurrent_jobs`
- `environment_json`

Secrets must be encrypted using a KMS or platform secret manager. Private keys must never be stored in plaintext or exposed to agents.

## 4. Execution Flow

1. User selects runtime profile.
2. Backend validates permissions.
3. Runtime worker opens SSH connection.
4. Worker validates remote workspace.
5. Worker launches command with structured environment variables.
6. stdout/stderr stream to Redis and WebSocket.
7. Metrics collector parses known metric formats or reads emitted JSONL.
8. Artifacts are synced to object storage.
9. Run status is finalized.

## 5. Agent Permissions

Agents may propose remote commands but should not execute them without user approval unless the project policy explicitly permits automation.

Approval must show:

- Target server
- Working directory
- Command
- Environment variables excluding secrets
- Expected outputs
- Estimated risk

## 6. Metrics Collection

Supported MVP patterns:

- Parse JSONL metrics written by training scripts.
- Read TensorBoard scalar exports when available.
- Parse simple stdout patterns as fallback.
- Poll GPU stats through `nvidia-smi` when installed.

## 7. Isolation

SSH servers are external trust boundaries. ResearchOS should:

- Avoid sharing credentials across projects by default.
- Limit concurrent commands per profile.
- Support command cancellation.
- Log command start/stop and user approvals.
- Redact secrets in logs.
- Prefer containerized remote execution when users provide Docker commands.

## 8. Failure Handling

Failure classes:

- Authentication failed
- Host unreachable
- Remote path missing
- Command failed
- Command timeout
- Artifact sync failed
- Metrics parse failed

The run should preserve logs even when artifact sync or metric parsing fails.

## 9. Future Extensions

- Kubernetes job launcher
- Slurm integration
- Ray cluster integration
- Cloud GPU provisioning
- Remote file sync
- Server health monitoring
- Runtime policy templates per organization
