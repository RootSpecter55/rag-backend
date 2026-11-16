from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.auth import CurrentTenant
from app.core.pagination import PageParams, page_params
from app.modules.chunks.controller import ChunksController


def chunks_router(controller: ChunksController, current_tenant: Callable[..., Any]) -> APIRouter:
    router = APIRouter(tags=["chunks"])
    Tenant = Annotated[CurrentTenant, Depends(current_tenant)]

    @router.get("/documents/{document_id}/chunks", summary="A document's chunks, in order")
    async def list_chunks(
        document_id: UUID, tenant: Tenant, page: Annotated[PageParams, Depends(page_params)]
    ) -> dict[str, Any]:
        return await controller.list_for_document(tenant, document_id, page)

    @router.get("/chunks/{chunk_id}", summary="Get one chunk")
    async def get_chunk(chunk_id: UUID, tenant: Tenant) -> dict[str, Any]:
        return await controller.get(tenant, chunk_id)

    return router
