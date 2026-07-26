"""OpenAI-compatible LLM provider adapter.

Supports any API that speaks the OpenAI /v1/chat/completions format:
OpenAI, vLLM, Ollama, Groq, DeepSeek, etc. The base URL, model, and API key
come from the per-project LLMProviderConfig, with environment-variable
fallback (``OPENAI_API_KEY`` — never the Anthropic key, which must not leak
to arbitrary user-configured base URLs).
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

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


class OpenAICompatibleProvider:
    name = "openai_compatible"

    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        settings = get_settings()
        # A non-empty base_url is a user-supplied endpoint; the platform env key
        # must never be sent there. The env fallback applies only when the caller
        # did not specify a custom endpoint (base_url empty/None → canonical host).
        custom_base = bool(base_url)
        self.base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        self.model = model or settings.llm_model
        if api_key:
            self.api_key = api_key
        elif not custom_base:
            self.api_key = settings.openai_api_key
        else:
            self.api_key = ""
        self._http_client = http_client
        if not self.api_key:
            raise AppError(
                "An explicit API key is required when a custom base URL is configured."
                if custom_base
                else "No API key configured. Set it in Settings → LLM Provider.",
                code="config_error",
                http_status=500,
            )

    def _build_body(
        self,
        messages: list[LLMMessage],
        tools: list[LLMTool] | None,
        response_schema: dict | None,
        force_structured: bool,
        *,
        include_response_format: bool,
    ) -> dict:
        settings = get_settings()
        body: dict = {
            "model": self.model,
            "messages": _to_openai(messages),
            "stream": True,
            "stream_options": {"include_usage": True},
            "max_tokens": settings.llm_max_output_tokens,
        }
        if tools and not force_structured:
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
        if response_schema is not None and include_response_format:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "agent_output",
                    "schema": response_schema,
                    "strict": False,
                },
            }
        return body

    async def stream(
        self,
        *,
        messages: list[LLMMessage],
        tools: list[LLMTool] | None = None,
        response_schema: dict | None = None,
        force_structured: bool = False,
    ) -> AsyncIterator[StreamEvent]:
        settings = get_settings()
        client = self._http_client
        owns_client = client is None
        if client is None:
            client = httpx.AsyncClient(timeout=settings.llm_request_timeout_seconds)
        try:
            # Compatibility fallback: some servers reject response_format; retry
            # once without it. Safe — no events are yielded before the status
            # check on the first response.
            attempts = [True]
            if response_schema is not None:
                attempts.append(False)
            for attempt_index, include_rf in enumerate(attempts):
                body = self._build_body(
                    messages,
                    tools,
                    response_schema,
                    force_structured,
                    include_response_format=include_rf,
                )
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
                        is_last = attempt_index == len(attempts) - 1
                        if (
                            not is_last
                            and 400 <= resp.status_code < 500
                            and "response_format" in text.lower()
                        ):
                            continue
                        raise AppError(
                            f"LLM API error ({resp.status_code}): {text[:500]}",
                            code="llm_error",
                            http_status=502,
                        )

                    async for event in self._consume_stream(resp):
                        yield event
                    return
        finally:
            if owns_client:
                await client.aclose()

    @staticmethod
    async def _consume_stream(resp: httpx.Response) -> AsyncIterator[StreamEvent]:
        tool_calls_acc: dict[int, dict] = {}
        finish_reason: str | None = None
        async for line in resp.aiter_lines():
            if not line.startswith("data: "):
                continue
            data = line[6:]
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
            except json.JSONDecodeError:
                continue

            for choice in chunk.get("choices", []):
                finish_reason = choice.get("finish_reason") or finish_reason
                delta = choice.get("delta", {})
                if delta.get("content"):
                    yield TextDelta(delta["content"])
                for tc in delta.get("tool_calls") or []:
                    idx = tc.get("index", 0)
                    if idx not in tool_calls_acc:
                        tool_calls_acc[idx] = {"id": tc.get("id", ""), "name": "", "arguments": ""}
                    acc = tool_calls_acc[idx]
                    if tc.get("id"):
                        acc["id"] = tc["id"]
                    fn = tc.get("function") or {}
                    acc["name"] = acc["name"] + (fn.get("name", ""))
                    acc["arguments"] = acc["arguments"] + (fn.get("arguments", ""))

            if chunk.get("usage"):
                u = chunk["usage"]
                yield Usage(
                    input_tokens=u.get("prompt_tokens") or 0,
                    output_tokens=u.get("completion_tokens") or 0,
                )

        for acc in tool_calls_acc.values():
            if acc["name"]:
                try:
                    args = json.loads(acc["arguments"] or "{}")
                except json.JSONDecodeError:
                    args = {}
                yield ToolCall(id=acc["id"], name=acc["name"], arguments=args)

        if finish_reason == "tool_calls":
            yield StreamDone(stop_reason="tool_use")
        else:
            yield StreamDone(stop_reason="stop")


def _to_openai(messages: list[LLMMessage]) -> list[dict]:
    paired = paired_tool_indexes(messages)
    out: list[dict] = []
    for i, msg in enumerate(messages):
        if msg.role == "system":
            out.append({"role": "system", "content": msg.content})
        elif msg.role == "tool":
            if i not in paired:
                # Context document (answers no tool_calls turn): plain user turn.
                out.append({"role": "user", "content": msg.content})
                continue
            out.append(
                {
                    "role": "tool",
                    "content": msg.content,
                    "tool_call_id": msg.tool_call_id or "",
                }
            )
        elif msg.role == "assistant":
            if msg.tool_calls:
                out.append(
                    {
                        "role": "assistant",
                        "content": msg.content or None,
                        "tool_calls": [
                            {
                                "id": c.id,
                                "type": "function",
                                "function": {
                                    "name": c.name,
                                    "arguments": json.dumps(c.arguments),
                                },
                            }
                            for c in msg.tool_calls
                        ],
                    }
                )
            else:
                out.append({"role": "assistant", "content": msg.content})
        else:
            out.append({"role": "user", "content": msg.content})
    return out
