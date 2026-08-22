"""AutoDesign-backed release generation.

ResearchOS owns authorization, model selection, and durable job metadata. The
AutoDesign service owns the long-running design harness and its editable files
under ``out/runs/<external_run_id>/final``. Provider secrets are forwarded only
for the start request and are never stored on the release job.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from urllib.parse import urljoin

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from researchos.common.config import get_settings
from researchos.common.errors import NotFoundError, ValidationError
from researchos.common.roles import ProjectRole
from researchos.common.secrets import decrypt_secret
from researchos.identity.models import User
from researchos.llm_config.models import LLMProviderConfig
from researchos.projects.service import ProjectService

from .models import ReleaseGenerationJob
from .schemas import CreateReleaseJobRequest, ReleaseIntegrationStatus

_QWEN_MODEL = "qwen-plus"
_ARTIFACT_TYPE = {"poster": "poster", "slides": "deck", "website": "landing"}
_ACTIVE_STATES = {"reserved", "uploading", "queued", "running", "completing", "cancelling"}
_SUCCESS_STATES = {"completed"}
_FAILURE_STATES = {"cancelled", "failed"}


def _now() -> datetime:
    return datetime.now(tz=UTC)


class ReleaseService:
    def __init__(self, db: AsyncSession, *, http_client: httpx.AsyncClient | None = None) -> None:
        self.db = db
        self.projects = ProjectService(db)
        self._http_client = http_client
        self.settings = get_settings()

    async def integration_status(
        self, actor: User, project_id: uuid.UUID
    ) -> ReleaseIntegrationStatus:
        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
        url = self.settings.autodesign_base_url.rstrip("/")
        try:
            async with self._client(timeout=2.5) as client:
                response = await client.get(f"{url}/api/health")
                response.raise_for_status()
        except (httpx.HTTPError, ValueError) as exc:
            return ReleaseIntegrationStatus(
                available=False,
                service_url=self.settings.autodesign_public_url.rstrip("/"),
                message=f"AutoDesign 未就绪：{type(exc).__name__}",
            )
        return ReleaseIntegrationStatus(
            available=True,
            service_url=self.settings.autodesign_public_url.rstrip("/"),
            message="AutoDesign DesignHarness 已连接",
        )

    async def create_job(
        self,
        actor: User,
        project_id: uuid.UUID,
        payload: CreateReleaseJobRequest,
    ) -> ReleaseGenerationJob:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        config = await self._qwen_config(project_id)
        job = ReleaseGenerationJob(
            project_id=project_id,
            created_by=actor.id,
            kind=payload.kind,
            engine="autodesign",
            model=_QWEN_MODEL,
            status="queued",
            story_pack=payload.story_pack,
            progress_json={"phase": "queued", "message": "已创建 AutoDesign 任务"},
        )
        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)

        try:
            await self._start_external(job, config, payload)
        except Exception as exc:  # noqa: BLE001 - preserve a durable, inspectable failure
            job.status = "failed"
            job.error_message = str(exc)[:4000]
            job.progress_json = {"phase": "failed", "message": "AutoDesign 启动失败"}
            job.finished_at = _now()
        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def list_jobs(
        self, actor: User, project_id: uuid.UUID, *, limit: int = 20
    ) -> list[ReleaseGenerationJob]:
        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
        return list(
            (
                await self.db.execute(
                    select(ReleaseGenerationJob)
                    .where(ReleaseGenerationJob.project_id == project_id)
                    .order_by(ReleaseGenerationJob.created_at.desc())
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )

    async def get_job(
        self,
        actor: User,
        project_id: uuid.UUID,
        job_id: uuid.UUID,
        *,
        refresh: bool = True,
    ) -> ReleaseGenerationJob:
        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
        job = await self.db.get(ReleaseGenerationJob, job_id)
        if job is None or job.project_id != project_id:
            raise NotFoundError("Release job not found.")
        if refresh and job.status in {"queued", "running"} and job.external_run_id:
            await self._refresh_external(job)
        return job

    async def cancel_job(
        self, actor: User, project_id: uuid.UUID, job_id: uuid.UUID
    ) -> ReleaseGenerationJob:
        job = await self.get_job(actor, project_id, job_id, refresh=False)
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        if job.status not in {"queued", "running"} or not job.external_run_id:
            return job
        base = self.settings.autodesign_base_url.rstrip("/")
        try:
            async with self._client(timeout=15.0) as client:
                response = await client.post(f"{base}/api/runs/{job.external_run_id}/cancel")
                response.raise_for_status()
        except httpx.HTTPError as exc:
            job.progress_json = {
                "phase": "cancelling",
                "message": f"取消请求待确认：{type(exc).__name__}",
            }
        else:
            job.status = "cancelled"
            job.finished_at = _now()
            job.progress_json = {"phase": "cancelled", "message": "任务已取消"}
        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def _qwen_config(self, project_id: uuid.UUID) -> LLMProviderConfig:
        config = await self.db.scalar(
            select(LLMProviderConfig)
            .where(
                LLMProviderConfig.project_id == project_id,
                LLMProviderConfig.is_active.is_(True),
                func.lower(LLMProviderConfig.model) == _QWEN_MODEL,
            )
            .order_by(LLMProviderConfig.updated_at.desc(), LLMProviderConfig.id)
            .limit(1)
        )
        if config is None:
            raise ValidationError(
                "成果发布需要一个已启用的 qwen-plus 模型配置。",
                code="qwen_plus_required",
            )
        if config.provider_type != "openai_compatible":
            raise ValidationError(
                "qwen-plus 必须使用 OpenAI-compatible 配置。",
                code="qwen_plus_provider_invalid",
            )
        if not decrypt_secret(config.api_key):
            raise ValidationError("qwen-plus 配置缺少 API key。", code="qwen_plus_key_required")
        return config

    async def _start_external(
        self,
        job: ReleaseGenerationJob,
        config: LLMProviderConfig,
        payload: CreateReleaseJobRequest,
    ) -> None:
        base = self.settings.autodesign_base_url.rstrip("/")
        model_headers = {
            "x-model-designer": _QWEN_MODEL,
            "x-model-enhancer": _QWEN_MODEL,
            "x-model-claim-graph": _QWEN_MODEL,
            "x-model-deck-outline": _QWEN_MODEL,
            "x-model-paper-memory": _QWEN_MODEL,
            "x-model-critic": _QWEN_MODEL,
            "x-model-composer": _QWEN_MODEL,
            "x-model-ingest": _QWEN_MODEL,
            "x-provider-designer": "openai_compat",
            "x-provider-enhancer": "openai_compat",
            "x-provider-claim-graph": "openai_compat",
            "x-provider-deck-outline": "openai_compat",
            "x-provider-paper-memory": "openai_compat",
            "x-provider-critic": "openai_compat",
            "x-provider-composer": "openai_compat",
            "x-openai-key": decrypt_secret(config.api_key),
            "x-custom-openai-base": config.base_url,
        }
        brief = self._brief(payload.kind)
        form = {
            "brief": brief,
            "artifact_type": _ARTIFACT_TYPE[payload.kind],
            "conversation_id": f"researchos-{job.id}",
            "authoring_max_attempts": "4",
        }
        if payload.template and payload.kind == "poster":
            form["template"] = payload.template
        files = {
            "files": (
                "research-story-pack.md",
                payload.story_pack.encode("utf-8"),
                "text/markdown",
            )
        }
        async with self._client(timeout=self.settings.autodesign_start_timeout_seconds) as client:
            response = await client.post(
                f"{base}/api/generate",
                data=form,
                files=files,
                headers=model_headers,
            )
            if response.status_code >= 400:
                raise ValidationError(
                    f"AutoDesign returned {response.status_code}: {response.text[:1000]}",
                    code="autodesign_start_failed",
                )
            data = response.json()
        external_run_id = str(data.get("run_id") or "").strip()
        if not external_run_id:
            raise ValidationError("AutoDesign did not return a run id.")
        job.external_run_id = external_run_id
        job.status = "running"
        job.started_at = _now()
        job.progress_json = {
            "phase": "running",
            "message": "AutoDesign 正在生成可编辑成果",
            "external_run_id": external_run_id,
            "output_directory": f"out/runs/{external_run_id}/final",
        }

    async def _refresh_external(self, job: ReleaseGenerationJob) -> None:
        base = self.settings.autodesign_base_url.rstrip("/")
        assert job.external_run_id is not None
        try:
            async with self._client(timeout=10.0) as client:
                response = await client.get(f"{base}/api/runs/{job.external_run_id}/status")
                response.raise_for_status()
                external = response.json()
                state = str(external.get("run_state") or "running").lower()
                job.progress_json = {
                    **job.progress_json,
                    "phase": state,
                    "external_state": state,
                    "revision": external.get("revision"),
                    "publishable": bool(external.get("publishable")),
                }
                if state in _ACTIVE_STATES:
                    job.status = "running"
                elif state in _SUCCESS_STATES | _FAILURE_STATES:
                    await self._load_artifact(client, job, state)
        except httpx.HTTPError as exc:
            job.progress_json = {
                **job.progress_json,
                "sync_warning": f"AutoDesign status 暂不可用：{type(exc).__name__}",
            }
        await self.db.commit()
        await self.db.refresh(job)

    async def _load_artifact(
        self, client: httpx.AsyncClient, job: ReleaseGenerationJob, external_state: str
    ) -> None:
        base = self.settings.autodesign_base_url.rstrip("/")
        assert job.external_run_id is not None
        response = await client.get(f"{base}/api/runs/{job.external_run_id}/artifact")
        if response.status_code == 200:
            rewritten = self._public_artifact_urls(response.json())
            payload = self._compact_artifact_payload(rewritten)
            artifact = payload.get("artifact")
            job.artifact_json = payload
            if artifact:
                job.status = "succeeded"
                job.error_message = None
                job.progress_json = {
                    **job.progress_json,
                    "phase": "succeeded",
                    "message": "成果已生成，可预览与下载",
                }
            else:
                job.status = "failed"
                message = payload.get("message") if isinstance(payload, dict) else None
                failure = message.get("failure") if isinstance(message, dict) else None
                job.error_message = str(
                    (failure or {}).get("error_message") or "AutoDesign 未生成有效成果。"
                )
        elif external_state in _FAILURE_STATES:
            job.status = "cancelled" if external_state == "cancelled" else "failed"
            job.error_message = f"AutoDesign run ended with state: {external_state}"
        else:
            retries = int(job.progress_json.get("artifact_wait_attempts") or 0) + 1
            job.progress_json = {
                **job.progress_json,
                "artifact_wait_attempts": retries,
                "message": "AutoDesign 已完成，正在等待成果索引",
            }
            if retries >= 5:
                job.status = "failed"
                job.error_message = (
                    f"AutoDesign completed but artifact lookup returned {response.status_code}."
                )
        if job.status in {"succeeded", "failed", "cancelled"}:
            job.finished_at = _now()

    @staticmethod
    def _compact_artifact_payload(value: object) -> dict:
        if not isinstance(value, dict):
            return {}
        message = value.get("message")
        artifact = value.get("artifact")
        compact_message: dict = {}
        if isinstance(message, dict):
            compact_message = {
                key: message.get(key)
                for key in ("id", "text", "status", "failure", "download_url")
                if message.get(key) is not None
            }
        compact_artifact: dict | None = None
        if isinstance(artifact, dict):
            fields = (
                "artifact_id",
                "name",
                "artifact_type",
                "canvas",
                "native_file_url",
                "native_format",
                "view_file_url",
                "view_format",
                "download_url",
                "pdf_url",
                "downloads",
                "preview_url",
                "card_preview_url",
                "quality_status",
                "quality_diagnostics",
            )
            compact_artifact = {
                key: artifact.get(key) for key in fields if artifact.get(key) is not None
            }
        return {"message": compact_message, "artifact": compact_artifact}

    def _public_artifact_urls(self, value: object) -> object:
        public_base = self.settings.autodesign_public_url.rstrip("/") + "/"
        if isinstance(value, dict):
            return {
                key: (
                    urljoin(public_base, item)
                    if key.endswith("_url") and isinstance(item, str) and item
                    else self._public_artifact_urls(item)
                )
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [self._public_artifact_urls(item) for item in value]
        return value

    def _client(self, *, timeout: float) -> httpx.AsyncClient:
        if self._http_client is not None:
            return _BorrowedClient(self._http_client)  # type: ignore[return-value]
        return httpx.AsyncClient(timeout=timeout)

    @staticmethod
    def _brief(kind: str) -> str:
        medium = {
            "poster": "a conference poster",
            "slides": "an academic conference slide deck",
            "website": "an editable academic project webpage",
        }[kind]
        return (
            f"Create {medium} from the attached Research Story Pack. "
            "Treat the source as authoritative, preserve uncertainty, do not invent metrics or "
            "citations, and keep all output editable. Use a restrained editorial research style "
            "with clear evidence provenance and accessible typography."
        )


class _BorrowedClient:
    """Async context wrapper that does not close an injected test/shared client."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def __aenter__(self) -> httpx.AsyncClient:
        return self.client

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None
