from datetime import datetime
from uuid import UUID

from app.core.schemas import ApiModel


class DocumentOut(ApiModel):
    id: UUID
    filename: str
    content_type: str
    size_bytes: int
    status: str
    chunk_count: int
    error: str | None
    created_at: datetime
