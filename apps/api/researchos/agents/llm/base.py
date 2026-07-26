"""LLM provider protocol and streaming event types.

Providers stream a sequence of events. The runtime consumes them, emitting token
events, collecting tool calls, and (for structured agents) parsing the final
text. This abstraction lets the mock provider drive the full agent loop with no
external calls or API keys.

Message-protocol invariants (enforced by the strict mock provider and required
by the real APIs):

1. An assistant message with ``tool_calls`` is followed by exactly
   ``len(tool_calls)`` messages of ``role="tool"``, in the same order, each with
   a ``tool_call_id`` matching one of the ids.
2. Any other ``role="tool"`` message is a caller-provided *context document*
   (e.g. the gap-matrix paper list); it must not directly follow an assistant
   turn, and the real adapters render it as a plain user turn.
3. ``system`` messages appear only at the start of the list.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable

Role = Literal["system", "user", "assistant", "tool"]


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


@dataclass
class LLMMessage:
    role: Role
    content: str
    name: str | None = None
    tool_call_id: str | None = None
    # Assistant tool-use turns: the calls the model emitted in this turn.
    tool_calls: list[ToolCall] | None = None


def paired_tool_indexes(messages: list[LLMMessage]) -> set[int]:
    """Indexes of tool messages that answer an assistant ``tool_calls`` turn.

    Tool messages NOT in this set are context documents; adapters render them
    as plain user turns (real APIs reject unpaired tool results).
    """

    out: set[int] = set()
    for i, msg in enumerate(messages):
        if msg.role == "assistant" and msg.tool_calls:
            for offset in range(len(msg.tool_calls)):
                j = i + 1 + offset
                if j < len(messages) and messages[j].role == "tool":
                    out.add(j)
    return out


@runtime_checkable
class LLMProvider(Protocol):
    name: str

    def stream(
        self,
        *,
        messages: list[LLMMessage],
        tools: list[LLMTool] | None = None,
        response_schema: dict | None = None,
        force_structured: bool = False,
    ) -> AsyncIterator[StreamEvent]: ...
