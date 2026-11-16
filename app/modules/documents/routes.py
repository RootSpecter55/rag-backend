from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Response, UploadFile

from app.core.auth import CurrentTenant
from app.core.pagination import PageParams, page_params
from app.modules.documents.controller import DocumentsController


def documents_router(
    controller: DocumentsController, current_tenant: Callable[..., Any]
) -> APIRouter:
    router = APIRouter(prefix="/documents", tags=["documents"])
    Tenant = Annotated[CurrentTenant, Depends(current_tenant)]

    @router.post(
        "", status_code=201, summary="Upload a .txt or .md file; it is chunked and embedded"
    )
    async def upload(tenant: Tenant, file: Annotated[UploadFile, File()]) -> dict[str, Any]:
        return await controller.upload(tenant, file)

    @router.get("", summary="List your documents, newest first")
    async def list_documents(
        tenant: Tenant, page: Annotated[PageParams, Depends(page_params)]
    ) -> dict[str, Any]:
        return await controller.list(tenant, page)

    @router.get("/{document_id}", summary="Get a document")
    async def get(document_id: UUID, tenant: Tenant) -> dict[str, Any]:
        return await controller.get(tenant, document_id)

    @router.delete("/{document_id}", status_code=204, summary="Delete a document and its chunks")
    async def delete(document_id: UUID, tenant: Tenant) -> Response:
        await controller.delete(tenant, document_id)
        return Response(status_code=204)

    return router
