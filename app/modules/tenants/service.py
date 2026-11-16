from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentTenant
from app.core.db import Database
from app.core.errors import NotFoundError
from app.core.pagination import PageParams
from app.core.security import generate_api_key, hash_key
from app.modules.tenants.models import Tenant
from app.modules.tenants.repository import TenantRepository
from app.modules.tenants.schemas import TenantCreate, TenantOut, TenantUpdate, TenantWithKey


class TenantsService:
    def __init__(self, db: Database, tenants: TenantRepository, default_query_limit: int) -> None:
        self._db = db
        self._tenants = tenants
        self._default_limit = default_query_limit

    async def create(self, data: TenantCreate) -> TenantWithKey:
        key, key_hash = generate_api_key()
        limit = data.monthly_query_limit
        async with self._db.transaction() as session:
            tenant = await self._tenants.add(
                session,
                Tenant(
                    name=data.name,
                    api_key_hash=key_hash,
                    monthly_query_limit=self._default_limit if limit is None else limit,
                ),
            )
        return TenantWithKey(tenant=TenantOut.model_validate(tenant), api_key=key)

    async def list(self, page: PageParams) -> tuple[list[TenantOut], int]:
        async with self._db.transaction() as session:
            rows, total = await self._tenants.list(
                session, order_by=Tenant.created_at, offset=page.offset, limit=page.page_size
            )
        return [TenantOut.model_validate(t) for t in rows], total

    async def get(self, tenant_id: UUID) -> TenantOut:
        async with self._db.transaction() as session:
            tenant = await self._require(session, tenant_id)
        return TenantOut.model_validate(tenant)

    async def update(self, tenant_id: UUID, data: TenantUpdate) -> TenantOut:
        async with self._db.transaction() as session:
            tenant = await self._require(session, tenant_id)
            if data.name is not None:
                tenant.name = data.name
            if data.monthly_query_limit is not None:
                tenant.monthly_query_limit = data.monthly_query_limit
        return TenantOut.model_validate(tenant)

    async def rotate_key(self, tenant_id: UUID) -> TenantWithKey:
        """Issues a new key; the old one stops working immediately."""
        key, key_hash = generate_api_key()
        async with self._db.transaction() as session:
            tenant = await self._require(session, tenant_id)
            tenant.api_key_hash = key_hash
        return TenantWithKey(tenant=TenantOut.model_validate(tenant), api_key=key)

    async def delete(self, tenant_id: UUID) -> None:
        """Deletes the tenant with its documents, chunks and queries (database cascade).

        Stored files are not removed here; see the README's known limitations.
        """
        async with self._db.transaction() as session:
            await self._tenants.delete(session, await self._require(session, tenant_id))

    async def resolve(self, api_key: str) -> CurrentTenant | None:
        """Used by tenant auth: maps a raw API key to its tenant, by hash."""
        async with self._db.transaction() as session:
            tenant = await self._tenants.get_by_key_hash(session, hash_key(api_key))
        if tenant is None:
            return None
        return CurrentTenant(tenant.id, tenant.name, tenant.monthly_query_limit)

    async def _require(self, session: AsyncSession, tenant_id: UUID) -> Tenant:
        tenant = await self._tenants.get(session, tenant_id)
        if tenant is None:
            raise NotFoundError("Tenant")
        return tenant
