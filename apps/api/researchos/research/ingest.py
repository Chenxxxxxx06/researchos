"""Paper full-text ingestion: ar5iv HTML -> typed ``paper_sections`` rows.

Entry points:
- ``ingest_paper``: worker/task path, opens its own session;
- ``ingest_paper_with_session``: API/background/test path with a caller session.

Idempotent (full section replace per run, safe under acks_late redelivery).
Publishes ``paper.ingest.*`` WS events; event failures never fail ingestion.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime

import httpx
import structlog
from selectolax.parser import HTMLParser, Node
from sqlalchemy.ext.asyncio import AsyncSession

from researchos.common.config import get_settings
from researchos.common.db import get_sessionmaker
from researchos.common.pubsub import publish_event
from researchos.knowledge.indexing import index_paper_sections
from researchos.websocket.envelopes import EventEnvelope

from .enums import PaperIngestStatus, PaperSectionKind
from .models import Paper, PaperSection
from .providers.federated import normalize_arxiv_id
from .providers.retry import fetch_with_retry
from .repository import PaperSectionRepository

logger = structlog.get_logger(__name__)

_FETCH_TIMEOUT_SECONDS = 20.0
# Leading section numbering ("1 ", "2.1 ", "IV. ", "A ") — requires trailing
# whitespace so words like "Introduction" are never clipped. The token is
# restricted to a dotted decimal, a Roman-numeral run, or a single capital
# letter; a full A-Z range would eat real first words like "BERT"/"GAN".
_NUMBERING_RE = re.compile(r"^\s*(?:\d+(?:\.\d+)*|[IVXLCDM]+|[A-Z])\.?\s+")

_KIND_RULES: tuple[tuple[tuple[str, ...], PaperSectionKind], ...] = (
    (("introduction",), PaperSectionKind.INTRODUCTION),
    (("background", "preliminar", "notation"), PaperSectionKind.BACKGROUND),
    (("method", "approach", "model", "architecture", "framework"), PaperSectionKind.METHOD),
    (("experiment", "evaluation", "setup", "implementation"), PaperSectionKind.EXPERIMENTS),
    (("result", "analysis", "ablation", "discussion"), PaperSectionKind.RESULTS),
    (("related",), PaperSectionKind.RELATED_WORK),
    (("conclusion", "future", "limitation"), PaperSectionKind.CONCLUSION),
)


def classify_kind(heading: str, *, appendix: bool = False) -> PaperSectionKind:
    if appendix:
        return PaperSectionKind.APPENDIX
    lowered = heading.lower()
    for keywords, kind in _KIND_RULES:
        if any(keyword in lowered for keyword in keywords):
            return kind
    return PaperSectionKind.OTHER


class ParsedSection:
    __slots__ = ("seq", "level", "heading", "body", "kind")

    def __init__(
        self, seq: int, level: int, heading: str, body: str, kind: PaperSectionKind
    ) -> None:
        self.seq = seq
        self.level = level
        self.heading = heading
        self.body = body
        self.kind = kind


def _clean_subtree(node: Node) -> None:
    """Replace math with alttext; drop figures, SVG, equations, bibliography."""

    for math_node in node.css("math"):
        alt = (math_node.attributes or {}).get("alttext")
        if alt:
            math_node.replace_with(alt)
        # Math without alttext keeps its (symbol) text content.
    for selector in ("figure", "svg", "table.ltx_equation", ".ltx_bibliography"):
        for child in node.css(selector):
            child.decompose()


def _node_body(node: Node, *, max_chars: int) -> str:
    text = node.text(separator="\n", strip=True)
    return text[:max_chars]


def _strip_numbering(heading: str) -> str:
    return _NUMBERING_RE.sub("", heading).strip()


def parse_ar5iv_html(html: str, *, max_chars: int) -> list[ParsedSection]:
    """Parse an ar5iv/arXiv-HTML document into ordered typed sections.

    Abstract (when present) is ``seq=0, level=1``; top-level sections and
    appendices are ``seq=1..N, level=2`` with subsections flattened into the
    parent body.
    """

    tree = HTMLParser(html)
    sections: list[ParsedSection] = []
    seq = 0

    abstract_node = tree.css_first(".ltx_abstract")
    if abstract_node is not None:
        for title in abstract_node.css(".ltx_title"):
            title.decompose()
        _clean_subtree(abstract_node)
        body = _node_body(abstract_node, max_chars=max_chars)
        if body:
            sections.append(ParsedSection(0, 1, "Abstract", body, PaperSectionKind.ABSTRACT))
            seq = 1

    if not sections:
        seq = 1

    for node in tree.css("section.ltx_section, section.ltx_appendix"):
        classes = (node.attributes or {}).get("class") or ""
        is_appendix = "ltx_appendix" in classes.split()
        heading = ""
        title_node = node.css_first(".ltx_title")
        if title_node is not None:
            # ar5iv wraps section numbering in .ltx_tag spans; drop them first
            # (text(strip=True) would otherwise fuse "1" onto "Introduction").
            for tag in title_node.css(".ltx_tag"):
                tag.decompose()
            heading = _strip_numbering(" ".join(title_node.text(strip=True).split()))
            # Remove the section's own title; subsection titles stay inline.
            title_node.decompose()
        _clean_subtree(node)
        body = _node_body(node, max_chars=max_chars)
        if not body and not heading:
            continue
        sections.append(
            ParsedSection(seq, 2, heading[:500], body, classify_kind(heading, appendix=is_appendix))
        )
        seq += 1

    return sections


# --- WS events ---------------------------------------------------------------
async def _publish_ingest_event(
    project_id: uuid.UUID, paper_id: uuid.UUID, event_type: str, payload: dict
) -> None:
    try:
        envelope = EventEnvelope(
            event_type=event_type,
            project_id=str(project_id),
            resource_type="paper",
            resource_id=str(paper_id),
            timestamp=datetime.now(tz=UTC).isoformat(),
            payload=payload,
        ).model_dump()
        await publish_event(str(project_id), envelope)
    except Exception as exc:  # noqa: BLE001 - events must never fail ingestion
        logger.warning("paper_ingest_event_publish_failed", paper_id=str(paper_id), error=str(exc))


# --- Fetch chain -------------------------------------------------------------
async def _get_html(client: httpx.AsyncClient, url: str) -> tuple[str | None, str | None]:
    try:
        resp = await fetch_with_retry(
            lambda: client.get(url, follow_redirects=True),
            attempts=get_settings().provider_retry_attempts,
        )
    except httpx.HTTPError as exc:
        return None, str(exc)
    if resp.status_code != 200:
        return None, f"HTTP {resp.status_code} from {url}"
    return resp.text, None


async def _fetch_paper_html(
    arxiv_id: str, http_client: httpx.AsyncClient | None
) -> tuple[str | None, str | None]:
    """ar5iv first, arXiv native HTML second. Returns (html, error)."""

    settings = get_settings()
    urls = [
        f"{settings.ar5iv_base_url.rstrip('/')}/{arxiv_id}",
        f"{settings.arxiv_html_base_url.rstrip('/')}/{arxiv_id}",
    ]
    errors: list[str] = []

    async def _try_all(client: httpx.AsyncClient) -> str | None:
        for url in urls:
            html, error = await _get_html(client, url)
            if html is not None:
                return html
            errors.append(error or "unknown error")
        return None

    if http_client is not None:
        html = await _try_all(http_client)
    else:
        async with httpx.AsyncClient(
            timeout=_FETCH_TIMEOUT_SECONDS,
            headers={"User-Agent": "ResearchOS/0.2 (+research-copilot)"},
        ) as client:
            html = await _try_all(client)
    return html, ("; ".join(errors) if errors else None)


# --- Ingestion entry points --------------------------------------------------
async def ingest_paper(
    paper_id: uuid.UUID, *, http_client: httpx.AsyncClient | None = None
) -> PaperIngestStatus:
    async with get_sessionmaker()() as db:
        return await ingest_paper_with_session(db, paper_id, http_client=http_client)


async def ingest_paper_with_session(
    db: AsyncSession,
    paper_id: uuid.UUID,
    *,
    http_client: httpx.AsyncClient | None = None,
) -> PaperIngestStatus:
    paper = await db.get(Paper, paper_id)
    if paper is None:
        logger.warning("ingest_paper_missing", paper_id=str(paper_id))
        return PaperIngestStatus.FAILED

    sections_repo = PaperSectionRepository(db)
    paper.ingest_status = PaperIngestStatus.RUNNING
    paper.ingest_error = None
    await db.commit()
    await _publish_ingest_event(
        paper.project_id, paper.id, "paper.ingest.started", {"paper_id": str(paper.id)}
    )

    async def _finish(
        status: PaperIngestStatus, *, section_count: int = 0, error: str | None = None
    ) -> PaperIngestStatus:
        paper.ingest_status = status
        paper.ingest_error = error[:500] if error else None
        if status in (PaperIngestStatus.SUCCEEDED, PaperIngestStatus.ABSTRACT_ONLY):
            paper.ingested_at = datetime.now(tz=UTC)
        await db.commit()
        if status is PaperIngestStatus.FAILED:
            await _publish_ingest_event(
                paper.project_id,
                paper.id,
                "paper.ingest.failed",
                {"paper_id": str(paper.id), "error": (error or "ingestion failed")[:500]},
            )
        else:
            await _publish_ingest_event(
                paper.project_id,
                paper.id,
                "paper.ingest.completed",
                {
                    "paper_id": str(paper.id),
                    "status": status.value,
                    "section_count": section_count,
                },
            )
        return status

    async def _abstract_fallback(error: str | None) -> PaperIngestStatus:
        if paper.abstract:
            body = paper.abstract[: get_settings().paper_section_max_chars]
            await sections_repo.replace_for_paper(
                paper.id,
                [
                    PaperSection(
                        paper_id=paper.id,
                        seq=0,
                        level=1,
                        heading="Abstract",
                        body=body,
                        char_count=len(body),
                        kind=PaperSectionKind.ABSTRACT,
                    )
                ],
            )
            await index_paper_sections(db, paper)
            return await _finish(PaperIngestStatus.ABSTRACT_ONLY, section_count=1)
        return await _finish(
            PaperIngestStatus.FAILED,
            error=error or "No full text source and no abstract available.",
        )

    arxiv_id = paper.arxiv_id
    if not arxiv_id and paper.source == "arxiv":
        arxiv_id = paper.external_id
    if not arxiv_id:
        raw = (paper.metadata_json or {}).get("arxiv_id")
        arxiv_id = raw if isinstance(raw, str) and raw else None
    if arxiv_id:
        arxiv_id = normalize_arxiv_id(arxiv_id)

    if not arxiv_id:
        return await _abstract_fallback(None)

    html, fetch_error = await _fetch_paper_html(arxiv_id, http_client)
    if html is None:
        return await _abstract_fallback(fetch_error)

    parsed = parse_ar5iv_html(html, max_chars=get_settings().paper_section_max_chars)
    if not parsed:
        return await _abstract_fallback("No sections parsed from fetched HTML.")

    rows = [
        PaperSection(
            paper_id=paper.id,
            seq=section.seq,
            level=section.level,
            heading=section.heading,
            body=section.body,
            char_count=len(section.body),
            kind=section.kind,
        )
        for section in parsed
    ]
    await sections_repo.replace_for_paper(paper.id, rows)
    await index_paper_sections(db, paper)
    return await _finish(PaperIngestStatus.SUCCEEDED, section_count=len(rows))
