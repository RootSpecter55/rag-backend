from typing import Any
from uuid import UUID

from fastapi import UploadFile

from app.core.auth import CurrentTenant
from app.core.pagination import PageParams, data_envelope, page_envelope
from app.modules.documents.service import DocumentsService


class DocumentsController:
    def __init__(self, service: DocumentsService) -> None:
        self._service = service

    async def upload(self, tenant: CurrentTenant, file: UploadFile) -> dict[str, Any]:
        data = await file.read()
        document = await self._service.upload(
            tenant.id, file.filename or "upload.txt", file.content_type or "text/plain", data
        )
        return data_envelope(document.to_json())

    async def list(self, tenant: CurrentTenant, page: PageParams) -> dict[str, Any]:
        items, total = await self._service.list(tenant.id, page)
        return page_envelope([d.to_json() for d in items], total, page)

    async def get(self, tenant: CurrentTenant, document_id: UUID) -> dict[str, Any]:
        return data_envelope((await self._service.get(tenant.id, document_id)).to_json())

    async def delete(self, tenant: CurrentTenant, document_id: UUID) -> None:
        await self._service.delete(tenant.id, document_id)
