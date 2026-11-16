from typing import Any
from uuid import UUID

from app.core.auth import CurrentTenant
from app.core.pagination import data_envelope
from app.modules.usage.service import UsageService


class UsageController:
    def __init__(self, service: UsageService) -> None:
        self._service = service

    async def mine(self, tenant: CurrentTenant, month: str | None) -> dict[str, Any]:
        return data_envelope((await self._service.summary(tenant.id, month)).to_json())

    async def for_tenant(self, tenant_id: UUID, month: str | None) -> dict[str, Any]:
        return data_envelope((await self._service.summary(tenant_id, month)).to_json())
