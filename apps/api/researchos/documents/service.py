"""LaTeX document business logic, authorization, and a safe mock compiler.

The compiler is a pure-Python structural pass (see ``latex_parse``). There is
NO shell, NO subprocess, and NO shell-escape (PHASE3/5 security): real isolated
LaTeX compilation is a later phase.

Every content mutation (saves, suggestion accepts, anchor includes, citation
inserts) goes through ``write_file_versioned`` so each write is compare-and-
swapped on the per-file version counter and snapshotted into
``document_file_revisions``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from researchos.common.errors import ConflictError, NotFoundError
from researchos.common.pubsub import publish_event
from researchos.common.roles import ProjectRole
from researchos.identity.models import User
from researchos.projects.service import ProjectService
from researchos.websocket.envelopes import EventEnvelope

from .enums import CompileStatus
from .latex_parse import parse_document, render_plain_preview
from .merge import three_way_merge
from .models import DocumentFile, DocumentFileRevision, LatexCompileJob, LatexProject
from .repository import (
    CompileJobRepository,
    DocumentFileRepository,
    DocumentRevisionRepository,
    LatexProjectRepository,
)

logger = structlog.get_logger(__name__)

_DEFAULT_MAIN = r"""\documentclass{article}
\title{Untitled Paper}
\author{ResearchOS}
\begin{document}
\maketitle

\section{Introduction}
Write your introduction here.

\section{Method}
Describe your method.

\section{Results}
Present your results.

\end{document}
"""

_PAPER_TEMPLATES: dict[str, str] = {
    "article": _DEFAULT_MAIN,
    "ieee": r"""\documentclass[conference]{IEEEtran}
\title{Paper Title}
\author{\IEEEauthorblockN{Author Name}
\IEEEauthorblockA{Affiliation\\email@example.com}}
\begin{document}
\maketitle
\begin{abstract}
Summarize the problem, method, results, and significance.
\end{abstract}
\section{Introduction}
\section{Related Work}
\section{Method}
\section{Experiments}
\section{Conclusion}
\bibliographystyle{IEEEtran}
\bibliography{references}
\end{document}
""",
    "acm": r"""\documentclass[sigconf]{acmart}
\title{Paper Title}
\author{Author Name}
\affiliation{\institution{Institution}\country{Country}}
\email{email@example.com}
\begin{document}
\begin{abstract}
Summarize the problem, method, results, and significance.
\end{abstract}
\maketitle
\section{Introduction}
\section{Related Work}
\section{Method}
\section{Evaluation}
\section{Conclusion}
\bibliographystyle{ACM-Reference-Format}
\bibliography{references}
\end{document}
""",
    "elsevier": r"""\documentclass[preprint,12pt]{elsarticle}
\journal{Journal Name}
\begin{document}
\begin{frontmatter}
\title{Paper Title}
\author{Author Name}
\begin{abstract}
Summarize the problem, method, results, and significance.
\end{abstract}
\begin{keyword}
keyword one \sep keyword two
\end{keyword}
\end{frontmatter}
\section{Introduction}
\section{Related Work}
\section{Method}
\section{Experiments}
\section{Conclusion}
\bibliographystyle{elsarticle-num}
\bibliography{references}
\end{document}
""",
}

# Keep at most this many revisions per file (newest retained).
_REVISION_KEEP = 50
# Omit server_content from 409 payloads beyond this size.
_SERVER_CONTENT_MAX_BYTES = 512 * 1024


class DocumentService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.projects = ProjectService(db)
        self.latex_projects = LatexProjectRepository(db)
        self.files = DocumentFileRepository(db)
        self.revisions = DocumentRevisionRepository(db)
        self.jobs = CompileJobRepository(db)

    async def create_latex_project(
        self,
        actor: User,
        project_id: uuid.UUID,
        *,
        name: str,
        template_id: str = "article",
    ) -> LatexProject:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        lp = await self.latex_projects.add(
            LatexProject(project_id=project_id, name=name, created_by=actor.id)
        )
        await self.write_file_versioned(
            actor,
            lp.id,
            path="main.tex",
            content=_PAPER_TEMPLATES.get(template_id, _DEFAULT_MAIN),
        )
        await self.write_file_versioned(
            actor,
            lp.id,
            path="references.bib",
            content="% Export project references here.\n",
        )
        await self.db.commit()
        await self.db.refresh(lp)
        return lp

    async def list_latex_projects(self, actor: User, project_id: uuid.UUID) -> list[LatexProject]:
        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
        return await self.latex_projects.list(project_id)

    async def require_latex_project(
        self, actor: User, project_id: uuid.UUID, latex_project_id: uuid.UUID, role: ProjectRole
    ) -> LatexProject:
        """Access guard shared with the suggestion/citation/anchor services."""

        await self.projects.ensure_access(actor, project_id, role)
        lp = await self.latex_projects.get(project_id, latex_project_id)
        if lp is None:
            raise NotFoundError("LaTeX project not found.")
        return lp

    async def get_latex_project(
        self, actor: User, project_id: uuid.UUID, latex_project_id: uuid.UUID
    ) -> LatexProject:
        return await self.require_latex_project(
            actor, project_id, latex_project_id, ProjectRole.VIEWER
        )

    async def list_files(
        self, actor: User, project_id: uuid.UUID, latex_project_id: uuid.UUID
    ) -> list[DocumentFile]:
        await self.require_latex_project(actor, project_id, latex_project_id, ProjectRole.VIEWER)
        return await self.files.list(latex_project_id)

    async def get_file(
        self, actor: User, project_id: uuid.UUID, latex_project_id: uuid.UUID, path: str
    ) -> DocumentFile:
        await self.require_latex_project(actor, project_id, latex_project_id, ProjectRole.VIEWER)
        file = await self.files.get_by_path(latex_project_id, path)
        if file is None:
            raise NotFoundError("Document file not found.")
        return file

    # --- versioned write core -------------------------------------------------

    async def build_version_conflict(
        self, file: DocumentFile, *, expected_version: int, client_content: str
    ) -> ConflictError:
        """409 payload with the server content and a three-way merge hint."""

        server_content = file.content
        omitted = len(server_content.encode("utf-8")) > _SERVER_CONTENT_MAX_BYTES
        details: dict = {
            "path": file.path,
            "expected_version": expected_version,
            "current_version": file.version,
            "server_content_omitted": omitted,
            "base_available": False,
            "merge": None,
        }
        if not omitted:
            details["server_content"] = server_content
        base = await self.revisions.get_by_version(file.id, expected_version)
        if base is not None:
            details["base_available"] = True
            details["merge"] = three_way_merge(
                base.content, server_content, client_content
            ).to_payload()
        return ConflictError(
            f"Document changed since version {expected_version}.",
            code="document_version_conflict",
            details=details,
        )

    async def write_file_versioned(
        self,
        actor: User,
        latex_project_id: uuid.UUID,
        *,
        path: str,
        content: str,
        expected_version: int | None = None,
    ) -> DocumentFile:
        """Create-or-update a file with CAS + a revision snapshot. No commit.

        All internal writers (suggestion accept, anchor include, citation
        insert) share this core so every mutation is versioned and revisioned.
        """

        file = await self.files.get_by_path(latex_project_id, path)
        if file is None:
            candidate = DocumentFile(
                latex_project_id=latex_project_id,
                path=path,
                content=content,
                updated_by=actor.id,
            )
            try:
                async with self.db.begin_nested():
                    self.db.add(candidate)
                    await self.db.flush()
            except IntegrityError:
                # Concurrent create of the same path: re-select and fall
                # through to the update path instead of a 500.
                file = await self.files.get_by_path(latex_project_id, path)
                if file is None:  # pragma: no cover - unexpected integrity source
                    raise
            else:
                await self.revisions.add(
                    DocumentFileRevision(
                        document_file_id=candidate.id,
                        version=candidate.version,
                        content=content,
                        updated_by=actor.id,
                    )
                )
                return candidate

        if expected_version is not None and expected_version != file.version:
            raise await self.build_version_conflict(
                file, expected_version=expected_version, client_content=content
            )

        # The Python-side version check is advisory; the revision table's
        # UNIQUE(document_file_id, version) is the real CAS. Stage the content
        # bump AND the revision insert in one savepoint so a concurrent writer
        # that already claimed this version rolls the whole thing back and gets
        # a 409 merge hint instead of an opaque 500.
        new_version = file.version + 1
        file.content = content
        file.version = new_version
        file.updated_by = actor.id
        try:
            async with self.db.begin_nested():
                await self.db.flush()
                await self.revisions.add(
                    DocumentFileRevision(
                        document_file_id=file.id,
                        version=new_version,
                        content=content,
                        updated_by=actor.id,
                    )
                )
        except IntegrityError:
            fresh = await self.files.get_by_path(latex_project_id, path)
            target = fresh if fresh is not None else file
            raise await self.build_version_conflict(
                target,
                expected_version=expected_version
                if expected_version is not None
                else target.version,
                client_content=content,
            ) from None
        await self.revisions.prune(file.id, keep=_REVISION_KEEP)
        return file

    async def save_file(
        self,
        actor: User,
        project_id: uuid.UUID,
        latex_project_id: uuid.UUID,
        *,
        path: str,
        content: str,
        expected_version: int | None = None,
    ) -> DocumentFile:
        await self.require_latex_project(
            actor, project_id, latex_project_id, ProjectRole.RESEARCHER
        )
        file = await self.write_file_versioned(
            actor, latex_project_id, path=path, content=content, expected_version=expected_version
        )
        await self.db.commit()
        await self.db.refresh(file)
        return file

    # --- history --------------------------------------------------------------

    async def list_file_history(
        self,
        actor: User,
        project_id: uuid.UUID,
        latex_project_id: uuid.UUID,
        *,
        path: str,
        limit: int,
    ) -> list[DocumentFileRevision]:
        await self.require_latex_project(actor, project_id, latex_project_id, ProjectRole.VIEWER)
        file = await self.files.get_by_path(latex_project_id, path)
        if file is None:
            raise NotFoundError("Document file not found.")
        return await self.revisions.list_versions(file.id, limit=limit)

    async def get_file_revision(
        self,
        actor: User,
        project_id: uuid.UUID,
        latex_project_id: uuid.UUID,
        *,
        path: str,
        version: int,
    ) -> tuple[DocumentFile, DocumentFileRevision]:
        await self.require_latex_project(actor, project_id, latex_project_id, ProjectRole.VIEWER)
        file = await self.files.get_by_path(latex_project_id, path)
        if file is None:
            raise NotFoundError("Document file not found.")
        revision = await self.revisions.get_by_version(file.id, version)
        if revision is None:
            raise NotFoundError("Revision not found (it may have been pruned).")
        return file, revision

    # --- compile --------------------------------------------------------------

    async def compile(
        self, actor: User, project_id: uuid.UUID, latex_project_id: uuid.UUID
    ) -> LatexCompileJob:
        lp = await self.require_latex_project(
            actor, project_id, latex_project_id, ProjectRole.RESEARCHER
        )
        files = await self.files.list(latex_project_id)
        file_map = {f.path: f.content for f in files}
        preview_model, diagnostics = parse_document(file_map, lp.main_file_path)
        errors = [d for d in diagnostics if d["severity"] == "error"]
        status = CompileStatus.FAILED if errors else CompileStatus.SUCCEEDED
        job = await self.jobs.add(
            LatexCompileJob(
                latex_project_id=latex_project_id,
                project_id=project_id,
                status=status,
                engine="mock",
                log=(
                    "Mock compile (no shell, no shell-escape): "
                    f"{len(diagnostics)} diagnostic(s)."
                ),
                preview=render_plain_preview(preview_model),
                preview_model_json=preview_model,
                diagnostics_json=diagnostics,
                error_summary=errors[0]["message"] if errors else None,
                created_by=actor.id,
                finished_at=datetime.now(tz=UTC),
            )
        )
        await self.db.commit()
        await self.db.refresh(job)
        await self._publish_compile_event(job)
        return job

    async def _publish_compile_event(self, job: LatexCompileJob) -> None:
        event_type = (
            "latex.compile.failed"
            if job.status == CompileStatus.FAILED
            else "latex.compile.completed"
        )
        envelope = EventEnvelope(
            event_type=event_type,
            project_id=str(job.project_id),
            resource_type="latex_compile",
            resource_id=str(job.id),
            timestamp=datetime.now(tz=UTC).isoformat(),
            payload={
                "job_id": str(job.id),
                "status": job.status.value,
                "engine": job.engine,
                "diagnostics_count": len(job.diagnostics_json or []),
                "error_summary": job.error_summary,
            },
        ).model_dump()
        try:
            await publish_event(str(job.project_id), envelope)
        except Exception:  # noqa: BLE001 - live events must not fail the compile
            logger.warning("latex_compile_event_publish_failed", job_id=str(job.id))

    async def get_compile_job(
        self, actor: User, project_id: uuid.UUID, latex_project_id: uuid.UUID, job_id: uuid.UUID
    ) -> LatexCompileJob:
        await self.require_latex_project(actor, project_id, latex_project_id, ProjectRole.VIEWER)
        job = await self.jobs.get(latex_project_id, job_id)
        if job is None:
            raise NotFoundError("Compile job not found.")
        return job
