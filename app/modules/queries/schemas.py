from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.core.schemas import ApiModel


class QueryRequest(ApiModel):
    question: str = Field(min_length=1, max_length=2000)
    top_k: int | None = Field(default=None, ge=1, le=20)


class QueryOut(ApiModel):
    id: UUID
    question: str
    answer: str
    top_k: int
    source_chunk_ids: list[UUID]
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: Decimal
    latency_ms: int
    status: str
    created_at: datetime
