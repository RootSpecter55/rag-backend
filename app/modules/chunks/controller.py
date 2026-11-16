from typing import Any
from uuid import UUID

from app.core.auth import CurrentTenant
from app.core.pagination import PageParams, data_envelope, page_envelope
from app.modules.chunks.service import ChunksService


class ChunksController:
    def __init__(self, service: ChunksService) -> None:
        self._service = service

    async def list_for_document(
        self, tenant: CurrentTenant, document_id: UUID, page: PageParams
    ) -> dict[str, Any]:
        items, total = await self._service.list_for_document(tenant.id, document_id, page)
        return page_envelope([c.to_json() for c in items], total, page)

    async def get(self, tenant: CurrentTenant, chunk_id: UUID) -> dict[str, Any]:
        return data_envelope((await self._service.get(tenant.id, chunk_id)).to_json())
