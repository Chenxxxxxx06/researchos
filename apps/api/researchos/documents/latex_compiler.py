"""Safe, bounded LaTeX compilation for the paper workspace."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from researchos.common.config import Settings

_LOG_DIAGNOSTIC = re.compile(
    r"^(?P<file>[^:\n]+\.tex):(?P<line>\d+):\s*(?P<message>.+)$", re.MULTILINE
)


@dataclass(frozen=True)
class LatexCompileResult:
    engine: str
    succeeded: bool
    log: str
    diagnostics: list[dict]
    pdf_path: str | None
    pdf_size: int | None
    duration_ms: int
    source_fingerprint: str


def source_fingerprint(files: dict[str, str], main_file_path: str) -> str:
    digest = hashlib.sha256()
    digest.update(main_file_path.encode("utf-8"))
    digest.update(b"\0")
    for path, content in sorted(files.items()):
        digest.update(path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(content.encode("utf-8")).digest())
    return digest.hexdigest()


def compile_latex_project(
    *,
    files: dict[str, str],
    main_file_path: str,
    project_id: str,
    job_id: str,
    settings: Settings,
) -> LatexCompileResult | None:
    """Compile with latexmk when installed; return ``None`` for mock fallback.

    The workspace is newly created, all paths are validated as relative POSIX
    paths, shell escape is disabled, the command is an argv list (never a
    shell), and both runtime and output size are bounded by the caller's
    settings. API/worker containers run this process as their unprivileged
    service user in production deployments.
    """

    engine_path = shutil.which(settings.latex_engine)
    if engine_path is None:
        return None
    fingerprint = source_fingerprint(files, main_file_path)
    started = time.monotonic()
    artifact_dir = Path(settings.artifact_root) / "latex" / project_id
    artifact_dir.mkdir(parents=True, exist_ok=True)
    final_pdf = artifact_dir / f"{job_id}.pdf"

    with tempfile.TemporaryDirectory(prefix="researchos-latex-") as temporary:
        workdir = Path(temporary)
        for raw_path, content in files.items():
            relative = _safe_relative_path(raw_path)
            target = workdir.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8", newline="\n")
        main_relative = _safe_relative_path(main_file_path)
        main_path = workdir.joinpath(*main_relative.parts)
        if not main_path.is_file():
            return LatexCompileResult(
                engine="latexmk",
                succeeded=False,
                log=f"Main file not found: {main_file_path}",
                diagnostics=[
                    {
                        "severity": "error",
                        "code": "main_file_missing",
                        "message": f"Main file not found: {main_file_path}",
                        "file": main_file_path,
                        "line": 1,
                    }
                ],
                pdf_path=None,
                pdf_size=None,
                duration_ms=_elapsed_ms(started),
                source_fingerprint=fingerprint,
            )
        output_dir = workdir / "build"
        output_dir.mkdir()
        command = [
            engine_path,
            "-pdf",
            "-interaction=nonstopmode",
            "-halt-on-error",
            "-file-line-error",
            "-no-shell-escape",
            f"-outdir={output_dir}",
            main_relative.as_posix(),
        ]
        environment = {
            **os.environ,
            "openin_any": "p",
            "openout_any": "p",
            "TEXMFOUTPUT": str(output_dir),
        }
        try:
            completed = subprocess.run(
                command,
                cwd=workdir,
                env=environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=settings.latex_compile_timeout_seconds,
                check=False,
            )
            log = (completed.stdout + "\n" + completed.stderr).strip()
            timed_out = False
        except subprocess.TimeoutExpired as exc:
            stdout = (
                exc.stdout.decode(errors="replace")
                if isinstance(exc.stdout, bytes)
                else exc.stdout
            )
            stderr = (
                exc.stderr.decode(errors="replace")
                if isinstance(exc.stderr, bytes)
                else exc.stderr
            )
            log = ((stdout or "") + "\n" + (stderr or "")).strip()
            timed_out = True
            completed = None
        log = log[-settings.latex_compile_log_max_chars :]
        diagnostics = _diagnostics(log, main_file_path, timed_out=timed_out)
        built_pdf = output_dir / f"{main_path.stem}.pdf"
        succeeded = bool(completed and completed.returncode == 0 and built_pdf.is_file())
        if succeeded:
            temporary_pdf = final_pdf.with_suffix(".pdf.tmp")
            shutil.copyfile(built_pdf, temporary_pdf)
            temporary_pdf.replace(final_pdf)
            pdf_size = final_pdf.stat().st_size
            pdf_path: str | None = str(final_pdf)
        else:
            final_pdf.unlink(missing_ok=True)
            pdf_size = None
            pdf_path = None
            if not diagnostics:
                diagnostics.append(
                    {
                        "severity": "error",
                        "code": "latex_compile_failed",
                        "message": (
                            "LaTeX compilation failed. Open diagnostics for the compiler log."
                        ),
                        "file": main_file_path,
                        "line": 1,
                    }
                )
        return LatexCompileResult(
            engine="latexmk",
            succeeded=succeeded,
            log=log,
            diagnostics=diagnostics,
            pdf_path=pdf_path,
            pdf_size=pdf_size,
            duration_ms=_elapsed_ms(started),
            source_fingerprint=fingerprint,
        )


def _safe_relative_path(path: str) -> PurePosixPath:
    relative = PurePosixPath(path)
    if not path or relative.is_absolute() or ".." in relative.parts or "" in relative.parts:
        raise ValueError(f"Unsafe LaTeX project path: {path!r}")
    return relative


def _diagnostics(log: str, main_file_path: str, *, timed_out: bool) -> list[dict]:
    if timed_out:
        return [
            {
                "severity": "error",
                "code": "latex_compile_timeout",
                "message": "LaTeX compilation exceeded the configured time limit.",
                "file": main_file_path,
                "line": 1,
            }
        ]
    items: list[dict] = []
    seen: set[tuple[str, int, str]] = set()
    for match in _LOG_DIAGNOSTIC.finditer(log):
        file_name = match.group("file").replace("\\", "/")
        line = int(match.group("line"))
        message = match.group("message").strip()
        key = (file_name, line, message)
        if key in seen:
            continue
        seen.add(key)
        severity = "warning" if "warning" in message.lower() else "error"
        items.append(
            {
                "severity": severity,
                "code": "latex_warning" if severity == "warning" else "latex_error",
                "message": message[:1000],
                "file": file_name,
                "line": max(1, line),
            }
        )
        if len(items) >= 100:
            break
    return items


def _elapsed_ms(started: float) -> int:
    return max(0, round((time.monotonic() - started) * 1000))
