"""Tool registry and Tool Broker.

Agents never call tools directly. The broker enforces the per-agent tool
allowlist, records every invocation in ``tool_calls``, and emits tool-call
events. This is the extension point where Phase 6 skill permission policy will
plug in.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from researchos.agents.enums import ToolCallStatus
from researchos.agents.models import ToolCall
from researchos.agents.repository import ToolCallRepository
from researchos.common.errors import AppError
from researchos.identity.models import User
from researchos.research.service import PaperService

from .events import EventEmitter


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
}


class ToolBroker:
    """Executes tools with permission checks, persistence, and events."""

    def __init__(self, ctx: ToolContext) -> None:
        self.ctx = ctx
        self.tool_calls = ToolCallRepository(ctx.db)

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
        await ctx.emitter.tool_call_started(seq, tool_name, arguments)

        if spec is None or tool_name not in ctx.allowed_tools:
            record.status = ToolCallStatus.FAILED
            record.error = "tool not permitted"
            record.finished_at = _now()
            await ctx.db.commit()
            await ctx.emitter.tool_call_completed(seq, tool_name, "failed")
            raise ToolDenied()

        try:
            result = await spec.impl(ctx, arguments)
        except Exception as exc:  # noqa: BLE001 - record and surface tool failures
            record.status = ToolCallStatus.FAILED
            record.error = str(exc)
            record.finished_at = _now()
            await ctx.db.commit()
            await ctx.emitter.tool_call_completed(seq, tool_name, "failed")
            raise

        record.result_json = result
        record.status = ToolCallStatus.SUCCEEDED
        record.finished_at = _now()
        await ctx.db.commit()
        await ctx.emitter.tool_call_completed(
            seq, tool_name, "succeeded", f"{len(result.get('results', []))} result(s)"
        )

        # Grow the citation whitelist from any papers this tool surfaced.
        for item in result.get("results", []):
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
