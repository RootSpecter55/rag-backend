from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class LLMUsage:
    """Sent once, after the last text chunk."""

    input_tokens: int
    output_tokens: int
    stop_reason: str | None
    model: str


class LLMProvider(Protocol):
    """Streams an answer. Implementations: deterministic fake (default), Anthropic, Bedrock.

    `stream` yields text chunks (str) and finishes with exactly one LLMUsage.
    """

    name: str
    model: str

    def stream(self, system: str, user: str) -> AsyncIterator[str | LLMUsage]: ...
