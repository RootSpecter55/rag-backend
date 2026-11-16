from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Response

from app.core.auth import CurrentTenant
from app.core.pagination import PageParams, page_params
from app.modules.tenants.controller import TenantsController
from app.modules.tenants.schemas import TenantCreate, TenantUpdate


def admin_tenants_router(
    controller: TenantsController, require_admin: Callable[..., Any]
) -> APIRouter:
    router = APIRouter(
        prefix="/admin/tenants", tags=["admin: tenants"], dependencies=[Depends(require_admin)]
    )

    @router.post("", status_code=201, summary="Create a tenant (returns its API key once)")
    async def create(body: TenantCreate) -> dict[str, Any]:
        return await controller.create(body)

    @router.get("", summary="List tenants")
    async def list_tenants(page: Annotated[PageParams, Depends(page_params)]) -> dict[str, Any]:
        return await controller.list(page)

    @router.get("/{tenant_id}", summary="Get a tenant")
    async def get(tenant_id: UUID) -> dict[str, Any]:
        return await controller.get(tenant_id)

    @router.patch("/{tenant_id}", summary="Rename a tenant or change its query limit")
    async def update(tenant_id: UUID, body: TenantUpdate) -> dict[str, Any]:
        return await controller.update(tenant_id, body)

    @router.post(
        "/{tenant_id}/rotate-key", summary="Issue a new API key; the old one stops working"
    )
    async def rotate_key(tenant_id: UUID) -> dict[str, Any]:
        return await controller.rotate_key(tenant_id)

    @router.delete("/{tenant_id}", status_code=204, summary="Delete a tenant and all its data")
    async def delete(tenant_id: UUID) -> Response:
        await controller.delete(tenant_id)
        return Response(status_code=204)

    return router


def tenant_router(controller: TenantsController, current_tenant: Callable[..., Any]) -> APIRouter:
    router = APIRouter(prefix="/tenant", tags=["tenant"])

    @router.get("", summary="The tenant your API key belongs to")
    async def me(tenant: Annotated[CurrentTenant, Depends(current_tenant)]) -> dict[str, Any]:
        return await controller.me(tenant)

    return router
