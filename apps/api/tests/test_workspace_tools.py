"""Agent workspace tools (read/grep) through the ToolBroker, plus REST grep."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from researchos.agents.enums import AgentRunStatus, AgentType, ToolCallStatus
from researchos.agents.models import AgentRun
from researchos.agents.repository import AgentRunRepository, ToolCallRepository
from researchos.agents.runtime.events import EventEmitter
from researchos.agents.runtime.tools import ToolBroker, ToolContext, ToolDenied
from researchos.common.config import get_settings
from researchos.identity.service import AuthService
from researchos.projects.service import ProjectService
from researchos.workspace import fs

from .helpers import csrf_headers, register


async def _make_broker(db: AsyncSession, email: str, allowed: set[str]):
    user, org = await AuthService(db).register(
        email=email, password="password123", display_name="Tooler"
    )
    project = await ProjectService(db).create_project(
        user, organization_id=org.id, name="P", description=None, field=None
    )
    run = await AgentRunRepository(db).create(
        AgentRun(
            project_id=project.id,
            user_id=user.id,
            agent_type=AgentType.CODING,
            status=AgentRunStatus.RUNNING,
            input_json={"message": "m", "context": {}},
        )
    )
    await db.commit()
    ctx = ToolContext(
        db=db,
        actor=user,
        project_id=project.id,
        run_id=run.id,
        emitter=EventEmitter(db, project_id=project.id, run_id=run.id),
        allowed_tools=allowed,
    )
    return ctx, ToolBroker(ctx), project, run


async def test_ranged_read_clamps_and_records_whole_file_sha(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx, broker, project, _run = await _make_broker(
        db_session, "tool-read@example.com", {"workspace.read"}
    )
    content = "".join(f"line {i}\n" for i in range(1, 101))
    full_sha = fs.write_file(project.id, "big.txt", content)
    monkeypatch.setattr(get_settings(), "workspace_read_max_lines", 10)

    result = await broker.execute(
        "workspace.read", {"path": "big.txt", "start_line": 1, "end_line": 50}
    )
    assert result["truncated"] is True
    assert result["start_line"] == 1 and result["end_line"] == 10
    assert result["total_lines"] == 100
    assert result["sha"] == full_sha  # whole-file sha despite the ranged read
    assert ctx.read_paths["big.txt"] == full_sha


async def test_read_budget_exhaustion_is_inband_error(db_session: AsyncSession) -> None:
    ctx, broker, project, run = await _make_broker(
        db_session, "tool-budget@example.com", {"workspace.read"}
    )
    fs.write_file(project.id, "f.txt", "content\n")
    ctx.read_bytes_used = get_settings().workspace_read_budget_bytes

    result = await broker.execute("workspace.read", {"path": "f.txt"})
    assert result["error"]["code"] == "read_budget_exhausted"
    calls = await ToolCallRepository(db_session).list_by_run(run.id)
    assert calls[-1].status == ToolCallStatus.FAILED
    # The run itself is untouched — the error is an in-band tool result.
    assert "f.txt" not in ctx.read_paths


async def test_read_missing_and_binary_files_are_inband_errors(
    db_session: AsyncSession,
) -> None:
    _ctx, broker, project, _run = await _make_broker(
        db_session, "tool-miss@example.com", {"workspace.read"}
    )
    result = await broker.execute("workspace.read", {"path": "nope.txt"})
    assert result["error"]["code"] == "not_found"

    ws = Path(get_settings().workspace_root) / str(project.id)
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "blob.bin").write_bytes(b"\x00\x01\x02rest")
    result = await broker.execute("workspace.read", {"path": "blob.bin"})
    assert result["error"]["code"] == "unreadable_file"


async def test_grep_bounds_and_errors(db_session: AsyncSession) -> None:
    _ctx, broker, project, _run = await _make_broker(
        db_session, "tool-grep@example.com", {"workspace.grep"}
    )
    fs.write_file(project.id, "a.py", "needle one\nnothing\nneedle two\n")
    fs.write_file(project.id, "b.py", "needle three\n")
    fs.write_file(project.id, "c.txt", "no match here\n")
    ws = Path(get_settings().workspace_root) / str(project.id)
    (ws / ".env").write_text("needle secret\n", encoding="utf-8")
    (ws / "bin.dat").write_bytes(b"\x00needle\x00")

    result = await broker.execute("workspace.grep", {"pattern": "needle", "max_results": 2})
    assert len(result["matches"]) == 2
    assert result["truncated"] is True

    result = await broker.execute("workspace.grep", {"pattern": "needle"})
    paths = {m["path"] for m in result["matches"]}
    assert paths == {"a.py", "b.py"}  # deny-listed and binary files excluded
    assert all("needle" in m["line"] for m in result["matches"])

    result = await broker.execute("workspace.grep", {"pattern": "need", "glob": "*.py"})
    assert {m["path"] for m in result["matches"]} == {"a.py", "b.py"}

    result = await broker.execute("workspace.grep", {"pattern": "[invalid"})
    assert result["error"]["code"] == "invalid_pattern"


async def test_unknown_and_denied_tools_raise_tool_denied(db_session: AsyncSession) -> None:
    _ctx, broker, _project, run = await _make_broker(
        db_session, "tool-deny@example.com", {"workspace.read"}
    )
    with pytest.raises(ToolDenied):
        await broker.execute("no.such.tool", {})
    with pytest.raises(ToolDenied):
        await broker.execute("paper.search", {"query": "q"})  # registered but not allowed

    calls = await ToolCallRepository(db_session).list_by_run(run.id)
    assert [c.status for c in calls] == [ToolCallStatus.FAILED, ToolCallStatus.FAILED]


async def test_tool_impl_exception_becomes_inband_error(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ctx, broker, _project, run = await _make_broker(
        db_session, "tool-boom@example.com", {"workspace.tree"}
    )

    async def boom(ctx, args):
        raise RuntimeError("kaput")

    from researchos.agents.runtime import tools as tools_mod

    spec = tools_mod.TOOL_REGISTRY["workspace.tree"]
    monkeypatch.setitem(
        tools_mod.TOOL_REGISTRY,
        "workspace.tree",
        tools_mod.ToolSpec(
            name=spec.name, description=spec.description, parameters=spec.parameters, impl=boom
        ),
    )
    result = await broker.execute("workspace.tree", {})
    assert result["error"] == {"code": "tool_failed", "message": "kaput"}
    calls = await ToolCallRepository(db_session).list_by_run(run.id)
    assert calls[-1].status == ToolCallStatus.FAILED


# --- REST grep ----------------------------------------------------------------
async def _make_project(client, email: str) -> str:
    await register(client, email=email)
    org_id = (await client.get("/organizations")).json()[0]["id"]
    resp = await client.post(
        "/projects", json={"organization_id": org_id, "name": "P"}, headers=csrf_headers(client)
    )
    return resp.json()["id"]


async def test_rest_grep_literal_and_shape(client) -> None:
    project_id = await _make_project(client, "grep-rest@example.com")
    fs.write_file(uuid.UUID(project_id), "src/x.py", "value = a + b  # sum\n")

    resp = await client.get(
        f"/projects/{project_id}/workspace/grep", params={"query": "a + b"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["truncated"] is False
    assert body["matches"] == [
        {"path": "src/x.py", "line": 1, "preview": "value = a + b  # sum"}
    ]


async def test_rest_grep_invalid_regex_400(client) -> None:
    project_id = await _make_project(client, "grep-bad@example.com")
    resp = await client.get(
        f"/projects/{project_id}/workspace/grep",
        params={"query": "[unclosed", "regex": "true"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "validation_error"
