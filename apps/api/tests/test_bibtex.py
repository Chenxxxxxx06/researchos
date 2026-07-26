"""Pure unit tests for BibTeX key generation and entry rendering."""

from __future__ import annotations

from datetime import UTC, datetime

from researchos.documents.bibtex import (
    bib_key_for,
    bibtex_entry,
    parse_bib_keys,
    resolve_cite_key,
)
from researchos.research.models import Paper


def _paper(**overrides) -> Paper:
    defaults = dict(
        source="arxiv",
        external_id="1706.03762",
        title="Attention Is All You Need",
        authors_json=["Ashish Vaswani", "Noam Shazeer"],
        published_at=datetime(2017, 6, 12, tzinfo=UTC),
        url="https://arxiv.org/abs/1706.03762",
        venue=None,
    )
    defaults.update(overrides)
    return Paper(**defaults)


# --- key generation -----------------------------------------------------------
def test_bib_key_basic() -> None:
    assert bib_key_for(_paper()) == "vaswani2017attention"


def test_bib_key_unicode_fold_and_no_year() -> None:
    paper = _paper(
        title="The Über Study of Things",
        authors_json=["José Ñuñez"],
        published_at=None,
    )
    # NFKD fold: Ñuñez -> nunez; no year -> "nd"; "The" is a stopword, "Über"
    # folds to the 4-char title word "uber".
    assert bib_key_for(paper) == "nuneznduber"


def test_bib_key_stopword_title_word_skipped() -> None:
    paper = _paper(
        title="The Understanding of Systems",
        authors_json=["Ada Lovelace"],
        published_at=datetime(1843, 1, 1, tzinfo=UTC),
    )
    assert bib_key_for(paper) == "lovelace1843understanding"


def test_bib_key_anon_fallback_and_short_title() -> None:
    paper = _paper(authors_json=[], title="On AI", published_at=None)
    # No author -> anon; no word >= 4 chars -> first word fallback.
    assert bib_key_for(paper) == "anonndon"


# --- entry rendering (deterministic string equality) --------------------------
def test_arxiv_entry_exact() -> None:
    entry = bibtex_entry(_paper(), "vaswani2017attention")
    assert entry == (
        "@misc{vaswani2017attention,\n"
        "  title = {{Attention Is All You Need}},\n"
        "  author = {Ashish Vaswani and Noam Shazeer},\n"
        "  year = {2017},\n"
        "  eprint = {1706.03762},\n"
        "  archivePrefix = {arXiv},\n"
        "  url = {https://arxiv.org/abs/1706.03762}\n"
        "}\n"
    )


def test_venue_entry_exact() -> None:
    paper = _paper(
        source="openalex",
        external_id="W123",
        title="A Venue Paper",
        authors_json=["Grace Hopper"],
        published_at=datetime(1952, 5, 2, tzinfo=UTC),
        url="https://example.org/w123",
        venue="Communications of the ACM",
    )
    entry = bibtex_entry(paper, "hopper1952venue")
    assert entry == (
        "@article{hopper1952venue,\n"
        "  title = {{A Venue Paper}},\n"
        "  author = {Grace Hopper},\n"
        "  year = {1952},\n"
        "  journal = {Communications of the ACM},\n"
        "  url = {https://example.org/w123}\n"
        "}\n"
    )


def test_entry_escapes_braces_in_fields() -> None:
    paper = _paper(title="Braces {inside} title", authors_json=["A B"])
    entry = bibtex_entry(paper, "b2017braces")
    assert "Braces \\{inside\\} title" in entry


# --- key parsing --------------------------------------------------------------
def test_parse_bib_keys() -> None:
    content = "@misc{a2020x,\n  title = {T}\n}\n@article{b2021y, title={U}}\nnot an entry\n"
    assert parse_bib_keys(content) == {"a2020x", "b2021y"}


def test_parse_bib_keys_empty() -> None:
    assert parse_bib_keys("") == set()


# --- collision handling -------------------------------------------------------
def test_collision_with_different_paper_suffixes() -> None:
    other = (
        "@misc{vaswani2017attention,\n"
        "  title = {{A Different Paper}},\n"
        "  url = {https://other.example/xyz}\n"
        "}\n"
    )
    key, present = resolve_cite_key(_paper(), other)
    assert key == "vaswani2017attentiona"
    assert present is False


def test_same_paper_reuses_existing_key() -> None:
    existing = bibtex_entry(_paper(), "vaswani2017attention")
    key, present = resolve_cite_key(_paper(), existing)
    assert key == "vaswani2017attention"
    assert present is True


def test_fresh_key_when_bib_empty() -> None:
    key, present = resolve_cite_key(_paper(), "")
    assert key == "vaswani2017attention"
    assert present is False
