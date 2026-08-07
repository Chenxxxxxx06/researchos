"""ResearchOS CLI — a thin research harness over the existing API."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any, TypedDict

from .client import APIError, ResearchOSClient
from .config import CLIConfig
from .context import ContextBuilder, dump_context
from .memory import MemoryStore
from .session import MissionStore, SessionStore

TERMINAL_STATUSES = {"completed", "failed", "cancelled"}
AGENT_TYPES = ("research", "coding", "latex", "experiment")
MEMORY_KINDS = ("decision", "claim", "experiment", "preference", "failure", "handoff")
MEMORY_STATUSES = ("candidate", "verified", "rejected", "superseded")
MISSION_STATUSES = ("draft", "active", "paused", "completed", "archived")
MISSION_STEP_KINDS = ("scope", "literature", "reading", "review", "experiment_plan")
MISSION_STEP_STATUSES = ("locked", "ready", "in_progress", "needs_review", "completed")


class ExternalAdapter(TypedDict):
    name: str
    executable: str
    project: str
    url: str
    integration: str


EXTERNAL_ADAPTERS: tuple[ExternalAdapter, ...] = (
    {
        "name": "claude",
        "executable": "claude",
        "project": "Claude Code",
        "url": "https://code.claude.com/docs/en/overview",
        "integration": "external CLI adapter planned; no source migration",
    },
    {
        "name": "codex",
        "executable": "codex",
        "project": "OpenAI Codex CLI",
        "url": "https://github.com/openai/codex",
        "integration": "external CLI/app-server adapter planned",
    },
    {
        "name": "openclaw",
        "executable": "openclaw",
        "project": "OpenClaw",
        "url": "https://github.com/openclaw/openclaw",
        "integration": "gateway/workspace concepts only; bridge planned",
    },
    {
        "name": "nanobot",
        "executable": "nanobot",
        "project": "nanobot",
        "url": "https://github.com/HKUDS/nanobot",
        "integration": "provider/gateway bridge planned",
    },
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="researchos",
        description="ResearchOS scientific agent harness CLI",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    sub = parser.add_subparsers(dest="command")

    init = sub.add_parser("init", help="Initialize ResearchOS metadata in this repository.")
    init.add_argument("--project-id")

    config = sub.add_parser("config", help="Configure API URL or active project.")
    config.add_argument("--api-url")
    config.add_argument("--project-id")
    config.add_argument("--show", action="store_true")

    login = sub.add_parser("login", help="Authenticate against the ResearchOS API.")
    login.add_argument("--email", required=True)
    login_password = login.add_mutually_exclusive_group()
    login_password.add_argument("--password-stdin", action="store_true")
    login_password.add_argument("--password-env", action="store_true")

    register = sub.add_parser("register", help="Create a ResearchOS account and organization.")
    register.add_argument("--email", required=True)
    register.add_argument("--display-name", required=True)
    register_password = register.add_mutually_exclusive_group()
    register_password.add_argument("--password-stdin", action="store_true")
    register_password.add_argument("--password-env", action="store_true")

    sub.add_parser("doctor", help="Check API, auth, project, worker-facing configuration.")

    projects = sub.add_parser("projects", help="List projects.")
    projects.add_argument("action", choices=("list", "create"), nargs="?", default="list")
    projects.add_argument("--limit", type=int, default=50)
    projects.add_argument("--organization-id")
    projects.add_argument("--name")
    projects.add_argument("--description")
    projects.add_argument("--field")

    use = sub.add_parser("use", help="Set the active project.")
    use.add_argument("project_id")

    ask = sub.add_parser("ask", help="Run one agent turn and wait for its result.")
    ask.add_argument("message")
    ask.add_argument("--agent", choices=AGENT_TYPES, default="research")
    ask.add_argument("--no-context", action="store_true")
    ask.add_argument("--timeout", type=int, default=180)
    ask.add_argument("--no-wait", action="store_true")

    chat = sub.add_parser("chat", help="Open an interactive project-scoped session.")
    chat.add_argument("--agent", choices=AGENT_TYPES, default="research")
    chat.add_argument("--session")

    runs = sub.add_parser("runs", help="List, inspect, or cancel agent runs.")
    runs_sub = runs.add_subparsers(dest="runs_command", required=True)
    runs_list = runs_sub.add_parser("list")
    runs_list.add_argument("--limit", type=int, default=20)
    runs_status = runs_sub.add_parser("status")
    runs_status.add_argument("run_id")
    runs_cancel = runs_sub.add_parser("cancel")
    runs_cancel.add_argument("run_id")

    context = sub.add_parser("context", help="Inspect the context pack sent to agents.")
    context.add_argument("--session")
    context.add_argument("--render", action="store_true")
    context.add_argument("--budget", type=int, default=7000)

    memory = sub.add_parser("memory", help="Manage append-only scientific memory.")
    memory_sub = memory.add_subparsers(dest="memory_command", required=True)
    memory_add = memory_sub.add_parser("add")
    memory_add.add_argument("kind", choices=MEMORY_KINDS)
    memory_add.add_argument("content")
    memory_add.add_argument("--source", required=True)
    memory_add.add_argument("--status", choices=MEMORY_STATUSES, default="candidate")
    memory_add.add_argument("--confidence", type=float, default=0.5)
    memory_add.add_argument("--tag", action="append", default=[])
    memory_list = memory_sub.add_parser("list")
    memory_list.add_argument("--kind", choices=MEMORY_KINDS)
    memory_list.add_argument("--status", choices=MEMORY_STATUSES)
    memory_list.add_argument("--limit", type=int, default=50)

    mission = sub.add_parser("mission", help="Manage durable coordinator-run scaffolds.")
    mission_sub = mission.add_subparsers(dest="mission_command", required=True)
    mission_run = mission_sub.add_parser("run")
    mission_run.add_argument("objective")
    mission_run.add_argument("--timeout", type=int, default=180)
    mission_status = mission_sub.add_parser("status")
    mission_status.add_argument("mission_id")
    mission_approve = mission_sub.add_parser("approve")
    mission_approve.add_argument("mission_id")
    mission_approve.add_argument("gate", choices=("scope", "evidence", "release"))
    mission_approve.add_argument("--note", default="")

    missions = sub.add_parser(
        "missions",
        help="Manage server-backed research missions shared with the web workspace.",
    )
    missions_sub = missions.add_subparsers(dest="missions_command", required=True)
    missions_list = missions_sub.add_parser("list", help="List research missions.")
    missions_list.add_argument("--status", choices=MISSION_STATUSES)
    missions_list.add_argument("--limit", type=int, default=50)
    missions_create = missions_sub.add_parser("create", help="Create a five-step mission.")
    missions_create.add_argument("topic")
    missions_create.add_argument("--objective", default="")
    missions_create.add_argument("--field")
    missions_create.add_argument(
        "--scope-json",
        default="{}",
        help="JSON object or @path containing search scope and evidence targets.",
    )
    missions_show = missions_sub.add_parser("show", help="Show a mission and its steps.")
    missions_show.add_argument("mission_id")
    missions_update = missions_sub.add_parser("update", help="Update mission metadata or status.")
    missions_update.add_argument("mission_id")
    missions_update.add_argument("--version", type=int)
    missions_update.add_argument("--topic")
    missions_update.add_argument("--objective")
    missions_update.add_argument("--field")
    missions_update.add_argument("--status", choices=MISSION_STATUSES)
    missions_update.add_argument("--scope-json")
    missions_step = missions_sub.add_parser(
        "step-save", help="Persist inputs, outputs, or state for one mission step."
    )
    missions_step.add_argument("mission_id")
    missions_step.add_argument("step", choices=MISSION_STEP_KINDS)
    missions_step.add_argument("--version", type=int)
    missions_step.add_argument("--input-json")
    missions_step.add_argument("--output-json")
    missions_step.add_argument("--summary", help="Shortcut for output_json.summary.")
    missions_step.add_argument("--status", choices=MISSION_STEP_STATUSES)
    missions_approve_step = missions_sub.add_parser(
        "approve", help="Approve a step and unlock the next one."
    )
    missions_approve_step.add_argument("mission_id")
    missions_approve_step.add_argument("step", choices=MISSION_STEP_KINDS)
    missions_approve_step.add_argument("--version", type=int)
    missions_approve_step.add_argument("--note", default="")
    missions_timeline = missions_sub.add_parser(
        "timeline", help="Show the mission evidence and approval timeline."
    )
    missions_timeline.add_argument("mission_id")
    missions_timeline.add_argument("--limit", type=int, default=50)
    missions_generate_card = missions_sub.add_parser(
        "generate-card",
        help="Run the section-grounded reading-card agent and wait for its result.",
    )
    missions_generate_card.add_argument("mission_id")
    missions_generate_card.add_argument("paper_id")
    missions_generate_card.add_argument("--regenerate", action="store_true")
    missions_generate_card.add_argument("--timeout", type=int, default=180)
    missions_generate_card.add_argument("--no-wait", action="store_true")
    missions_card_versions = missions_sub.add_parser(
        "card-versions", help="List immutable reading-card versions for a paper."
    )
    missions_card_versions.add_argument("mission_id")
    missions_card_versions.add_argument("paper_id")
    missions_review_show = missions_sub.add_parser(
        "review-show", help="Show the structured review and citation coverage."
    )
    missions_review_show.add_argument("mission_id")
    missions_review_outline = missions_sub.add_parser(
        "review-outline", help="Generate or rebuild the source-bound review outline."
    )
    missions_review_outline.add_argument("mission_id")
    missions_review_outline.add_argument("--regenerate", action="store_true")
    missions_review_generate = missions_sub.add_parser(
        "review-generate", help="Run the evidence-bound agent for one review section."
    )
    missions_review_generate.add_argument("mission_id")
    missions_review_generate.add_argument("section_id")
    missions_review_generate.add_argument("--version", type=int)
    missions_review_generate.add_argument("--regenerate", action="store_true")
    missions_review_generate.add_argument("--timeout", type=int, default=180)
    missions_review_generate.add_argument("--no-wait", action="store_true")
    missions_review_save = missions_sub.add_parser(
        "review-save", help="Save one review section and create an immutable version."
    )
    missions_review_save.add_argument("mission_id")
    missions_review_save.add_argument("section_id")
    missions_review_save.add_argument("--version", type=int)
    missions_review_save.add_argument("--title")
    missions_review_save.add_argument("--purpose")
    missions_review_save.add_argument("--body")
    missions_review_save.add_argument("--body-file")
    missions_review_save.add_argument("--citation", action="append", default=[])
    missions_review_save.add_argument(
        "--status", choices=("outline", "draft", "needs_review", "approved")
    )
    missions_review_versions = missions_sub.add_parser(
        "review-versions", help="List immutable review versions."
    )
    missions_review_versions.add_argument("mission_id")
    missions_plan_show = missions_sub.add_parser(
        "plan-show", help="Show the mission's structured experiment plan."
    )
    missions_plan_show.add_argument("mission_id")
    missions_plan_generate = missions_sub.add_parser(
        "plan-generate", help="Generate an evidence-bound experiment plan and wait."
    )
    missions_plan_generate.add_argument("mission_id")
    missions_plan_generate.add_argument("--regenerate", action="store_true")
    missions_plan_generate.add_argument("--timeout", type=int, default=180)
    missions_plan_generate.add_argument("--no-wait", action="store_true")
    missions_plan_save = missions_sub.add_parser(
        "plan-save", help="Save a structured plan from a UTF-8 JSON object."
    )
    missions_plan_save.add_argument("mission_id")
    missions_plan_save.add_argument("--file", required=True)
    missions_plan_publish = missions_sub.add_parser(
        "plan-publish", help="Validate and publish the plan into Experiments."
    )
    missions_plan_publish.add_argument("mission_id")
    missions_plan_versions = missions_sub.add_parser(
        "plan-versions", help="List immutable experiment-plan versions."
    )
    missions_plan_versions.add_argument("mission_id")
    missions_dataset_list = missions_sub.add_parser(
        "dataset-list", help="List registered read-only dataset snapshots."
    )
    missions_dataset_list.add_argument("mission_id")
    missions_dataset_register = missions_sub.add_parser(
        "dataset-register", help="Register a dataset from a JSON request file."
    )
    missions_dataset_register.add_argument("mission_id")
    missions_dataset_register.add_argument("--file", required=True)
    missions_sql_query = missions_sub.add_parser(
        "sql-query", help="Ask the read-only SQL Agent a question and wait."
    )
    missions_sql_query.add_argument("mission_id")
    missions_sql_query.add_argument("dataset_source_id")
    missions_sql_query.add_argument("question")
    missions_sql_query.add_argument("--timeout", type=int, default=180)
    missions_sql_query.add_argument("--no-wait", action="store_true")
    missions_sql_results = missions_sub.add_parser(
        "sql-results", help="List persisted SQL Agent results for a mission."
    )
    missions_sql_results.add_argument("mission_id")
    missions_citation_audit = missions_sub.add_parser(
        "citation-audit", help="Run the citation organizer and wait."
    )
    missions_citation_audit.add_argument("mission_id")
    missions_citation_audit.add_argument("--timeout", type=int, default=180)
    missions_citation_audit.add_argument("--no-wait", action="store_true")
    missions_citation_show = missions_sub.add_parser(
        "citation-show", help="Show the latest citation audit."
    )
    missions_citation_show.add_argument("mission_id")

    adapters = sub.add_parser("adapters", help="Inspect optional external harness adapters.")
    adapters.add_argument("action", choices=("list", "doctor"), default="list", nargs="?")

    release = sub.add_parser("release", help="Run release readiness checks.")
    release.add_argument("action", choices=("preflight",), default="preflight", nargs="?")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        if sys.stdin.isatty():
            args = parser.parse_args(["chat"])
        else:
            parser.print_help()
            return 2
    try:
        return dispatch(args)
    except (APIError, RuntimeError, ValueError, FileNotFoundError) as exc:
        if getattr(args, "json", False):
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        else:
            print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130


def dispatch(args: argparse.Namespace) -> int:
    root = find_project_root(Path.cwd())
    config = CLIConfig.load()
    if args.command == "init":
        return command_init(root, config, args)
    if args.command == "config":
        return command_config(config, args)
    if args.command == "use":
        config.project_id = args.project_id
        config.save()
        print(f"Active project: {args.project_id}")
        return 0

    client = ResearchOSClient(config.api_url)
    if args.command == "login":
        password = read_password(args)
        user = client.login(args.email, password)
        return emit(args, {"ok": True, "user": user}, f"Logged in as {user.get('email')}")
    if args.command == "register":
        password = read_password(args)
        payload = client.register(args.email, password, args.display_name)
        email = (payload.get("user") or {}).get("email")
        return emit(args, {"ok": True, **payload}, f"Registered and logged in as {email}")
    if args.command == "doctor":
        return command_doctor(client, config, args)
    if args.command == "projects":
        return command_projects(client, args)
    if args.command == "context":
        pack = ContextBuilder(root, budget_chars=args.budget).build(session_id=args.session)
        return emit(args, pack.to_json(), pack.render() if args.render else dump_context(pack))
    if args.command == "memory":
        return command_memory(root, args)
    if args.command == "adapters":
        return command_adapters(args)
    if args.command == "release":
        return command_release_preflight(root, args)

    project_id = require_project(config)
    if args.command == "ask":
        result = run_turn(
            client,
            project_id,
            root=root,
            message=args.message,
            agent_type=args.agent,
            include_context=not args.no_context,
            timeout=args.timeout,
            wait=not args.no_wait,
        )
        return emit(args, result, _format_run(result))
    if args.command == "chat":
        return command_chat(client, project_id, root, args)
    if args.command == "runs":
        return command_runs(client, project_id, args)
    if args.command == "mission":
        return command_mission(client, project_id, root, args)
    if args.command == "missions":
        return command_missions(client, project_id, args)
    raise RuntimeError(f"Unsupported command: {args.command}")


def command_init(root: Path, config: CLIConfig, args: argparse.Namespace) -> int:
    directory = root / ".researchos"
    directory.mkdir(exist_ok=True)
    project_file = directory / "project.json"
    if not project_file.exists():
        project_file.write_text(
            json.dumps(
                {"schema": "researchos.project/v1", "project_id": args.project_id},
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    ignore = directory / ".gitignore"
    if not ignore.exists():
        ignore.write_text("sessions/\nmissions/\ncontext-cache/\n", encoding="utf-8")
    policy = root / "RESEARCHOS.md"
    if not policy.exists():
        policy.write_text(_policy_template(), encoding="utf-8")
    if args.project_id:
        config.project_id = args.project_id
        config.save()
    print("Initialized .researchos/ and RESEARCHOS.md")
    return 0


def command_config(config: CLIConfig, args: argparse.Namespace) -> int:
    if args.api_url:
        config.api_url = args.api_url.rstrip("/")
    if args.project_id:
        config.project_id = args.project_id
    if args.api_url or args.project_id:
        config.save()
    print(json.dumps({"api_url": config.api_url, "project_id": config.project_id}, indent=2))
    return 0


def command_doctor(client: ResearchOSClient, config: CLIConfig, args: argparse.Namespace) -> int:
    checks: list[dict[str, Any]] = []
    for name, path in (("api", "/healthz"), ("dependencies", "/readyz"), ("auth", "/auth/me")):
        try:
            payload = client.request("GET", path)
            checks.append({"name": name, "ok": True, "detail": payload})
        except APIError as exc:
            checks.append({"name": name, "ok": False, "detail": str(exc), "status": exc.status})
    checks.append(
        {
            "name": "project",
            "ok": bool(config.project_id),
            "detail": config.project_id or "Run: researchos use <project-id>",
        }
    )
    ok = all(check["ok"] for check in checks)
    text = "\n".join(
        f"{'OK' if check['ok'] else 'FAIL':4} {check['name']}: {check['detail']}"
        for check in checks
    )
    emit(args, {"ok": ok, "checks": checks}, text)
    return 0 if ok else 1


def command_projects(client: ResearchOSClient, args: argparse.Namespace) -> int:
    me = client.request("GET", "/auth/me")
    organizations = me.get("organizations", [])
    organization_id = args.organization_id
    if not organization_id and organizations:
        organization_id = organizations[0]["id"]
    if not organization_id:
        raise RuntimeError("No organization found for this account.")
    if args.action == "create":
        if not args.name:
            raise ValueError("projects create requires --name.")
        project = client.request(
            "POST",
            "/projects",
            body={
                "organization_id": organization_id,
                "name": args.name,
                "description": args.description,
                "field": args.field,
            },
        )
        return emit(args, project, f"{project['id']}  {project['name']}  [created]")
    page = client.request(
        "GET",
        "/projects",
        query={
            "organization_id": organization_id,
            "limit": args.limit,
        },
    )
    return emit(args, page, _format_projects(page))


def command_memory(root: Path, args: argparse.Namespace) -> int:
    store = MemoryStore(root)
    if args.memory_command == "add":
        record = store.add(
            kind=args.kind,
            content=args.content,
            source=args.source,
            status=args.status,
            confidence=args.confidence,
            tags=args.tag,
        )
        return emit(args, asdict(record), f"Added {record.kind} memory {record.id}")
    records = store.list_records(kind=args.kind, status=args.status, limit=args.limit)
    payload = [
        {
            "id": item.id,
            "kind": item.kind,
            "status": item.status,
            "confidence": item.confidence,
            "content": item.content,
            "source": item.source,
        }
        for item in records
    ]
    text = (
        "\n".join(
            f"{item.id[:8]} {item.status:10} {item.kind:10} {item.confidence:.2f} {item.content}"
            for item in records
        )
        or "No memory records."
    )
    return emit(args, payload, text)


def command_adapters(args: argparse.Namespace) -> int:
    payload = []
    for adapter in EXTERNAL_ADAPTERS:
        executable = shutil.which(adapter["executable"])
        payload.append({**adapter, "installed": executable is not None, "path": executable})
    text = "\n".join(
        f"{'READY' if item['installed'] else 'LINK ':5} {item['project']}: "
        f"{item['path'] or item['url']} - {item['integration']}"
        for item in payload
    )
    return emit(args, payload, text)


def command_release_preflight(root: Path, args: argparse.Namespace) -> int:
    required = (
        "LICENSE",
        "NOTICE.md",
        "OWNERSHIP.json",
        "README.md",
        "README_zh.md",
        "VERSION",
        "docs/site/index.html",
        ".github/workflows/pages.yml",
        ".github/workflows/release.yml",
    )
    checks = [
        {"name": path, "ok": (root / path).exists(), "detail": "present"} for path in required
    ]
    try:
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        clean = not status.stdout.strip()
        checks.append(
            {
                "name": "git-clean",
                "ok": clean,
                "detail": "clean" if clean else "uncommitted changes",
            }
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        checks.append({"name": "git-clean", "ok": False, "detail": str(exc)})
    ok = all(check["ok"] for check in checks)
    text = "\n".join(
        f"{'OK' if check['ok'] else 'FAIL':4} {check['name']}: {check['detail']}"
        for check in checks
    )
    emit(args, {"ok": ok, "checks": checks}, text)
    return 0 if ok else 1


def command_runs(client: ResearchOSClient, project_id: str, args: argparse.Namespace) -> int:
    base = f"/projects/{project_id}/agents/runs"
    if args.runs_command == "list":
        page = client.request("GET", base, query={"limit": args.limit})
        return emit(args, page, _format_runs(page))
    if args.runs_command == "status":
        run = client.request("GET", f"{base}/{args.run_id}")
        return emit(args, run, _format_run(run))
    run = client.request("POST", f"{base}/{args.run_id}/cancel")
    return emit(args, run, _format_run(run))


def command_missions(client: ResearchOSClient, project_id: str, args: argparse.Namespace) -> int:
    """Operate the durable mission API used by the web workspace."""

    base = f"/projects/{project_id}/missions"
    command = args.missions_command
    if command == "list":
        page = client.request("GET", base, query={"status": args.status, "limit": args.limit})
        return emit(args, page, _format_missions(page))
    if command == "create":
        mission = client.request(
            "POST",
            base,
            body={
                "topic": args.topic,
                "objective": args.objective,
                "field": args.field,
                "scope": _parse_json_object(args.scope_json, label="scope"),
            },
        )
        return emit(args, mission, _format_mission(mission))
    mission_path = f"{base}/{args.mission_id}"
    if command == "show":
        mission = client.request("GET", mission_path)
        return emit(args, mission, _format_mission(mission))
    if command == "timeline":
        page = client.request("GET", f"{mission_path}/timeline", query={"limit": args.limit})
        return emit(args, page, _format_mission_timeline(page))
    if command == "card-versions":
        versions = client.request(
            "GET",
            f"{base.rsplit('/missions', 1)[0]}/papers/{args.paper_id}/reading-card/versions",
            query={"mission_id": args.mission_id},
        )
        return emit(args, versions, _format_card_versions(versions))
    if command == "generate-card":
        created = client.request(
            "POST",
            f"{base.rsplit('/missions', 1)[0]}/papers/{args.paper_id}/reading-card/generate",
            body={"mission_id": args.mission_id, "regenerate": args.regenerate},
        )
        if args.no_wait:
            return emit(args, created, f"{created['agent_run_id']} [{created['status']}]")
        run = wait_for_run(
            client,
            project_id,
            str(created["agent_run_id"]),
            timeout=args.timeout,
        )
        return emit(args, run, _format_run(run))
    review_path = f"{mission_path}/review"
    if command == "review-show":
        review = client.request("GET", review_path)
        return emit(args, review, _format_review(review))
    if command == "review-outline":
        review = client.request(
            "POST", f"{review_path}/outline", body={"regenerate": args.regenerate}
        )
        return emit(args, review, _format_review(review))
    if command == "review-versions":
        versions = client.request("GET", f"{review_path}/versions")
        return emit(args, versions, _format_review_versions(versions))
    if command == "review-generate":
        review = client.request("GET", review_path)
        section = next(
            (item for item in review.get("sections", []) if item.get("id") == args.section_id),
            None,
        )
        if section is None:
            raise ValueError(f"Review section not found: {args.section_id}")
        created = client.request(
            "POST",
            f"{review_path}/sections/{args.section_id}/generate",
            body={
                "expected_version": args.version or section["version"],
                "regenerate": args.regenerate,
            },
        )
        if args.no_wait:
            return emit(args, created, f"{created['agent_run_id']} [{created['status']}]")
        run = wait_for_run(
            client,
            project_id,
            str(created["agent_run_id"]),
            timeout=args.timeout,
        )
        return emit(args, run, _format_run(run))
    if command == "review-save":
        if args.body is not None and args.body_file is not None:
            raise ValueError("Use either --body or --body-file, not both.")
        review = client.request("GET", review_path)
        section = next(
            (item for item in review.get("sections", []) if item.get("id") == args.section_id),
            None,
        )
        if section is None:
            raise ValueError(f"Review section not found: {args.section_id}")
        review_body: dict[str, Any] = {"expected_version": args.version or section["version"]}
        for key in ("title", "purpose", "status"):
            value = getattr(args, key)
            if value is not None:
                review_body[key] = value
        if args.body is not None:
            review_body["body"] = args.body
        elif args.body_file is not None:
            review_body["body"] = Path(args.body_file).read_text(encoding="utf-8")
        if args.citation:
            review_body["citations"] = args.citation
        if len(review_body) == 1:
            raise ValueError("review-save requires a title, purpose, body, citation, or status.")
        updated = client.request(
            "PUT", f"{review_path}/sections/{args.section_id}", body=review_body
        )
        return emit(args, updated, _format_review(updated))
    plan_path = f"{mission_path}/experiment-plan"
    if command == "plan-show":
        plan = client.request("GET", plan_path)
        return emit(args, plan, _format_experiment_plan(plan))
    if command == "plan-generate":
        current: dict[str, Any] | None
        try:
            current = client.request("GET", plan_path)
        except APIError as exc:
            if exc.status != 404:
                raise
            current = None
        created = client.request(
            "POST",
            f"{plan_path}/generate",
            body={
                "expected_version": current.get("version", 0) if current else 0,
                "regenerate": args.regenerate,
            },
        )
        if args.no_wait:
            return emit(args, created, f"{created['agent_run_id']} [{created['status']}]")
        run = wait_for_run(
            client,
            project_id,
            str(created["agent_run_id"]),
            timeout=args.timeout,
        )
        return emit(args, run, _format_run(run))
    if command == "plan-save":
        body = json.loads(Path(args.file).read_text(encoding="utf-8"))
        if not isinstance(body, dict):
            raise ValueError("plan-save --file must contain a JSON object.")
        if "expected_version" not in body:
            try:
                current = client.request("GET", plan_path)
            except APIError as exc:
                if exc.status != 404:
                    raise
            else:
                body["expected_version"] = current["version"]
        plan = client.request("PUT", plan_path, body=body)
        return emit(args, plan, _format_experiment_plan(plan))
    if command == "plan-publish":
        result = client.request("POST", f"{plan_path}/publish")
        return emit(args, result, _format_experiment_plan(result["plan"]))
    if command == "plan-versions":
        versions = client.request("GET", f"{plan_path}/versions")
        return emit(args, versions, _format_plan_versions(versions))
    project_path = base.rsplit("/missions", 1)[0]
    if command == "dataset-list":
        sources = client.request("GET", f"{project_path}/datasets")
        return emit(args, sources, _format_datasets(sources))
    if command == "dataset-register":
        body = json.loads(Path(args.file).read_text(encoding="utf-8"))
        if not isinstance(body, dict):
            raise ValueError("dataset-register --file must contain a JSON object.")
        source = client.request("POST", f"{project_path}/datasets", body=body)
        return emit(args, source, _format_datasets([source]))
    if command == "sql-query":
        created = client.request(
            "POST",
            f"{mission_path}/sql-query",
            body={"dataset_source_id": args.dataset_source_id, "question": args.question},
        )
        if args.no_wait:
            return emit(args, created, f"{created['agent_run_id']} [{created['status']}]")
        run = wait_for_run(
            client,
            project_id,
            str(created["agent_run_id"]),
            timeout=args.timeout,
        )
        return emit(args, run, _format_run(run))
    if command == "sql-results":
        results = client.request("GET", f"{mission_path}/sql-results")
        return emit(args, results, _format_sql_results(results))
    citation_path = f"{mission_path}/citation-audits"
    if command == "citation-audit":
        created = client.request("POST", citation_path)
        if args.no_wait:
            return emit(args, created, f"{created['agent_run_id']} [{created['status']}]")
        run = wait_for_run(
            client,
            project_id,
            str(created["agent_run_id"]),
            timeout=args.timeout,
        )
        return emit(args, run, _format_run(run))
    if command == "citation-show":
        audits = client.request("GET", citation_path)
        latest = audits[0] if audits else None
        return emit(args, latest, _format_citation_audit(latest))
    if command == "update":
        update_body: dict[str, Any] = {
            "expected_version": args.version or _mission_version(client, mission_path)
        }
        for key in ("topic", "objective", "field", "status"):
            value = getattr(args, key)
            if value is not None:
                update_body[key] = value
        if args.scope_json is not None:
            update_body["scope"] = _parse_json_object(args.scope_json, label="scope")
        if len(update_body) == 1:
            raise ValueError("missions update requires at least one field option.")
        mission = client.request("PATCH", mission_path, body=update_body)
        return emit(args, mission, _format_mission(mission))
    step_path = f"{mission_path}/steps/{args.step}"
    expected_version = args.version or _mission_step_version(client, mission_path, args.step)
    if command == "step-save":
        step_body: dict[str, Any] = {"expected_version": expected_version}
        if args.input_json is not None:
            step_body["input"] = _parse_json_object(args.input_json, label="step input")
        if args.output_json is not None:
            step_body["output"] = _parse_json_object(args.output_json, label="step output")
        if args.summary is not None:
            if "output" in step_body:
                raise ValueError("Use either --summary or --output-json, not both.")
            step_body["output"] = {"summary": args.summary}
        if args.status is not None:
            step_body["status"] = args.status
        if len(step_body) == 1:
            raise ValueError("missions step-save requires input, output, summary, or status.")
        mission = client.request("PUT", step_path, body=step_body)
        return emit(args, mission, _format_mission(mission))
    mission = client.request(
        "POST",
        f"{step_path}/approve",
        body={"expected_version": expected_version, "note": args.note or None},
    )
    return emit(args, mission, _format_mission(mission))


def command_chat(
    client: ResearchOSClient,
    project_id: str,
    root: Path,
    args: argparse.Namespace,
) -> int:
    sessions = SessionStore(root)
    session_id = args.session or sessions.new_id()
    print(f"ResearchOS {args.agent} session {session_id}")
    print("Commands: /context, /compact <summary>, /clear, /exit")
    while True:
        raw = input("researchos> ").strip()
        if not raw:
            continue
        if raw in {"/exit", "/quit"}:
            return 0
        if raw == "/context":
            print(ContextBuilder(root).build(session_id=session_id).render())
            continue
        if raw.startswith("/compact"):
            summary = raw.removeprefix("/compact").strip()
            if not summary:
                summary = "Compacted by user without a supplied semantic summary."
            sessions.compact(session_id, summary)
            print("Session compaction marker written.")
            continue
        if raw == "/clear":
            session_id = sessions.new_id()
            print(f"New session {session_id}")
            continue
        sessions.append(session_id, "user", raw)
        result = run_turn(
            client,
            project_id,
            root=root,
            message=raw,
            agent_type=args.agent,
            include_context=True,
            timeout=180,
            wait=True,
            session_id=session_id,
        )
        message = _run_message(result)
        sessions.append(session_id, "assistant", message, run_id=result.get("id"))
        print(message)


def command_mission(
    client: ResearchOSClient,
    project_id: str,
    root: Path,
    args: argparse.Namespace,
) -> int:
    store = MissionStore(root)
    if args.mission_command == "run":
        prompt = _mission_prompt(args.objective)
        run = run_turn(
            client,
            project_id,
            root=root,
            message=prompt,
            agent_type="research",
            include_context=True,
            timeout=args.timeout,
            wait=True,
        )
        mission = store.create(
            {
                "objective": args.objective,
                "project_id": project_id,
                "coordinator_run_id": run.get("id"),
                "remote_status": run.get("status"),
                "status": "awaiting_scope_approval",
            }
        )
        print(json.dumps(mission, ensure_ascii=False, indent=2))
        print("Gate required: researchos mission approve <id> scope")
        return 0
    mission = store.load(args.mission_id)
    if args.mission_command == "approve":
        mission["gates"][args.gate] = {"approved": True, "note": args.note}
        if args.gate == "scope":
            mission["status"] = "scope_approved"
        elif args.gate == "evidence":
            mission["status"] = "evidence_approved"
        else:
            mission["status"] = "release_approved"
        store.save(mission)
        print(f"Approved {args.gate} gate for mission {args.mission_id}")
        return 0
    run_id = mission.get("coordinator_run_id")
    if run_id:
        run = client.request("GET", f"/projects/{project_id}/agents/runs/{run_id}")
        mission["remote_status"] = run.get("status")
        store.save(mission)
    print(json.dumps(mission, ensure_ascii=False, indent=2))
    return 0


def run_turn(
    client: ResearchOSClient,
    project_id: str,
    *,
    root: Path,
    message: str,
    agent_type: str,
    include_context: bool,
    timeout: int,
    wait: bool,
    session_id: str | None = None,
) -> dict[str, Any]:
    if include_context:
        context = ContextBuilder(root).build(session_id=session_id).render()
        message = f"{context}\n\n<user_task>\n{message}\n</user_task>"
    message = message[:9900]
    created = client.request(
        "POST",
        f"/projects/{project_id}/agents/runs",
        body={"agent_type": agent_type, "message": message, "context": {}},
    )
    run_id = created["agent_run_id"]
    if not wait:
        return dict(created)
    return wait_for_run(client, project_id, str(run_id), timeout=timeout)


def wait_for_run(
    client: ResearchOSClient, project_id: str, run_id: str, *, timeout: int
) -> dict[str, Any]:
    """Wait for an already-created AgentRun and return its terminal representation."""

    deadline = time.monotonic() + max(1, timeout)
    while time.monotonic() < deadline:
        run = client.request("GET", f"/projects/{project_id}/agents/runs/{run_id}")
        if run.get("status") in TERMINAL_STATUSES:
            return dict(run)
        time.sleep(1)
    raise RuntimeError(f"Run {run_id} did not finish within {timeout}s.")


def require_project(config: CLIConfig) -> str:
    if not config.project_id:
        raise RuntimeError("No active project. Run: researchos projects; researchos use <id>")
    return config.project_id


def read_password(args: argparse.Namespace) -> str:
    if args.password_stdin:
        password = sys.stdin.readline().rstrip("\r\n")
    elif args.password_env:
        password = os.environ.get("RESEARCHOS_PASSWORD", "")
    else:
        password = getpass.getpass()
    if not password:
        raise ValueError("Password is empty.")
    return password


def find_project_root(cwd: Path) -> Path:
    resolved = cwd.resolve()
    for candidate in (resolved, *resolved.parents):
        if (candidate / ".researchos" / "project.json").exists():
            return candidate
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=resolved,
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip()).resolve()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return resolved


def emit(args: argparse.Namespace, payload: Any, text: str) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json else text)
    return 0


def _format_projects(page: dict[str, Any]) -> str:
    return (
        "\n".join(
            f"{item['id']}  {item.get('name', '')}  [{item.get('role', item.get('status', ''))}]"
            for item in page.get("items", [])
        )
        or "No projects."
    )


def _format_runs(page: dict[str, Any]) -> str:
    return (
        "\n".join(
            f"{item['id']}  {item['status']:10}  {item['agent_type']}"
            for item in page.get("items", [])
        )
        or "No runs."
    )


def _format_missions(page: dict[str, Any]) -> str:
    return (
        "\n".join(
            f"{item['id']}  {item.get('progress', 0):5.1f}%  "
            f"{item.get('status', ''):9}  {item.get('current_step', ''):15}  "
            f"{item.get('topic', '')}"
            for item in page.get("items", [])
        )
        or "No research missions."
    )


def _format_mission(mission: dict[str, Any]) -> str:
    lines = [
        f"{mission.get('id')}  [{mission.get('status')}]  {mission.get('progress', 0):.1f}%",
        str(mission.get("topic", "")),
    ]
    objective = mission.get("objective")
    if objective:
        lines.append(str(objective))
    for step in mission.get("steps", []):
        marker = "[x]" if step.get("status") == "completed" else "[ ]"
        lines.append(
            f"  {marker} {step.get('step_kind', ''):15} "
            f"{step.get('status', ''):14} v{step.get('version', '')}"
        )
    return "\n".join(lines)


def _format_mission_timeline(page: dict[str, Any]) -> str:
    return (
        "\n".join(
            f"{item.get('created_at', '')}  {item.get('event_type', ''):18}  "
            f"{item.get('summary', '')}"
            for item in page.get("items", [])
        )
        or "No mission events."
    )


def _format_card_versions(versions: list[dict[str, Any]]) -> str:
    return (
        "\n".join(
            f"v{item.get('version', ''):<4} {item.get('source_type', ''):8} "
            f"{item.get('created_at', '')}  run={item.get('source_run_id') or '-'}"
            for item in versions
        )
        or "No reading-card versions."
    )


def _format_review(review: dict[str, Any]) -> str:
    lines = [
        f"{review.get('id')} [v{review.get('version')}] {review.get('status')}  "
        f"coverage={review.get('citation_coverage', 0):.1f}%  "
        f"unsupported={review.get('unsupported_claims', 0)}",
        str(review.get("title", "")),
    ]
    lines.extend(
        f"  {item.get('id')}  {item.get('position', 0) + 1}. "
        f"{item.get('title', '')}  [{item.get('status')}, "
        f"v{item.get('version')}, {len(item.get('citations_json', []))} cites]"
        for item in review.get("sections", [])
    )
    return "\n".join(lines)


def _format_review_versions(versions: list[dict[str, Any]]) -> str:
    return (
        "\n".join(
            f"v{item.get('version', ''):<4} {item.get('source_type', ''):8} "
            f"{item.get('created_at', '')}"
            for item in versions
        )
        or "No review versions."
    )


def _format_experiment_plan(plan: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"{plan.get('id')} [v{plan.get('version')}] {plan.get('status')}",
            str(plan.get("title", "")),
            f"hypothesis: {plan.get('hypothesis', '')}",
            f"variables={len(plan.get('variables_json', []))}  "
            f"baselines={len(plan.get('baselines_json', []))}  "
            f"datasets={len(plan.get('datasets_json', []))}  "
            f"metrics={len(plan.get('metrics_json', []))}  "
            f"matrix={len(plan.get('matrix_json', []))}",
            f"published_experiment={plan.get('published_experiment_id') or '-'}",
        ]
    )


def _format_plan_versions(versions: list[dict[str, Any]]) -> str:
    return (
        "\n".join(
            f"v{item.get('version', ''):<4} {item.get('source_type', ''):8} "
            f"{item.get('created_at', '')}  run={item.get('source_run_id') or '-'}"
            for item in versions
        )
        or "No experiment-plan versions."
    )


def _format_datasets(items: list[dict[str, Any]]) -> str:
    return (
        "\n".join(
            f"{item.get('id')}  {item.get('name')}  "
            f"[{len(item.get('rows_json', []))} rows, "
            f"{len(item.get('columns_json', []))} columns]"
            for item in items
        )
        or "No registered datasets."
    )


def _format_sql_results(items: list[dict[str, Any]]) -> str:
    return (
        "\n".join(
            f"{item.get('id')}  rows={item.get('row_count', 0)}  "
            f"{item.get('question', '')}\n  {item.get('sql', '')}"
            for item in items
        )
        or "No SQL results."
    )


def _format_citation_audit(audit: dict[str, Any] | None) -> str:
    if audit is None:
        return "No citation audits."
    return (
        f"{audit.get('id')}  papers={len(audit.get('items_json', []))}  "
        f"missing={audit.get('missing_field_count', 0)}  "
        f"duplicates={len(audit.get('duplicate_groups_json', []))}"
    )


def _format_run(run: dict[str, Any]) -> str:
    message = _run_message(run)
    return f"{run.get('id', run.get('agent_run_id'))} [{run.get('status')}]\n{message}".rstrip()


def _run_message(run: dict[str, Any]) -> str:
    output = run.get("output_json") or {}
    error = run.get("error_json") or {}
    return str(output.get("message") or error.get("message") or "")


def _parse_json_object(raw: str, *, label: str) -> dict[str, Any]:
    """Read a JSON object from an inline value or an @file argument."""

    if raw.startswith("@"):
        path = Path(raw[1:]).expanduser()
        raw = path.read_text(encoding="utf-8")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid {label} JSON: {exc.msg}.") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label.capitalize()} JSON must be an object.")
    return value


def _mission_version(client: ResearchOSClient, mission_path: str) -> int:
    mission = client.request("GET", mission_path)
    return int(mission["version"])


def _mission_step_version(client: ResearchOSClient, mission_path: str, step_kind: str) -> int:
    mission = client.request("GET", mission_path)
    for step in mission.get("steps", []):
        if step.get("step_kind") == step_kind:
            return int(step["version"])
    raise RuntimeError(f"Mission does not contain step: {step_kind}")


def _mission_prompt(objective: str) -> str:
    return f"""Act as the ResearchOS mission coordinator. Do not perform unbounded autonomous work.
Produce a scoped, evidence-aware plan for this objective:

{objective}

Return: research question, success metrics, evidence requirements, proposed artifact DAG, specialist
agent assignments, compute/time budget, failure/stop conditions, and the exact questions requiring
human scope approval. Do not invent papers, results, available code, or completed experiments."""


def _policy_template() -> str:
    return """# ResearchOS Project Memory

## Research objective

- TODO: define the scientific question, target venue, compute budget, and success metric.

## Non-negotiable rules

- Never fabricate citations, datasets, baselines, metrics, experiments, or reviewer feedback.
- Bind important claims to source papers or verified experiment artifacts.
- Agent output is a proposal until a human approves the relevant scope, evidence, or release gate.
- Code changes use reviewable patches; experiments record commit, environment, data, and parameters.

## Context compaction

Preserve research decisions, rejected hypotheses and why, verified claims with sources, experiment
lineage, unresolved risks, and the next executable task. Drop raw logs already stored as artifacts.
"""
