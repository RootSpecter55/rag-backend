from uuid import UUID

from app.core.schemas import ApiModel


class ChunkOut(ApiModel):
    id: UUID
    document_id: UUID
    ordinal: int
    text: str


class RetrievedChunk(ApiModel):
    """A search result: the chunk, its document's filename, and how close it was."""

    id: UUID
    document_id: UUID
    filename: str
    ordinal: int
    text: str
    distance: float
