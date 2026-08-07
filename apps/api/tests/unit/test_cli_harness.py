"""Pure tests for the local ResearchOS CLI harness primitives."""

from __future__ import annotations

import json

from researchos.cli.config import CLIConfig
from researchos.cli.context import ContextBuilder
from researchos.cli.main import build_parser, command_missions, find_project_root, main
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
    lines = (
        (tmp_path / ".researchos" / "sessions" / "s1.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    assert len(lines) == 3


def test_cli_init_creates_policy_and_project_metadata(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RESEARCHOS_HOME", str(tmp_path / "home"))
    assert main(["init", "--project-id", "project-1"]) == 0
    assert (tmp_path / "RESEARCHOS.md").exists()
    project = json.loads((tmp_path / ".researchos" / "project.json").read_text(encoding="utf-8"))
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


class _MissionClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict | None, dict | None]] = []

    def request(self, method, path, *, body=None, query=None):
        self.calls.append((method, path, body, query))
        if path.endswith("/reading-card/generate"):
            return {"agent_run_id": "run-1", "status": "queued", "stream": "/ws"}
        if path.endswith("/experiment-plan/generate"):
            return {"agent_run_id": "run-plan", "status": "queued", "stream": "/ws"}
        if path.endswith("/sql-query"):
            return {"agent_run_id": "run-sql", "status": "queued", "stream": "/ws"}
        if method == "POST" and path.endswith("/citation-audits"):
            return {"agent_run_id": "run-citations", "status": "queued", "stream": "/ws"}
        if method == "GET" and path.endswith("/experiment-plan"):
            return {
                "id": "plan-1",
                "version": 3,
                "status": "needs_review",
                "title": "Primary comparison",
                "hypothesis": "H1",
                "variables_json": [],
                "baselines_json": [],
                "datasets_json": [],
                "metrics_json": [],
                "matrix_json": [],
            }
        if method == "GET" and not path.endswith("/timeline"):
            return {
                "id": "mission-1",
                "version": 4,
                "status": "active",
                "progress": 20.0,
                "topic": "Grounded review",
                "steps": [{"step_kind": "literature", "status": "ready", "version": 3}],
            }
        if path.endswith("/timeline"):
            return {"items": [], "total": 0, "limit": 50, "offset": 0}
        return {
            "id": "mission-1",
            "version": 5,
            "status": "active",
            "progress": 20.0,
            "topic": "Grounded review",
            "steps": [],
        }


def test_cli_missions_create_targets_shared_api(capsys) -> None:
    args = build_parser().parse_args(
        [
            "--json",
            "missions",
            "create",
            "Grounded review",
            "--objective",
            "Produce a cited review",
            "--scope-json",
            '{"minimum_papers":8}',
        ]
    )
    client = _MissionClient()
    assert command_missions(client, "project-1", args) == 0
    method, path, body, query = client.calls[0]
    assert (method, path, query) == ("POST", "/projects/project-1/missions", None)
    assert body == {
        "topic": "Grounded review",
        "objective": "Produce a cited review",
        "field": None,
        "scope": {"minimum_papers": 8},
    }
    assert json.loads(capsys.readouterr().out)["id"] == "mission-1"


def test_cli_missions_step_save_resolves_optimistic_version(capsys) -> None:
    args = build_parser().parse_args(
        [
            "--json",
            "missions",
            "step-save",
            "mission-1",
            "literature",
            "--summary",
            "Eight papers included",
            "--status",
            "needs_review",
        ]
    )
    client = _MissionClient()
    assert command_missions(client, "project-1", args) == 0
    assert client.calls[0][:2] == (
        "GET",
        "/projects/project-1/missions/mission-1",
    )
    assert client.calls[1] == (
        "PUT",
        "/projects/project-1/missions/mission-1/steps/literature",
        {
            "expected_version": 3,
            "output": {"summary": "Eight papers included"},
            "status": "needs_review",
        },
        None,
    )
    assert json.loads(capsys.readouterr().out)["version"] == 5


def test_cli_missions_generate_card_can_return_durable_run(capsys) -> None:
    args = build_parser().parse_args(
        [
            "--json",
            "missions",
            "generate-card",
            "mission-1",
            "paper-1",
            "--regenerate",
            "--no-wait",
        ]
    )
    client = _MissionClient()
    assert command_missions(client, "project-1", args) == 0
    assert client.calls[0] == (
        "POST",
        "/projects/project-1/papers/paper-1/reading-card/generate",
        {"mission_id": "mission-1", "regenerate": True},
        None,
    )
    assert json.loads(capsys.readouterr().out)["agent_run_id"] == "run-1"


def test_cli_plan_generate_uses_current_version_and_returns_run(capsys) -> None:
    args = build_parser().parse_args(
        [
            "--json",
            "missions",
            "plan-generate",
            "mission-1",
            "--regenerate",
            "--no-wait",
        ]
    )
    client = _MissionClient()

    assert command_missions(client, "project-1", args) == 0

    assert client.calls[0][:2] == (
        "GET",
        "/projects/project-1/missions/mission-1/experiment-plan",
    )
    assert client.calls[1] == (
        "POST",
        "/projects/project-1/missions/mission-1/experiment-plan/generate",
        {"expected_version": 3, "regenerate": True},
        None,
    )
    assert json.loads(capsys.readouterr().out)["agent_run_id"] == "run-plan"


def test_cli_sql_query_targets_registered_snapshot_and_returns_run(capsys) -> None:
    args = build_parser().parse_args(
        [
            "--json",
            "missions",
            "sql-query",
            "mission-1",
            "dataset-1",
            "Compare mean macro F1",
            "--no-wait",
        ]
    )
    client = _MissionClient()

    assert command_missions(client, "project-1", args) == 0

    assert client.calls[0] == (
        "POST",
        "/projects/project-1/missions/mission-1/sql-query",
        {"dataset_source_id": "dataset-1", "question": "Compare mean macro F1"},
        None,
    )
    assert json.loads(capsys.readouterr().out)["agent_run_id"] == "run-sql"


def test_cli_citation_audit_returns_durable_run(capsys) -> None:
    args = build_parser().parse_args(
        ["--json", "missions", "citation-audit", "mission-1", "--no-wait"]
    )
    client = _MissionClient()

    assert command_missions(client, "project-1", args) == 0

    assert client.calls[0] == (
        "POST",
        "/projects/project-1/missions/mission-1/citation-audits",
        None,
        None,
    )
    assert json.loads(capsys.readouterr().out)["agent_run_id"] == "run-citations"
