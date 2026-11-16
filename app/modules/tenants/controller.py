from typing import Any
from uuid import UUID

from app.core.auth import CurrentTenant
from app.core.pagination import PageParams, data_envelope, page_envelope
from app.modules.tenants.schemas import TenantCreate, TenantUpdate
from app.modules.tenants.service import TenantsService


class TenantsController:
    """Translates between HTTP and the service: envelopes in, envelopes out. No business rules."""

    def __init__(self, service: TenantsService) -> None:
        self._service = service

    async def create(self, body: TenantCreate) -> dict[str, Any]:
        return data_envelope((await self._service.create(body)).to_json())

    async def list(self, page: PageParams) -> dict[str, Any]:
        items, total = await self._service.list(page)
        return page_envelope([t.to_json() for t in items], total, page)

    async def get(self, tenant_id: UUID) -> dict[str, Any]:
        return data_envelope((await self._service.get(tenant_id)).to_json())

    async def update(self, tenant_id: UUID, body: TenantUpdate) -> dict[str, Any]:
        return data_envelope((await self._service.update(tenant_id, body)).to_json())

    async def rotate_key(self, tenant_id: UUID) -> dict[str, Any]:
        return data_envelope((await self._service.rotate_key(tenant_id)).to_json())

    async def delete(self, tenant_id: UUID) -> None:
        await self._service.delete(tenant_id)

    async def me(self, tenant: CurrentTenant) -> dict[str, Any]:
        return data_envelope((await self._service.get(tenant.id)).to_json())
