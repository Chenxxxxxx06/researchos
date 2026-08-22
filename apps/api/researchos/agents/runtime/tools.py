"""Tool registry and Tool Broker.

Agents never call tools directly. The broker enforces the per-agent tool
allowlist, records every invocation in ``tool_calls``, and emits tool-call
events. Unknown/unpermitted tools still raise ``ToolDenied`` (the runtime
converts it into a recoverable tool-result message); tool *implementation*
failures never raise — they return a structured ``{"error": {...}}`` payload
so a single bad call cannot fail the whole run.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from researchos.agents.enums import ToolCallStatus
from researchos.agents.models import ToolCall
from researchos.agents.repository import ToolCallRepository
from researchos.common.config import get_settings
from researchos.common.errors import AppError
from researchos.identity.models import User
from researchos.research.service import PaperService

from .events import EventEmitter

logger = structlog.get_logger(__name__)


@dataclass
class ToolContext:
    db: AsyncSession
    actor: User
    project_id: uuid.UUID
    run_id: uuid.UUID
    emitter: EventEmitter
    allowed_tools: set[str]
    http_client: httpx.AsyncClient | None = None
    citation_whitelist: set[str] = field(default_factory=set)
    # key -> {source, external_id, title, url} for building completed-event citations.
    citation_sources: dict[str, dict] = field(default_factory=dict)
    # rel path -> whole-file sha recorded at read time (read-before-write guard;
    # the recorded sha overrides whatever base_sha the agent echoes back).
    read_paths: dict[str, str] = field(default_factory=dict)
    read_bytes_used: int = 0
    # tool name -> "agent" or the granting skill slug (populated by the runtime).
    granted_by: dict[str, str] = field(default_factory=dict)


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict
    impl: Callable[[ToolContext, dict], Awaitable[dict]]


class ToolDenied(AppError):
    code = "tool_denied"
    http_status = 403
    message = "Tool is not permitted for this agent."


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _tool_error(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


def _opt_int(value: object) -> int | None:
    if not isinstance(value, int | float | str):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# --- Tool implementations ----------------------------------------------------
async def _paper_search(ctx: ToolContext, args: dict) -> dict:
    query = str(args.get("query", "")).strip()
    limit = int(args.get("limit", 5))
    results = await PaperService(ctx.db, http_client=ctx.http_client).search(
        ctx.actor, ctx.project_id, query=query, limit=limit
    )
    items = [
        {
            "source": r.source,
            "external_id": r.external_id,
            "title": r.title,
            "url": r.url,
            "abstract": r.abstract,
        }
        for r in results
    ]
    return {"results": items}


async def _library_list(ctx: ToolContext, args: dict) -> dict:
    page = await PaperService(ctx.db, http_client=ctx.http_client).list_library(
        ctx.actor, ctx.project_id, limit=50, offset=0
    )
    items = [
        {"source": p.source, "external_id": p.external_id, "title": p.title, "url": p.url}
        for p in page.items
    ]
    return {"results": items}


async def _workspace_tree(ctx: ToolContext, args: dict) -> dict:
    from researchos.workspace.service import WorkspaceService

    tree = await WorkspaceService(ctx.db).get_tree(ctx.actor, ctx.project_id)
    return {"tree": tree.model_dump(mode="json")}


async def _workspace_read(ctx: ToolContext, args: dict) -> dict:
    from researchos.workspace.service import WorkspaceService

    settings = get_settings()
    if ctx.read_bytes_used >= settings.workspace_read_budget_bytes:
        return _tool_error(
            "read_budget_exhausted",
            "The read budget for this run is exhausted; work with what you have read.",
        )

    path = str(args.get("path", ""))
    data = await WorkspaceService(ctx.db).read_file_range(
        ctx.actor,
        ctx.project_id,
        path,
        start_line=_opt_int(args.get("start_line")),
        end_line=_opt_int(args.get("end_line")),
    )
    if data.get("binary") or data.get("too_large"):
        return _tool_error("unreadable_file", f"{path} is binary or too large to read.")

    content: str = data["content"] or ""
    ctx.read_bytes_used += len(content.encode("utf-8"))
    # Whole-file sha even for ranged reads — this is the base_sha guard value.
    ctx.read_paths[path] = data["sha"]
    return {
        "path": path,
        "content": content,
        "start_line": data["start_line"],
        "end_line": data["end_line"],
        "total_lines": data["total_lines"],
        "sha": data["sha"],
        "truncated": data["truncated"],
    }


async def _workspace_grep(ctx: ToolContext, args: dict) -> dict:
    from researchos.workspace.service import WorkspaceService

    settings = get_settings()
    cap = settings.workspace_grep_max_results
    max_results = min(_opt_int(args.get("max_results")) or cap, cap)
    try:
        result = await WorkspaceService(ctx.db).grep(
            ctx.actor,
            ctx.project_id,
            pattern=str(args.get("pattern", "")),
            glob=str(args["glob"]) if args.get("glob") else None,
            max_results=max_results,
            ignore_case=bool(args.get("ignore_case", False)),
        )
    except re.error as exc:
        return _tool_error("invalid_pattern", str(exc))
    return result


async def _paper_sections(ctx: ToolContext, args: dict) -> dict:
    from researchos.research.service import PaperService

    return await PaperService(ctx.db, http_client=ctx.http_client).sections_for_agent(
        ctx.actor, ctx.project_id, paper_key=str(args.get("paper_key", "")),
        kind=args.get("kind"), seq=args.get("seq"))


async def _knowledge_rag_search(ctx: ToolContext, args: dict) -> dict:
    """Hybrid vector + keyword retrieval over parsed project paper chunks."""

    from researchos.knowledge.schemas import RagSearchRequest
    from researchos.knowledge.service import KnowledgeService

    payload = RagSearchRequest.model_validate(
        {
            "query": str(args.get("query", "")),
            "mission_id": args.get("mission_id"),
            "limit": min(_opt_int(args.get("limit")) or 12, 20),
            "kinds": args.get("kinds") or [],
        }
    )
    response = await KnowledgeService(ctx.db).rag_search(ctx.actor, ctx.project_id, payload)
    results: list[dict] = []
    for hit in response.hits:
        source, separator, external_id = hit.citation_key.partition(":")
        results.append(
            {
                **hit.model_dump(mode="json"),
                "source": source if separator else "library",
                "external_id": external_id if separator else hit.citation_key,
                "url": "",
            }
        )
    return {
        "mode": response.mode,
        "embedding_model": response.embedding_model,
        "indexed_papers": response.indexed_papers,
        "indexed_chunks": response.indexed_chunks,
        "results": results,
    }


TOOL_REGISTRY: dict[str, ToolSpec] = {
    "paper.search": ToolSpec(
        name="paper.search",
        description="Search external literature (arXiv) for papers matching a query.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": ["query"],
        },
        impl=_paper_search,
    ),
    "library.list": ToolSpec(
        name="library.list",
        description="List papers already imported into the project's library.",
        parameters={"type": "object", "properties": {}},
        impl=_library_list,
    ),
    "workspace.tree": ToolSpec(
        name="workspace.tree",
        description="List the project's workspace file tree (read-only).",
        parameters={"type": "object", "properties": {}},
        impl=_workspace_tree,
    ),
    "workspace.read": ToolSpec(
        name="workspace.read",
        description=(
            "Read a workspace file (optionally a 1-based inclusive line range). "
            "Returns the file content plus its whole-file sha — use that sha "
            "verbatim as base_sha when proposing changes to the file."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "start_line": {"type": "integer"},
                "end_line": {"type": "integer"},
            },
            "required": ["path"],
        },
        impl=_workspace_read,
    ),
    "workspace.grep": ToolSpec(
        name="workspace.grep",
        description=(
            "Search workspace file contents with a regular expression. "
            "Returns matching lines with paths and line numbers."
        ),
        parameters={
            "type": "object",
            "properties": {
                "pattern": {"type": "string"},
                "glob": {"type": "string"},
                "max_results": {"type": "integer"},
                "ignore_case": {"type": "boolean"},
            },
            "required": ["pattern"],
        },
        impl=_workspace_grep,
    ),
}

TOOL_REGISTRY["paper.sections"] = ToolSpec(
    name="paper.sections",
    description=("Read structured full-text sections of a library paper by "
                 "'source:external_id' key; optional kind or seq filter."),
    parameters={"type": "object", "properties": {
        "paper_key": {"type": "string"}, "kind": {"type": "string"},
        "seq": {"type": "integer"}}, "required": ["paper_key"]},
    impl=_paper_sections)

TOOL_REGISTRY["knowledge.rag_search"] = ToolSpec(
    name="knowledge.rag_search",
    description=(
        "Search parsed project papers with hybrid vector and keyword retrieval. "
        "Returns source-addressable snippets, section ids, scores, and citation keys."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "mission_id": {"type": "string"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 20},
            "kinds": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["query"],
    },
    impl=_knowledge_rag_search,
)


def _result_summary(result: dict) -> str:
    if "error" in result:
        return f"error: {result['error'].get('code', 'unknown')}"
    if "matches" in result:
        return f"{len(result['matches'])} match(es)"
    if "content" in result and "total_lines" in result:
        return f"{len(str(result['content']).splitlines())} line(s)"
    return f"{len(result.get('results', []))} result(s)"


class ToolBroker:
    """Executes tools with permission checks, persistence, and events."""

    def __init__(self, ctx: ToolContext) -> None:
        self.ctx = ctx
        self.tool_calls = ToolCallRepository(ctx.db)

    async def _emit_started(self, seq: int, tool_name: str, arguments: dict) -> None:
        # Emitted directly (not via the events.py helper) so the payload can
        # carry per-skill grant attribution (runtime-llm CP-2b).
        await self.ctx.emitter.emit(
            "agent.run.tool_call.started",
            {
                "seq": seq,
                "tool_name": tool_name,
                "arguments": arguments,
                "granted_by": self.ctx.granted_by.get(tool_name, "agent"),
            },
            persist=True,
        )

    async def execute(self, tool_name: str, arguments: dict) -> dict:
        ctx = self.ctx
        seq = await self.tool_calls.next_seq(ctx.run_id)

        spec = TOOL_REGISTRY.get(tool_name)
        record = ToolCall(
            agent_run_id=ctx.run_id,
            project_id=ctx.project_id,
            seq=seq,
            tool_name=tool_name,
            arguments_json=arguments,
            status=ToolCallStatus.PENDING,
            started_at=_now(),
        )
        await self.tool_calls.create(record)
        await ctx.db.commit()
        await self._emit_started(seq, tool_name, arguments)

        if spec is None or tool_name not in ctx.allowed_tools:
            record.status = ToolCallStatus.FAILED
            record.error = "tool not permitted"
            record.finished_at = _now()
            await ctx.db.commit()
            await ctx.emitter.tool_call_completed(seq, tool_name, "failed")
            raise ToolDenied()

        try:
            result = await spec.impl(ctx, arguments)
        except Exception as exc:  # noqa: BLE001 - surfaced as an in-band error result
            code = exc.code if isinstance(exc, AppError) else "tool_failed"
            logger.warning(
                "tool_call_failed",
                run_id=str(ctx.run_id),
                tool_name=tool_name,
                code=code,
                error=str(exc),
            )
            result = _tool_error(code, str(exc))

        is_error = "error" in result
        record.result_json = result
        record.status = ToolCallStatus.FAILED if is_error else ToolCallStatus.SUCCEEDED
        record.error = result["error"].get("message") if is_error else None
        record.finished_at = _now()
        await ctx.db.commit()
        await ctx.emitter.tool_call_completed(
            seq,
            tool_name,
            "failed" if is_error else "succeeded",
            _result_summary(result),
        )

        # Grow the citation whitelist from any papers this tool surfaced
        # (error payloads carry no "results" key, so they are naturally inert).
        for item in result.get("results", []):
            if not isinstance(item, dict):
                continue
            src, ext = item.get("source"), item.get("external_id")
            if src and ext:
                key = f"{src}:{ext}"
                ctx.citation_whitelist.add(key)
                ctx.citation_sources[key] = {
                    "source": src,
                    "external_id": ext,
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                }
        return result
