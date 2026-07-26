"""Pure-Python structural LaTeX analysis: flatten, preview model, diagnostics.

There is NO shell and NO subprocess (PHASE3/5 retained): this is a text-level
pass that powers the mock compile. The preview-model/diagnostics contract is
designed so a real engine can later populate the same fields.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_COMMENT_RE = re.compile(r"(?<!\\)%.*")
_INPUT_RE = re.compile(r"\\(?:input|include)\{([^}]+)\}")
_BEGIN_RE = re.compile(r"\\begin\{([A-Za-z]+\*?)\}")
_END_RE = re.compile(r"\\end\{([A-Za-z]+\*?)\}")
_SECTION_RE = re.compile(r"\\(section|subsection|subsubsection)(\*?)\s*\{")
_TITLE_RE = re.compile(r"\\title\s*\{")
_LABEL_RE = re.compile(r"\\label\{([^}]*)\}")
_REF_RE = re.compile(r"\\(?:ref|eqref|autoref)\{([^}]*)\}")
_CITE_RE = re.compile(r"\\cite[pt]?\*?(?:\[[^\]]*\])?\{([^}]*)\}")
_DOCUMENTCLASS_RE = re.compile(r"\\documentclass")
# Structural one-liners that never contribute paragraph text.
_SKIP_LINE_RE = re.compile(
    r"^\s*\\(documentclass|usepackage|maketitle|author|date|title|bibliographystyle|"
    r"bibliography|addbibresource|newcommand|renewcommand|graphicspath|geometry|"
    r"setlength|pagestyle|thispagestyle|centering|noindent|label|vspace|hspace|"
    r"includegraphics|caption|tableofcontents|appendix)\b"
)
# Inline formatting commands reduced innermost-first (fixes nested-brace
# corruption of the old single regex; math like \frac{a}{b} stays verbatim).
_INLINE_CMD_RE = re.compile(r"\\(?:textbf|textit|texttt|textsc|emph|underline)\{([^{}]*)\}")

_MATH_ENVS = {
    "equation",
    "equation*",
    "align",
    "align*",
    "gather",
    "gather*",
    "multline",
    "multline*",
    "eqnarray",
    "eqnarray*",
    "displaymath",
    "math",
}
_FIGURE_ENVS = {"figure", "figure*"}
_TABLE_ENVS = {"table", "table*", "tabular"}
_LIST_ENVS = {"itemize", "enumerate", "description"}

_MAX_INPUT_DEPTH = 10
_SECTION_LEVELS = {"section": 1, "subsection": 2, "subsubsection": 3}


@dataclass(frozen=True)
class SourceLine:
    file: str
    line: int
    text: str


def _diag(severity: str, code: str, message: str, file: str, line: int) -> dict:
    return {"severity": severity, "code": code, "message": message, "file": file, "line": line}


def _read_brace_arg(text: str, open_idx: int) -> str:
    """Read a balanced ``{...}`` argument starting at ``open_idx`` ('{')."""

    depth = 0
    for i in range(open_idx, len(text)):
        char = text[i]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[open_idx + 1 : i]
    return text[open_idx + 1 :]


def strip_inline_commands(text: str) -> str:
    """Iteratively reduce inline formatting commands, innermost braces first."""

    prev = None
    while prev != text:
        prev = text
        text = _INLINE_CMD_RE.sub(lambda m: m.group(1), text)
    return text


def flatten(files: dict[str, str], main_path: str) -> tuple[list[SourceLine], list[dict]]:
    """Resolve ``\\input``/``\\include`` into a single line stream.

    Comments are stripped. Unknown targets produce ``missing_input`` warnings;
    cycles (or depth > 10) produce ``input_cycle`` errors.
    """

    out: list[SourceLine] = []
    diagnostics: list[dict] = []
    if main_path not in files:
        diagnostics.append(
            _diag("warning", "empty_document", f"Main file '{main_path}' not found.", main_path, 1)
        )
        return out, diagnostics

    def visit(path: str, stack: tuple[str, ...]) -> None:
        for lineno, raw in enumerate(files[path].split("\n"), start=1):
            text = _COMMENT_RE.sub("", raw)
            rest = text
            matched = False
            while True:
                m = _INPUT_RE.search(rest)
                if m is None:
                    break
                matched = True
                before = rest[: m.start()]
                if before.strip():
                    out.append(SourceLine(path, lineno, before))
                target = m.group(1).strip()
                if not target.endswith(".tex"):
                    target = f"{target}.tex"
                if target in stack:
                    diagnostics.append(
                        _diag(
                            "error", "input_cycle", f"\\input cycle via '{target}'.", path, lineno
                        )
                    )
                elif len(stack) >= _MAX_INPUT_DEPTH:
                    diagnostics.append(
                        _diag(
                            "error",
                            "input_cycle",
                            f"\\input nesting deeper than {_MAX_INPUT_DEPTH}.",
                            path,
                            lineno,
                        )
                    )
                elif target not in files:
                    diagnostics.append(
                        _diag(
                            "warning",
                            "missing_input",
                            f"\\input target '{target}' not found in project.",
                            path,
                            lineno,
                        )
                    )
                else:
                    visit(target, stack + (target,))
                rest = rest[m.end() :]
            if matched:
                if rest.strip():
                    out.append(SourceLine(path, lineno, rest))
            else:
                out.append(SourceLine(path, lineno, text))

    visit(main_path, (main_path,))
    return out, diagnostics


def _capture_kind(env: str) -> str | None:
    if env in _MATH_ENVS:
        return "math"
    if env in _FIGURE_ENVS:
        return "figure"
    if env in _TABLE_ENVS:
        return "table"
    if env in _LIST_ENVS:
        return "list"
    return None


def parse_document(files: dict[str, str], main_path: str) -> tuple[dict, list[dict]]:
    """Single structural pass. Returns ``(preview_model, diagnostics)``."""

    lines, diagnostics = flatten(files, main_path)

    from .bibtex import parse_bib_keys  # deferred: bibtex imports service at module level

    bib_keys: set[str] = set()
    for path, content in files.items():
        if path.endswith(".bib"):
            bib_keys |= parse_bib_keys(content)

    sections: list[dict] = []
    current: dict | None = None
    counters = [0, 0, 0]
    labels: dict[str, tuple[str, int]] = {}
    refs: list[tuple[str, str, int]] = []
    cites: list[tuple[str, str, int]] = []
    title = ""
    env_stack: list[tuple[str, str, int]] = []
    para: list[str] = []
    para_file, para_line = main_path, 1
    capture: dict | None = None
    has_documentclass = False
    has_content = False
    word_count = 0

    def ensure_section(file: str, line: int) -> dict:
        nonlocal current
        if current is None:
            current = {
                "level": 1,
                "number": "",
                "title": "",
                "file": file,
                "line": line,
                "blocks": [],
            }
            sections.append(current)
        return current

    def flush_para() -> None:
        nonlocal para, word_count
        if not para:
            return
        text = strip_inline_commands("\n".join(para)).strip()
        para = []
        if not text:
            return
        section = ensure_section(para_file, para_line)
        section["blocks"].append(
            {"kind": "paragraph", "text": text, "file": para_file, "line": para_line}
        )
        word_count += len(text.split())

    def close_capture() -> None:
        nonlocal capture
        assert capture is not None
        text = "\n".join(capture["lines"]).strip()
        section = ensure_section(capture["file"], capture["line"])
        section["blocks"].append(
            {
                "kind": capture["kind"],
                "text": text,
                "file": capture["file"],
                "line": capture["line"],
            }
        )
        capture = None

    for src in lines:
        text = src.text
        stripped = text.strip()
        if stripped:
            has_content = True
        if _DOCUMENTCLASS_RE.search(text):
            has_documentclass = True

        # Collectors run on every line (labels inside figures are real labels).
        for m in _LABEL_RE.finditer(text):
            key = m.group(1).strip()
            if not key:
                continue
            if key in labels:
                diagnostics.append(
                    _diag(
                        "warning",
                        "duplicate_label",
                        f"\\label{{{key}}} is already defined at "
                        f"{labels[key][0]}:{labels[key][1]}.",
                        src.file,
                        src.line,
                    )
                )
            else:
                labels[key] = (src.file, src.line)
        for m in _REF_RE.finditer(text):
            for key in m.group(1).split(","):
                if key.strip():
                    refs.append((key.strip(), src.file, src.line))
        for m in _CITE_RE.finditer(text):
            for key in m.group(1).split(","):
                if key.strip():
                    cites.append((key.strip(), src.file, src.line))

        # Environment bookkeeping (stack integrity even inside captures).
        env_capture_closed = False
        was_capturing = capture is not None and capture.get("env") is not None
        if capture is not None:
            capture["lines"].append(text)
        tokens = sorted(
            [(m.start(), "begin", m.group(1)) for m in _BEGIN_RE.finditer(text)]
            + [(m.start(), "end", m.group(1)) for m in _END_RE.finditer(text)]
        )
        for _, kind, env in tokens:
            if kind == "begin":
                env_stack.append((env, src.file, src.line))
                if capture is None and env != "document":
                    capture_kind = _capture_kind(env)
                    if capture_kind is not None:
                        flush_para()
                        capture = {
                            "kind": capture_kind,
                            "env": env,
                            "depth": len(env_stack),
                            "lines": [text],
                            "file": src.file,
                            "line": src.line,
                        }
            else:
                if not env_stack:
                    diagnostics.append(
                        _diag(
                            "error",
                            "unexpected_end",
                            f"\\end{{{env}}} without a matching \\begin.",
                            src.file,
                            src.line,
                        )
                    )
                    continue
                top_env, top_file, top_line = env_stack[-1]
                if top_env != env:
                    diagnostics.append(
                        _diag(
                            "error",
                            "mismatched_environment",
                            f"\\begin{{{top_env}}} at {top_file}:{top_line} closed by "
                            f"\\end{{{env}}}.",
                            src.file,
                            src.line,
                        )
                    )
                env_stack.pop()
                if capture is not None and capture.get("env") is not None:
                    if len(env_stack) < capture["depth"]:
                        env_capture_closed = True
        if env_capture_closed:
            close_capture()
            continue
        if was_capturing or (capture is not None and capture.get("env") is not None):
            continue

        # Display math delimited by \[ \] or $$ pairs.
        if capture is not None and capture.get("env") is None:
            if "\\]" in text or "$$" in text:
                close_capture()
            continue
        if "\\[" in text or "$$" in text:
            flush_para()
            if "\\[" in text:
                closes_inline = "\\]" in text
            else:
                closes_inline = text.count("$$") % 2 == 0
            capture = {
                "kind": "math",
                "env": None,
                "depth": len(env_stack),
                "lines": [text],
                "file": src.file,
                "line": src.line,
            }
            if closes_inline:
                close_capture()
            continue

        # Structural commands.
        sm = _TITLE_RE.search(text)
        if sm is not None:
            title = strip_inline_commands(_read_brace_arg(text, sm.end() - 1)).strip()
            continue
        sm = _SECTION_RE.search(text)
        if sm is not None:
            flush_para()
            level = _SECTION_LEVELS[sm.group(1)]
            starred = sm.group(2) == "*"
            heading = strip_inline_commands(_read_brace_arg(text, sm.end() - 1)).strip()
            if starred:
                number = ""
            else:
                counters[level - 1] += 1
                for i in range(level, 3):
                    counters[i] = 0
                number = ".".join(str(counters[i]) for i in range(level))
            current = {
                "level": level,
                "number": number,
                "title": heading,
                "file": src.file,
                "line": src.line,
                "blocks": [],
            }
            sections.append(current)
            continue
        if tokens:
            # A pure \begin/\end line (e.g. \begin{document}) is structural.
            flush_para()
            continue
        if _SKIP_LINE_RE.match(text):
            continue
        if not stripped:
            flush_para()
            continue
        if not para:
            para_file, para_line = src.file, src.line
        para.append(text)

    flush_para()
    if capture is not None:
        close_capture()

    for env, file, line in env_stack:
        if env == "document":
            diagnostics.append(
                _diag(
                    "error",
                    "missing_end_document",
                    "\\begin{document} is never closed by \\end{document}.",
                    file,
                    line,
                )
            )
        else:
            diagnostics.append(
                _diag(
                    "error",
                    "unclosed_environment",
                    f"\\begin{{{env}}} is never closed.",
                    file,
                    line,
                )
            )

    for key, file, line in refs:
        if key not in labels:
            diagnostics.append(
                _diag(
                    "warning",
                    "undefined_reference",
                    f"\\ref{{{key}}} has no matching \\label.",
                    file,
                    line,
                )
            )
    for key, file, line in cites:
        if key not in bib_keys:
            diagnostics.append(
                _diag(
                    "warning",
                    "undefined_citation",
                    f"\\cite{{{key}}} has no entry in the project bibliography.",
                    file,
                    line,
                )
            )

    if main_path in files and not has_content:
        diagnostics.append(
            _diag("warning", "empty_document", "The document has no content.", main_path, 1)
        )
    elif has_content and not has_documentclass:
        diagnostics.append(
            _diag(
                "warning",
                "missing_documentclass",
                "No \\documentclass declaration found.",
                main_path,
                1,
            )
        )

    model = {
        "title": title,
        "sections": sections,
        "labels": sorted(labels),
        "bib_keys": sorted(bib_keys),
        "word_count": word_count,
    }
    return model, diagnostics


def render_plain_preview(model: dict) -> str:
    """Readable plain-text preview derived from the preview model."""

    out: list[str] = []
    if model.get("title"):
        out.append(f"# {model['title']}")
    for section in model.get("sections", []):
        if section.get("title"):
            prefix = "#" * max(1, min(3, int(section.get("level", 1))))
            number = f"{section['number']} " if section.get("number") else ""
            out.append(f"{prefix} {number}{section['title']}")
        for block in section.get("blocks", []):
            if block.get("text"):
                out.append(block["text"])
    return "\n\n".join(out).strip() or "(empty document)"
