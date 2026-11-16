from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_repository import BaseRepository
from app.modules.queries.models import Query


class QueryRepository(BaseRepository[Query]):
    model = Query

    async def count_since(self, session: AsyncSession, tenant_id: UUID, since: datetime) -> int:
        count = await session.scalar(
            select(func.count())
            .select_from(Query)
            .where(Query.tenant_id == tenant_id, Query.created_at >= since)
        )
        return count or 0

    async def get_for_tenant(
        self, session: AsyncSession, query_id: UUID, tenant_id: UUID
    ) -> Query | None:
        return await session.scalar(
            select(Query).where(Query.id == query_id, Query.tenant_id == tenant_id)
        )
