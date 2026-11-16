from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_repository import BaseRepository
from app.modules.documents.models import Document


class DocumentRepository(BaseRepository[Document]):
    model = Document

    async def get_for_tenant(
        self, session: AsyncSession, document_id: UUID, tenant_id: UUID
    ) -> Document | None:
        """A document only if it belongs to the tenant, so ids from other tenants look missing."""
        return await session.scalar(
            select(Document).where(Document.id == document_id, Document.tenant_id == tenant_id)
        )
