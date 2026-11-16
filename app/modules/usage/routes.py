from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.auth import CurrentTenant
from app.modules.usage.controller import UsageController

Month = Annotated[
    str | None,
    Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$", description="YYYY-MM, default the current month"),
]


def usage_router(
    controller: UsageController,
    current_tenant: Callable[..., Any],
    require_admin: Callable[..., Any],
) -> APIRouter:
    router = APIRouter(tags=["usage"])

    @router.get("/usage", summary="Your queries, tokens and estimated cost for a month")
    async def mine(
        tenant: Annotated[CurrentTenant, Depends(current_tenant)], month: Month = None
    ) -> dict[str, Any]:
        return await controller.mine(tenant, month)

    @router.get(
        "/admin/tenants/{tenant_id}/usage",
        summary="Any tenant's usage for a month",
        dependencies=[Depends(require_admin)],
        tags=["admin: tenants"],
    )
    async def for_tenant(tenant_id: UUID, month: Month = None) -> dict[str, Any]:
        return await controller.for_tenant(tenant_id, month)

    return router
