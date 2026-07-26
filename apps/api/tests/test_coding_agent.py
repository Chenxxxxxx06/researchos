"""Coding agent runtime tests: mock flow, scripted read+edit flow, violations.

The scripted provider drives exact tool/answer sequences through the real
runtime so the read-before-write enforcement and the server-side sha override
are exercised end to end.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from researchos.agents.enums import AgentRunStatus, AgentType
from researchos.agents.llm.base import (
    LLMMessage,
    LLMTool,
    StreamDone,
    StreamEvent,
    TextDelta,
    ToolCall,
    Usage,
)
from researchos.agents.models import AgentRun
from researchos.agents.repository import AgentRunRepository
from researchos.agents.runtime import AgentRuntime
from researchos.agents.runtime.base import AgentContext
from researchos.agents.runtime.coding_agent import CodingAgent
from researchos.agents.runtime.events import EventEmitter
from researchos.agents.runtime.tools import ToolContext
from researchos.identity.service import AuthService
from researchos.patches.enums import PatchStatus
from researchos.patches.repository import PatchRepository
from researchos.projects.service import ProjectService
from researchos.workspace import fs


class _ScriptedLLM:
    """Deterministic provider: emit the scripted tool calls, then the final text.

    Repeated final-turn calls (e.g. the prevalidate corrective re-stream) keep
    returning the same final text.
    """

    name = "scripted"

    def __init__(self, tool_calls: list[ToolCall], final_text: str) -> None:
        self._tool_calls = tool_calls
        self._final_text = final_text

    async def stream(
        self,
        *,
        messages: list[LLMMessage],
        tools: list[LLMTool] | None = None,
        response_schema: dict | None = None,
        force_structured: bool = False,
    ) -> AsyncIterator[StreamEvent]:
        turns = sum(1 for m in messages if m.role == "assistant" and m.tool_calls)
        if tools and not force_structured and turns < len(self._tool_calls):
            yield self._tool_calls[turns]
            yield StreamDone(stop_reason="tool_use")
            return
        yield TextDelta(self._final_text)
        yield Usage(input_tokens=10, output_tokens=10)
        yield StreamDone(stop_reason="stop")


async def _setup(db: AsyncSession, email: str):
    user, org = await AuthService(db).register(
        email=email, password="password123", display_name="Coder"
    )
    project = await ProjectService(db).create_project(
        user, organization_id=org.id, name="P", description=None, field=None
    )
    return user, project


async def _make_run(db: AsyncSession, user, project) -> AgentRun:
    run = await AgentRunRepository(db).create(
        AgentRun(
            project_id=project.id,
            user_id=user.id,
            agent_type=AgentType.CODING,
            status=AgentRunStatus.QUEUED,
            input_json={"message": "add notes", "context": {}},
        )
    )
    await db.commit()
    return run


async def test_coding_agent_creates_pending_patch(db_session: AsyncSession) -> None:
    """Mock-provider default flow (empty workspace) proposes the notes create."""

    user, project = await _setup(db_session, "coder@example.com")
    run = await _make_run(db_session, user, project)

    await AgentRuntime(db_session).run(run.id)
    await db_session.refresh(run)
    assert run.status == AgentRunStatus.COMPLETED

    # A pending patch was proposed, referencing this run.
    patches, total = await PatchRepository(db_session).list_by_project(
        project.id, limit=10, offset=0
    )
    assert total == 1
    patch = patches[0]
    assert patch.status == PatchStatus.PENDING
    assert patch.agent_run_id == run.id
    assert patch.files[0].path == "AGENT_NOTES.md"
    assert patch.files[0].change_type.value == "create"

    # The agent did NOT write the file — it only proposed it.
    assert fs.current_sha(project.id, "AGENT_NOTES.md") is None


async def test_scripted_read_then_edits_uses_server_recorded_sha(
    db_session: AsyncSession,
) -> None:
    user, project = await _setup(db_session, "coder-edit@example.com")
    base = "alpha\nbeta\ngamma\n"
    real_sha = fs.write_file(project.id, "src/util.py", base)
    run = await _make_run(db_session, user, project)

    final = json.dumps(
        {
            "summary": "Uppercase beta",
            "files": [
                {
                    "path": "src/util.py",
                    "change_type": "modify",
                    # Deliberately wrong echo: the broker-recorded read sha wins.
                    "base_sha": "f" * 64,
                    "edits": [{"search": "beta\n", "replace": "BETA\n"}],
                }
            ],
        }
    )
    llm = _ScriptedLLM(
        [ToolCall(id="c1", name="workspace.read", arguments={"path": "src/util.py"})],
        final,
    )
    await AgentRuntime(db_session, llm=llm).run(run.id)
    await db_session.refresh(run)
    assert run.status == AgentRunStatus.COMPLETED
    assert run.output_json["rejected_files"] == []
    assert run.output_json["file_count"] == 1

    patch = await PatchRepository(db_session).get(
        project.id, uuid.UUID(run.output_json["patch_id"])
    )
    assert patch is not None
    f = patch.files[0]
    assert f.base_sha == real_sha  # server override, not the agent's echo
    assert f.new_content == "alpha\nBETA\ngamma\n"  # materialized from edits
    assert f.base_content == base
    assert f.edits_json == [{"search": "beta\n", "replace": "BETA\n"}]
    assert f.hunks, "hunks are server-derived"
    # Proposal only: the workspace is untouched.
    assert fs.current_sha(project.id, "src/util.py") == real_sha


async def test_scripted_modify_of_unread_path_is_rejected(
    db_session: AsyncSession,
) -> None:
    user, project = await _setup(db_session, "coder-unread@example.com")
    fs.write_file(project.id, "a.txt", "content\n")
    run = await _make_run(db_session, user, project)

    final = json.dumps(
        {
            "summary": "Sneaky edit",
            "files": [
                {
                    "path": "a.txt",
                    "change_type": "modify",
                    "base_sha": "0" * 64,
                    "edits": [{"search": "content\n", "replace": "changed\n"}],
                }
            ],
        }
    )
    await AgentRuntime(db_session, llm=_ScriptedLLM([], final)).run(run.id)
    await db_session.refresh(run)
    assert run.status == AgentRunStatus.COMPLETED

    assert run.output_json["patch_id"] is None
    rejected = run.output_json["rejected_files"]
    assert rejected and rejected[0]["path"] == "a.txt"
    assert rejected[0]["reason"] == "unread_file"
    _patches, total = await PatchRepository(db_session).list_by_project(
        project.id, limit=10, offset=0
    )
    assert total == 0


async def test_finalize_parse_failure_is_visible(db_session: AsyncSession) -> None:
    """Garbage output yields a COMPLETED-but-flagged result, never a silent drop."""

    user, project = await _setup(db_session, "coder-parse@example.com")
    run = await _make_run(db_session, user, project)
    tool_ctx = ToolContext(
        db=db_session,
        actor=user,
        project_id=project.id,
        run_id=run.id,
        emitter=EventEmitter(db_session, project_id=project.id, run_id=run.id),
        allowed_tools=set(),
    )
    actx = AgentContext(
        db=db_session,
        actor=user,
        project_id=project.id,
        run=run,
        message="add notes",
        context={},
        tool_ctx=tool_ctx,
    )

    output_json, citations = await CodingAgent().finalize(
        actx,
        output_text="I could not produce JSON, sorry!",
        whitelist=set(),
        citation_sources={},
        usage={},
    )
    assert citations == []
    assert output_json == {
        "message": "",
        "patch_id": None,
        "file_count": 0,
        "error": "parse_failure",
    }
