"""Anthropic LLM adapter (enabled by configuration only).

This adapter is never exercised by the test suite (which always uses the mock
provider). It is imported lazily by the factory and requires both the
``anthropic`` package and an API key. The model id comes from ``LLM_MODEL`` and
is never hardcoded.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from researchos.common.config import get_settings
from researchos.common.errors import AppError

from .base import LLMMessage, LLMTool, StreamDone, StreamEvent, TextDelta, ToolCall, Usage


class AnthropicProvider:
    name = "anthropic"

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.anthropic_api_key:
            raise AppError(
                "ANTHROPIC_API_KEY is required for the anthropic provider.",
                code="config_error",
                http_status=500,
            )
        if not settings.llm_model or settings.llm_model == "mock-model":
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

        self._model = settings.llm_model
        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def stream(
        self,
        *,
        messages: list[LLMMessage],
        tools: list[LLMTool] | None = None,
        response_schema: dict | None = None,
    ) -> AsyncIterator[StreamEvent]:  # pragma: no cover - requires real key
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
        kwargs: dict = {"model": self._model, "max_tokens": 1024, "messages": api_messages}
        if system:
            kwargs["system"] = system
        if api_tools:
            kwargs["tools"] = api_tools

        async with self._client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield TextDelta(text)
            final = await stream.get_final_message()
            for block in final.content:
                if getattr(block, "type", None) == "tool_use":
                    yield ToolCall(id=block.id, name=block.name, arguments=dict(block.input))
            usage = getattr(final, "usage", None)
            if usage is not None:
                yield Usage(
                    input_tokens=getattr(usage, "input_tokens", 0),
                    output_tokens=getattr(usage, "output_tokens", 0),
                )
            if final.stop_reason == "tool_use":
                yield StreamDone(stop_reason="tool_use")
            else:
                yield StreamDone(stop_reason="stop")


def _to_anthropic_messages(messages: list[LLMMessage]) -> list[dict]:  # pragma: no cover
    out: list[dict] = []
    for msg in messages:
        if msg.role == "system":
            continue
        if msg.role == "tool":
            out.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": msg.tool_call_id or "",
                            "content": msg.content,
                        }
                    ],
                }
            )
        else:
            out.append({"role": msg.role, "content": msg.content})
    return out
