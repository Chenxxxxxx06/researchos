"""Coding chat: session CRUD, tenancy, busy gating, history injection, seq retry."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from researchos.agents.enums import AgentRunStatus, AgentType
from researchos.agents.models import AgentRun
from researchos.agents.repository import AgentRunRepository
from researchos.agents.runtime import AgentRuntime
from researchos.agents.runtime.base import AgentContext
from researchos.agents.runtime.coding_agent import CodingAgent
from researchos.agents.runtime.events import EventEmitter
from researchos.agents.runtime.tools import ToolContext
from researchos.coding_chat.models import ChatMessage, ChatSession
from researchos.coding_chat.service import CodingChatService
from researchos.identity.service import AuthService
from researchos.projects.service import ProjectService

from .helpers import csrf_headers, register


async def _make_project(client, email: str) -> str:
    await register(client, email=email)
    org_id = (await client.get("/organizations")).json()[0]["id"]
    resp = await client.post(
        "/projects", json={"organization_id": org_id, "name": "P"}, headers=csrf_headers(client)
    )
    return resp.json()["id"]


async def test_session_crud_and_pagination(client) -> None:
    project_id = await _make_project(client, "chat1@example.com")

    created = await client.post(
        f"/projects/{project_id}/coding-chat/sessions",
        json={"title": "First"},
        headers=csrf_headers(client),
    )
    assert created.status_code == 201
    body = created.json()
    assert body["title"] == "First"
    assert body["agent_type"] == "coding"
    assert body["project_id"] == project_id

    await client.post(
        f"/projects/{project_id}/coding-chat/sessions",
        json={"title": "Second"},
        headers=csrf_headers(client),
    )
    page = (
        await client.get(f"/projects/{project_id}/coding-chat/sessions", params={"limit": 1})
    ).json()
    assert page["total"] == 2
    assert len(page["items"]) == 1
    assert page["items"][0]["title"] == "Second"  # newest first

    detail = await client.get(f"/projects/{project_id}/coding-chat/sessions/{body['id']}")
    assert detail.status_code == 200
    assert detail.json()["messages"] == []


async def test_session_isolated_from_non_members(make_client) -> None:
    owner = make_client()
    project_id = await _make_project(owner, "chat-owner@example.com")
    session = (
        await owner.post(
            f"/projects/{project_id}/coding-chat/sessions",
            json={"title": "secret"},
            headers=csrf_headers(owner),
        )
    ).json()

    outsider = make_client()
    await register(outsider, email="chat-outsider@example.com")
    resp = await outsider.get(f"/projects/{project_id}/coding-chat/sessions/{session['id']}")
    assert resp.status_code == 404  # membership hidden, not 403


async def test_post_message_creates_linked_run_and_busy_409(client) -> None:
    project_id = await _make_project(client, "chat2@example.com")
    session = (
        await client.post(
            f"/projects/{project_id}/coding-chat/sessions",
            json={},
            headers=csrf_headers(client),
        )
    ).json()

    posted = await client.post(
        f"/projects/{project_id}/coding-chat/sessions/{session['id']}/messages",
        json={"message": "rename foo to bar in utils"},
        headers=csrf_headers(client),
    )
    assert posted.status_code == 201
    body = posted.json()
    assert body["status"] == "queued"
    assert body["stream"] == f"/ws?project_id={project_id}"

    detail = (
        await client.get(f"/projects/{project_id}/coding-chat/sessions/{session['id']}")
    ).json()
    assert detail["title"] == "rename foo to bar in utils"  # first message titles the session
    assert len(detail["messages"]) == 1
    msg = detail["messages"][0]
    assert msg["role"] == "user"
    assert msg["seq"] == 0
    assert msg["agent_run_id"] == body["agent_run_id"]

    # The run is still queued (no worker in tests) -> the session is busy.
    busy = await client.post(
        f"/projects/{project_id}/coding-chat/sessions/{session['id']}/messages",
        json={"message": "and also this"},
        headers=csrf_headers(client),
    )
    assert busy.status_code == 409
    assert busy.json()["error"]["code"] == "session_busy"


async def test_full_turn_persists_assistant_message_with_patch(
    db_session: AsyncSession,
) -> None:
    user, org = await AuthService(db_session).register(
        email="chat-turn@example.com", password="password123", display_name="Chatter"
    )
    project = await ProjectService(db_session).create_project(
        user, organization_id=org.id, name="P", description=None, field=None
    )
    svc = CodingChatService(db_session)
    session = await svc.create_session(user, project.id)
    _msg, run = await svc.post_message(user, project.id, session.id, message="add notes")

    # Execute the queued run in-process (mock provider: tree -> create patch).
    await AgentRuntime(db_session).run(run.id)
    await db_session.refresh(run)
    assert run.status == AgentRunStatus.COMPLETED
    assert run.output_json["patch_id"] is not None

    detail = await svc.get_session(user, project.id, session.id)
    roles = [(m.seq, m.role) for m in detail.messages]
    assert roles == [(0, "user"), (1, "assistant")]
    assistant = detail.messages[1]
    assert assistant.agent_run_id == run.id
    assert str(assistant.patch_id) == run.output_json["patch_id"]
    assert assistant.content  # the summary text

    # A completed run frees the session again.
    assert await svc._latest_run_busy(session.id) is False


async def test_build_messages_injects_history_in_order_and_caps(
    db_session: AsyncSession,
) -> None:
    user, org = await AuthService(db_session).register(
        email="chat-hist@example.com", password="password123", display_name="H"
    )
    project = await ProjectService(db_session).create_project(
        user, organization_id=org.id, name="P", description=None, field=None
    )
    session = ChatSession(project_id=project.id, created_by=user.id, agent_type=AgentType.CODING)
    db_session.add(session)
    await db_session.flush()
    for seq, (role, content) in enumerate(
        [("user", "first ask"), ("assistant", "first answer"), ("user", "x" * 9000)]
    ):
        db_session.add(
            ChatMessage(session_id=session.id, seq=seq, role=role, content=content)
        )
    run = await AgentRunRepository(db_session).create(
        AgentRun(
            project_id=project.id,
            user_id=user.id,
            agent_type=AgentType.CODING,
            status=AgentRunStatus.RUNNING,
            input_json={
                "message": "current",
                "context": {"chat_session_id": str(session.id)},
            },
        )
    )
    await db_session.commit()

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
        message="current",
        context={"chat_session_id": str(session.id)},
        tool_ctx=tool_ctx,
    )
    messages = await CodingAgent().build_messages(actx)
    assert messages[0].role == "system"
    assert messages[-1].role == "user" and messages[-1].content == "current"
    # The 9000-char message alone blows the 8k budget: older turns are dropped.
    history = messages[1:-1]
    assert [m.content for m in history] == ["x" * 9000]

    # A foreign project's session id injects nothing (tenancy in the query).
    actx.context = {"chat_session_id": str(uuid.uuid4())}
    messages = await CodingAgent().build_messages(actx)
    assert len(messages) == 2


async def test_seq_collision_retries_once(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    user, org = await AuthService(db_session).register(
        email="chat-seq@example.com", password="password123", display_name="S"
    )
    project = await ProjectService(db_session).create_project(
        user, organization_id=org.id, name="P", description=None, field=None
    )
    svc = CodingChatService(db_session)
    session = await svc.create_session(user, project.id)
    db_session.add(
        ChatMessage(session_id=session.id, seq=0, role="user", content="existing")
    )
    await db_session.commit()

    real_next_seq = CodingChatService._next_seq
    calls = {"n": 0}

    async def stale_next_seq(self, session_id):
        calls["n"] += 1
        if calls["n"] == 1:
            return 0  # stale value colliding with the existing row
        return await real_next_seq(self, session_id)

    monkeypatch.setattr(CodingChatService, "_next_seq", stale_next_seq)
    session = await svc.get_session(user, project.id, session.id)
    message = await svc._insert_message(session, role="user", content="retry me")
    await db_session.commit()
    assert message.seq == 1
    assert calls["n"] == 2
