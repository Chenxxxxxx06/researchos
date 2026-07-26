"""Selection-op suggestions: spans, full mock pipeline, accept/reject (DB, CI)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from researchos.agents.enums import AgentRunStatus, AgentType
from researchos.agents.llm.base import StreamDone, TextDelta, Usage
from researchos.agents.models import AgentRun
from researchos.agents.repository import AgentRunRepository
from researchos.agents.runtime import AgentRuntime
from researchos.agents.runtime.base import AgentContext
from researchos.agents.runtime.events import EventEmitter
from researchos.agents.runtime.latex_agent import LatexAgent
from researchos.agents.runtime.tools import ToolContext
from researchos.common.errors import ConflictError, ValidationError
from researchos.documents.enums import SuggestionOp, SuggestionStatus
from researchos.documents.repository import SuggestionRepository
from researchos.documents.schemas import SelectionOpRequest
from researchos.documents.service import DocumentService
from researchos.documents.suggestions import (
    SuggestionService,
    compute_spans,
    prepare_op_context,
)
from researchos.identity.service import AuthService
from researchos.projects.service import ProjectService

from .helpers import csrf_headers, register

_GRAMMAR_DOC = (
    "\\documentclass{article}\n\\begin{document}\n"
    "the results  shows  gains\n\\end{document}\n"
)
_GRAMMAR_SELECTION = "the results  shows  gains"
_GRAMMAR_FIXED = "The results shows gains."


# --- compute_spans (pure) -----------------------------------------------------
def test_compute_spans_roundtrip_and_adjacent_merge() -> None:
    old = "The results shows gains"
    new = "The results show gains overall"
    spans = compute_spans(old, new)
    assert "".join(s["old"] for s in spans) == old
    assert "".join(s["new"] for s in spans) == new
    kinds = [s["kind"] for s in spans]
    # Adjacent same-kind spans are merged.
    assert all(kinds[i] != kinds[i + 1] for i in range(len(kinds) - 1))
    assert {"equal", "replace"} <= set(kinds) or {"equal", "insert"} <= set(kinds)


def test_compute_spans_insert_only_for_continue_writing() -> None:
    spans = compute_spans("", "brand new text")
    assert spans == [{"kind": "insert", "old": "", "new": "brand new text"}]


def test_compute_spans_identical_texts() -> None:
    spans = compute_spans("same", "same")
    assert spans == [{"kind": "equal", "old": "same", "new": "same"}]


# --- HTTP setup helpers -------------------------------------------------------
async def _paper_project(client, email: str) -> tuple[str, str]:
    await register(client, email=email)
    org_id = (await client.get("/organizations")).json()[0]["id"]
    h = csrf_headers(client)
    project_id = (
        await client.post("/projects", json={"organization_id": org_id, "name": "P"}, headers=h)
    ).json()["id"]
    lp_id = (
        await client.post(
            f"/projects/{project_id}/latex-projects", json={"name": "Paper"}, headers=h
        )
    ).json()["id"]
    return project_id, lp_id


def _base(p: str, lp: str) -> str:
    return f"/projects/{p}/latex-projects/{lp}"


def _grammar_op_payload() -> dict:
    return {
        "op": "fix_grammar",
        "path": "main.tex",
        "range": {"start": {"line": 3, "col": 1}, "end": {"line": 3, "col": 26}},
        "selection_text": _GRAMMAR_SELECTION,
        "expected_version": 2,
        "instruction": None,
    }


# --- endpoint validation ------------------------------------------------------
async def test_selection_op_endpoint_validations(client) -> None:
    p, lp = await _paper_project(client, "sug-val@example.com")
    h = csrf_headers(client)

    url = f"{_base(p, lp)}/selection-ops"
    bad_op = dict(_grammar_op_payload(), op="obliterate")
    assert (await client.post(url, json=bad_op, headers=h)).status_code == 422

    empty = dict(_grammar_op_payload(), selection_text="", op="rewrite")
    assert (await client.post(url, json=empty, headers=h)).status_code == 422

    missing = dict(_grammar_op_payload(), path="nope.tex")
    assert (await client.post(url, json=missing, headers=h)).status_code == 404


# --- full pipeline (mock provider is deterministic) ---------------------------
async def test_fix_grammar_pipeline_roundtrip(client, db_session: AsyncSession) -> None:
    p, lp = await _paper_project(client, "sug-pipe@example.com")
    h = csrf_headers(client)
    await client.put(
        f"{_base(p, lp)}/files",
        json={"path": "main.tex", "content": _GRAMMAR_DOC, "expected_version": 1},
        headers=h,
    )

    resp = await client.post(
        f"{_base(p, lp)}/selection-ops", json=_grammar_op_payload(), headers=h
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["stream"].startswith("/ws?project_id=")
    run_id = uuid.UUID(body["agent_run_id"])

    # Drive the queued run exactly like the worker would (mock LLM provider).
    await AgentRuntime(db_session).run(run_id)
    run = await AgentRunRepository(db_session).get_unscoped(run_id)
    assert run is not None and run.status == AgentRunStatus.COMPLETED
    suggestion_id = run.output_json["suggestion_id"]
    assert run.output_json["op"] == "fix_grammar"
    assert run.output_json["path"] == "main.tex"

    detail = await client.get(f"{_base(p, lp)}/suggestions/{suggestion_id}")
    assert detail.status_code == 200
    suggestion = detail.json()
    assert suggestion["op"] == "fix_grammar"
    assert suggestion["status"] == "proposed"
    assert suggestion["base_version"] == 2
    assert suggestion["old_text"] == _GRAMMAR_SELECTION
    assert suggestion["new_text"] == _GRAMMAR_FIXED
    assert suggestion["rationale"] == "Mock fix_grammar suggestion (deterministic)."
    assert suggestion["agent_run_id"] == str(run_id)
    assert suggestion["spans"], "spans must be non-empty"
    assert "".join(s["old"] for s in suggestion["spans"]) == _GRAMMAR_SELECTION
    assert "".join(s["new"] for s in suggestion["spans"]) == _GRAMMAR_FIXED

    listing = (
        await client.get(f"{_base(p, lp)}/suggestions?status=proposed&path=main.tex")
    ).json()
    assert listing["total"] == 1
    assert listing["items"][0]["id"] == suggestion_id

    accept = await client.post(
        f"{_base(p, lp)}/suggestions/{suggestion_id}/accept",
        json={"expected_version": 2},
        headers=h,
    )
    assert accept.status_code == 200
    accepted = accept.json()
    assert accepted["suggestion"]["status"] == "accepted"
    assert accepted["file"]["version"] == 3
    assert _GRAMMAR_FIXED in accepted["file"]["content"]
    assert _GRAMMAR_SELECTION not in accepted["file"]["content"]


async def test_chat_mode_without_op_still_works(db_session: AsyncSession) -> None:
    user, org = await AuthService(db_session).register(
        email="sug-chat@example.com", password="password123", display_name="C"
    )
    project = await ProjectService(db_session).create_project(
        user, organization_id=org.id, name="P", description=None, field=None
    )
    run = await AgentRunRepository(db_session).create(
        AgentRun(
            project_id=project.id,
            user_id=user.id,
            agent_type=AgentType.LATEX,
            status=AgentRunStatus.QUEUED,
            input_json={"message": "How do I improve my abstract?", "context": {}},
        )
    )
    await db_session.commit()

    await AgentRuntime(db_session).run(run.id)
    await db_session.refresh(run)
    assert run.status == AgentRunStatus.COMPLETED
    assert set(run.output_json) == {"message"}
    assert run.output_json["message"]


# --- service-level accept variants -------------------------------------------
async def _service_setup(db: AsyncSession, email: str):
    user, org = await AuthService(db).register(
        email=email, password="password123", display_name="S"
    )
    project = await ProjectService(db).create_project(
        user, organization_id=org.id, name="P", description=None, field=None
    )
    documents = DocumentService(db)
    lp = await documents.create_latex_project(user, project.id, name="Paper")
    return user, project, documents, lp


async def _queued_run(db: AsyncSession, user, project, context: dict) -> AgentRun:
    run = await AgentRunRepository(db).create(
        AgentRun(
            project_id=project.id,
            user_id=user.id,
            agent_type=AgentType.LATEX,
            status=AgentRunStatus.QUEUED,
            input_json={"message": "op", "context": context},
        )
    )
    await db.commit()
    return run


def _op_request(selection: str, *, line: int, end_col: int) -> SelectionOpRequest:
    return SelectionOpRequest.model_validate(
        {
            "op": "rewrite",
            "path": "main.tex",
            "range": {"start": {"line": line, "col": 1}, "end": {"line": line, "col": end_col}},
            "selection_text": selection,
        }
    )


async def test_accept_reanchors_after_intervening_edit(db_session: AsyncSession) -> None:
    user, project, documents, lp = await _service_setup(db_session, "sug-re@example.com")
    content = "intro line\ntarget sentence here\noutro line\n"
    await documents.save_file(user, project.id, lp.id, path="main.tex", content=content)
    file = await documents.files.get_by_path(lp.id, "main.tex")

    payload = _op_request("target sentence here", line=2, end_col=21)
    context = prepare_op_context(file=file, latex_project_id=lp.id, payload=payload)
    run = await _queued_run(db_session, user, project, context)
    service = SuggestionService(db_session)
    suggestion = await service.create_from_run(
        run=run, context=context, replacement="REPLACED SENTENCE", rationale="r"
    )
    await db_session.commit()

    # Intervening edit elsewhere bumps the version; accept re-anchors by text.
    await documents.save_file(
        user,
        project.id,
        lp.id,
        path="main.tex",
        content=content.replace("intro line", "INTRO EDITED"),
    )
    accepted, file = await service.accept(user, project.id, lp.id, suggestion.id)
    assert accepted.status == SuggestionStatus.ACCEPTED
    assert "REPLACED SENTENCE" in file.content
    assert "INTRO EDITED" in file.content
    assert accepted.applied_version == file.version


async def test_accept_anchor_not_found_keeps_suggestion_proposed(
    db_session: AsyncSession,
) -> None:
    user, project, documents, lp = await _service_setup(db_session, "sug-nf@example.com")
    content = "intro line\ntarget sentence here\noutro line\n"
    await documents.save_file(user, project.id, lp.id, path="main.tex", content=content)
    file = await documents.files.get_by_path(lp.id, "main.tex")

    payload = _op_request("target sentence here", line=2, end_col=21)
    context = prepare_op_context(file=file, latex_project_id=lp.id, payload=payload)
    run = await _queued_run(db_session, user, project, context)
    service = SuggestionService(db_session)
    suggestion = await service.create_from_run(
        run=run, context=context, replacement="X", rationale=""
    )
    await db_session.commit()

    await documents.save_file(
        user, project.id, lp.id, path="main.tex", content="completely different now\n"
    )
    with pytest.raises(ConflictError) as excinfo:
        await service.accept(user, project.id, lp.id, suggestion.id)
    assert excinfo.value.code == "suggestion_conflict"
    assert excinfo.value.details == {"reason": "anchor_not_found"}

    await db_session.refresh(suggestion)
    assert suggestion.status == SuggestionStatus.PROPOSED
    assert suggestion.last_error == "anchor_not_found"


async def test_accept_ambiguous_anchor_conflict(db_session: AsyncSession) -> None:
    user, project, documents, lp = await _service_setup(db_session, "sug-amb@example.com")
    await documents.save_file(user, project.id, lp.id, path="main.tex", content="dup dup\n")
    file = await documents.files.get_by_path(lp.id, "main.tex")

    # Hand-built context with empty anchors: both occurrences stay ambiguous.
    context = {
        "op": "rewrite",
        "path": "main.tex",
        "latex_project_id": str(lp.id),
        "document_file_id": str(file.id),
        "base_version": file.version,
        "anchor_mode": "text",
        "selection_text": "dup",
        "instruction": None,
        "range": {"start": {"line": 1, "col": 1}, "end": {"line": 1, "col": 4}},
        "offset_start": 0,
        "offset_end": 3,
        "anchor_prefix": "",
        "anchor_suffix": "",
    }
    run = await _queued_run(db_session, user, project, context)
    service = SuggestionService(db_session)
    suggestion = await service.create_from_run(
        run=run, context=context, replacement="DUP", rationale=""
    )
    await db_session.commit()

    with pytest.raises(ConflictError) as excinfo:
        await service.accept(user, project.id, lp.id, suggestion.id)
    assert excinfo.value.details == {"reason": "ambiguous_anchor"}
    await db_session.refresh(suggestion)
    assert suggestion.status == SuggestionStatus.PROPOSED


async def test_accept_stale_expected_version_conflict(db_session: AsyncSession) -> None:
    user, project, documents, lp = await _service_setup(db_session, "sug-cas@example.com")
    file = await documents.files.get_by_path(lp.id, "main.tex")
    payload = _op_request("Untitled", line=2, end_col=9)
    context = prepare_op_context(file=file, latex_project_id=lp.id, payload=payload)
    run = await _queued_run(db_session, user, project, context)
    service = SuggestionService(db_session)
    suggestion = await service.create_from_run(
        run=run, context=context, replacement="Titled", rationale=""
    )
    await db_session.commit()

    with pytest.raises(ConflictError) as excinfo:
        await service.accept(
            user, project.id, lp.id, suggestion.id, expected_version=file.version + 5
        )
    assert excinfo.value.code == "document_version_conflict"
    await db_session.refresh(suggestion)
    assert suggestion.status == SuggestionStatus.PROPOSED


async def test_reject_then_not_pending(db_session: AsyncSession) -> None:
    user, project, documents, lp = await _service_setup(db_session, "sug-rej@example.com")
    file = await documents.files.get_by_path(lp.id, "main.tex")
    payload = _op_request("Untitled", line=2, end_col=9)
    context = prepare_op_context(file=file, latex_project_id=lp.id, payload=payload)
    run = await _queued_run(db_session, user, project, context)
    service = SuggestionService(db_session)
    suggestion = await service.create_from_run(
        run=run, context=context, replacement="Titled", rationale=""
    )
    await db_session.commit()

    rejected, path = await service.reject(user, project.id, lp.id, suggestion.id)
    assert rejected.status == SuggestionStatus.REJECTED
    assert path == "main.tex"

    with pytest.raises(ValidationError):
        await service.reject(user, project.id, lp.id, suggestion.id)
    with pytest.raises(ValidationError):
        await service.accept(user, project.id, lp.id, suggestion.id)


# --- failure modes ------------------------------------------------------------
class _ScriptedProvider:
    """Streams a fixed text once (simulates a misbehaving real provider)."""

    name = "scripted"

    def __init__(self, text: str) -> None:
        self._text = text

    async def stream(
        self, *, messages, tools=None, response_schema=None, force_structured=False
    ):
        yield TextDelta(self._text)
        yield Usage(input_tokens=1, output_tokens=1)
        yield StreamDone(stop_reason="stop")


async def _op_run_for_failure(db: AsyncSession, email: str) -> tuple[AgentRun, uuid.UUID]:
    user, project, documents, lp = await _service_setup(db, email)
    file = await documents.files.get_by_path(lp.id, "main.tex")
    payload = _op_request("Untitled", line=2, end_col=9)
    context = prepare_op_context(file=file, latex_project_id=lp.id, payload=payload)
    run = await _queued_run(db, user, project, context)
    return run, lp.id


async def test_replacement_less_json_fails_run(db_session: AsyncSession) -> None:
    run, lp_id = await _op_run_for_failure(db_session, "sug-fail1@example.com")
    await AgentRuntime(db_session, llm=_ScriptedProvider('{"rationale": "no replacement"}')).run(
        run.id
    )
    await db_session.refresh(run)
    assert run.status == AgentRunStatus.FAILED
    assert run.error_json["code"] == "structured_output_parse_error"
    rows, total = await SuggestionRepository(db_session).list_by_project(
        lp_id, status=None, path=None, limit=10, offset=0
    )
    assert total == 0  # never persist an empty suggestion as success


async def test_unparsable_output_fails_run(db_session: AsyncSession) -> None:
    run, lp_id = await _op_run_for_failure(db_session, "sug-fail2@example.com")
    await AgentRuntime(db_session, llm=_ScriptedProvider("garbage, not json at all")).run(run.id)
    await db_session.refresh(run)
    assert run.status == AgentRunStatus.FAILED
    assert run.error_json["code"] == "structured_output_parse_error"
    _, total = await SuggestionRepository(db_session).list_by_project(
        lp_id, status=None, path=None, limit=10, offset=0
    )
    assert total == 0


async def test_finalize_unstructured_fallback_direct(db_session: AsyncSession) -> None:
    """Finalize keeps unparsable text reviewable when invoked without the gate."""

    user, project, documents, lp = await _service_setup(db_session, "sug-unstr@example.com")
    file = await documents.files.get_by_path(lp.id, "main.tex")
    payload = _op_request("Untitled", line=2, end_col=9)
    context = prepare_op_context(file=file, latex_project_id=lp.id, payload=payload)
    run = await _queued_run(db_session, user, project, context)

    emitter = EventEmitter(db_session, project_id=project.id, run_id=run.id)
    tool_ctx = ToolContext(
        db=db_session,
        actor=user,
        project_id=project.id,
        run_id=run.id,
        emitter=emitter,
        allowed_tools=set(),
        http_client=None,
    )
    actx = AgentContext(
        db=db_session,
        actor=user,
        project_id=project.id,
        run=run,
        message="op",
        context=context,
        tool_ctx=tool_ctx,
        skills=[],
    )
    output_json, citations = await LatexAgent().finalize(
        actx,
        output_text="Plain rewritten text without JSON.",
        whitelist=set(),
        citation_sources={},
        usage={},
    )
    await db_session.commit()
    assert citations == []
    assert output_json["unstructured"] is True
    suggestion = await SuggestionRepository(db_session).get(
        lp.id, uuid.UUID(output_json["suggestion_id"])
    )
    assert suggestion is not None
    assert suggestion.new_text == "Plain rewritten text without JSON."
    assert suggestion.op == SuggestionOp.REWRITE
