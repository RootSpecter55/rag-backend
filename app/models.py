"""Imports every ORM model so Base.metadata is complete (Alembic and tests use this)."""

from app.core.db import Base
from app.modules.chunks.models import Chunk
from app.modules.documents.models import Document
from app.modules.queries.models import Query
from app.modules.tenants.models import Tenant

__all__ = ["Base", "Chunk", "Document", "Query", "Tenant"]
