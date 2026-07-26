"""Pure unit tests for the structural LaTeX pass (documents/latex_parse.py)."""

from __future__ import annotations

from researchos.documents.latex_parse import (
    flatten,
    parse_document,
    render_plain_preview,
    strip_inline_commands,
)
from researchos.documents.service import _DEFAULT_MAIN


def _codes(diagnostics: list[dict]) -> list[str]:
    return [d["code"] for d in diagnostics]


# --- default template stays clean (seed/smoke flows must keep SUCCEEDED) ------
def test_default_template_has_no_diagnostics() -> None:
    model, diagnostics = parse_document({"main.tex": _DEFAULT_MAIN}, "main.tex")
    assert diagnostics == []
    assert model["title"] == "Untitled Paper"
    assert [s["title"] for s in model["sections"]] == ["Introduction", "Method", "Results"]
    assert [s["number"] for s in model["sections"]] == ["1", "2", "3"]
    assert model["word_count"] > 0


# --- flatten ------------------------------------------------------------------
def test_flatten_resolves_input_and_flags_missing_target() -> None:
    files = {
        "main.tex": (
            "\\documentclass{article}\n\\begin{document}\n"
            "\\input{intro}\n\\input{missing}\n\\end{document}\n"
        ),
        "intro.tex": "Hello from intro.\n",
    }
    lines, diagnostics = flatten(files, "main.tex")
    assert any("Hello from intro." in ln.text and ln.file == "intro.tex" for ln in lines)
    missing = [d for d in diagnostics if d["code"] == "missing_input"]
    assert len(missing) == 1
    assert missing[0]["severity"] == "warning"
    assert "missing.tex" in missing[0]["message"]


def test_flatten_detects_input_cycle() -> None:
    files = {
        "main.tex": "\\begin{document}\n\\input{intro}\n\\end{document}\n",
        "intro.tex": "Loop below.\n\\input{main}\n",
    }
    _, diagnostics = flatten(files, "main.tex")
    cycle = [d for d in diagnostics if d["code"] == "input_cycle"]
    assert len(cycle) == 1
    assert cycle[0]["severity"] == "error"
    assert cycle[0]["file"] == "intro.tex"


def test_flatten_missing_main_file() -> None:
    lines, diagnostics = flatten({}, "main.tex")
    assert lines == []
    assert _codes(diagnostics) == ["empty_document"]


# --- environment stack --------------------------------------------------------
def test_unclosed_environment_and_missing_end_document() -> None:
    doc = "\\documentclass{article}\n\\begin{document}\nText\n\\begin{figure}\n"
    _, diagnostics = parse_document({"main.tex": doc}, "main.tex")
    codes = set(_codes(diagnostics))
    assert {"unclosed_environment", "missing_end_document"} <= codes
    assert all(d["severity"] == "error" for d in diagnostics)


def test_mismatched_environment() -> None:
    doc = (
        "\\documentclass{article}\n\\begin{document}\n"
        "\\begin{itemize}\n\\item x\n\\end{document}\n"
    )
    _, diagnostics = parse_document({"main.tex": doc}, "main.tex")
    assert "mismatched_environment" in _codes(diagnostics)


def test_unexpected_end_without_begin() -> None:
    doc = "\\documentclass{article}\n\\begin{document}\n\\end{itemize}\n\\end{document}\n"
    _, diagnostics = parse_document({"main.tex": doc}, "main.tex")
    assert "unexpected_end" in _codes(diagnostics)


# --- reference / citation / label checks --------------------------------------
def test_undefined_ref_cite_and_duplicate_label() -> None:
    doc = (
        "\\documentclass{article}\n\\begin{document}\n"
        "\\section{A}\\label{sec:a}\n"
        "See \\ref{sec:missing} and \\cite{nope2020}.\n"
        "\\label{sec:a}\n"
        "\\end{document}\n"
    )
    _, diagnostics = parse_document({"main.tex": doc}, "main.tex")
    codes = _codes(diagnostics)
    assert "undefined_reference" in codes
    assert "undefined_citation" in codes
    assert "duplicate_label" in codes
    # All reference-level findings are warnings: the document still compiles.
    assert all(d["severity"] == "warning" for d in diagnostics)


def test_cite_resolved_by_project_bib() -> None:
    files = {
        "main.tex": (
            "\\documentclass{article}\n\\begin{document}\n"
            "Hi \\cite{good2021}.\n\\end{document}\n"
        ),
        "refs.bib": "@article{good2021,\n  title = {T}\n}\n",
    }
    model, diagnostics = parse_document(files, "main.tex")
    assert "undefined_citation" not in _codes(diagnostics)
    assert model["bib_keys"] == ["good2021"]


def test_missing_documentclass_is_warning_only() -> None:
    doc = "\\section{Intro}\nHello world.\n"
    model, diagnostics = parse_document({"main.tex": doc}, "main.tex")
    assert _codes(diagnostics) == ["missing_documentclass"]
    assert diagnostics[0]["severity"] == "warning"
    assert model["sections"][0]["title"] == "Intro"


def test_empty_document_warning() -> None:
    _, diagnostics = parse_document({"main.tex": "   \n"}, "main.tex")
    assert _codes(diagnostics) == ["empty_document"]


# --- text extraction (nested braces, math verbatim) ---------------------------
def test_strip_inline_commands_handles_nesting() -> None:
    assert strip_inline_commands("\\textbf{bold \\emph{both}} rest") == "bold both rest"


def test_nested_braces_survive_block_extraction() -> None:
    doc = (
        "\\documentclass{article}\n\\begin{document}\n"
        "\\section{M}\n"
        "\\begin{equation}\n\\frac{a}{b}\n\\end{equation}\n"
        "Para with \\textbf{deep {nested} braces} here.\n"
        "\\end{document}\n"
    )
    model, diagnostics = parse_document({"main.tex": doc}, "main.tex")
    assert diagnostics == []
    blocks = model["sections"][0]["blocks"]
    math = [b for b in blocks if b["kind"] == "math"]
    assert len(math) == 1
    # Math is kept verbatim: \frac{a}{b} must NOT be corrupted to "a{b}".
    assert "\\frac{a}{b}" in math[0]["text"]
    paras = [b for b in blocks if b["kind"] == "paragraph"]
    assert len(paras) == 1
    assert "deep {nested} braces" in paras[0]["text"]


def test_display_math_brackets() -> None:
    doc = "\\documentclass{article}\n\\begin{document}\n\\[\nx=1\n\\]\nAfter.\n\\end{document}\n"
    model, diagnostics = parse_document({"main.tex": doc}, "main.tex")
    assert diagnostics == []
    blocks = model["sections"][0]["blocks"]
    assert any(b["kind"] == "math" and "x=1" in b["text"] for b in blocks)
    assert any(b["kind"] == "paragraph" and "After." in b["text"] for b in blocks)


# --- preview model shape ------------------------------------------------------
def test_preview_model_section_tree() -> None:
    doc = (
        "\\documentclass{article}\n\\title{Tree}\n\\begin{document}\n"
        "\\section{One}\nA.\n"
        "\\subsection{OneOne}\nB.\n"
        "\\section{Two}\nC.\n"
        "\\end{document}\n"
    )
    model, diagnostics = parse_document({"main.tex": doc}, "main.tex")
    assert diagnostics == []
    assert model["title"] == "Tree"
    assert [(s["level"], s["number"], s["title"]) for s in model["sections"]] == [
        (1, "1", "One"),
        (2, "1.1", "OneOne"),
        (1, "2", "Two"),
    ]
    for section in model["sections"]:
        assert {"file", "line", "blocks"} <= set(section)


def test_render_plain_preview_contains_headings_and_text() -> None:
    model, _ = parse_document({"main.tex": _DEFAULT_MAIN}, "main.tex")
    preview = render_plain_preview(model)
    assert "Untitled Paper" in preview
    assert "1 Introduction" in preview
    assert "Write your introduction here." in preview
