import re
from collections.abc import AsyncIterator

from app.providers.llm.base import LLMUsage

# The text of source [1]: everything after its "[1] (filename)" line, up to the next source
# or the question.
_SOURCE_ONE = re.compile(r"^\[1\][^\n]*\n(.*?)(?=\n\n\[2\]|\n\nQuestion:|\Z)", re.M | re.S)


class FakeLLM:
    """Deterministic stand-in for a model, so the API and tests run with no API key.

    It answers with the first sentence of source [1] (skipping markdown headings) and cites it.
    Token counts are word counts, which keeps cost tracking testable but says nothing about real
    tokenisers.
    """

    name = "fake"
    model = "fake-llm"

    def _answer(self, user: str) -> str:
        match = _SOURCE_ONE.search(user)
        if not match:
            return "I could not find this in the provided sources."
        lines = [
            line.strip()
            for line in match.group(1).splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        text = " ".join(lines)
        first_sentence = re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0]
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
