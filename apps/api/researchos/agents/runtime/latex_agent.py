"""LaTeX writing agent: chat replies and tracked-change selection ops.

Two modes, keyed on ``context["op"]``:

* Chat (no op): today's behavior, verbatim — free-text guidance for the paper
  assistant, ``{"message": output_text}``.
* Selection op (rewrite/expand/condense/fix_grammar/continue_writing/custom):
  a strict JSON output contract (``_SELECTION_OP_SCHEMA``); ``finalize``
  persists a ``DocumentSuggestion`` (proposed) — the AI never silently
  replaces text; the user accepts or rejects.

The first user-message line (``SELECTION_OP_INPUT: {...}``) is the
machine-readable contract the mock LLM provider parses — do not reformat it.
"""

from __future__ import annotations

import json

from researchos.agents.enums import AgentType
from researchos.agents.llm import LLMMessage
from researchos.documents.suggestions import SuggestionService

from .base import Agent, AgentContext

_CHAT_SYSTEM = (
    "You are an academic writing assistant for LaTeX papers. Improve clarity and "
    "academic tone. Do not invent citations; mark speculative claims as assumptions."
)

_SELECTION_OP_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "replacement": {"type": "string"},
        "rationale": {"type": "string"},
    },
    "required": ["replacement", "rationale"],
}

_OP_PREAMBLE = (
    "You are an academic LaTeX writing assistant. Output ONLY a JSON object "
    'matching the schema {"replacement": string, "rationale": string}. '
    "Preserve LaTeX commands, math, labels and citation keys verbatim unless "
    "the instruction targets them. Never invent \\cite keys."
)

_OP_DIRECTIVES: dict[str, str] = {
    "rewrite": (
        "Rewrite the selection to improve clarity and academic tone. Keep the "
        "same meaning and stay within 20% of the original length."
    ),
    "expand": (
        "Expand the selection by elaborating with 2-4 additional sentences. "
        "Mark speculative claims explicitly as assumptions."
    ),
    "condense": (
        "Condense the selection to at most 50% of its length. Keep all citations."
    ),
    "fix_grammar": "Fix grammar, spelling and spacing only. Make minimal edits.",
    "continue_writing": (
        "Write the next 2-4 sentences continuing the text shown in 'Context "
        "before'. Return them as the replacement."
    ),
    "custom": "Follow the user's instruction for the selection.",
}


class LatexAgent(Agent):
    agent_type = AgentType.LATEX
    allowed_tools: list[str] = []
    response_schema: dict | None = None

    async def build_messages(self, actx: AgentContext) -> list[LLMMessage]:
        op = actx.context.get("op")
        if not op:
            # Chat mode: unchanged legacy behavior for the paper assistant.
            self.response_schema = None
            selection = str(actx.context.get("selection", "")).strip()
            user = actx.message
            if selection:
                user = f"{actx.message}\n\nSelected text:\n{selection}"
            return [
                LLMMessage(role="system", content=_CHAT_SYSTEM),
                LLMMessage(role="user", content=user),
            ]

        # Instance attribute is legal: the runtime reads ``agent.response_schema``
        # only after ``build_messages``.
        self.response_schema = _SELECTION_OP_SCHEMA
        directive = _OP_DIRECTIVES.get(str(op), _OP_DIRECTIVES["custom"])
        selection_text = str(actx.context.get("selection_text", ""))
        instruction = str(actx.context.get("instruction") or "")
        context_before = str(actx.context.get("context_before", ""))
        context_after = str(actx.context.get("context_after", ""))
        header = "SELECTION_OP_INPUT: " + json.dumps(
            {"op": str(op), "selection": selection_text, "instruction": instruction}
        )
        user = (
            f"{header}\n"
            "\n"
            "Context before:\n"
            f"{context_before}\n"
            "Selection:\n"
            f"{selection_text}\n"
            "Context after:\n"
            f"{context_after}"
        )
        return [
            LLMMessage(role="system", content=f"{_OP_PREAMBLE} {directive}"),
            LLMMessage(role="user", content=user),
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
        op = actx.context.get("op")
        if not op:
            return {"message": output_text}, []

        unstructured = False
        try:
            parsed = json.loads(output_text)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            if "replacement" not in parsed:
                # Schema-shaped output without a replacement (e.g. an unextended
                # mock returning the critic object): fail the run honestly
                # rather than persisting an empty suggestion as success.
                raise ValueError("Selection-op output is missing the 'replacement' key.")
            replacement = str(parsed["replacement"])
            rationale = str(parsed.get("rationale") or "")
        else:
            # Unparsable output: keep it reviewable — the human accept gate
            # makes this safe (nothing applies without accept).
            replacement = output_text.strip()
            rationale = ""
            unstructured = True

        suggestion = await SuggestionService(actx.db).create_from_run(
            run=actx.run,
            context=actx.context,
            replacement=replacement,
            rationale=rationale,
        )
        output_json: dict = {
            "message": rationale or f"Proposed a {op} suggestion.",
            "suggestion_id": str(suggestion.id),
            "path": actx.context.get("path"),
            "op": str(op),
        }
        if unstructured:
            output_json["unstructured"] = True
        return output_json, []
