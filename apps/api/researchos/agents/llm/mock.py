# ruff: noqa: E501
"""Deterministic mock LLM provider.

Drives the full agent loop with no external calls or API keys, and *validates*
the message protocol the way a real API would (strict mode, default on), so
tests reject the exact message shapes Anthropic/OpenAI reject.

Deterministic scripts covered (cross-partition contract, CONSOLIDATION risk 7):

1. Multi-turn coding tool use (coding-git CP-4): ``workspace.tree`` →
   ``workspace.read`` of the first file → a no-op-safe SEARCH/REPLACE modify of
   that file; empty tree or no read tool → the legacy ``AGENT_NOTES.md`` create.
2. Selection ops (writing CP-1): schema with a ``replacement`` property →
   deterministic ``_mock_op`` transform of the ``SELECTION_OP_INPUT:`` payload.
3. Gap ideas (research CP-4): schema with an ``ideas`` property → one fixed
   gap-typed idea citing keys from tool-shaped context messages.
4. Section-grounded explain (research CP-5f): a prompt containing the
   ``## Referenced paper sections`` block → prose echoing the section heading
   and the paper key.
"""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator, Iterable

from .base import LLMMessage, LLMTool, StreamDone, StreamEvent, TextDelta, ToolCall, Usage

SKILLS_HEADER = "## Active skills"
SECTIONS_HEADER = "## Referenced paper sections"

_SECTION_PAPER_RE = re.compile(r"^Paper: (\S+)", re.MULTILINE)
_SECTION_HEADING_RE = re.compile(r"^### \[S\d+\] (.+)$", re.MULTILINE)
_READING_SECTION_RE = re.compile(
    r"\[SECTION id=([0-9a-f-]+)[^\]]*\]\n(.*?)(?=\n\[SECTION|\Z)",
    re.DOTALL,
)
_REVIEW_EVIDENCE_RE = re.compile(
    r"\[EVIDENCE paper_id=([0-9a-f-]+) section_id=([0-9a-f-]+)[^\]]*\]\n"
    r"(.*?)(?=\n\[EVIDENCE|\Z)",
    re.DOTALL,
)
_SELECTION_OP_PREFIX = "SELECTION_OP_INPUT: "
_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE
)
_CITATION_KEY_RE = re.compile(r'"citation_key"\s*:\s*"([^"]+)"')


def _last_user_text(messages: list[LLMMessage]) -> str:
    for msg in reversed(messages):
        if msg.role == "user":
            return msg.content
    return ""


def _cited_keys_from_tools(messages: list[LLMMessage]) -> list[str]:
    keys: list[str] = []
    for msg in messages:
        if msg.role != "tool":
            continue
        try:
            data = json.loads(msg.content)
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict):
            continue
        for item in data.get("results", []):
            source = item.get("source")
            ext = item.get("external_id")
            if source and ext:
                keys.append(f"{source}:{ext}")
    return keys


def _tool_results(messages: list[LLMMessage]) -> list[dict]:
    """Parsed JSON payloads of every tool message, in order."""

    out: list[dict] = []
    for msg in messages:
        if msg.role != "tool":
            continue
        try:
            data = json.loads(msg.content)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            out.append(data)
    return out


def _called_tool_names(messages: list[LLMMessage]) -> set[str]:
    called: set[str] = set()
    for msg in messages:
        if msg.role == "assistant" and msg.tool_calls:
            called.update(c.name for c in msg.tool_calls)
    return called


def _validate_protocol(messages: list[LLMMessage]) -> None:
    """Reject message shapes a real API would reject (see base.py invariants).

    A tool message that answers no assistant ``tool_calls`` turn is tolerated
    as a context document ONLY when it does not directly follow an assistant
    turn (or a consumed tool-result block) — the exact shapes the old runtime
    bug produced remain rejected.
    """

    seen_non_system = False
    consumed: set[int] = set()
    i = 0
    while i < len(messages):
        msg = messages[i]
        if msg.role == "system":
            if seen_non_system:
                raise ValueError(
                    "mock protocol violation: system message after non-system messages"
                )
            i += 1
            continue
        seen_non_system = True
        if msg.role == "assistant" and msg.tool_calls:
            for offset, call in enumerate(msg.tool_calls):
                j = i + 1 + offset
                if j >= len(messages) or messages[j].role != "tool":
                    raise ValueError(
                        "mock protocol violation: assistant tool_calls not followed "
                        f"by {len(msg.tool_calls)} tool message(s)"
                    )
                if messages[j].tool_call_id != call.id:
                    raise ValueError(
                        "mock protocol violation: tool message id "
                        f"{messages[j].tool_call_id!r} does not match tool_call id "
                        f"{call.id!r} (order matters)"
                    )
                consumed.add(j)
            i += 1 + len(msg.tool_calls)
            continue
        if msg.role == "tool":
            prev = messages[i - 1] if i > 0 else None
            if prev is not None and (
                prev.role == "assistant" or (prev.role == "tool" and (i - 1) in consumed)
            ):
                raise ValueError(
                    "mock protocol violation: tool message at index "
                    f"{i} follows an assistant turn without matching tool_calls"
                )
        i += 1


# --- Coding script (coding-git CP-4) -----------------------------------------
def _first_file_path(nodes: Iterable[dict]) -> str | None:
    for node in nodes:
        if node.get("type") == "file":
            return str(node.get("path", "")) or None
        child = _first_file_path(node.get("children", []) or [])
        if child:
            return child
    return None


def _coding_script_call(
    messages: list[LLMMessage], tool_names: list[str], called: set[str]
) -> ToolCall | None:
    if "workspace.tree" not in called:
        return ToolCall(id=f"call_{len(called) + 1}", name="workspace.tree", arguments={})
    if "workspace.read" in tool_names and "workspace.read" not in called:
        tree_path: str | None = None
        for result in _tool_results(messages):
            tree = result.get("tree")
            if isinstance(tree, dict):
                tree_path = _first_file_path(tree.get("nodes", []) or [])
        if tree_path:
            return ToolCall(
                id=f"call_{len(called) + 1}",
                name="workspace.read",
                arguments={"path": tree_path},
            )
    return None


def _coding_answer(messages: list[LLMMessage]) -> dict:
    read: dict | None = None
    for result in _tool_results(messages):
        if "sha" in result and "content" in result and "path" in result:
            read = result
    if read is not None and read.get("content"):
        first_line = str(read["content"]).splitlines()[0] + "\n"
        return {
            "summary": "Mock edit",
            "files": [
                {
                    "path": read["path"],
                    "change_type": "modify",
                    "base_sha": read["sha"],
                    "edits": [{"search": first_line, "replace": first_line}],
                }
            ],
        }
    # Empty tree / no readable file: propose a small, safe create.
    return {
        "summary": "Add a notes file describing the requested change.",
        "files": [
            {
                "path": "AGENT_NOTES.md",
                "change_type": "create",
                "base_sha": None,
                "new_content": (
                    "# Agent Notes\n\nThis file was proposed by the coding agent for review.\n"
                ),
            }
        ],
    }


# --- Selection ops (writing CP-1) --------------------------------------------
def _mock_op(op: str, selection: str, instruction: str | None) -> str:
    if op == "fix_grammar":
        text = re.sub(r"\s+", " ", selection).strip()
        if text:
            text = text[0].upper() + text[1:]
        if text and text[-1] not in ".!?":
            text += "."
        return text
    if op == "condense":
        idx = selection.find(". ")
        if idx != -1:
            return selection[: idx + 2]
        return " ".join(selection.split()[:15]) + "."
    if op == "expand":
        return (
            selection
            + " Moreover, this observation holds under the additional settings considered."
        )
    if op == "rewrite":
        if not selection:
            return "This work shows that "
        return "This work shows that " + selection[:1].lower() + selection[1:]
    if op == "continue_writing":
        return "Building on the previous paragraph, we next describe the evaluation protocol."
    if op == "custom":
        return selection + " [addressed: " + (instruction or "")[:40] + "]"
    # Unknown op: behave like fix_grammar (deterministic, never empty-handed).
    return _mock_op("fix_grammar", selection, instruction)


def _selection_op_object(messages: list[LLMMessage]) -> dict:
    last_user = _last_user_text(messages)
    payload: dict | None = None
    for line in last_user.splitlines():
        if line.startswith(_SELECTION_OP_PREFIX):
            try:
                candidate = json.loads(line[len(_SELECTION_OP_PREFIX) :])
            except json.JSONDecodeError:
                candidate = None
            if isinstance(candidate, dict):
                payload = candidate
    if payload is None:
        op = "fix_grammar"
        selection = last_user
        instruction = None
    else:
        op = str(payload.get("op", "fix_grammar"))
        selection = str(payload.get("selection", ""))
        raw_instruction = payload.get("instruction")
        instruction = None if raw_instruction is None else str(raw_instruction)
    return {
        "replacement": _mock_op(op, selection, instruction),
        "rationale": f"Mock {op} suggestion (deterministic).",
    }


# --- Section-grounded explain (research CP-5f) --------------------------------
def _explain_text(messages: list[LLMMessage]) -> str | None:
    block: str | None = None
    for msg in messages:
        if SECTIONS_HEADER in msg.content:
            block = msg.content
            break
    if block is None:
        return None
    paper = _SECTION_PAPER_RE.search(block)
    heading = _SECTION_HEADING_RE.search(block)
    key = paper.group(1) if paper else "unknown:unknown"
    title = heading.group(1) if heading else "the referenced section"
    return (
        f'The section "{title}" of {key} explains the following: this is a '
        "deterministic mock explanation grounded only in the injected section "
        f"bodies of {key}."
    )


class MockLLMProvider:
    name = "mock"

    def __init__(self, strict_protocol: bool = True) -> None:
        self.strict_protocol = strict_protocol

    async def stream(
        self,
        *,
        messages: list[LLMMessage],
        tools: list[LLMTool] | None = None,
        response_schema: dict | None = None,
        force_structured: bool = False,
    ) -> AsyncIterator[StreamEvent]:
        if self.strict_protocol:
            _validate_protocol(messages)

        called = _called_tool_names(messages)
        tool_names = [t.name for t in (tools or [])]

        if tools and not force_structured:
            call: ToolCall | None = None
            if "workspace.tree" in tool_names:
                call = _coding_script_call(messages, tool_names, called)
            elif len(called) < 2:
                remaining = [name for name in tool_names if name not in called]
                if remaining:
                    if "knowledge.rag_search" in remaining:
                        name = "knowledge.rag_search"
                    elif "paper.search" in remaining:
                        name = "paper.search"
                    else:
                        name = remaining[0]
                    args: dict = {}
                    if name in {"paper.search", "knowledge.rag_search"}:
                        args = {"query": _last_user_text(messages), "limit": 5}
                    call = ToolCall(id=f"call_{len(called) + 1}", name=name, arguments=args)
            if call is not None:
                yield call
                yield Usage(input_tokens=12, output_tokens=0)
                yield StreamDone(stop_reason="tool_use")
                return

        cited = _cited_keys_from_tools(messages)
        skills_active = any(m.role == "system" and SKILLS_HEADER in m.content for m in messages)

        if response_schema is not None:
            props = (response_schema or {}).get("properties", {})
            if "files" in props:
                obj: dict = _coding_answer(messages)
            elif "replacement" in props:
                obj = _selection_op_object(messages)
            elif "ideas" in props:
                first_line = (_last_user_text(messages).splitlines() or [""])[0]
                obj = {
                    "ideas": [
                        {
                            "title": f"Bridge gap: {first_line[:60]}",
                            "description": ("Deterministic mock idea grounded in provided papers."),
                            "hypothesis": "H1",
                            "gap_type": "coverage",
                            "supporting_paper_keys": cited[:2],
                        }
                    ]
                }
            elif "directions" in props:
                source = _last_user_text(messages)
                paper_ids = list(dict.fromkeys(_UUID_RE.findall(source)))
                obj = {
                    "directions": [
                        {
                            "title": "Evidence-ranked controlled pilot",
                            "hypothesis": "A single-component intervention improves the primary metric under fixed budget.",
                            "rationale": "Prioritize a small falsifiable change before full-scale evaluation.",
                            "source_paper_ids": paper_ids[:2],
                            "benchmark_plan": ["Use the highest-credibility reported benchmark"],
                            "ablation_plan": ["Remove only the proposed component"],
                            "pilot_scope": "one benchmark, one seed, ten percent of the training budget",
                            "score": 0.82,
                        }
                    ]
                }
            elif "primary_benchmark" in props and "pilot_matrix" in props:
                obj = {
                    "benchmarks": [
                        {"name": "Reported evaluation setting", "evidence_status": "grounded"}
                    ],
                    "primary_benchmark": "Reported evaluation setting",
                    "primary_metric": "primary_score",
                    "pilot_matrix": [{"arm": "baseline"}, {"arm": "candidate"}],
                    "full_matrix": [
                        {"arm": "baseline", "seeds": [1, 2, 3]},
                        {"arm": "candidate", "seeds": [1, 2, 3]},
                    ],
                    "ablations": [{"component": "proposed_component", "setting": "removed"}],
                    "decision_rules": [
                        "Scale only after the candidate beats baseline under the fixed pilot budget."
                    ],
                    "stop_conditions": [
                        "Stop on invalid metrics, leakage, timeout, or no improvement."
                    ],
                }
            elif "verdict" in props and "blocking_findings" in props:
                obj = {
                    "verdict": "pass",
                    "confidence": 0.8,
                    "blocking_findings": [],
                    "non_blocking_findings": [
                        "Run the declared full seed matrix before a paper claim."
                    ],
                    "evidence_checked": ["task artifacts", "recorded run metrics", "git commit"],
                    "next_action": "Advance to the next bounded task.",
                }
            elif "decision" in props and "required_approvals" in props:
                obj = {
                    "decision": "continue_pilot",
                    "direction_rank": 1,
                    "rationale": "The bounded pilot is the cheapest next information-gain step.",
                    "next_task": "Complete and review the small-batch pilot.",
                    "required_approvals": [],
                    "budget_note": "Do not scale until a Viewer pass is recorded.",
                }
            elif "latex" in props and "claim_links" in props:
                keys = list(dict.fromkeys(_CITATION_KEY_RE.findall(_last_user_text(messages))))
                obj = {
                    "venue": "generic",
                    "section": "methods",
                    "latex": "\\section{Methods}\\nWe evaluate the proposed method using the recorded protocol.",
                    "citation_keys": keys[:2],
                    "claim_links": [],
                    "unresolved_evidence": ["Add verified result values after full experiments."],
                }
            elif "mermaid" in props and "figures" in props:
                obj = {
                    "mermaid": "flowchart LR\n    evidence[Paper evidence] --> idea[Ranked idea]\n    idea --> code[Implementation]\n    code --> pilot[Small-batch pilot]\n    pilot --> review[Viewer review]\n    review --> full[Full experiment]",
                    "figures": [],
                    "tables": [],
                    "captions": ["Evidence-bound research and evaluation workflow."],
                    "source_run_ids": [],
                }
            elif "progress_percent" in props and "active_agents" in props:
                source = _last_user_text(messages)
                match = re.search(r'"deterministic_progress_percent"\s*:\s*([0-9.]+)', source)
                progress = float(match.group(1)) if match else 0.0
                obj = {
                    "progress_percent": progress,
                    "active_agents": [],
                    "completed": [],
                    "blockers": [],
                    "next_actions": ["Dispatch the next ready task."],
                    "eta_basis": "deterministic task graph only",
                }
            elif "research_question" in props:
                source = _last_user_text(messages)
                section = _READING_SECTION_RE.search(source)
                section_id = section.group(1) if section else ""
                body = " ".join((section.group(2) if section else "").split())
                quote = body[: min(120, len(body))]
                obj = {
                    "summary": "A deterministic, source-grounded reading-card summary.",
                    "research_question": "What problem does the supplied paper address?",
                    "method_flow": ["Define the task", "Apply the proposed method", "Evaluate"],
                    "experimental_setup": [
                        "The supplied sections do not report a complete experimental setup"
                    ],
                    "key_results": [
                        "The supplied sections do not report a complete numerical result"
                    ],
                    "conclusions": ["The conclusion is limited to the supplied section evidence"],
                    "strengths": ["The method is described in the supplied sections"],
                    "limitations": ["Only supplied sections were available for this card"],
                    "reproducibility": ["Verify data splits, hyperparameters, and random seeds"],
                    "github_repositories": [],
                    "paper_ideas": [
                        {
                            "title": "Test the supplied method under a controlled shift",
                            "hypothesis": "The method retains its reported advantage under shift.",
                            "motivation": "Derived from the supplied limitation.",
                            "section_id": section_id,
                            "quote": quote,
                            "inference": True,
                        }
                    ],
                    "benchmarks": [
                        {
                            "name": "Reported evaluation setting",
                            "task": "paper-specific task",
                            "metric": "not fully reported in the supplied excerpt",
                            "section_id": section_id,
                            "quote": quote,
                        }
                    ],
                    "ablation_findings": [],
                    "knowledge_tuples": [
                        {
                            "kind": "summary",
                            "head": "paper",
                            "relation": "addresses",
                            "tail": "the supplied research question",
                            "section_id": section_id,
                            "quote": quote,
                            "inference": False,
                        },
                        {
                            "kind": "idea",
                            "head": "controlled distribution shift",
                            "relation": "tests",
                            "tail": "method robustness",
                            "section_id": section_id,
                            "quote": quote,
                            "inference": True,
                        },
                    ],
                    "claims": [
                        {
                            "text": "The card is grounded in a supplied paper section.",
                            "section_id": section_id,
                            "quote": quote,
                            "inference": False,
                        }
                    ],
                }
            elif "body" in props and "claims" in props:
                source = _last_user_text(messages)
                evidence = _REVIEW_EVIDENCE_RE.search(source)
                paper_id = evidence.group(1) if evidence else ""
                section_id = evidence.group(2) if evidence else ""
                evidence_body = " ".join((evidence.group(3) if evidence else "").split())
                quote = evidence_body[: min(120, len(evidence_body))]
                obj = {
                    "body": (
                        "The supplied literature provides evidence relevant to this section. "
                        "This deterministic draft is ready for human synthesis and review."
                    ),
                    "claims": [
                        {
                            "text": (
                                "The section draft uses evidence from a selected mission paper."
                            ),
                            "paper_id": paper_id,
                            "section_id": section_id,
                            "quote": quote,
                            "inference": False,
                        }
                    ],
                }
            elif "variables" in props and "matrix" in props:
                source = _last_user_text(messages)
                evidence = _REVIEW_EVIDENCE_RE.search(source)
                paper_id = evidence.group(1) if evidence else None
                section_id = evidence.group(2) if evidence else None
                evidence_body = " ".join((evidence.group(3) if evidence else "").split())
                quote = evidence_body[: min(120, len(evidence_body))]
                grounded = bool(paper_id and section_id and quote)
                obj = {
                    "title": "Evidence-bound primary experiment",
                    "research_gap": "The reviewed literature leaves a testable performance gap.",
                    "hypothesis": (
                        "The proposed treatment improves the primary metric over the baseline."
                    ),
                    "variables": [
                        {
                            "name": "Treatment",
                            "role": "independent",
                            "operational_definition": "Enable the proposed method.",
                            "levels_or_measurement": "off / on",
                        },
                        {
                            "name": "Primary score",
                            "role": "dependent",
                            "operational_definition": "Held-out evaluation score.",
                            "levels_or_measurement": "continuous",
                        },
                        {
                            "name": "Training budget",
                            "role": "control",
                            "operational_definition": "Equal compute for all groups.",
                            "levels_or_measurement": "fixed",
                        },
                    ],
                    "baselines": [
                        {
                            "name": "Literature baseline",
                            "rationale": "Selected from mission evidence.",
                            "source_paper_id": paper_id,
                            "evidence_section_id": section_id,
                            "evidence_quote": quote,
                            "evidence_status": "grounded" if grounded else "needs_evidence",
                        }
                    ],
                    "datasets": [
                        {
                            "name": "Evaluation dataset",
                            "split": "train/validation/test with a held-out test set",
                            "preprocessing": "Fit preprocessing on training data only.",
                            "license_or_access": "Verify before execution.",
                        }
                    ],
                    "metrics": [
                        {"name": "primary_score", "direction": "max", "primary": True, "unit": ""}
                    ],
                    "matrix": [
                        {
                            "name": "Main comparison",
                            "factors": {"method": ["baseline", "proposed"]},
                            "repetitions": 3,
                            "seed_policy": "Use the same three declared seeds.",
                            "compute_budget": "Equal budget per arm.",
                        }
                    ],
                    "decision_rules": [
                        "Accept the hypothesis only when the primary score improves consistently."
                    ],
                    "stop_conditions": [
                        "Stop after the predeclared matrix and repetitions finish."
                    ],
                    "risks": [
                        {
                            "risk": "Dataset leakage",
                            "mitigation": "Keep the test set inaccessible during development.",
                            "severity": "high",
                        }
                    ],
                    "reproducibility": [
                        "Record code revision, environment, data version, seeds, and full config."
                    ],
                }
            elif "sql" in props and "explanation" in props:
                obj = {
                    "sql": "SELECT * FROM dataset LIMIT 20",
                    "explanation": (
                        "Read-only preview generated from the registered dataset schema."
                    ),
                }
            else:
                # Critic agent: citations reference real retrieved papers.
                obj = {
                    "novelty_summary": (
                        "The idea has partial novelty; related work exists in the retrieved papers."
                    ),
                    "weaknesses": ["Limited evaluation scope", "Unclear baseline comparison"],
                    "missing_baselines": ["A strong supervised baseline"],
                    "dataset_risks": ["Potential dataset license constraints"],
                    "reproducibility": ["Specify random seeds", "Release training config"],
                    "citations": cited,
                }
            if skills_active:
                obj["_skills_active"] = True
            text = json.dumps(obj)
        else:
            explain = _explain_text(messages)
            if explain is not None:
                text = explain
            else:
                # Research synthesis. The runtime derives citations from tool results.
                n = len(cited)
                text = (
                    f"Based on {n} retrieved paper(s), here is a brief synthesis of "
                    "the current literature relevant to your query."
                )
            if skills_active:
                text = "[skills-active] " + text

        # Stream the text in a few deltas to exercise token streaming.
        for chunk in _chunks(text, 24):
            yield TextDelta(chunk)
        yield Usage(input_tokens=20, output_tokens=max(1, len(text) // 4))
        yield StreamDone(stop_reason="stop")


def _chunks(text: str, size: int) -> list[str]:
    return [text[i : i + size] for i in range(0, len(text), size)] or [""]
