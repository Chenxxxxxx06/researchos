"""Research agent: finds papers and produces a source-backed synthesis.

The runtime returns only the LAST iteration's text as the final answer —
pre-tool prose lives inside prior assistant messages, never in the output.

"Explain this section" support: when the run context carries ``paper_id`` (and
optionally ``section_seqs``), the referenced section bodies are injected into
the system prompt via ``PaperService.sections_for_agent`` and the paper joins
the citation whitelist. The service method lands with the research partition;
until then the agent degrades to the plain prompt (lazy import + hasattr
guard), so this module works standalone.
"""

from __future__ import annotations

import uuid

import structlog

from researchos.agents.enums import AgentType
from researchos.agents.llm import LLMMessage

from .base import Agent, AgentContext
from .citations import filter_citations

logger = structlog.get_logger(__name__)

_SYSTEM = (
    "You are a research assistant for an AI researcher. Search the existing project "
    "corpus with knowledge.rag_search first when the question can be answered from "
    "imported papers; use paper.search for external discovery and paper.sections for "
    "full section context. Synthesize a concise, source-backed answer. Only cite "
    "papers returned by the tools. Never invent citations. If you are unsure, say so "
    "and mark the statement as an assumption."
)

# Contract with the mock provider's section-grounded explain script.
_SECTIONS_HEADER = "## Referenced paper sections"


async def _build_sections_block(actx: AgentContext) -> str:
    """Render the referenced sections block ('' when unavailable).

    Also seeds the citation whitelist with the referenced paper so a grounded
    explanation may cite it even without a tool round-trip.
    """

    raw_paper_id = actx.context.get("paper_id")
    if not raw_paper_id:
        return ""
    try:
        paper_id = uuid.UUID(str(raw_paper_id))
    except ValueError:
        return ""

    try:
        from researchos.research.models import Paper
        from researchos.research.service import PaperService
    except ImportError:  # pragma: no cover - parallel-partition seam
        return ""

    paper = await actx.db.get(Paper, paper_id)
    if paper is None or paper.project_id != actx.project_id:
        return ""
    key = f"{paper.source}:{paper.external_id}"
    actx.tool_ctx.citation_whitelist.add(key)
    actx.tool_ctx.citation_sources[key] = {
        "source": paper.source,
        "external_id": paper.external_id,
        "title": paper.title,
        "url": paper.url or "",
    }

    service = PaperService(actx.db, http_client=actx.tool_ctx.http_client)
    if not hasattr(service, "sections_for_agent"):
        # Research partition not landed yet: whitelist-only degradation.
        return ""
    data = await service.sections_for_agent(actx.actor, actx.project_id, paper_key=key)
    results = list(data.get("results", []))
    section_seqs = actx.context.get("section_seqs") or []
    if section_seqs:
        wanted = {int(s) for s in section_seqs}
        filtered = [r for r in results if int(r.get("seq", -1)) in wanted]
        results = filtered or results
    if not results:
        return ""

    lines = [_SECTIONS_HEADER, f"Paper: {key} — {paper.title}"]
    for row in results:
        lines.append(f"### [S{row.get('seq', 0)}] {row.get('heading', '')}")
        body = str(row.get("body", ""))
        if body:
            lines.append(body)
    logger.info(
        "research_sections_injected",
        run_id=str(actx.run.id),
        paper_key=key,
        section_count=len(results),
    )
    return "\n".join(lines)


class ResearchAgent(Agent):
    agent_type = AgentType.RESEARCH
    allowed_tools = [
        "knowledge.rag_search",
        "paper.search",
        "library.list",
        "paper.sections",
    ]
    response_schema = None

    async def build_messages(self, actx: AgentContext) -> list[LLMMessage]:
        system = _SYSTEM
        sections_block = await _build_sections_block(actx)
        if sections_block:
            system = (
                system
                + "\n\nGround your explanation in the referenced sections below; cite "
                "the paper by its key.\n\n"
                + sections_block
            )
        return [
            LLMMessage(role="system", content=system),
            LLMMessage(role="user", content=actx.message),
        ]

    async def finalize(
        self,
        actx: AgentContext,
        *,
        output_text: str,
        whitelist: set[str],
        citation_sources: dict[str, dict],
        usage: dict,
    ) -> tuple[dict, list[dict]]:
        # Research cites everything it actually retrieved (all whitelisted papers).
        kept, _dropped = filter_citations(list(whitelist), whitelist)
        citations = [citation_sources[k] for k in kept if k in citation_sources]
        output_json = {"message": output_text, "citations": kept}
        return output_json, citations
