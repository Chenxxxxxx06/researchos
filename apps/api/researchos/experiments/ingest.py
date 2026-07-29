"""NDJSON telemetry ingest: bearer-token auth, line parsing, processing.

Auth is a per-project token (``rosit_`` + 40 hex), stored hashed. No session
cookie and no CSRF — the router in ``ingest_router.py`` carries no cookie
dependencies. Partial acceptance: invalid lines are rejected individually and
never fail the whole request (payload-size caps excepted).
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

from pydantic import TypeAdapter
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from researchos.common.errors import AppError, ConflictError, NotFoundError, UnauthorizedError
from researchos.common.hashing import sha256_hex
from researchos.common.rate_limit import enforce_rate_limit
from researchos.figures.events import publish_run_event

from .models import ExperimentIngestToken, ExperimentLog, ExperimentMetric, ExperimentRun
from .repository import IngestTokenRepository, RunRepository
from .schemas import (
    IngestLine,
    IngestResult,
    LogLine,
    MetricLine,
    RejectedLine,
    StatusLine,
)
from .service import INGEST_TOKEN_PREFIX, ExperimentService

MAX_BODY_BYTES = 1_000_000
MAX_LINES = 1000
INGEST_RATE_LIMIT_PER_MINUTE = 120

_LINE_ADAPTER: TypeAdapter[MetricLine | LogLine | StatusLine] = TypeAdapter(IngestLine)


class PayloadTooLargeError(AppError):
    code = "payload_too_large"
    http_status = 413
    message = "Request body exceeds the ingest limits."


class InvalidIngestTokenError(UnauthorizedError):
    code = "invalid_token"
    message = "Ingest token is missing, unknown, or revoked."


def _line_error(exc: PydanticValidationError) -> str:
    first = exc.errors()[0]
    loc = ".".join(str(part) for part in first.get("loc", ()) if part != "t")
    msg = first.get("msg", "invalid line")
    return f"{loc}: {msg}" if loc else msg


def parse_ndjson(
    body: bytes,
) -> tuple[list[tuple[int, MetricLine | LogLine | StatusLine]], list[RejectedLine]]:
    """Parse all lines first; 1-based line numbers; blank lines are skipped."""

    if len(body) > MAX_BODY_BYTES:
        raise PayloadTooLargeError("Request body exceeds 1 MB.")
    text = body.decode("utf-8", errors="replace")
    raw_lines = text.split("\n")
    numbered = [(idx + 1, line.strip()) for idx, line in enumerate(raw_lines) if line.strip()]
    if len(numbered) > MAX_LINES:
        raise PayloadTooLargeError(f"Request exceeds {MAX_LINES} lines.")

    valid: list[tuple[int, MetricLine | LogLine | StatusLine]] = []
    rejected: list[RejectedLine] = []
    for lineno, raw in numbered:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            rejected.append(RejectedLine(line=lineno, error=f"invalid JSON: {exc.msg}"))
            continue
        try:
            valid.append((lineno, _LINE_ADAPTER.validate_python(payload)))
        except PydanticValidationError as exc:
            rejected.append(RejectedLine(line=lineno, error=_line_error(exc)))
    return valid, rejected


class IngestService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.tokens = IngestTokenRepository(db)
        self.runs = RunRepository(db)

    async def authenticate(
        self, authorization: str | None, run_id: uuid.UUID
    ) -> tuple[ExperimentIngestToken, ExperimentRun]:
        """Bearer token -> (token, run); 401 on bad token, 404 on foreign run."""

        if not authorization or not authorization.startswith("Bearer "):
            raise InvalidIngestTokenError()
        presented = authorization.removeprefix("Bearer ").strip()
        if not presented.startswith(INGEST_TOKEN_PREFIX):
            raise InvalidIngestTokenError()
        token = await self.tokens.get_active_by_hash(sha256_hex(presented))
        if token is None:
            raise InvalidIngestTokenError()
        await enforce_rate_limit(f"ingest:{token.id}", limit=INGEST_RATE_LIMIT_PER_MINUTE)
        run = await self.runs.get(token.project_id, run_id)
        if run is None:
            raise NotFoundError("Run not found.")
        return token, run

    async def process(
        self, token: ExperimentIngestToken, run: ExperimentRun, body: bytes
    ) -> IngestResult:
        valid, rejected = parse_ndjson(body)

        metric_lines = [line for _, line in valid if isinstance(line, MetricLine)]
        log_lines = [line for _, line in valid if isinstance(line, LogLine)]
        status_items = [(lineno, line) for lineno, line in valid if isinstance(line, StatusLine)]
        accepted = len(metric_lines) + len(log_lines)

        if metric_lines:
            self.db.add_all(
                ExperimentMetric(
                    run_id=run.id,
                    project_id=run.project_id,
                    name=line.name,
                    step=line.step,
                    value=line.value,
                )
                for line in metric_lines
            )
        last_seq: int | None = None
        if log_lines:
            first_seq = await self.runs.allocate_log_seqs(run.id, len(log_lines))
            for offset, line in enumerate(log_lines):
                self.db.add(
                    ExperimentLog(
                        run_id=run.id,
                        project_id=run.project_id,
                        seq=first_seq + offset,
                        level=line.level,
                        message=line.msg,
                    )
                )
            last_seq = first_seq + len(log_lines) - 1

        # Status lines go through the guarded transition; an invalid transition
        # rejects the line, never the request.
        service = ExperimentService(self.db)
        stale_anchor_ids: list[uuid.UUID] = []
        status_applied = False
        for lineno, status_line in status_items:
            try:
                if status_line.progress is not None:
                    run.progress = status_line.progress
                    status_applied = True
                if status_line.current_step is not None:
                    config = dict(run.config_json or {})
                    config["current_step"] = status_line.current_step
                    run.config_json = config
                    status_applied = True
                if run.status == status_line.status:
                    accepted += 1  # idempotent no-op
                    continue
                stale_anchor_ids.extend(await service.apply_run_status(run, status_line.status))
                status_applied = True
                accepted += 1
            except ConflictError as exc:
                rejected.append(RejectedLine(line=lineno, error=exc.message))

        token.last_used_at = datetime.now(tz=UTC)  # best-effort, same commit
        await self.db.commit()
        await self.db.refresh(run)

        await self._publish_events(
            run,
            metric_lines=metric_lines,
            log_count=len(log_lines),
            last_seq=last_seq,
            status_changed=status_applied,
            stale_anchor_ids=stale_anchor_ids,
        )
        rejected.sort(key=lambda r: r.line)
        return IngestResult(accepted=accepted, rejected=rejected, run_status=run.status)

    async def _publish_events(
        self,
        run: ExperimentRun,
        *,
        metric_lines: list[MetricLine],
        log_count: int,
        last_seq: int | None,
        status_changed: bool,
        stale_anchor_ids: list[uuid.UUID],
    ) -> None:
        if metric_lines:
            await publish_run_event(
                event_type="experiment.metric.recorded",
                project_id=run.project_id,
                run_id=run.id,
                payload={
                    "run_id": str(run.id),
                    "count": len(metric_lines),
                    "names": sorted({line.name for line in metric_lines}),
                },
            )
        if log_count and last_seq is not None:
            await publish_run_event(
                event_type="experiment.log.appended",
                project_id=run.project_id,
                run_id=run.id,
                payload={"run_id": str(run.id), "count": log_count, "last_seq": last_seq},
            )
        if status_changed:
            service = ExperimentService(self.db)
            await service._publish_run_status(run)
            await service._publish_anchor_staleness(run.project_id, stale_anchor_ids)
