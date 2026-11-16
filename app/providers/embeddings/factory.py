from app.core.config import Settings
from app.providers.embeddings.base import EmbeddingProvider
from app.providers.embeddings.bedrock import BedrockEmbeddings
from app.providers.embeddings.fake import FakeEmbeddings


# Factory: picks the embedding implementation from config; services only see the interface.
def create_embeddings(settings: Settings) -> EmbeddingProvider:
    if settings.embedding_provider == "bedrock":
        return BedrockEmbeddings(settings.bedrock_embedding_model, settings.aws_region or "")
    return FakeEmbeddings()
