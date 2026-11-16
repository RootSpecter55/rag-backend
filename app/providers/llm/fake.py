import re
from collections.abc import AsyncIterator

from app.providers.llm.base import LLMUsage

_FIRST_SOURCE = re.compile(r"^\[1\][^\n]*\n(.+?)(?:\n\n|\Z)", re.MULTILINE | re.DOTALL)


class FakeLLM:
    """Deterministic stand-in for a model, so the API and tests run with no API key.

    It answers with the first sentence of source [1] and cites it. Token counts are word counts,
    which keeps cost tracking testable but says nothing about real tokenisers.
    """

    name = "fake"
    model = "fake-llm"

    def _answer(self, user: str) -> str:
        match = _FIRST_SOURCE.search(user)
        if not match:
            return "I could not find this in the provided sources."
        first_sentence = re.split(r"(?<=[.!?])\s", match.group(1).strip(), maxsplit=1)[0]
        return f"According to [1]: {first_sentence}"

    async def stream(self, system: str, user: str) -> AsyncIterator[str | LLMUsage]:
        answer = self._answer(user)
        words = answer.split(" ")
        for i, word in enumerate(words):
            yield word if i == len(words) - 1 else word + " "
        yield LLMUsage(
            input_tokens=len(f"{system} {user}".split()),
            output_tokens=len(words),
            stop_reason="end_turn",
            model=self.model,
        )
