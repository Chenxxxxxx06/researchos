"""Append-only, provenance-aware research memory."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

MemoryKind = Literal["decision", "claim", "experiment", "preference", "failure", "handoff"]
MemoryStatus = Literal["candidate", "verified", "rejected", "superseded"]


@dataclass(slots=True)
class MemoryRecord:
    id: str
    kind: MemoryKind
    content: str
    source: str
    status: MemoryStatus
    confidence: float
    scope: str
    tags: list[str]
    created_at: str
    supersedes: str | None = None


class MemoryStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.path = root / ".researchos" / "memory.jsonl"

    def add(
        self,
        *,
        kind: MemoryKind,
        content: str,
        source: str,
        status: MemoryStatus = "candidate",
        confidence: float = 0.5,
        scope: str = "project",
        tags: list[str] | None = None,
        supersedes: str | None = None,
    ) -> MemoryRecord:
        record = MemoryRecord(
            id=str(uuid.uuid4()),
            kind=kind,
            content=content.strip(),
            source=source.strip(),
            status=status,
            confidence=max(0.0, min(1.0, confidence)),
            scope=scope,
            tags=tags or [],
            created_at=datetime.now(UTC).isoformat(),
            supersedes=supersedes,
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
        return record

    def list_records(
        self,
        *,
        kind: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[MemoryRecord]:
        if not self.path.exists():
            return []
        records: list[MemoryRecord] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                payload = json.loads(line)
                record = MemoryRecord(**payload)
            except (json.JSONDecodeError, TypeError):
                continue
            if kind and record.kind != kind:
                continue
            if status and record.status != status:
                continue
            records.append(record)
        return records[-limit:]

    def context_records(self, *, limit: int = 24) -> list[MemoryRecord]:
        records = [
            record
            for record in self.list_records(limit=500)
            if record.status in {"verified", "candidate"}
        ]
        records.sort(
            key=lambda item: (
                item.status == "verified",
                item.confidence,
                item.created_at,
            ),
            reverse=True,
        )
        return records[:limit]
