"""Pure tests for the LLM message protocol layer (no DB, no network).

Covers adapter round-trip conversion (tool_use pairing, merged tool results),
structured-output extraction, and the strict mock protocol validation that
rejects the exact message shapes real APIs reject.
"""

from __future__ import annotations

import json

import pytest

from researchos.agents.llm.anthropic import _to_anthropic_messages
from researchos.agents.llm.base import LLMMessage, ToolCall
from researchos.agents.llm.mock import _validate_protocol
from researchos.agents.llm.openai_compatible import _to_openai
from researchos.agents.llm.structured import (
    StructuredOutputError,
    _check_required,
    extract_json,
)


def _tool_turn_history() -> list[LLMMessage]:
    return [
        LLMMessage(role="system", content="sys"),
        LLMMessage(role="user", content="do the thing"),
        LLMMessage(
            role="assistant",
            content="Let me look.",
            tool_calls=[
                ToolCall(id="call_1", name="library.list", arguments={}),
                ToolCall(id="call_2", name="paper.search", arguments={"query": "q"}),
            ],
        ),
        LLMMessage(
            role="tool", name="library.list", tool_call_id="call_1", content='{"results": []}'
        ),
        LLMMessage(
            role="tool", name="paper.search", tool_call_id="call_2", content='{"results": []}'
        ),
    ]


# --- Anthropic conversion ----------------------------------------------------
def test_anthropic_assistant_tool_calls_become_tool_use_blocks() -> None:
    out = _to_anthropic_messages(_tool_turn_history())
    # system excluded entirely.
    assert all("system" != m["role"] for m in out)
    assistant = out[1]
    assert assistant["role"] == "assistant"
    types = [b["type"] for b in assistant["content"]]
    assert types == ["text", "tool_use", "tool_use"]
    assert assistant["content"][1]["id"] == "call_1"
    assert assistant["content"][2]["input"] == {"query": "q"}


def test_anthropic_merges_consecutive_tool_results_into_one_user_turn() -> None:
    out = _to_anthropic_messages(_tool_turn_history())
    # user question, assistant turn, ONE merged results turn.
    assert len(out) == 3
    results = out[2]
    assert results["role"] == "user"
    ids = [b["tool_use_id"] for b in results["content"]]
    assert ids == ["call_1", "call_2"]
    assert all(b["type"] == "tool_result" for b in results["content"])


def test_anthropic_skips_empty_assistant_filler() -> None:
    messages = [
        LLMMessage(role="user", content="hi"),
        LLMMessage(role="assistant", content="   "),
        LLMMessage(role="user", content="again"),
    ]
    out = _to_anthropic_messages(messages)
    assert [m["role"] for m in out] == ["user", "user"]


def test_anthropic_contextual_tool_doc_becomes_user_turn() -> None:
    # The gap-matrix caller's exact shape: a tool-shaped context document
    # (WITH an id) that answers no assistant tool_calls turn.
    messages = [
        LLMMessage(role="system", content="ground"),
        LLMMessage(role="tool", content='{"results": []}', tool_call_id="gap_context_1"),
        LLMMessage(role="user", content="gaps?"),
    ]
    out = _to_anthropic_messages(messages)
    assert [m["role"] for m in out] == ["user", "user"]
    assert out[0]["content"] == '{"results": []}'
    # OpenAI adapter: same context document becomes a plain user turn too.
    oa = _to_openai(messages)
    assert [m["role"] for m in oa] == ["system", "user", "user"]


# --- OpenAI conversion -------------------------------------------------------
def test_openai_serializes_tool_calls_with_json_arguments() -> None:
    out = _to_openai(_tool_turn_history())
    assistant = out[2]
    assert assistant["role"] == "assistant"
    calls = assistant["tool_calls"]
    assert [c["id"] for c in calls] == ["call_1", "call_2"]
    assert calls[1]["function"]["arguments"] == json.dumps({"query": "q"})
    assert out[3] == {"role": "tool", "content": '{"results": []}', "tool_call_id": "call_1"}


def test_openai_empty_assistant_tool_turn_has_null_content() -> None:
    messages = [
        LLMMessage(
            role="assistant",
            content="",
            tool_calls=[ToolCall(id="c1", name="t", arguments={})],
        ),
        LLMMessage(role="tool", tool_call_id="c1", content="{}"),
    ]
    out = _to_openai(messages)
    assert out[0]["content"] is None


# --- extract_json ------------------------------------------------------------
def test_extract_json_direct_object() -> None:
    assert extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_markdown_fence() -> None:
    assert extract_json('Here you go:\n```json\n{"a": 1}\n```\nDone.') == {"a": 1}


def test_extract_json_prose_wrapped_balanced_object() -> None:
    assert extract_json('Sure! The answer is {"a": {"b": 2}} as requested.') == {"a": {"b": 2}}


def test_extract_json_nested_braces_inside_strings() -> None:
    text = 'prefix {"msg": "uses { and } and \\" freely", "n": 1} suffix'
    assert extract_json(text) == {"msg": 'uses { and } and " freely', "n": 1}


def test_extract_json_rejects_list() -> None:
    with pytest.raises(StructuredOutputError):
        extract_json("[1, 2, 3]")


def test_extract_json_garbage_raises() -> None:
    with pytest.raises(StructuredOutputError):
        extract_json("no json here at all")


def test_check_required_missing_key_raises() -> None:
    schema = {"type": "object", "required": ["novelty_summary"]}
    _check_required({"novelty_summary": "x"}, schema)
    with pytest.raises(StructuredOutputError, match="missing required keys"):
        _check_required({"other": 1}, schema)


# --- strict mock protocol validation -----------------------------------------
def test_mock_accepts_runtime_shaped_history() -> None:
    _validate_protocol(_tool_turn_history())  # must not raise


def test_mock_accepts_gap_matrix_context_document() -> None:
    # system -> tool-shaped context (with id, no assistant pairing) -> user.
    _validate_protocol(
        [
            LLMMessage(role="system", content="ground"),
            LLMMessage(
                role="tool",
                name="library.context",
                tool_call_id="gap_context_1",
                content='{"results": []}',
            ),
            LLMMessage(role="user", content="gaps?"),
        ]
    )


def test_mock_rejects_old_empty_assistant_before_tool_shape() -> None:
    # The pre-rewrite runtime bug: empty assistant with NO tool_calls, then a
    # paired tool message. Real APIs reject this; the strict mock must too.
    old_bug = [
        LLMMessage(role="system", content="sys"),
        LLMMessage(role="user", content="q"),
        LLMMessage(role="assistant", content=""),
        LLMMessage(role="tool", name="t", tool_call_id="call_1", content="{}"),
    ]
    with pytest.raises(ValueError, match="mock protocol violation"):
        _validate_protocol(old_bug)


def test_mock_rejects_short_tool_result_block() -> None:
    short = [
        LLMMessage(role="user", content="q"),
        LLMMessage(
            role="assistant",
            content="",
            tool_calls=[
                ToolCall(id="c1", name="a", arguments={}),
                ToolCall(id="c2", name="b", arguments={}),
            ],
        ),
        LLMMessage(role="tool", tool_call_id="c1", content="{}"),
    ]
    with pytest.raises(ValueError, match="mock protocol violation"):
        _validate_protocol(short)


def test_mock_rejects_out_of_order_tool_ids() -> None:
    swapped = [
        LLMMessage(role="user", content="q"),
        LLMMessage(
            role="assistant",
            content="",
            tool_calls=[
                ToolCall(id="c1", name="a", arguments={}),
                ToolCall(id="c2", name="b", arguments={}),
            ],
        ),
        LLMMessage(role="tool", tool_call_id="c2", content="{}"),
        LLMMessage(role="tool", tool_call_id="c1", content="{}"),
    ]
    with pytest.raises(ValueError, match="mock protocol violation"):
        _validate_protocol(swapped)


def test_mock_rejects_system_after_non_system() -> None:
    late_system = [
        LLMMessage(role="user", content="q"),
        LLMMessage(role="system", content="late"),
    ]
    with pytest.raises(ValueError, match="mock protocol violation"):
        _validate_protocol(late_system)
