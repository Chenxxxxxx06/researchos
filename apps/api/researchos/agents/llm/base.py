"""LLM provider protocol and streaming event types.

Providers stream a sequence of events. The runtime consumes them, emitting token
events, collecting tool calls, and (for structured agents) parsing the final
text. This abstraction lets the mock provider drive the full agent loop with no
external calls or API keys.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable

Role = Literal["system", "user", "assistant", "tool"]


@dataclass
class LLMMessage:
    role: Role
    content: str
    name: str | None = None
    tool_call_id: str | None = None


@dataclass
class LLMTool:
    name: str
    description: str
    parameters: dict = field(default_factory=dict)


# --- Streaming events --------------------------------------------------------
@dataclass
class TextDelta:
    text: str


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class StreamDone:
    stop_reason: Literal["stop", "tool_use"] = "stop"


StreamEvent = TextDelta | ToolCall | Usage | StreamDone


@runtime_checkable
class LLMProvider(Protocol):
    name: str

    def stream(
        self,
        *,
        messages: list[LLMMessage],
        tools: list[LLMTool] | None = None,
        response_schema: dict | None = None,
    ) -> AsyncIterator[StreamEvent]: ...
