"""LaTeX document business logic, authorization, and a safe mock compiler.

The compiler is a pure-Python text transform. There is NO shell, NO subprocess,
and NO shell-escape (PHASE3/5 security): real isolated LaTeX compilation is a
later phase.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from researchos.common.errors import NotFoundError
from researchos.common.roles import ProjectRole
from researchos.identity.models import User
from researchos.projects.service import ProjectService

from .enums import CompileStatus
from .models import DocumentFile, LatexCompileJob, LatexProject
from .repository import CompileJobRepository, DocumentFileRepository, LatexProjectRepository

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

_CMD_RE = re.compile(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?(\{([^{}]*)\})?")
_COMMENT_RE = re.compile(r"(?<!\\)%.*")


def _mock_preview(latex: str) -> str:
    """Render a readable plain-text preview from LaTeX (no compilation)."""

    out: list[str] = []
    for line in latex.splitlines():
        line = _COMMENT_RE.sub("", line)
        if line.strip().startswith(("\\documentclass", "\\usepackage", "\\begin", "\\end")):
            continue
        line = re.sub(r"\\section\*?\{([^}]*)\}", r"\n# \1", line)
        line = re.sub(r"\\subsection\*?\{([^}]*)\}", r"\n## \1", line)
        line = re.sub(r"\\title\{([^}]*)\}", r"# \1", line)
        line = re.sub(r"\\textbf\{([^}]*)\}", r"\1", line)
        line = re.sub(r"\\emph\{([^}]*)\}", r"\1", line)
        line = _CMD_RE.sub(lambda m: m.group(3) or "", line)
        out.append(line)
    return "\n".join(out).strip() or "(empty document)"


class DocumentService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.projects = ProjectService(db)
        self.latex_projects = LatexProjectRepository(db)
        self.files = DocumentFileRepository(db)
        self.jobs = CompileJobRepository(db)

    async def create_latex_project(
        self, actor: User, project_id: uuid.UUID, *, name: str
    ) -> LatexProject:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        lp = await self.latex_projects.add(
            LatexProject(project_id=project_id, name=name, created_by=actor.id)
        )
        await self.files.add(
            DocumentFile(
                latex_project_id=lp.id, path="main.tex", content=_DEFAULT_MAIN, updated_by=actor.id
            )
        )
        await self.db.commit()
        await self.db.refresh(lp)
        return lp

    async def list_latex_projects(self, actor: User, project_id: uuid.UUID) -> list[LatexProject]:
        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
        return await self.latex_projects.list(project_id)

    async def _require_latex_project(
        self, actor: User, project_id: uuid.UUID, latex_project_id: uuid.UUID, role: ProjectRole
    ) -> LatexProject:
        await self.projects.ensure_access(actor, project_id, role)
        lp = await self.latex_projects.get(project_id, latex_project_id)
        if lp is None:
            raise NotFoundError("LaTeX project not found.")
        return lp

    async def get_latex_project(
        self, actor: User, project_id: uuid.UUID, latex_project_id: uuid.UUID
    ) -> LatexProject:
        return await self._require_latex_project(
            actor, project_id, latex_project_id, ProjectRole.VIEWER
        )

    async def list_files(
        self, actor: User, project_id: uuid.UUID, latex_project_id: uuid.UUID
    ) -> list[DocumentFile]:
        await self._require_latex_project(actor, project_id, latex_project_id, ProjectRole.VIEWER)
        return await self.files.list(latex_project_id)

    async def get_file(
        self, actor: User, project_id: uuid.UUID, latex_project_id: uuid.UUID, path: str
    ) -> DocumentFile:
        await self._require_latex_project(actor, project_id, latex_project_id, ProjectRole.VIEWER)
        file = await self.files.get_by_path(latex_project_id, path)
        if file is None:
            raise NotFoundError("Document file not found.")
        return file

    async def save_file(
        self,
        actor: User,
        project_id: uuid.UUID,
        latex_project_id: uuid.UUID,
        *,
        path: str,
        content: str,
    ) -> DocumentFile:
        await self._require_latex_project(
            actor, project_id, latex_project_id, ProjectRole.RESEARCHER
        )
        file = await self.files.get_by_path(latex_project_id, path)
        if file is None:
            file = await self.files.add(
                DocumentFile(
                    latex_project_id=latex_project_id,
                    path=path,
                    content=content,
                    updated_by=actor.id,
                )
            )
        else:
            file.content = content
            file.version += 1
            file.updated_by = actor.id
        await self.db.commit()
        await self.db.refresh(file)
        return file

    async def compile(
        self, actor: User, project_id: uuid.UUID, latex_project_id: uuid.UUID
    ) -> LatexCompileJob:
        lp = await self._require_latex_project(
            actor, project_id, latex_project_id, ProjectRole.RESEARCHER
        )
        main = await self.files.get_by_path(latex_project_id, lp.main_file_path)
        content = main.content if main else ""
        job = await self.jobs.add(
            LatexCompileJob(
                latex_project_id=latex_project_id,
                project_id=project_id,
                status=CompileStatus.SUCCEEDED,
                engine="mock",
                log="Mock compile succeeded (no shell, no shell-escape).",
                preview=_mock_preview(content),
                created_by=actor.id,
                finished_at=datetime.now(tz=UTC),
            )
        )
        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def get_compile_job(
        self, actor: User, project_id: uuid.UUID, latex_project_id: uuid.UUID, job_id: uuid.UUID
    ) -> LatexCompileJob:
        await self._require_latex_project(actor, project_id, latex_project_id, ProjectRole.VIEWER)
        job = await self.jobs.get(latex_project_id, job_id)
        if job is None:
            raise NotFoundError("Compile job not found.")
        return job
