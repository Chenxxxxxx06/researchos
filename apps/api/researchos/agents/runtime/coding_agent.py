"""Coding agent: proposes a reviewable patch. It never writes files.

The agent inspects the workspace (read-only tool) and finalizes by creating a
*pending* patch proposal. Applying the patch is a separate, user-initiated
action (see researchos.patches).
"""

from __future__ import annotations

import json

from researchos.agents.enums import AgentType
from researchos.agents.llm import LLMMessage
from researchos.common.paths import WorkspaceAccessError, resolve_in_workspace
from researchos.patches.schemas import PatchFileInput
from researchos.patches.service import PatchService

from .base import Agent, AgentContext

_SYSTEM = (
    "You are a coding assistant working inside a project workspace. Inspect the "
    "workspace with the workspace.tree tool, then propose changes as a patch. "
    "Respond with a JSON object: {summary, files:[{path, change_type "
    "('create'|'modify'|'delete'), base_sha, new_content}]}. You never write "
    "files directly; your patch is reviewed by the user before it is applied."
)

_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "files": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "change_type": {"type": "string"},
                    "base_sha": {"type": ["string", "null"]},
                    "new_content": {"type": ["string", "null"]},
                },
                "required": ["path", "change_type"],
            },
        },
    },
    "required": ["summary", "files"],
}


class CodingAgent(Agent):
    agent_type = AgentType.CODING
    allowed_tools = ["workspace.tree"]
    response_schema = _SCHEMA

    async def build_messages(self, actx: AgentContext) -> list[LLMMessage]:
        return [
            LLMMessage(role="system", content=_SYSTEM),
            LLMMessage(role="user", content=actx.message),
        ]

    async def finalize(
        self,
        actx: AgentContext,
        *,
        output_text: str,
        whitelist: set[str],
        citation_sources: dict[str, dict],
        usage: dict,
    ) -> tuple[dict, list[dict]]:
        try:
            parsed = json.loads(output_text)
        except json.JSONDecodeError:
            parsed = {}

        safe_files: list[PatchFileInput] = []
        for raw in parsed.get("files", []):
            try:
                candidate = PatchFileInput(
                    path=str(raw["path"]),
                    change_type=raw["change_type"],
                    base_sha=raw.get("base_sha"),
                    new_content=raw.get("new_content"),
                )
            except (KeyError, ValueError):
                continue
            # Drop any path that violates the workspace guard (denied / escape).
            try:
                resolve_in_workspace(actx.project_id, candidate.path)
            except WorkspaceAccessError:
                continue
            safe_files.append(candidate)

        patch_id: str | None = None
        if safe_files:
            proposal = await PatchService(actx.db).create_proposal(
                project_id=actx.project_id,
                created_by=actx.actor.id,
                summary=str(parsed.get("summary", "Proposed changes")),
                files=safe_files,
                agent_run_id=actx.run.id,
            )
            patch_id = str(proposal.id)

        output_json = {
            "message": str(parsed.get("summary", "")),
            "patch_id": patch_id,
            "file_count": len(safe_files),
        }
        return output_json, []
