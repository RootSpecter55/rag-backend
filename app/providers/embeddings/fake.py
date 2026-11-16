import hashlib
import math
import re

from app.providers.embeddings.base import EMBEDDING_DIMENSION

_WORD = re.compile(r"[a-z0-9]+")


class FakeEmbeddings:
    """Deterministic embeddings with no model or network: the "hashing trick".

    Each word is hashed to one of the 1024 dimensions (with a +1/-1 sign) and counted; the vector
    is then normalised. Texts sharing words end up close in cosine distance, so retrieval in
    tests and local runs behaves sensibly on word overlap. It knows nothing about meaning, so
    synonyms do not match.
    """

    name = "fake"

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * EMBEDDING_DIMENSION
        for word in _WORD.findall(text.lower()):
            digest = hashlib.sha256(word.encode()).digest()
            index = int.from_bytes(digest[:4], "big") % EMBEDDING_DIMENSION
            vector[index] += 1.0 if digest[4] % 2 == 0 else -1.0
        norm = math.sqrt(sum(v * v for v in vector))
        return [v / norm for v in vector] if norm else vector

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]
