"""Deterministic mock LLM provider.

Drives the full agent loop with no external calls or API keys: it requests the
first available tool, then (on the second pass, once a tool result is present)
produces either a short text answer or a structured JSON object. Used as the
default provider and in all tests.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from .base import LLMMessage, LLMTool, StreamDone, StreamEvent, TextDelta, ToolCall, Usage


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
        for item in data.get("results", []):
            source = item.get("source")
            ext = item.get("external_id")
            if source and ext:
                keys.append(f"{source}:{ext}")
    return keys


class MockLLMProvider:
    name = "mock"

    async def stream(
        self,
        *,
        messages: list[LLMMessage],
        tools: list[LLMTool] | None = None,
        response_schema: dict | None = None,
    ) -> AsyncIterator[StreamEvent]:
        has_tool_result = any(m.role == "tool" for m in messages)

        # First pass: call the first available tool.
        if tools and not has_tool_result:
            tool = tools[0]
            args: dict = {}
            if tool.name == "paper.search":
                args = {"query": _last_user_text(messages), "limit": 5}
            yield ToolCall(id="call_1", name=tool.name, arguments=args)
            yield Usage(input_tokens=12, output_tokens=0)
            yield StreamDone(stop_reason="tool_use")
            return

        cited = _cited_keys_from_tools(messages)

        if response_schema is not None:
            props = (response_schema or {}).get("properties", {})
            if "files" in props:
                # Coding agent: propose a small, safe patch (creates a notes file).
                obj: dict = {
                    "summary": "Add a notes file describing the requested change.",
                    "files": [
                        {
                            "path": "AGENT_NOTES.md",
                            "change_type": "create",
                            "base_sha": None,
                            "new_content": (
                                "# Agent Notes\n\n"
                                "This file was proposed by the coding agent for review.\n"
                            ),
                        }
                    ],
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
            text = json.dumps(obj)
        else:
            # Research synthesis. The runtime derives citations from tool results.
            n = len(cited)
            text = (
                f"Based on {n} retrieved paper(s), here is a brief synthesis of the "
                "current literature relevant to your query."
            )

        # Stream the text in a few deltas to exercise token streaming.
        for chunk in _chunks(text, 24):
            yield TextDelta(chunk)
        yield Usage(input_tokens=20, output_tokens=max(1, len(text) // 4))
        yield StreamDone(stop_reason="stop")


def _chunks(text: str, size: int) -> list[str]:
    return [text[i : i + size] for i in range(0, len(text), size)] or [""]
