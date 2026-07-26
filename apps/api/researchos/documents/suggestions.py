"""Tracked-change suggestions: spans, selection-op capture, and lifecycle.

Selection ops ride the existing AgentRun/Celery/WS pipeline (streaming, rate
limits and cancellation for free). The LatexAgent finalizes into a
``document_suggestions`` row via ``SuggestionService.create_from_run``; nothing
is ever applied without an explicit user accept.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from difflib import SequenceMatcher

from sqlalchemy.ext.asyncio import AsyncSession

from researchos.agents.enums import AgentType
from researchos.agents.models import AgentRun
from researchos.agents.service import AgentRunService
from researchos.common.errors import ConflictError, NotFoundError, ValidationError
from researchos.common.roles import ProjectRole
from researchos.identity.models import User

from .enums import SuggestionOp, SuggestionStatus
from .models import DocumentFile, DocumentSuggestion
from .repository import SuggestionRepository
from .schemas import SelectionOpRequest, TextRange
from .service import DocumentService

_TOKEN_SPLIT_RE = re.compile(r"(\s+)")

# Characters of surrounding text captured for later re-anchoring.
_ANCHOR_CHARS = 64
_CONTEXT_BEFORE_LINES = 40
_CONTEXT_AFTER_LINES = 20

_OP_LABELS: dict[SuggestionOp, str] = {
    SuggestionOp.REWRITE: "Rewrite selection",
    SuggestionOp.EXPAND: "Expand selection",
    SuggestionOp.CONDENSE: "Condense selection",
    SuggestionOp.FIX_GRAMMAR: "Fix grammar in selection",
    SuggestionOp.CONTINUE_WRITING: "Continue writing",
    SuggestionOp.CUSTOM: "Apply custom edit to selection",
}


def compute_spans(old: str, new: str) -> list[dict]:
    """Deterministic word-level old->new spans (round-trip lossless).

    ``''.join(span.old) == old`` and ``''.join(span.new) == new``; adjacent
    spans of the same kind are merged.
    """

    old_tokens = _TOKEN_SPLIT_RE.split(old)
    new_tokens = _TOKEN_SPLIT_RE.split(new)
    matcher = SequenceMatcher(a=old_tokens, b=new_tokens, autojunk=False)
    spans: list[dict] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        old_part = "".join(old_tokens[i1:i2])
        new_part = "".join(new_tokens[j1:j2])
        if not old_part and not new_part:
            continue
        if tag == "equal":
            kind = "equal"
        elif not old_part:
            kind = "insert"
        elif not new_part:
            kind = "delete"
        else:
            kind = "replace"
        if spans and spans[-1]["kind"] == kind:
            spans[-1]["old"] += old_part
            spans[-1]["new"] += new_part
        else:
            spans.append({"kind": kind, "old": old_part, "new": new_part})
    return spans


def _offset_of(lines: list[str], line: int, col: int) -> int:
    """Char offset for a 1-based Monaco position, clamped into the document."""

    line_idx = max(0, min(line - 1, len(lines) - 1))
    offset = sum(len(lines[i]) + 1 for i in range(line_idx))
    offset += max(0, min(col - 1, len(lines[line_idx])))
    total = sum(len(text) + 1 for text in lines) - 1 if lines else 0
    return max(0, min(offset, total))


def prepare_op_context(
    *,
    file: DocumentFile,
    latex_project_id: uuid.UUID,
    payload: SelectionOpRequest,
) -> dict:
    """Server-side capture of everything the agent and the accept need."""

    content = file.content
    lines = content.split("\n")
    offset_start = _offset_of(lines, payload.range.start.line, payload.range.start.col)
    offset_end = _offset_of(lines, payload.range.end.line, payload.range.end.col)
    if offset_end < offset_start:
        offset_start, offset_end = offset_end, offset_start

    extracted = content[offset_start:offset_end]
    # If the client buffer is ahead of the store, its selection_text stays
    # authoritative and accept re-anchors by text search only.
    anchor_mode = "range" if extracted == payload.selection_text else "text"

    start_line_idx = max(0, min(payload.range.start.line - 1, len(lines)))
    end_line_idx = max(0, min(payload.range.end.line, len(lines)))
    return {
        "op": payload.op.value,
        "path": file.path,
        "latex_project_id": str(latex_project_id),
        "document_file_id": str(file.id),
        "base_version": file.version,
        "anchor_mode": anchor_mode,
        "selection_text": payload.selection_text,
        "instruction": payload.instruction,
        "range": {
            "start": {"line": payload.range.start.line, "col": payload.range.start.col},
            "end": {"line": payload.range.end.line, "col": payload.range.end.col},
        },
        "offset_start": offset_start,
        "offset_end": offset_end,
        "anchor_prefix": content[max(0, offset_start - _ANCHOR_CHARS) : offset_start],
        "anchor_suffix": content[offset_end : offset_end + _ANCHOR_CHARS],
        "context_before": "\n".join(
            lines[max(0, start_line_idx - _CONTEXT_BEFORE_LINES) : start_line_idx]
        ),
        "context_after": "\n".join(lines[end_line_idx : end_line_idx + _CONTEXT_AFTER_LINES]),
    }


class SuggestionService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.documents = DocumentService(db)
        self.suggestions = SuggestionRepository(db)

    # --- selection op creation (router side) ---------------------------------

    async def create_selection_op(
        self,
        actor: User,
        project_id: uuid.UUID,
        latex_project_id: uuid.UUID,
        payload: SelectionOpRequest,
    ) -> AgentRun:
        """Validate, capture context, and enqueue the run. Never blocks on LLM."""

        await self.documents.require_latex_project(
            actor, project_id, latex_project_id, ProjectRole.RESEARCHER
        )
        file = await self.documents.files.get_by_path(latex_project_id, payload.path)
        if file is None:
            raise NotFoundError("Document file not found.")
        context = prepare_op_context(
            file=file, latex_project_id=latex_project_id, payload=payload
        )
        return await AgentRunService(self.db).create_run(
            actor,
            project_id,
            agent_type=AgentType.LATEX,
            message=payload.instruction or _OP_LABELS[payload.op],
            context=context,
        )

    # --- worker side (called from LatexAgent.finalize) -----------------------

    async def create_from_run(
        self,
        *,
        run: AgentRun,
        context: dict,
        replacement: str,
        rationale: str,
    ) -> DocumentSuggestion:
        """Persist the proposed suggestion (flush only; the runtime commits)."""

        op = SuggestionOp(str(context["op"]))
        old_text = (
            "" if op == SuggestionOp.CONTINUE_WRITING else str(context.get("selection_text", ""))
        )
        suggestion = DocumentSuggestion(
            latex_project_id=uuid.UUID(str(context["latex_project_id"])),
            document_file_id=uuid.UUID(str(context["document_file_id"])),
            agent_run_id=run.id,
            op=op,
            status=SuggestionStatus.PROPOSED,
            base_version=int(context.get("base_version", 1)),
            anchor_mode=str(context.get("anchor_mode", "range")),
            range_json={
                "start": context.get("range", {}).get("start", {"line": 1, "col": 1}),
                "end": context.get("range", {}).get("end", {"line": 1, "col": 1}),
                "anchor_prefix": str(context.get("anchor_prefix", "")),
                "anchor_suffix": str(context.get("anchor_suffix", "")),
                "offset_start": int(context.get("offset_start", 0)),
                "offset_end": int(context.get("offset_end", 0)),
            },
            old_text=old_text,
            new_text=replacement,
            rationale=rationale,
            spans_json=compute_spans(old_text, replacement),
            created_by=run.user_id,
        )
        return await self.suggestions.add(suggestion)

    # --- reads ---------------------------------------------------------------

    async def _require_suggestion(
        self,
        actor: User,
        project_id: uuid.UUID,
        latex_project_id: uuid.UUID,
        suggestion_id: uuid.UUID,
        role: ProjectRole,
    ) -> DocumentSuggestion:
        await self.documents.require_latex_project(actor, project_id, latex_project_id, role)
        suggestion = await self.suggestions.get(latex_project_id, suggestion_id)
        if suggestion is None:
            raise NotFoundError("Suggestion not found.")
        return suggestion

    async def _file_for(self, suggestion: DocumentSuggestion) -> DocumentFile:
        file = await self.documents.files.get_by_id(
            suggestion.latex_project_id, suggestion.document_file_id
        )
        if file is None:
            raise NotFoundError("Document file not found.")
        return file

    async def list_suggestions(
        self,
        actor: User,
        project_id: uuid.UUID,
        latex_project_id: uuid.UUID,
        *,
        status: SuggestionStatus | None,
        path: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[tuple[DocumentSuggestion, str]], int]:
        await self.documents.require_latex_project(
            actor, project_id, latex_project_id, ProjectRole.VIEWER
        )
        return await self.suggestions.list_by_project(
            latex_project_id, status=status, path=path, limit=limit, offset=offset
        )

    async def get_suggestion(
        self,
        actor: User,
        project_id: uuid.UUID,
        latex_project_id: uuid.UUID,
        suggestion_id: uuid.UUID,
    ) -> tuple[DocumentSuggestion, str]:
        suggestion = await self._require_suggestion(
            actor, project_id, latex_project_id, suggestion_id, ProjectRole.VIEWER
        )
        file = await self._file_for(suggestion)
        return suggestion, file.path

    # --- accept / reject ------------------------------------------------------

    async def _conflict(self, suggestion: DocumentSuggestion, reason: str) -> ConflictError:
        # Record why the accept failed but KEEP the suggestion proposed so the
        # user can retry after editing (no dead-end state).
        suggestion.last_error = reason
        await self.db.commit()
        return ConflictError(
            "Suggestion could not be applied to the current document.",
            code="suggestion_conflict",
            details={"reason": reason},
        )

    def _anchor(self, suggestion: DocumentSuggestion, content: str) -> tuple[int, int] | str:
        """Locate the target region. Returns ``(start, end)`` or an error reason."""

        range_json = suggestion.range_json or {}
        old_text = suggestion.old_text
        prefix = str(range_json.get("anchor_prefix", ""))
        suffix = str(range_json.get("anchor_suffix", ""))

        if old_text == "":
            # Insertion (continue_writing): insert right after the prefix.
            if prefix == "":
                return (0, 0)
            count = content.count(prefix)
            if count == 1:
                pos = content.index(prefix) + len(prefix)
                return (pos, pos)
            if count == 0:
                return "anchor_not_found"
            probe = prefix + suffix
            if content.count(probe) == 1:
                pos = content.index(probe) + len(prefix)
                return (pos, pos)
            return "ambiguous_anchor"

        count = content.count(old_text)
        if count == 1:
            start = content.index(old_text)
            return (start, start + len(old_text))
        if count == 0:
            return "anchor_not_found"
        probe = prefix + old_text + suffix
        if content.count(probe) == 1:
            start = content.index(probe) + len(prefix)
            return (start, start + len(old_text))
        return "ambiguous_anchor"

    async def accept(
        self,
        actor: User,
        project_id: uuid.UUID,
        latex_project_id: uuid.UUID,
        suggestion_id: uuid.UUID,
        *,
        expected_version: int | None = None,
    ) -> tuple[DocumentSuggestion, DocumentFile]:
        suggestion = await self._require_suggestion(
            actor, project_id, latex_project_id, suggestion_id, ProjectRole.RESEARCHER
        )
        if suggestion.status != SuggestionStatus.PROPOSED:
            raise ValidationError("Suggestion is not pending.", code="suggestion_not_pending")
        file = await self._file_for(suggestion)
        if expected_version is not None and expected_version != file.version:
            raise await self.documents.build_version_conflict(
                file, expected_version=expected_version, client_content=file.content
            )

        content = file.content
        range_json = suggestion.range_json or {}
        region: tuple[int, int] | None = None

        # Fast path: unchanged file + trusted range — verify before applying.
        if file.version == suggestion.base_version and suggestion.anchor_mode == "range":
            start = int(range_json.get("offset_start", 0))
            end = int(range_json.get("offset_end", 0))
            if 0 <= start <= end <= len(content) and content[start:end] == suggestion.old_text:
                region = (start, end)

        if region is None:
            anchored = self._anchor(suggestion, content)
            if isinstance(anchored, str):
                raise await self._conflict(suggestion, anchored)
            region = anchored

        start, end = region
        new_content = content[:start] + suggestion.new_text + content[end:]
        file = await self.documents.write_file_versioned(
            actor, latex_project_id, path=file.path, content=new_content
        )
        suggestion.status = SuggestionStatus.ACCEPTED
        suggestion.last_error = None
        suggestion.applied_version = file.version
        suggestion.resolved_by = actor.id
        suggestion.resolved_at = datetime.now(tz=UTC)
        await self.db.commit()
        await self.db.refresh(suggestion)
        await self.db.refresh(file)
        return suggestion, file

    async def reject(
        self,
        actor: User,
        project_id: uuid.UUID,
        latex_project_id: uuid.UUID,
        suggestion_id: uuid.UUID,
    ) -> tuple[DocumentSuggestion, str]:
        suggestion = await self._require_suggestion(
            actor, project_id, latex_project_id, suggestion_id, ProjectRole.RESEARCHER
        )
        if suggestion.status != SuggestionStatus.PROPOSED:
            raise ValidationError("Suggestion is not pending.", code="suggestion_not_pending")
        file = await self._file_for(suggestion)
        suggestion.status = SuggestionStatus.REJECTED
        suggestion.resolved_by = actor.id
        suggestion.resolved_at = datetime.now(tz=UTC)
        await self.db.commit()
        await self.db.refresh(suggestion)
        return suggestion, file.path


def suggestion_range(suggestion: DocumentSuggestion) -> TextRange:
    range_json = suggestion.range_json or {}
    return TextRange.model_validate(
        {
            "start": range_json.get("start", {"line": 1, "col": 1}),
            "end": range_json.get("end", {"line": 1, "col": 1}),
        }
    )
