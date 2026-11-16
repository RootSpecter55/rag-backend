from fastapi import FastAPI

from app.container import Container, build_container
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.core.pagination import data_envelope
from app.modules.chunks.routes import chunks_router
from app.modules.documents.routes import documents_router
from app.modules.queries.routes import queries_router
from app.modules.tenants.routes import admin_tenants_router, tenant_router
from app.modules.usage.routes import usage_router


def create_app(container: Container | None = None) -> FastAPI:
    configure_logging()
    c = container or build_container(get_settings())

    app = FastAPI(
        title="RAG backend",
        version="1.0.0",
        description="Multi-tenant retrieval-augmented generation with streamed answers.",
    )
    register_error_handlers(app)

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, object]:
        return data_envelope({"status": "ok"})

    app.include_router(admin_tenants_router(c.tenants, c.require_admin))
    app.include_router(tenant_router(c.tenants, c.current_tenant))
    app.include_router(documents_router(c.documents, c.current_tenant))
    app.include_router(chunks_router(c.chunks, c.current_tenant))
    app.include_router(queries_router(c.queries, c.current_tenant))
    app.include_router(usage_router(c.usage, c.current_tenant, c.require_admin))
    return app
