"""Bounded local experiment execution for autopilot pilot/full receipts."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import UTC, datetime

import structlog

from researchos.common.db import get_sessionmaker
from researchos.experiments.enums import ExperimentRunStatus
from researchos.experiments.models import (
    ExperimentArtifact,
    ExperimentLog,
    ExperimentMetric,
    ExperimentRun,
)
from researchos.figures.events import publish_run_event
from researchos.identity.repository import UserRepository
from researchos.orchestration.enums import MissionTaskStatus
from researchos.orchestration.models import MissionTask
from researchos.orchestration.schemas import AutopilotStartRequest
from researchos.orchestration.service import OrchestrationService
from researchos.workspace.terminal import run_command

logger = structlog.get_logger(__name__)
_METRIC_RE = re.compile(r"^RESEARCHOS_METRIC\s+(\{.*\})\s*$")
_PYTEST_RE = re.compile(r"(?:(\d+) failed,?\s*)?(?:(\d+) passed)")


async def run_local_autopilot_experiment(
    run_id: str,
    task_id: str,
    user_id: str,
    policy_json: dict,
) -> None:
    policy = AutopilotStartRequest.model_validate(policy_json)
    async with get_sessionmaker()() as db:
        run = await db.get(ExperimentRun, uuid.UUID(run_id))
        task = await db.get(MissionTask, uuid.UUID(task_id))
        actor = await UserRepository(db).get_by_id(uuid.UUID(user_id))
        if run is None or task is None or actor is None:
            logger.error("local_autopilot_run_missing", run_id=run_id, task_id=task_id)
            return
        scale = str((run.config_json or {}).get("scale") or "pilot")
        argv = policy.pilot_argv if scale == "pilot" else policy.full_argv
        timeout = policy.pilot_timeout_seconds if scale == "pilot" else policy.full_timeout_seconds
        if not argv:
            run.status = ExperimentRunStatus.FAILED
            run.finished_at = datetime.now(tz=UTC)
            task.status = MissionTaskStatus.TERMINAL_FAILED
            task.last_error_json = {"code": "experiment_command_required", "scale": scale}
            await db.commit()
            return
        run.status = ExperimentRunStatus.RUNNING
        run.started_at = datetime.now(tz=UTC)
        run.progress = 5.0
        await db.commit()
        await publish_run_event(
            event_type="experiment.run.started",
            project_id=run.project_id,
            run_id=run.id,
            payload={"run_id": str(run.id), "scale": scale, "progress": 5.0},
        )

        result = await run_command(
            run.project_id,
            argv=argv,
            cwd=policy.run_cwd,
            timeout_seconds=timeout,
        )
        stdout = str(result["stdout"])
        stderr = str(result["stderr"])
        lines = [("stdout", line) for line in stdout.splitlines()]
        lines.extend(("stderr", line) for line in stderr.splitlines())
        for seq, (source, line) in enumerate(lines[:1000]):
            db.add(
                ExperimentLog(
                    run_id=run.id,
                    project_id=run.project_id,
                    seq=seq,
                    level="error" if source == "stderr" else "info",
                    message=line[:20_000],
                )
            )

        metric_count = 0
        for line in stdout.splitlines():
            match = _METRIC_RE.match(line.strip())
            if not match:
                continue
            try:
                value = json.loads(match.group(1))
                name = str(value["name"])[:120]
                step = int(value.get("step", 0))
                metric_value = float(value["value"])
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                continue
            db.add(
                ExperimentMetric(
                    run_id=run.id,
                    project_id=run.project_id,
                    name=name,
                    step=step,
                    value=metric_value,
                )
            )
            metric_count += 1
        pytest_match = _PYTEST_RE.search(stdout)
        if pytest_match:
            failed = int(pytest_match.group(1) or 0)
            passed = int(pytest_match.group(2) or 0)
            total = failed + passed
            db.add(
                ExperimentMetric(
                    run_id=run.id,
                    project_id=run.project_id,
                    name="test_pass_rate",
                    step=0,
                    value=(passed / total if total else 0.0),
                )
            )
            metric_count += 1
        db.add(
            ExperimentMetric(
                run_id=run.id,
                project_id=run.project_id,
                name="command_success",
                step=0,
                value=1.0 if result["exit_code"] == 0 and not result["timed_out"] else 0.0,
            )
        )
        metric_count += 1
        receipt = {
            "argv": argv,
            "cwd": result["cwd"],
            "exit_code": result["exit_code"],
            "duration_ms": result["duration_ms"],
            "timed_out": result["timed_out"],
            "stdout_sha256": hashlib.sha256(stdout.encode()).hexdigest(),
            "stderr_sha256": hashlib.sha256(stderr.encode()).hexdigest(),
            "metric_count": metric_count,
            "scale": scale,
        }
        db.add(
            ExperimentArtifact(
                run_id=run.id,
                project_id=run.project_id,
                artifact_type="execution_receipt",
                name=f"{scale}-execution-receipt.json",
                uri="",
                size_bytes=len(json.dumps(receipt)),
                metadata_json=receipt,
            )
        )
        success = result["exit_code"] == 0 and not result["timed_out"]
        run.status = ExperimentRunStatus.COMPLETED if success else ExperimentRunStatus.FAILED
        run.progress = 100.0
        run.finished_at = datetime.now(tz=UTC)
        task.status = MissionTaskStatus.READY if success else MissionTaskStatus.TERMINAL_FAILED
        task.output_json = {
            "experiment_run_id": str(run.id),
            "execution_receipt": receipt,
            "current_action": (
                "Pilot completed; waiting for metric analysis"
                if success
                else "Local experiment failed; inspect logs before retry"
            ),
        }
        task.last_error_json = (
            None
            if success
            else {
                "code": "local_experiment_failed",
                "exit_code": result["exit_code"],
                "timed_out": result["timed_out"],
            }
        )
        await OrchestrationService(db)._event(
            task,
            "experiment.local_completed" if success else "experiment.local_failed",
            task.output_json if success else (task.last_error_json or {}),
            actor_id=actor.id,
        )
        await db.commit()
        await publish_run_event(
            event_type="experiment.run.completed" if success else "experiment.run.failed",
            project_id=run.project_id,
            run_id=run.id,
            payload={"run_id": str(run.id), "status": run.status.value, "progress": 100.0},
        )
        if success:
            from researchos.common.celery_app import get_celery_client

            get_celery_client().send_task(
                "orchestration.advance",
                args=[str(run.project_id), str(task.mission_id), str(actor.id), policy_json],
                queue="default",
            )


async def mark_local_autopilot_failure(
    run_id: str,
    task_id: str,
    user_id: str,
    error: str,
) -> None:
    """Fold an unexpected worker exception into durable retry/terminal state."""

    async with get_sessionmaker()() as db:
        run = await db.get(ExperimentRun, uuid.UUID(run_id))
        task = await db.get(MissionTask, uuid.UUID(task_id))
        actor = await UserRepository(db).get_by_id(uuid.UUID(user_id))
        if run is None or task is None:
            return
        now = datetime.now(tz=UTC)
        run.status = ExperimentRunStatus.FAILED
        run.progress = 100.0
        run.finished_at = now
        task.status = (
            MissionTaskStatus.RETRYABLE_FAILED
            if task.attempt < task.max_attempts
            else MissionTaskStatus.TERMINAL_FAILED
        )
        task.last_error_json = {
            "code": "local_runner_exception",
            "message": error[:1000],
        }
        task.finished_at = now if task.status == MissionTaskStatus.TERMINAL_FAILED else None
        if actor is not None:
            await OrchestrationService(db)._event(
                task,
                "experiment.local_exception",
                task.last_error_json,
                actor_id=actor.id,
            )
        await db.commit()
        await publish_run_event(
            event_type="experiment.run.failed",
            project_id=run.project_id,
            run_id=run.id,
            payload={
                "run_id": str(run.id),
                "status": run.status.value,
                "error": error[:500],
            },
        )
