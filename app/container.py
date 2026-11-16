from dataclasses import dataclass
from typing import Any

from app.core.auth import make_admin_auth, make_tenant_auth
from app.core.config import Settings
from app.core.db import Database, get_engine
from app.modules.chunks.controller import ChunksController
from app.modules.chunks.repository import ChunkRepository
from app.modules.chunks.service import ChunksService
from app.modules.documents.controller import DocumentsController
from app.modules.documents.repository import DocumentRepository
from app.modules.documents.service import DocumentsService
from app.modules.queries.controller import QueriesController
from app.modules.queries.repository import QueryRepository
from app.modules.queries.service import QueriesService
from app.modules.tenants.controller import TenantsController
from app.modules.tenants.repository import TenantRepository
from app.modules.tenants.service import TenantsService
from app.modules.usage.controller import UsageController
from app.modules.usage.repository import UsageRepository
from app.modules.usage.service import UsageService
from app.providers.embeddings.base import EmbeddingProvider
from app.providers.embeddings.factory import create_embeddings
from app.providers.llm.base import LLMProvider
from app.providers.llm.factory import create_llm
from app.providers.storage.base import StorageProvider
from app.providers.storage.factory import create_storage


@dataclass
class Container:
    require_admin: Any
    current_tenant: Any
    tenants: TenantsController
    documents: DocumentsController
    chunks: ChunksController
    queries: QueriesController
    usage: UsageController


def build_container(
    settings: Settings,
    *,
    storage: StorageProvider | None = None,
    embeddings: EmbeddingProvider | None = None,
    llm: LLMProvider | None = None,
) -> Container:
    """Composition root: wires every repository, service and controller in one place.

    Providers come from their factories unless passed in (tests pass fakes with extra behaviour).
    """
    db = Database(get_engine())
    storage = storage or create_storage(settings)
    embeddings = embeddings or create_embeddings(settings)
    llm = llm or create_llm(settings)

    tenant_repo = TenantRepository()
    document_repo = DocumentRepository()
    chunk_repo = ChunkRepository()
    query_repo = QueryRepository()

    tenants = TenantsService(db, tenant_repo, settings.default_monthly_query_limit)
    documents = DocumentsService(
        db,
        document_repo,
        chunk_repo,
        storage,
        embeddings,
        chunk_size=settings.chunk_size_chars,
        chunk_overlap=settings.chunk_overlap_chars,
        max_bytes=settings.max_upload_bytes,
    )
    chunks = ChunksService(db, chunk_repo, document_repo)
    queries = QueriesService(
        db,
        query_repo,
        chunk_repo,
        embeddings,
        llm,
        default_top_k=settings.default_top_k,
        input_usd_per_mtok=settings.llm_input_usd_per_mtok,
        output_usd_per_mtok=settings.llm_output_usd_per_mtok,
    )
    usage = UsageService(db, UsageRepository(), tenant_repo)

    return Container(
        require_admin=make_admin_auth(settings.admin_api_key),
        current_tenant=make_tenant_auth(tenants.resolve),
        tenants=TenantsController(tenants),
        documents=DocumentsController(documents),
        chunks=ChunksController(chunks),
        queries=QueriesController(queries),
        usage=UsageController(usage),
    )
