from typing import Protocol

# Fixed so the database column has one size. Bedrock Titan Text Embeddings v2 supports 1024,
# and the fake provider produces the same size.
EMBEDDING_DIMENSION = 1024


class EmbeddingProvider(Protocol):
    """Turns texts into vectors. Implementations: deterministic fake (default) and Bedrock."""

    name: str

    async def embed(self, texts: list[str]) -> list[list[float]]: ...
