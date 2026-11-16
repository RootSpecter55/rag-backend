from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.core.auth import CurrentTenant
from app.core.pagination import PageParams, page_params
from app.modules.queries.controller import QueriesController
from app.modules.queries.schemas import QueryRequest


def queries_router(controller: QueriesController, current_tenant: Callable[..., Any]) -> APIRouter:
    router = APIRouter(prefix="/queries", tags=["queries"])
    Tenant = Annotated[CurrentTenant, Depends(current_tenant)]

    @router.post(
        "",
        summary="Ask a question; the answer streams as Server-Sent Events",
        response_class=StreamingResponse,
    )
    async def ask(body: QueryRequest, tenant: Tenant) -> StreamingResponse:
        return await controller.ask(tenant, body)

    @router.get("", summary="Past queries, newest first")
    async def list_queries(
        tenant: Tenant, page: Annotated[PageParams, Depends(page_params)]
    ) -> dict[str, Any]:
        return await controller.list(tenant, page)

    @router.get("/{query_id}", summary="One past query with its answer, tokens and cost")
    async def get(query_id: UUID, tenant: Tenant) -> dict[str, Any]:
        return await controller.get(tenant, query_id)

    return router
