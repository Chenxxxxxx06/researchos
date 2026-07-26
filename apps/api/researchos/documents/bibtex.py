"""BibTeX generation and citation insertion for library papers.

Key generation and entry rendering are deterministic pure functions (unit-
testable by string equality). ``CitationService`` wires them to the project
library and the versioned document write path.
"""

from __future__ import annotations

import re
import unicodedata
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from researchos.common.errors import NotFoundError
from researchos.common.roles import ProjectRole
from researchos.identity.models import User
from researchos.research.models import Paper
from researchos.research.repository import PaperRepository

from .service import DocumentService

_BIB_KEY_RE = re.compile(r"@\w+\s*\{\s*([^,\s{}]+)")
_ENTRY_START_TMPL = r"@\w+\s*\{\s*%s\s*,"

# Small stopword set for the title word of a citation key.
_STOPWORDS = {
    "the",
    "with",
    "from",
    "that",
    "this",
    "into",
    "over",
    "under",
    "about",
    "using",
    "toward",
    "towards",
    "their",
    "these",
    "those",
    "what",
    "when",
    "where",
    "which",
}


def parse_bib_keys(content: str) -> set[str]:
    """Extract entry keys from BibTeX source (regex-level, tolerant)."""

    return set(_BIB_KEY_RE.findall(content))


def _ascii_fold(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def _alnum(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", _ascii_fold(text).lower())


def bib_key_for(paper: Paper) -> str:
    """Deterministic citation key, e.g. ``vaswani2017attention``."""

    authors = paper.authors_json or []
    last = "anon"
    if authors:
        tokens = str(authors[0]).split()
        if tokens:
            last = _alnum(tokens[-1]) or "anon"
    year = str(paper.published_at.year) if paper.published_at else "nd"
    words = [w for w in (_alnum(word) for word in str(paper.title or "").split()) if w]
    title_word = ""
    for word in words:
        if len(word) >= 4 and word not in _STOPWORDS:
            title_word = word
            break
    if not title_word and words:
        title_word = words[0]
    return f"{last}{year}{title_word}"


def _escape_braces(value: str) -> str:
    return value.replace("{", r"\{").replace("}", r"\}")


def bibtex_entry(paper: Paper, key: str) -> str:
    """Render a BibTeX entry with a deterministic field order."""

    authors = " and ".join(str(a) for a in (paper.authors_json or []))
    fields: list[tuple[str, str]] = [("title", "{" + _escape_braces(str(paper.title)) + "}")]
    if authors:
        fields.append(("author", _escape_braces(authors)))
    if paper.published_at is not None:
        fields.append(("year", str(paper.published_at.year)))
    if paper.source == "arxiv":
        entry_type = "misc"
        fields.append(("eprint", _escape_braces(paper.external_id)))
        fields.append(("archivePrefix", "arXiv"))
    else:
        entry_type = "article"
        if paper.venue:
            fields.append(("journal", _escape_braces(paper.venue)))
    fields.append(("url", _escape_braces(paper.url)))
    body = ",\n".join(f"  {name} = {{{value}}}" for name, value in fields)
    return f"@{entry_type}{{{key},\n{body}\n}}\n"


def _entry_text(content: str, key: str) -> str:
    """Return the full text of the entry with ``key`` ('' when absent)."""

    match = re.search(_ENTRY_START_TMPL % re.escape(key), content)
    if match is None:
        return ""
    open_idx = content.index("{", match.start())
    depth = 0
    for i in range(open_idx, len(content)):
        char = content[i]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return content[match.start() : i + 1]
    return content[match.start() :]


def _entry_matches(entry_text: str, paper: Paper) -> bool:
    if not entry_text:
        return False
    if paper.url and paper.url in entry_text:
        return True
    return bool(paper.external_id) and f"eprint = {{{paper.external_id}}}" in entry_text


def _key_suffixes() -> list[str]:
    return [""] + [chr(c) for c in range(ord("a"), ord("z") + 1)]


def resolve_cite_key(paper: Paper, bib_content: str) -> tuple[str, bool]:
    """Return ``(key, already_present)`` deduplicating against the bib file.

    A collision with a *different* paper's entry gets an ``a``, ``b``, ...
    suffix; a matching entry for the same paper reuses its key.
    """

    base = bib_key_for(paper)
    keys = parse_bib_keys(bib_content)
    for suffix in _key_suffixes():
        candidate = base + suffix
        if candidate not in keys:
            return candidate, False
        if _entry_matches(_entry_text(bib_content, candidate), paper):
            return candidate, True
    # Pathological collision count: fall back to a numbered key.
    return f"{base}{len(keys)}", False


class CitationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.documents = DocumentService(db)
        self.papers = PaperRepository(db)

    async def list_citations(
        self,
        actor: User,
        project_id: uuid.UUID,
        latex_project_id: uuid.UUID,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[dict], int]:
        await self.documents.require_latex_project(
            actor, project_id, latex_project_id, ProjectRole.VIEWER
        )
        papers, total = await self.papers.list_by_project(project_id, limit=limit, offset=offset)
        bib = await self.documents.files.get_by_path(latex_project_id, "refs.bib")
        bib_content = bib.content if bib else ""
        items: list[dict] = []
        for paper in papers:
            key, present = resolve_cite_key(paper, bib_content)
            items.append(
                {
                    "paper_id": paper.id,
                    "title": paper.title,
                    "authors": [str(a) for a in (paper.authors_json or [])],
                    "year": paper.published_at.year if paper.published_at else None,
                    "cite_key": key,
                    "in_bib": present,
                }
            )
        return items, total

    async def insert_citation(
        self,
        actor: User,
        project_id: uuid.UUID,
        latex_project_id: uuid.UUID,
        *,
        paper_id: uuid.UUID,
        bib_path: str = "refs.bib",
        expected_bib_version: int | None = None,
        expected_main_version: int | None = None,
    ) -> dict:
        lp = await self.documents.require_latex_project(
            actor, project_id, latex_project_id, ProjectRole.RESEARCHER
        )
        paper = await self.papers.get_by_id(project_id, paper_id)
        if paper is None:
            raise NotFoundError("Paper not found.")

        bib = await self.documents.files.get_by_path(latex_project_id, bib_path)
        bib_content = bib.content if bib else ""
        key, present = resolve_cite_key(paper, bib_content)

        entry_added = False
        if present:
            bib_file = bib
        else:
            new_bib = bib_content
            if new_bib and not new_bib.endswith("\n"):
                new_bib += "\n"
            new_bib += bibtex_entry(paper, key)
            bib_file = await self.documents.write_file_versioned(
                actor,
                latex_project_id,
                path=bib_path,
                content=new_bib,
                expected_version=expected_bib_version if bib is not None else None,
            )
            entry_added = True

        # Ensure the main file emits a bibliography (idempotent).
        bibliography_command_added = False
        main = await self.documents.files.get_by_path(latex_project_id, lp.main_file_path)
        if (
            main is not None
            and "\\bibliography{" not in main.content
            and "\\addbibresource{" not in main.content
        ):
            stem = bib_path[:-4] if bib_path.endswith(".bib") else bib_path
            block = f"\\bibliographystyle{{plain}}\n\\bibliography{{{stem}}}\n"
            if "\\end{document}" in main.content:
                new_main = main.content.replace("\\end{document}", block + "\\end{document}", 1)
            else:
                new_main = main.content
                if new_main and not new_main.endswith("\n"):
                    new_main += "\n"
                new_main += block
            await self.documents.write_file_versioned(
                actor,
                latex_project_id,
                path=lp.main_file_path,
                content=new_main,
                expected_version=expected_main_version,
            )
            bibliography_command_added = True

        await self.db.commit()
        assert bib_file is not None
        await self.db.refresh(bib_file)
        return {
            "cite_key": key,
            "snippet": f"\\cite{{{key}}}",
            "bib_file": {"path": bib_path, "version": bib_file.version},
            "entry_added": entry_added,
            "bibliography_command_added": bibliography_command_added,
        }
