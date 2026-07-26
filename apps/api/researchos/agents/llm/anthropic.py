"""Anthropic LLM adapter (enabled by configuration only).

This adapter is never exercised by the test suite (which always uses the mock
provider); its pure message-conversion helpers are. It is imported lazily by
the factory and requires both the ``anthropic`` package and an API key. Model,
key, and base URL may come from the per-project DB config with environment
fallback; the model id is never hardcoded.

Structured output is transmitted as a synthetic ``emit_result`` tool whose
input schema is the response schema; under ``force_structured`` the call is
forced via ``tool_choice`` so the final turn is guaranteed to be the JSON
object.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from researchos.common.config import get_settings
from researchos.common.errors import AppError

from .base import (
    LLMMessage,
    LLMTool,
    StreamDone,
    StreamEvent,
    TextDelta,
    ToolCall,
    Usage,
    paired_tool_indexes,
)

_EMIT_RESULT = "emit_result"


class AnthropicProvider:
    name = "anthropic"

    def __init__(
        self,
        *,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        settings = get_settings()
        # Never send the platform key to a user-supplied endpoint: the env-var
        # fallback applies ONLY to the canonical Anthropic host (base_url=None).
        # A custom base_url must carry its own explicit api_key.
        if api_key:
            resolved_key = api_key
        elif base_url is None:
            resolved_key = settings.anthropic_api_key
        else:
            resolved_key = ""
        resolved_model = model or settings.llm_model
        if not resolved_key:
            raise AppError(
                "An explicit api_key is required for the anthropic provider when a "
                "custom base_url is configured."
                if base_url is not None
                else "ANTHROPIC_API_KEY is required for the anthropic provider.",
                code="config_error",
                http_status=500,
            )
        if not resolved_model or resolved_model == "mock-model":
            raise AppError(
                "LLM_MODEL must be set to a real model id for the anthropic provider.",
                code="config_error",
                http_status=500,
            )
        try:
            from anthropic import AsyncAnthropic
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise AppError(
                "The 'anthropic' package is not installed.",
                code="config_error",
                http_status=500,
            ) from exc

        self._model = resolved_model
        client_kwargs: dict = {
            "api_key": resolved_key,
            "timeout": settings.llm_request_timeout_seconds,
        }
        if base_url:
            client_kwargs["base_url"] = base_url
        self._client = AsyncAnthropic(**client_kwargs)

    async def stream(
        self,
        *,
        messages: list[LLMMessage],
        tools: list[LLMTool] | None = None,
        response_schema: dict | None = None,
        force_structured: bool = False,
    ) -> AsyncIterator[StreamEvent]:  # pragma: no cover - requires real key
        settings = get_settings()
        system = "\n".join(m.content for m in messages if m.role == "system")
        api_messages = _to_anthropic_messages(messages)
        api_tools = [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.parameters or {"type": "object"},
            }
            for t in (tools or [])
        ]
        kwargs: dict = {
            "model": self._model,
            "max_tokens": settings.llm_max_output_tokens,
            "messages": api_messages,
        }
        if response_schema is not None:
            emit_tool = {
                "name": _EMIT_RESULT,
                "description": (
                    "Submit your final structured answer. Call exactly once when done."
                ),
                "input_schema": response_schema,
            }
            if force_structured:
                api_tools = [emit_tool]
                kwargs["tool_choice"] = {"type": "tool", "name": _EMIT_RESULT}
            else:
                api_tools = [*api_tools, emit_tool]
            system = (system + "\n" if system else "") + (
                "When you have your final answer, call the emit_result tool "
                "exactly once with it."
            )
        if system:
            kwargs["system"] = system
        if api_tools:
            kwargs["tools"] = api_tools

        async with self._client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield TextDelta(text)
            final = await stream.get_final_message()
            emitted_result = False
            for block in final.content:
                if getattr(block, "type", None) != "tool_use":
                    continue
                if block.name == _EMIT_RESULT:
                    # The structured answer is final text, not a tool round-trip.
                    emitted_result = True
                    yield TextDelta(json.dumps(dict(block.input)))
                else:
                    yield ToolCall(id=block.id, name=block.name, arguments=dict(block.input))
            usage = getattr(final, "usage", None)
            if usage is not None:
                yield Usage(
                    input_tokens=getattr(usage, "input_tokens", 0),
                    output_tokens=getattr(usage, "output_tokens", 0),
                )
            if final.stop_reason == "tool_use" and not emitted_result:
                yield StreamDone(stop_reason="tool_use")
            else:
                yield StreamDone(stop_reason="stop")


def _to_anthropic_messages(messages: list[LLMMessage]) -> list[dict]:
    """Convert runtime messages to the Anthropic Messages shape.

    Assistant tool-use turns become ``tool_use`` blocks; consecutive tool
    results are merged into ONE following user turn (required by the API);
    empty assistant filler is skipped; context-style tool messages (not paired
    with an assistant ``tool_calls`` turn) become plain user turns.
    """

    paired = paired_tool_indexes(messages)
    out: list[dict] = []
    pending_results: list[dict] = []

    def _flush_results() -> None:
        if pending_results:
            out.append({"role": "user", "content": list(pending_results)})
            pending_results.clear()

    for i, msg in enumerate(messages):
        if msg.role == "system":
            continue
        if msg.role == "tool":
            if i not in paired:
                _flush_results()
                out.append({"role": "user", "content": msg.content})
                continue
            pending_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": msg.tool_call_id or "",
                    "content": msg.content,
                }
            )
            continue
        _flush_results()
        if msg.role == "assistant":
            if msg.tool_calls:
                content: list[dict] = []
                if msg.content.strip():
                    content.append({"type": "text", "text": msg.content})
                content.extend(
                    {
                        "type": "tool_use",
                        "id": c.id,
                        "name": c.name,
                        "input": c.arguments,
                    }
                    for c in msg.tool_calls
                )
                out.append({"role": "assistant", "content": content})
            elif msg.content.strip():
                out.append({"role": "assistant", "content": msg.content})
            # Empty assistant filler with no tool calls is skipped entirely.
            continue
        out.append({"role": msg.role, "content": msg.content})
    _flush_results()
    return out
