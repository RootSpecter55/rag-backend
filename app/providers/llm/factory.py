from anthropic import AsyncAnthropic, AsyncAnthropicBedrockMantle, BetaRefusalFallbackMiddleware

from app.core.config import Settings
from app.providers.llm.anthropic_llm import ClaudeLLM
from app.providers.llm.base import LLMProvider
from app.providers.llm.fake import FakeLLM


# Factory: picks the LLM implementation from config; the query service only sees the interface.
def create_llm(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "anthropic":
        return ClaudeLLM(
            # Credentials come from the environment (ANTHROPIC_API_KEY or an `ant auth` profile).
            AsyncAnthropic(),
            name="anthropic",
            model=settings.anthropic_model,
            effort=settings.llm_effort,
            max_tokens=settings.llm_max_tokens,
            server_side_fallbacks=True,
        )
    if settings.llm_provider == "bedrock":
        client = AsyncAnthropicBedrockMantle(
            aws_region=settings.aws_region,
            # Bedrock has no server-side fallbacks, so refusals fall back on the client side.
            middleware=[
                BetaRefusalFallbackMiddleware([{"model": settings.bedrock_fallback_model}])
            ],
        )
        return ClaudeLLM(
            client,
            name="bedrock",
            model=settings.bedrock_llm_model,
            effort=settings.llm_effort,
            max_tokens=settings.llm_max_tokens,
            server_side_fallbacks=False,
        )
    return FakeLLM()
