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
from sqlalchemy import select

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
                system + "\n\nGround your explanation in the referenced sections below; cite "
                "the paper by its key.\n\n" + sections_block
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
        task_key = str(actx.context.get("task_key") or "")
        if task_key == "discover":
            output_json.update(await _persist_discovery(actx, citation_sources, kept))
        elif task_key == "synthesize":
            output_json.update(await _persist_synthesis(actx, output_text, citation_sources, kept))
        return output_json, citations


async def _persist_synthesis(
    actx: AgentContext,
    body: str,
    citation_sources: dict[str, dict],
    keys: list[str],
) -> dict:
    from researchos.research.models import Paper
    from researchos.reviews.models import ReviewDocument, ReviewSection, ReviewVersion

    try:
        mission_id = uuid.UUID(str(actx.context["mission_id"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Synthesis task requires mission_id.") from exc
    paper_ids: list[str] = []
    for key in keys:
        source = citation_sources.get(key)
        if source is None:
            continue
        paper_id = await actx.db.scalar(
            select(Paper.id).where(
                Paper.project_id == actx.project_id,
                Paper.source == str(source["source"]),
                Paper.external_id == str(source["external_id"]),
            )
        )
        if paper_id is not None:
            paper_ids.append(str(paper_id))
    review = await actx.db.scalar(
        select(ReviewDocument).where(ReviewDocument.mission_id == mission_id)
    )
    if review is None:
        review = ReviewDocument(
            project_id=actx.project_id,
            mission_id=mission_id,
            title="Cross-paper evidence synthesis",
            status="needs_review",
            created_by=actx.actor.id,
            updated_by=actx.actor.id,
        )
        actx.db.add(review)
        await actx.db.flush()
    else:
        review.version += 1
        review.status = "needs_review"
        review.updated_by = actx.actor.id
    section = await actx.db.scalar(
        select(ReviewSection).where(
            ReviewSection.review_id == review.id,
            ReviewSection.section_key == "autopilot-synthesis",
        )
    )
    if section is None:
        section = ReviewSection(
            project_id=actx.project_id,
            mission_id=mission_id,
            review_id=review.id,
            section_key="autopilot-synthesis",
            position=0,
            title="Evidence synthesis and open gaps",
            purpose="Bridge reviewed paper insights into experiment planning.",
            updated_by=actx.actor.id,
        )
        actx.db.add(section)
    else:
        section.version += 1
    section.body = body
    section.citations_json = paper_ids
    section.claims_json = []
    section.status = "needs_review"
    section.generated_by_run_id = actx.run.id
    section.updated_by = actx.actor.id
    await actx.db.flush()
    actx.db.add(
        ReviewVersion(
            project_id=actx.project_id,
            mission_id=mission_id,
            review_id=review.id,
            version=review.version,
            snapshot_json={
                "title": review.title,
                "status": review.status,
                "sections": [
                    {
                        "id": str(section.id),
                        "key": section.section_key,
                        "title": section.title,
                        "purpose": section.purpose,
                        "body": section.body,
                        "citations": section.citations_json,
                        "claims": section.claims_json,
                        "status": section.status,
                        "version": section.version,
                    }
                ],
            },
            source_type="agent",
            source_run_id=actx.run.id,
            created_by=actx.actor.id,
        )
    )
    return {
        "review_document_id": str(review.id),
        "review_version": review.version,
        "review_section_id": str(section.id),
    }


async def _persist_discovery(
    actx: AgentContext,
    citation_sources: dict[str, dict],
    keys: list[str],
) -> dict:
    from researchos.knowledge.schemas import AddMissionPapersRequest
    from researchos.knowledge.service import KnowledgeService
    from researchos.research.providers import PaperImportRef
    from researchos.research.service import PaperService

    try:
        mission_id = uuid.UUID(str(actx.context["mission_id"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Discovery task requires mission_id.") from exc
    refs = [
        PaperImportRef(
            source=str(citation_sources[key]["source"]),
            external_id=str(citation_sources[key]["external_id"]),
        )
        for key in keys
        if key in citation_sources
    ][:50]
    if not refs:
        raise ValueError("Discovery produced no retrievable paper references.")
    papers, skipped = await PaperService(
        actx.db, http_client=actx.tool_ctx.http_client
    ).import_papers(actx.actor, actx.project_id, refs)
    if not papers:
        raise ValueError("Discovery references could not be verified and imported.")
    await KnowledgeService(actx.db).add_papers(
        actx.actor,
        actx.project_id,
        mission_id,
        AddMissionPapersRequest(
            paper_ids=[paper.id for paper in papers],
            inclusion_reason="Auto-included by evidence discovery with provider verification.",
        ),
    )
    return {
        "mission_id": str(mission_id),
        "imported_paper_ids": [str(paper.id) for paper in papers],
        "skipped_imports": [item.model_dump(mode="json") for item in skipped],
    }
