import logging
import re
import uuid
from uuid import UUID

from app.core.db import Database
from app.core.errors import AppError, BadRequestError, NotFoundError
from app.core.pagination import PageParams
from app.modules.chunks.chunker import chunk_text
from app.modules.chunks.models import Chunk
from app.modules.chunks.repository import ChunkRepository
from app.modules.documents.models import Document, DocumentStatus
from app.modules.documents.repository import DocumentRepository
from app.modules.documents.schemas import DocumentOut
from app.providers.embeddings.base import EmbeddingProvider
from app.providers.storage.base import StorageProvider

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = (".txt", ".md", ".markdown")


def safe_filename(name: str) -> str:
    """Keeps letters, digits, dots, dashes and underscores; never a path."""
    base = name.replace("\\", "/").rsplit("/", 1)[-1]
    return re.sub(r"[^A-Za-z0-9._-]", "_", base)[:200] or "upload"


class DocumentsService:
    def __init__(
        self,
        db: Database,
        documents: DocumentRepository,
        chunks: ChunkRepository,
        storage: StorageProvider,
        embeddings: EmbeddingProvider,
        *,
        chunk_size: int,
        chunk_overlap: int,
        max_bytes: int,
    ) -> None:
        self._db = db
        self._documents = documents
        self._chunks = chunks
        self._storage = storage
        self._embeddings = embeddings
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._max_bytes = max_bytes

    def _decode(self, filename: str, data: bytes) -> str:
        if not filename.lower().endswith(ALLOWED_EXTENSIONS):
            raise BadRequestError("UNSUPPORTED_FILE_TYPE", "Only .txt and .md files are supported")
        if len(data) > self._max_bytes:
            raise AppError(413, "FILE_TOO_LARGE", f"Files are limited to {self._max_bytes} bytes")
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise BadRequestError("INVALID_ENCODING", "Files must be UTF-8 text") from exc
        if not text.strip():
            raise BadRequestError("EMPTY_DOCUMENT", "The file has no text")
        return text

    async def upload(
        self, tenant_id: UUID, filename: str, content_type: str, data: bytes
    ) -> DocumentOut:
        """Stores the file, splits it into chunks, embeds them and saves everything.

        Runs within the request: fine for the size limit here; a queue would take over for
        large files (see README limitations).
        """
        text = self._decode(filename, data)
        document_id = uuid.uuid4()
        name = safe_filename(filename)
        storage_key = f"{tenant_id}/{document_id}/{name}"
        await self._storage.put(storage_key, data, content_type)

        document = Document(
            id=document_id,
            tenant_id=tenant_id,
            filename=name,
            content_type=content_type,
            size_bytes=len(data),
            storage_key=storage_key,
            status=DocumentStatus.READY,
        )
        pieces = chunk_text(text, self._chunk_size, self._chunk_overlap)
        try:
            vectors = await self._embeddings.embed(pieces)
        except Exception as exc:
            # Keep a record of the failed upload so it is visible in the document list.
            logger.exception("Embedding failed for document %s", document_id)
            document.status = DocumentStatus.FAILED
            document.error = "Embedding failed"
            async with self._db.transaction() as session:
                await self._documents.add(session, document)
            raise AppError(
                502,
                "EMBEDDING_FAILED",
                "Could not embed the document",
                {"documentId": str(document_id)},
            ) from exc

        document.chunk_count = len(pieces)
        async with self._db.transaction() as session:
            await self._documents.add(session, document)
            await self._chunks.add_all(
                session,
                [
                    Chunk(
                        document_id=document_id,
                        tenant_id=tenant_id,
                        ordinal=i,
                        text=piece,
                        embedding=vector,
                    )
                    for i, (piece, vector) in enumerate(zip(pieces, vectors, strict=True))
                ],
            )
        return DocumentOut.model_validate(document)

    async def list(self, tenant_id: UUID, page: PageParams) -> tuple[list[DocumentOut], int]:
        async with self._db.transaction() as session:
            rows, total = await self._documents.list(
                session,
                Document.tenant_id == tenant_id,
                order_by=Document.created_at.desc(),
                offset=page.offset,
                limit=page.page_size,
            )
        return [DocumentOut.model_validate(d) for d in rows], total

    async def get(self, tenant_id: UUID, document_id: UUID) -> DocumentOut:
        async with self._db.transaction() as session:
            document = await self._documents.get_for_tenant(session, document_id, tenant_id)
        if document is None:
            raise NotFoundError("Document")
        return DocumentOut.model_validate(document)

    async def delete(self, tenant_id: UUID, document_id: UUID) -> None:
        """Deletes the row (its chunks cascade), then the stored file."""
        async with self._db.transaction() as session:
            document = await self._documents.get_for_tenant(session, document_id, tenant_id)
            if document is None:
                raise NotFoundError("Document")
            storage_key = document.storage_key
            await self._documents.delete(session, document)
        await self._storage.delete(storage_key)
