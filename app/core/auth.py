from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Header

from app.core.errors import UnauthorizedError
from app.core.security import bearer_token, keys_match


@dataclass(frozen=True)
class CurrentTenant:
    """The tenant making the request, resolved from its API key."""

    id: UUID
    name: str
    monthly_query_limit: int


ResolveTenant = Callable[[str], Awaitable[CurrentTenant | None]]


def make_admin_auth(admin_key: str) -> Callable[..., Awaitable[None]]:
    """FastAPI dependency that only lets ADMIN_API_KEY through."""

    async def require_admin(authorization: Annotated[str | None, Header()] = None) -> None:
        token = bearer_token(authorization)
        if not token or not keys_match(token, admin_key):
            raise UnauthorizedError("Invalid admin key")

    return require_admin


def make_tenant_auth(resolve: ResolveTenant) -> Callable[..., Awaitable[CurrentTenant]]:
    """FastAPI dependency that turns a tenant API key into the CurrentTenant."""

    async def current_tenant(
        authorization: Annotated[str | None, Header()] = None,
    ) -> CurrentTenant:
        token = bearer_token(authorization)
        tenant = await resolve(token) if token else None
        if tenant is None:
            raise UnauthorizedError("Invalid API key")
        return tenant

    return current_tenant
