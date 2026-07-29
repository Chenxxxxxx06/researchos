"""Local CLI configuration with no project secrets."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

DEFAULT_API_URL = "http://localhost:8000"


def cli_home() -> Path:
    override = os.environ.get("RESEARCHOS_HOME")
    if override:
        return Path(override).expanduser().resolve()
    return Path.home() / ".researchos"


@dataclass(slots=True)
class CLIConfig:
    api_url: str = DEFAULT_API_URL
    project_id: str | None = None

    @classmethod
    def load(cls) -> CLIConfig:
        path = cli_home() / "config.json"
        if not path.exists():
            return cls()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return cls()
        return cls(
            api_url=str(payload.get("api_url", DEFAULT_API_URL)).rstrip("/"),
            project_id=payload.get("project_id"),
        )

    def save(self) -> None:
        home = cli_home()
        home.mkdir(parents=True, exist_ok=True)
        path = home / "config.json"
        path.write_text(json.dumps(asdict(self), indent=2) + "\n", encoding="utf-8")
        _private_file(path)


def _private_file(path: Path) -> None:
    try:
        path.chmod(0o600)
    except OSError:
        pass
