from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Every setting comes from environment variables and is validated at startup."""

    model_config = SettingsConfigDict(extra="ignore", case_sensitive=False)

    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"

    database_url: str = Field(pattern=r"^postgresql\+asyncpg://")
    admin_api_key: str = Field(min_length=32)

    # Storage (where uploaded files go)
    storage_provider: Literal["local", "s3"] = "local"
    local_storage_dir: str = "./data/uploads"
    s3_bucket: str | None = None
    aws_region: str | None = None

    # Embeddings
    embedding_provider: Literal["fake", "bedrock"] = "fake"
    bedrock_embedding_model: str = "amazon.titan-embed-text-v2:0"

    # LLM
    llm_provider: Literal["fake", "anthropic", "bedrock"] = "fake"
    anthropic_model: str = "claude-opus-5-5"
    bedrock_llm_model: str = "anthropic.claude-opus-5-5"
    bedrock_fallback_model: str = "anthropic.claude-opus-4-8"
    llm_effort: Literal["low", "medium", "high", "xhigh", "max"] = "medium"
    llm_max_tokens: int = Field(default=64_000, gt=0)
    # Prices are configuration, not code: set them from your provider's current price list.
    llm_input_usd_per_mtok: float = Field(default=0.0, ge=0)
    llm_output_usd_per_mtok: float = Field(default=0.0, ge=0)

    # Ingestion and retrieval
    chunk_size_chars: int = Field(default=1200, ge=200)
    chunk_overlap_chars: int = Field(default=200, ge=0)
    max_upload_bytes: int = Field(default=2_000_000, gt=0)
    default_top_k: int = Field(default=5, ge=1, le=20)
    default_monthly_query_limit: int = Field(default=1000, ge=0)

    @model_validator(mode="after")
    def check_provider_settings(self) -> Self:
        problems = []
        if self.storage_provider == "s3" and not (self.s3_bucket and self.aws_region):
            problems.append("STORAGE_PROVIDER=s3 needs S3_BUCKET and AWS_REGION")
        uses_bedrock = "bedrock" in (self.embedding_provider, self.llm_provider)
        if uses_bedrock and not self.aws_region:
            problems.append("Bedrock providers need AWS_REGION")
        if self.chunk_overlap_chars >= self.chunk_size_chars:
            problems.append("CHUNK_OVERLAP_CHARS must be smaller than CHUNK_SIZE_CHARS")
        if problems:
            raise ValueError("; ".join(problems))
        return self


@lru_cache
def get_settings() -> Settings:
    """Singleton: settings are parsed and validated once, then shared."""
    return Settings()  # type: ignore[call-arg]  # values come from the environment
