from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_repository import BaseRepository
from app.modules.chunks.models import Chunk
from app.modules.chunks.schemas import RetrievedChunk
from app.modules.documents.models import Document


class ChunkRepository(BaseRepository[Chunk]):
    model = Chunk

    async def add_all(self, session: AsyncSession, chunks: list[Chunk]) -> None:
        session.add_all(chunks)
        await session.flush()

    async def search(
        self, session: AsyncSession, tenant_id: UUID, embedding: list[float], top_k: int
    ) -> list[RetrievedChunk]:
        """The tenant's `top_k` chunks closest to `embedding` by cosine distance.

        The tenant filter is part of the query itself, so another tenant's chunks can never be
        returned, whatever the ranking.
        """
        distance = Chunk.embedding.cosine_distance(embedding).label("distance")
        rows = await session.execute(
            select(Chunk, Document.filename, distance)
            .join(Document, Document.id == Chunk.document_id)
            .where(Chunk.tenant_id == tenant_id)
            .order_by(distance)
            .limit(top_k)
        )
        return [
            RetrievedChunk(
                id=chunk.id,
                document_id=chunk.document_id,
                filename=filename,
                ordinal=chunk.ordinal,
                text=chunk.text,
                distance=float(dist),
            )
            for chunk, filename, dist in rows
        ]

    async def get_for_tenant(
        self, session: AsyncSession, chunk_id: UUID, tenant_id: UUID
    ) -> Chunk | None:
        return await session.scalar(
            select(Chunk).where(Chunk.id == chunk_id, Chunk.tenant_id == tenant_id)
        )
