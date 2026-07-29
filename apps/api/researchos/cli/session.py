"""Local append-only CLI sessions and mission receipts."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


class SessionStore:
    def __init__(self, root: Path) -> None:
        self.directory = root / ".researchos" / "sessions"

    def new_id(self) -> str:
        return datetime.now(UTC).strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]

    def append(self, session_id: str, role: str, content: str, **extra: Any) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        event = {"timestamp": now_iso(), "role": role, "content": content, **extra}
        with (self.directory / f"{session_id}.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, ensure_ascii=False) + "\n")

    def recent(self, session_id: str, *, limit: int = 12) -> list[dict[str, Any]]:
        path = self.directory / f"{session_id}.jsonl"
        if not path.exists():
            return []
        events: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        last_compaction = next(
            (
                index
                for index in range(len(events) - 1, -1, -1)
                if events[index]["role"] == "compact"
            ),
            0,
        )
        return events[last_compaction:][-limit:]

    def compact(self, session_id: str, summary: str) -> None:
        self.append(session_id, "compact", summary)


class MissionStore:
    def __init__(self, root: Path) -> None:
        self.directory = root / ".researchos" / "missions"

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        mission = {
            "id": str(uuid.uuid4()),
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "status": "dispatched",
            "gates": {},
            **payload,
        }
        self.save(mission)
        return mission

    def load(self, mission_id: str) -> dict[str, Any]:
        path = self.directory / f"{mission_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Mission {mission_id} was not found in this workspace.")
        return json.loads(path.read_text(encoding="utf-8"))

    def save(self, mission: dict[str, Any]) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        mission["updated_at"] = now_iso()
        path = self.directory / f"{mission['id']}.json"
        path.write_text(json.dumps(mission, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
