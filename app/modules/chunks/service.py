from uuid import UUID

from app.core.db import Database
from app.core.errors import NotFoundError
from app.core.pagination import PageParams
from app.modules.chunks.models import Chunk
from app.modules.chunks.repository import ChunkRepository
from app.modules.chunks.schemas import ChunkOut
from app.modules.documents.repository import DocumentRepository


class ChunksService:
    def __init__(
        self, db: Database, chunks: ChunkRepository, documents: DocumentRepository
    ) -> None:
        self._db = db
        self._chunks = chunks
        self._documents = documents

    async def list_for_document(
        self, tenant_id: UUID, document_id: UUID, page: PageParams
    ) -> tuple[list[ChunkOut], int]:
        async with self._db.transaction() as session:
            if not await self._documents.get_for_tenant(session, document_id, tenant_id):
                raise NotFoundError("Document")
            rows, total = await self._chunks.list(
                session,
                Chunk.document_id == document_id,
                order_by=Chunk.ordinal,
                offset=page.offset,
                limit=page.page_size,
            )
        return [ChunkOut.model_validate(c) for c in rows], total

    async def get(self, tenant_id: UUID, chunk_id: UUID) -> ChunkOut:
        async with self._db.transaction() as session:
            chunk = await self._chunks.get_for_tenant(session, chunk_id, tenant_id)
        if chunk is None:
            raise NotFoundError("Chunk")
        return ChunkOut.model_validate(chunk)
