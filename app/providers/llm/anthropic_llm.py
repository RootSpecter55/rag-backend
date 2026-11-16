from collections.abc import AsyncIterator
from contextlib import AbstractContextManager, nullcontext
from typing import Any

from anthropic import AsyncAnthropic, AsyncAnthropicBedrockMantle, BetaFallbackState

from app.providers.llm.base import LLMUsage


class ClaudeLLM:
    """Streams an answer from Claude with the official Anthropic SDK.

    The same class serves the Anthropic API (AsyncAnthropic) and Amazon Bedrock
    (AsyncAnthropicBedrockMantle): both clients expose the same Messages API.

    Refusals: if the model declines, the API can re-run the request on a fallback model inside
    the same call. On the Anthropic API that is the server-side `fallbacks="default"` option;
    Bedrock does not support it, so the Bedrock client is built with the SDK's client-side
    refusal-fallback middleware instead (see factory.py). A refusal that survives the fallback
    ends with stop_reason "refusal", which the query service records.

    Not covered by the test suite: it needs credentials and spends real money per call.
    """

    def __init__(
        self,
        client: AsyncAnthropic | AsyncAnthropicBedrockMantle,
        *,
        name: str,
        model: str,
        effort: str,
        max_tokens: int,
        server_side_fallbacks: bool,
    ) -> None:
        self._client = client
        self.name = name
        self.model = model
        self._effort = effort
        self._max_tokens = max_tokens
        self._server_side_fallbacks = server_side_fallbacks

    async def stream(self, system: str, user: str) -> AsyncIterator[str | LLMUsage]:
        options: dict[str, Any] = {}
        # The client-side middleware pins fallbacks through this per-request state.
        fallback_scope: AbstractContextManager[Any] = BetaFallbackState()
        if self._server_side_fallbacks:
            options = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}
            fallback_scope = nullcontext()

        with fallback_scope:
            async with self._client.beta.messages.stream(
                model=self.model,
                max_tokens=self._max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                # Effort is set explicitly; adaptive thinking is the default on this model.
                output_config={"effort": self._effort},
                **options,
            ) as stream:
                async for text in stream.text_stream:
                    yield text
                final = await stream.get_final_message()

        yield LLMUsage(
            input_tokens=final.usage.input_tokens,
            output_tokens=final.usage.output_tokens,
            stop_reason=final.stop_reason,
            model=final.model,  # the model that actually served it, after any fallback
        )
