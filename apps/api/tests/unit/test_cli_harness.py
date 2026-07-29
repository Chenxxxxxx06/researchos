"""Pure tests for the local ResearchOS CLI harness primitives."""

from __future__ import annotations

import json

from researchos.cli.config import CLIConfig
from researchos.cli.context import ContextBuilder
from researchos.cli.main import find_project_root, main
from researchos.cli.memory import MemoryStore
from researchos.cli.session import SessionStore


def test_cli_config_round_trip(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("RESEARCHOS_HOME", str(tmp_path / "home"))
    config = CLIConfig(api_url="http://example.test", project_id="project-1")
    config.save()
    assert CLIConfig.load() == config


def test_memory_and_context_keep_provenance(tmp_path) -> None:
    (tmp_path / "RESEARCHOS.md").write_text("Never fabricate results.", encoding="utf-8")
    record = MemoryStore(tmp_path).add(
        kind="claim",
        content="Method A is only a candidate improvement.",
        source="run:123",
        status="candidate",
        confidence=0.4,
    )
    pack = ContextBuilder(tmp_path, budget_chars=3000).build()
    rendered = pack.render()
    assert "Never fabricate results." in rendered
    assert "Method A is only a candidate improvement." in rendered
    assert "run:123" in rendered
    assert record.id in rendered


def test_session_compaction_is_append_only(tmp_path) -> None:
    sessions = SessionStore(tmp_path)
    sessions.append("s1", "user", "old question")
    sessions.compact("s1", "Verified summary")
    sessions.append("s1", "user", "new question")
    recent = sessions.recent("s1")
    assert [event["role"] for event in recent] == ["compact", "user"]
    lines = (tmp_path / ".researchos" / "sessions" / "s1.jsonl").read_text(
        encoding="utf-8"
    ).splitlines()
    assert len(lines) == 3


def test_cli_init_creates_policy_and_project_metadata(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RESEARCHOS_HOME", str(tmp_path / "home"))
    assert main(["init", "--project-id", "project-1"]) == 0
    assert (tmp_path / "RESEARCHOS.md").exists()
    project = json.loads(
        (tmp_path / ".researchos" / "project.json").read_text(encoding="utf-8")
    )
    assert project["schema"] == "researchos.project/v1"
    assert CLIConfig.load().project_id == "project-1"


def test_cli_adapters_emit_links_without_installing(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RESEARCHOS_HOME", str(tmp_path / "home"))
    assert main(["--json", "adapters", "list"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert any(item["project"] == "OpenAI Codex CLI" for item in output)
    assert any(item["url"] == "https://github.com/HKUDS/nanobot" for item in output)


def test_find_project_root_from_nested_directory(tmp_path) -> None:
    nested = tmp_path / "apps" / "api"
    nested.mkdir(parents=True)
    metadata = tmp_path / ".researchos"
    metadata.mkdir()
    (metadata / "project.json").write_text("{}", encoding="utf-8")
    assert find_project_root(nested) == tmp_path.resolve()
