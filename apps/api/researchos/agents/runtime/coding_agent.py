"""Coding agent: proposes a reviewable patch. It never writes files.

The agent inspects the workspace (read-only tools: tree, ranged read, grep) and
finalizes by creating a *pending* patch proposal. Read-before-write is
enforced: modify/delete of a file the agent never read is rejected, and the
server overrides the agent's echoed ``base_sha`` with the sha the tool broker
actually served. Applying the patch is a separate, user-initiated action (see
researchos.patches).
"""

from __future__ import annotations

import json
import uuid

from sqlalchemy import or_, select

from researchos.agents.enums import AgentType
from researchos.agents.llm import LLMMessage
from researchos.common.errors import NotFoundError
from researchos.common.paths import WorkspaceAccessError, resolve_in_workspace
from researchos.patches.enums import PatchChangeType, PatchStatus
from researchos.patches.repository import PatchRepository
from researchos.patches.resolution import EditBlock, EditResolutionError, resolve_edits
from researchos.patches.schemas import PatchFileInput
from researchos.patches.service import PatchService
from researchos.workspace import fs

from .base import Agent, AgentContext

_HISTORY_MAX_MESSAGES = 20
_HISTORY_MAX_CHARS = 8_000
_BASE_CONTENT_SNIPPET_CHARS = 2_000

_SYSTEM = (
    "You are a coding assistant working inside a project workspace. Inspect before you "
    "propose: workspace.tree lists files, workspace.read reads a file (optionally a line "
    "range) and returns the file's sha, workspace.grep searches file contents.\n"
    "Rules:\n"
    "1. ALWAYS read a file with workspace.read before modifying or deleting it, and take "
    "base_sha VERBATIM from the workspace.read result.\n"
    '2. Respond with a single JSON object: {"summary": string, "files": [{"path", '
    "\"change_type\" ('create'|'modify'|'delete'), \"base_sha\", \"new_content\"?, "
    '"edits"?}]}.\n'
    '3. For \'modify\' prefer "edits": a list of {"search", "replace"} blocks where '
    '"search" is copied VERBATIM from the file, includes at least 3 lines of surrounding '
    'context, and is unique within the file. Use "new_content" only for a full rewrite.\n'
    "4. For 'create' provide \"new_content\" (no base_sha, no edits); for 'delete' provide "
    "neither.\n"
    "5. You never write files directly; your patch is reviewed by the user before it is "
    "applied."
)

_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "files": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "change_type": {"type": "string"},
                    "base_sha": {"type": ["string", "null"]},
                    "new_content": {"type": ["string", "null"]},
                    "edits": {
                        "type": ["array", "null"],
                        "items": {
                            "type": "object",
                            "properties": {
                                "search": {"type": "string"},
                                "replace": {"type": "string"},
                            },
                            "required": ["search", "replace"],
                        },
                    },
                },
                "required": ["path", "change_type"],
            },
        },
    },
    "required": ["summary", "files"],
}


def _parse_output(output_text: str) -> dict | None:
    """Lenient JSON extraction (providers wrap JSON in prose/fences)."""

    try:
        parsed = json.loads(output_text)
    except json.JSONDecodeError:
        start = output_text.find("{")
        end = output_text.rfind("}")
        if start == -1 or end <= start:
            return None
        try:
            parsed = json.loads(output_text[start : end + 1])
        except json.JSONDecodeError:
            return None
    return parsed if isinstance(parsed, dict) else None


def _violation(path: str, reason: str, detail: str | None = None) -> dict:
    out: dict = {"path": path, "reason": reason}
    if detail is not None:
        out["detail"] = detail
    return out


def _parse_uuid(value: object) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None


class CodingAgent(Agent):
    agent_type = AgentType.CODING
    allowed_tools = ["workspace.tree", "workspace.read", "workspace.grep"]
    response_schema = _SCHEMA
    # Multi-file work needs more than the global default tool budget (the
    # runtime honors this via Agent.max_tool_calls when available).
    max_tool_calls = 25

    async def build_messages(self, actx: AgentContext) -> list[LLMMessage]:
        messages = [LLMMessage(role="system", content=_SYSTEM)]
        appendix = await self._repropose_appendix(actx)
        if appendix:
            messages.append(LLMMessage(role="system", content=appendix))
        messages.extend(await self._load_history(actx))
        messages.append(LLMMessage(role="user", content=actx.message))
        return messages

    async def _load_history(self, actx: AgentContext) -> list[LLMMessage]:
        """Prior chat turns (oldest→newest), excluding this run's own message."""

        session_id = _parse_uuid(actx.context.get("chat_session_id"))
        if session_id is None:
            return []
        from researchos.coding_chat.models import ChatMessage, ChatSession

        result = await actx.db.execute(
            select(ChatMessage)
            .join(ChatSession, ChatMessage.session_id == ChatSession.id)
            .where(
                ChatMessage.session_id == session_id,
                ChatSession.project_id == actx.project_id,
                or_(
                    ChatMessage.agent_run_id.is_(None),
                    ChatMessage.agent_run_id != actx.run.id,
                ),
            )
            .order_by(ChatMessage.seq.desc())
            .limit(_HISTORY_MAX_MESSAGES)
        )
        newest_first = list(result.scalars().all())
        kept: list = []
        used = 0
        for row in newest_first:  # drop oldest first when over the char budget
            if kept and used + len(row.content) > _HISTORY_MAX_CHARS:
                break
            kept.append(row)
            used += len(row.content)
        kept.reverse()
        return [
            LLMMessage(role="user" if r.role == "user" else "assistant", content=r.content)
            for r in kept
        ]

    async def _repropose_appendix(self, actx: AgentContext) -> str | None:
        old_id = _parse_uuid(actx.context.get("repropose_of"))
        if old_id is None:
            return None
        old = await PatchRepository(actx.db).get(actx.project_id, old_id)
        if old is None:
            return None
        conflicted = {c.get("path"): c for c in (old.conflict_json or []) if c.get("path")}
        lines = [
            f"A previous proposal ('{old.summary}') failed to apply because the workspace "
            "changed. Conflicts:"
        ]
        for path, c in conflicted.items():
            lines.append(
                f"- {path}: {c.get('reason')} "
                f"(expected sha {c.get('expected_sha')}, actual {c.get('actual_sha')})"
            )
        for f in old.files:
            if f.path in conflicted and f.base_content is not None:
                snippet = f.base_content[:_BASE_CONTENT_SNIPPET_CHARS]
                lines.append(
                    f"The proposal was anchored to this now-outdated content of {f.path} "
                    f"(the live file has changed):\n---\n{snippet}\n---"
                )
        lines.append(
            "Re-read every conflicted file with workspace.read and re-anchor your edits to "
            "the current content."
        )
        return "\n".join(lines)

    # --- output validation ----------------------------------------------------
    def _collect_files(
        self, actx: AgentContext, parsed: dict
    ) -> tuple[list[PatchFileInput], list[dict]]:
        """Validate file entries into inputs + visible violations (no drops)."""

        inputs: list[PatchFileInput] = []
        violations: list[dict] = []
        raw_files = parsed.get("files", [])
        if not isinstance(raw_files, list):
            return [], [_violation("", "invalid_change", "files must be a list")]
        for raw in raw_files:
            if not isinstance(raw, dict):
                violations.append(_violation("", "invalid_change", "file entry must be an object"))
                continue
            path = str(raw.get("path", ""))
            try:
                resolve_in_workspace(actx.project_id, path)
            except WorkspaceAccessError as exc:
                violations.append(_violation(path, "workspace_denied", str(exc)))
                continue
            try:
                change = PatchChangeType(str(raw.get("change_type", "")))
            except ValueError:
                violations.append(
                    _violation(
                        path, "invalid_change", f"unknown change_type {raw.get('change_type')!r}"
                    )
                )
                continue

            if change in (PatchChangeType.MODIFY, PatchChangeType.DELETE):
                recorded_sha = actx.tool_ctx.read_paths.get(path)
                if recorded_sha is None:
                    violations.append(
                        _violation(
                            path,
                            "unread_file",
                            "read the file with workspace.read before modifying it",
                        )
                    )
                    continue
                # The sha the broker served is authoritative; the agent's echo
                # is advisory (kills copy-error conflicts).
                base_sha: str | None = recorded_sha
            else:
                base_sha = None  # forced for create

            try:
                candidate = PatchFileInput(
                    path=path,
                    change_type=change,
                    base_sha=base_sha,
                    new_content=raw.get("new_content"),
                    edits=raw.get("edits") or None,
                )
            except ValueError as exc:
                violations.append(_violation(path, "invalid_change", str(exc)[:200]))
                continue
            inputs.append(candidate)
        return inputs, violations

    def _dry_run_failures(self, actx: AgentContext, inputs: list[PatchFileInput]) -> list[dict]:
        """Predict proposal-time per-file failures without persisting anything."""

        failures: list[dict] = []
        for f in inputs:
            if f.change_type == PatchChangeType.CREATE:
                if fs.current_sha(actx.project_id, f.path) is not None:
                    failures.append(_violation(f.path, "already_exists"))
                continue
            try:
                data = fs.read_file(actx.project_id, f.path)
            except NotFoundError:
                failures.append(_violation(f.path, "base_missing"))
                continue
            if f.change_type != PatchChangeType.MODIFY or not f.edits:
                continue
            if data["binary"] or data["too_large"]:
                failures.append(_violation(f.path, "unpatchable_binary"))
                continue
            if data["sha"] != f.base_sha:
                failures.append(_violation(f.path, "base_changed"))
                continue
            try:
                resolve_edits(
                    data["content"] or "",
                    [EditBlock(search=e.search, replace=e.replace) for e in f.edits],
                )
            except EditResolutionError as exc:
                failures.extend(
                    _violation(f.path, fl.reason, f"edit block {fl.index}") for fl in exc.failures
                )
        return failures

    async def prevalidate(self, actx: AgentContext, output_text: str) -> str | None:
        """Self-repair feedback: violations the agent can fix in one more turn."""

        parsed = _parse_output(output_text)
        if parsed is None:
            return (
                "Your reply could not be parsed as JSON. Respond with ONLY the JSON object "
                "matching {summary, files:[...]} — no prose, no code fences."
            )
        inputs, violations = self._collect_files(actx, parsed)
        violations.extend(self._dry_run_failures(actx, inputs))
        if not violations:
            return None
        lines = [
            "Some proposed files are invalid and would be rejected. Fix them and resend the "
            "FULL corrected JSON object:"
        ]
        for v in violations:
            detail = f" — {v['detail']}" if v.get("detail") else ""
            lines.append(f"- {v.get('path') or '(no path)'}: {v['reason']}{detail}")
        lines.append(
            "Remember: read files with workspace.read before modifying them, take base_sha "
            "from the read result, and make every 'search' block unique in its file."
        )
        return "\n".join(lines)

    # --- finalize -------------------------------------------------------------
    async def finalize(
        self,
        actx: AgentContext,
        *,
        output_text: str,
        whitelist: set[str],
        citation_sources: dict[str, dict],
        usage: dict,
    ) -> tuple[dict, list[dict]]:
        parsed = _parse_output(output_text)
        if parsed is None:
            await self._persist_chat_reply(
                actx,
                "The coding agent's reply could not be parsed; no patch was created.",
                None,
            )
            return (
                {"message": "", "patch_id": None, "file_count": 0, "error": "parse_failure"},
                [],
            )

        inputs, violations = self._collect_files(actx, parsed)
        summary = str(parsed.get("summary", ""))

        proposal = None
        if inputs:
            proposal, failures = await PatchService(actx.db).create_proposal(
                project_id=actx.project_id,
                created_by=actx.actor.id,
                summary=summary or "Proposed changes",
                files=inputs,
                agent_run_id=actx.run.id,
            )
            violations.extend(failures)

        if proposal is not None:
            await self._supersede_on_repropose(actx, proposal.id)

        patch_id = str(proposal.id) if proposal is not None else None
        file_count = len(proposal.files) if proposal is not None else 0
        auto_apply_requested = bool(actx.context.get("auto_apply_patch"))
        isolated_confirmed = bool(actx.context.get("isolated_workspace_confirmed"))
        apply_result = None
        if proposal is not None and not violations and auto_apply_requested:
            if not isolated_confirmed:
                violations.append(
                    _violation(
                        "",
                        "autonomy_policy_denied",
                        "auto-apply requires isolated_workspace_confirmed=true",
                    )
                )
            else:
                apply_result = await PatchService(actx.db).apply_patch(
                    actx.actor,
                    actx.project_id,
                    proposal.id,
                    require_git_commit=True,
                )
        output_json = {
            "message": summary,
            "patch_id": patch_id,
            "file_count": file_count,
            "rejected_files": violations,
            "auto_apply_requested": auto_apply_requested,
            "auto_applied": bool(apply_result and apply_result.status == PatchStatus.APPLIED),
            "patch_status": apply_result.status.value
            if apply_result
            else (proposal.status.value if proposal is not None else None),
            "applied_commit_sha": apply_result.applied_commit_sha if apply_result else None,
        }

        chat_content = summary
        if not chat_content:
            reasons = ", ".join(sorted({v["reason"] for v in violations})) or "empty response"
            chat_content = f"The coding agent produced no valid patch ({reasons})."
        await self._persist_chat_reply(
            actx, chat_content, proposal.id if proposal is not None else None
        )
        return output_json, []

    async def _supersede_on_repropose(self, actx: AgentContext, new_patch_id: uuid.UUID) -> None:
        old_id = _parse_uuid(actx.context.get("repropose_of"))
        if old_id is None:
            return
        repo = PatchRepository(actx.db)
        old = await repo.get(actx.project_id, old_id)
        if old is not None and old.status == PatchStatus.CONFLICT:
            await repo.mark_superseded(old, by=new_patch_id)

    async def _persist_chat_reply(
        self, actx: AgentContext, content: str, patch_id: uuid.UUID | None
    ) -> None:
        """Persist the assistant turn via CodingChatService so seq allocation and
        collision retry are handled centrally (the runtime commits after finalize)."""

        session_id = _parse_uuid(actx.context.get("chat_session_id"))
        if session_id is None:
            return
        from researchos.coding_chat.models import ChatSession
        from researchos.coding_chat.service import CodingChatService

        session = await actx.db.get(ChatSession, session_id)
        if session is None:
            return
        svc = CodingChatService(actx.db)
        msg = await svc._insert_message(session, role="assistant", content=content)
        # Write the links the chat pane expects onto the row.
        msg.agent_run_id = actx.run.id
        msg.patch_id = patch_id
        await actx.db.flush()
