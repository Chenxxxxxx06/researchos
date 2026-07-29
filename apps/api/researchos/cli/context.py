"""Deterministic research context packing with explicit budgets."""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from .memory import MemoryStore
from .session import SessionStore


@dataclass(slots=True)
class ContextSection:
    name: str
    priority: int
    content: str
    source: str
    included_chars: int
    truncated: bool


@dataclass(slots=True)
class ContextPack:
    version: str
    budget_chars: int
    used_chars: int
    sections: list[ContextSection]

    def render(self) -> str:
        blocks = ["<researchos_context version=\"1\">"]
        for section in self.sections:
            blocks.append(
                f'<section name="{section.name}" source="{section.source}" '
                f'truncated="{str(section.truncated).lower()}">\n{section.content}\n</section>'
            )
        blocks.append("</researchos_context>")
        return "\n\n".join(blocks)

    def to_json(self) -> dict:
        return {
            "version": self.version,
            "budget_chars": self.budget_chars,
            "used_chars": self.used_chars,
            "sections": [asdict(section) for section in self.sections],
        }


class ContextBuilder:
    def __init__(self, root: Path, *, budget_chars: int = 7000) -> None:
        self.root = root.resolve()
        self.budget_chars = budget_chars

    def build(self, *, session_id: str | None = None) -> ContextPack:
        candidates: list[tuple[int, str, str, str]] = []
        for name, filename, priority, cap in (
            ("project-policy", "RESEARCHOS.md", 100, 2600),
            ("agent-policy", "AGENTS.md", 95, 1800),
        ):
            path = self.root / filename
            if path.exists():
                candidates.append(
                    (priority, name, filename, path.read_text(encoding="utf-8")[:cap])
                )

        memory = MemoryStore(self.root).context_records()
        if memory:
            content = "\n".join(
                f"- [{item.status}/{item.kind}/{item.confidence:.2f}] "
                f"{item.content} (source: {item.source}; id: {item.id})"
                for item in memory
            )
            candidates.append((90, "research-memory", ".researchos/memory.jsonl", content))

        git_context = self._git_context()
        if git_context:
            candidates.append((70, "workspace-state", "git", git_context))

        if session_id:
            events = SessionStore(self.root).recent(session_id)
            if events:
                content = "\n".join(
                    f"{event.get('role', 'unknown')}: {str(event.get('content', ''))[:500]}"
                    for event in events
                )
                candidates.append((60, "recent-session", session_id, content))

        sections: list[ContextSection] = []
        remaining = self.budget_chars
        for priority, name, source, content in sorted(candidates, reverse=True):
            if remaining <= 0:
                break
            included = content[:remaining]
            sections.append(
                ContextSection(
                    name=name,
                    priority=priority,
                    content=included,
                    source=source,
                    included_chars=len(included),
                    truncated=len(included) < len(content),
                )
            )
            remaining -= len(included)
        return ContextPack(
            version="researchos.context/v1",
            budget_chars=self.budget_chars,
            used_chars=self.budget_chars - remaining,
            sections=sections,
        )

    def _git_context(self) -> str:
        try:
            result = subprocess.run(
                ["git", "status", "--short", "--branch"],
                cwd=self.root,
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return ""
        return result.stdout.strip()[:2000]


def dump_context(pack: ContextPack) -> str:
    return json.dumps(pack.to_json(), ensure_ascii=False, indent=2)
