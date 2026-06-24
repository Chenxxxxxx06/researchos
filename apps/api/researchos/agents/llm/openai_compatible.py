"""OpenAI-compatible LLM provider adapter.

Supports any API that speaks the OpenAI /v1/chat/completions format:
OpenAI, Anthropic Messages API, vLLM, Ollama, Groq, DeepSeek, etc.
The base URL, model, and API key come from the per-project LLMProviderConfig,
with environment-variable fallback for backwards compatibility.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx

from researchos.common.config import get_settings
from researchos.common.errors import AppError

from .base import LLMMessage, LLMTool, StreamDone, StreamEvent, TextDelta, ToolCall, Usage


class OpenAICompatibleProvider:
    name = "openai_compatible"

    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
    ) -> None:
        settings = get_settings()
        self.base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        self.model = model or settings.llm_model
        self.api_key = api_key or settings.anthropic_api_key
        if not self.api_key:
            raise AppError(
                "No API key configured. Set it in Settings → LLM Provider.",
                code="config_error",
                http_status=500,
            )

    async def stream(
        self,
        *,
        messages: list[LLMMessage],
        tools: list[LLMTool] | None = None,
        response_schema: dict | None = None,
    ) -> AsyncIterator[StreamEvent]:
        body: dict = {
            "model": self.model,
            "messages": _to_openai(messages),
            "stream": True,
        }
        if tools:
            body["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                }
                for t in tools
            ]

        async with httpx.AsyncClient(timeout=60) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                json=body,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            ) as resp:
                if resp.status_code >= 400:
                    text = (await resp.aread()).decode(errors="replace")
                    raise AppError(
                        f"LLM API error ({resp.status_code}): {text[:500]}",
                        code="llm_error",
                        http_status=502,
                    )

                tool_calls_acc: dict[int, dict] = {}
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    import json as _json

                    try:
                        chunk = _json.loads(data)
                    except _json.JSONDecodeError:
                        continue

                    choices = chunk.get("choices", [])
                    for choice in choices:
                        delta = choice.get("delta", {})
                        if delta.get("content"):
                            yield TextDelta(delta["content"])
                        tc_items = delta.get("tool_calls") or []
                        for tc in tc_items:
                            idx = tc.get("index", 0)
                            if idx not in tool_calls_acc:
                                tool_calls_acc[idx] = {
                                    "id": tc.get("id", ""),
                                    "name": "",
                                    "arguments": "",
                                }
                            acc = tool_calls_acc[idx]
                            if tc.get("id"):
                                acc["id"] = tc["id"]
                            fn = tc.get("function") or {}
                            acc["name"] = acc["name"] + (fn.get("name", ""))
                            acc["arguments"] = acc["arguments"] + (fn.get("arguments", ""))

                    if "usage" in chunk and chunk["usage"]:
                        u = chunk["usage"]
                        yield Usage(
                            input_tokens=u.get("prompt_tokens") or 0,
                            output_tokens=u.get("completion_tokens") or 0,
                        )

                for acc in tool_calls_acc.values():
                    if acc["name"]:
                        try:
                            args = _json.loads(acc["arguments"] or "{}")
                        except _json.JSONDecodeError:
                            args = {}
                        yield ToolCall(id=acc["id"], name=acc["name"], arguments=args)

                finish = choice.get("finish_reason") if choices else "stop"
                if finish == "tool_calls":
                    yield StreamDone(stop_reason="tool_use")
                else:
                    yield StreamDone(stop_reason="stop")


def _to_openai(messages: list[LLMMessage]) -> list[dict]:
    out: list[dict] = []
    for msg in messages:
        if msg.role == "system":
            out.append({"role": "system", "content": msg.content})
        elif msg.role == "tool":
            out.append(
                {
                    "role": "tool",
                    "content": msg.content,
                    "tool_call_id": msg.tool_call_id or "",
                }
            )
        elif msg.role == "assistant":
            out.append({"role": "assistant", "content": msg.content})
        else:
            out.append({"role": "user", "content": msg.content})
    return out
