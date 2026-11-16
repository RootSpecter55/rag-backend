from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_repository import BaseRepository
from app.modules.tenants.models import Tenant


class TenantRepository(BaseRepository[Tenant]):
    model = Tenant

    async def get_by_key_hash(self, session: AsyncSession, key_hash: str) -> Tenant | None:
        return await session.scalar(select(Tenant).where(Tenant.api_key_hash == key_hash))
