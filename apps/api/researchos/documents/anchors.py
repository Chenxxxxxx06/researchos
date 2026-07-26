"""Result-anchor macro insertion into LaTeX documents.

Validates the macro against the experiments/figures partition's facade when it
is importable; otherwise degrades gracefully (``validated: false``) and still
returns a usable snippet while maintaining the ``\\input{results/anchors}``
include. On validated inserts the current macros content (rendered by the
figures facade) is materialized into ``results/anchors.tex`` through the
versioned write path — the writing partition owns that write (CONSOLIDATION
§5); the figures partition only renders the text.
"""

from __future__ import annotations

import re
import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from researchos.common.errors import NotFoundError
from researchos.common.roles import ProjectRole
from researchos.identity.models import User

from .models import DocumentFile
from .schemas import FileVersionRef, InsertAnchorRequest, InsertAnchorResponse
from .service import DocumentService

logger = structlog.get_logger(__name__)

# Convention shared with the figures partition (CONSOLIDATION §5).
_ANCHORS_FILE_PATH = "results/anchors.tex"
_BEGIN_DOCUMENT_RE = re.compile(r"^.*\\begin\{document\}.*$", re.MULTILINE)


def _load_anchor_service() -> type:
    """Deferred import: the figures partition is built in parallel."""

    from researchos.figures.anchor_service import ResultAnchorService

    return ResultAnchorService


def _include_line(anchors_path: str) -> str:
    name = anchors_path[:-4] if anchors_path.endswith(".tex") else anchors_path
    return f"\\input{{{name}}}"


def _include_re(anchors_path: str) -> re.Pattern[str]:
    name = anchors_path[:-4] if anchors_path.endswith(".tex") else anchors_path
    return re.compile(r"\\input\{" + re.escape(name) + r"(?:\.tex)?\}")


def _splice_at(content: str, line: int, col: int, snippet: str) -> str:
    lines = content.split("\n")
    line_idx = max(0, min(line - 1, len(lines) - 1)) if lines else 0
    if not lines:
        return snippet
    col_idx = max(0, min(col - 1, len(lines[line_idx])))
    lines[line_idx] = lines[line_idx][:col_idx] + snippet + lines[line_idx][col_idx:]
    return "\n".join(lines)


class AnchorInsertService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.documents = DocumentService(db)

    async def insert(
        self,
        actor: User,
        project_id: uuid.UUID,
        latex_project_id: uuid.UUID,
        payload: InsertAnchorRequest,
    ) -> InsertAnchorResponse:
        await self.documents.require_latex_project(
            actor, project_id, latex_project_id, ProjectRole.RESEARCHER
        )
        target = await self.documents.files.get_by_path(latex_project_id, payload.target_path)
        if target is None:
            raise NotFoundError("Document file not found.")

        validated = False
        anchors_path = _ANCHORS_FILE_PATH
        anchor_service = None
        try:
            service_cls = _load_anchor_service()
        except ImportError:
            service_cls = None
        if service_cls is not None:
            anchor_service = service_cls(self.db)
            try:
                info = await anchor_service.get_anchor(
                    project_id, latex_project_id, payload.macro_name
                )
            except Exception:  # noqa: BLE001 - degrade to unvalidated insert
                anchor_service = None
                logger.warning(
                    "anchor_lookup_failed",
                    latex_project_id=str(latex_project_id),
                    macro_name=payload.macro_name,
                )
            else:
                if info is None:
                    raise NotFoundError("Result anchor not found.", code="anchor_not_found")
                validated = True
                anchors_path = getattr(info, "anchors_file_path", None) or _ANCHORS_FILE_PATH

        macros_file = None
        if validated and anchor_service is not None:
            macros_file = await self._materialize_macros(
                actor, project_id, latex_project_id, anchor_service, anchors_path
            )

        snippet = f"\\{payload.macro_name}{{}}"
        content = target.content
        new_content = content

        # SHOULD: server-side splice of the usage snippet at the caret. Done
        # before the include insertion so the caller's coordinates stay valid.
        if payload.insert_at is not None:
            new_content = _splice_at(
                new_content, payload.insert_at.line, payload.insert_at.col, snippet
            )

        include_added = False
        if not _include_re(anchors_path).search(new_content):
            match = _BEGIN_DOCUMENT_RE.search(new_content)
            include = _include_line(anchors_path)
            if match is not None:
                insert_pos = match.end()
                new_content = new_content[:insert_pos] + "\n" + include + new_content[insert_pos:]
            else:
                new_content = include + ("\n" + new_content if new_content else "\n")
            include_added = True

        if new_content != content:
            file = await self.documents.write_file_versioned(
                actor,
                latex_project_id,
                path=payload.target_path,
                content=new_content,
                expected_version=payload.expected_version,
            )
            await self.db.commit()
            await self.db.refresh(file)
        else:
            file = target
            if macros_file is not None:
                await self.db.commit()

        files = [FileVersionRef(path=payload.target_path, version=file.version)]
        if macros_file is not None:
            await self.db.refresh(macros_file)
            files.append(FileVersionRef(path=anchors_path, version=macros_file.version))
        return InsertAnchorResponse(
            snippet=snippet,
            include_added=include_added,
            validated=validated,
            files=files,
        )

    async def _materialize_macros(
        self,
        actor: User,
        project_id: uuid.UUID,
        latex_project_id: uuid.UUID,
        anchor_service: object,
        anchors_path: str,
    ) -> DocumentFile | None:
        """Write the rendered macros into the project (best-effort, versioned).

        The macros text comes from the figures facade; writing it through
        ``write_file_versioned`` keeps ``results/anchors.tex`` versioned like
        every other document mutation. Failures degrade (the snippet is still
        usable) rather than failing the insert.
        """

        render = getattr(anchor_service, "render_macros", None)
        if render is None:
            return None
        try:
            macros_tex = await render(project_id)
        except Exception:  # noqa: BLE001 - macros write is best-effort
            logger.warning(
                "anchor_macros_render_failed", latex_project_id=str(latex_project_id)
            )
            return None
        existing = await self.documents.files.get_by_path(latex_project_id, anchors_path)
        if existing is not None and existing.content == macros_tex:
            return existing
        return await self.documents.write_file_versioned(
            actor, latex_project_id, path=anchors_path, content=macros_tex
        )
