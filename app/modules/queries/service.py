import asyncio
import logging
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.core.auth import CurrentTenant
from app.core.db import Database
from app.core.errors import NotFoundError, QueryLimitError
from app.core.pagination import PageParams
from app.modules.chunks.repository import ChunkRepository
from app.modules.chunks.schemas import RetrievedChunk
from app.modules.queries.models import Query, QueryStatus
from app.modules.queries.prompt import (
    NO_SOURCES_ANSWER,
    SYSTEM_PROMPT,
    build_user_prompt,
    estimate_cost,
)
from app.modules.queries.repository import QueryRepository
from app.modules.queries.schemas import QueryOut, QueryRequest
from app.providers.embeddings.base import EmbeddingProvider
from app.providers.llm.base import LLMProvider, LLMUsage

logger = logging.getLogger(__name__)


def month_start(now: datetime) -> datetime:
    """Query limits reset on the first day of each calendar month (UTC)."""
    return datetime(now.year, now.month, 1, tzinfo=UTC)


@dataclass
class PreparedQuery:
    """Everything decided before streaming starts (so those errors are normal HTTP errors)."""

    id: UUID
    tenant_id: UUID
    question: str
    top_k: int
    sources: list[RetrievedChunk]
    started: float


SseEvent = dict[str, Any]  # {"event": name, "data": json-serialisable payload}


class QueriesService:
    def __init__(
        self,
        db: Database,
        queries: QueryRepository,
        chunks: ChunkRepository,
        embeddings: EmbeddingProvider,
        llm: LLMProvider,
        *,
        default_top_k: int,
        input_usd_per_mtok: float,
        output_usd_per_mtok: float,
    ) -> None:
        self._db = db
        self._queries = queries
        self._chunks = chunks
        self._embeddings = embeddings
        self._llm = llm
        self._default_top_k = default_top_k
        self._input_price = input_usd_per_mtok
        self._output_price = output_usd_per_mtok

    async def prepare(self, tenant: CurrentTenant, request: QueryRequest) -> PreparedQuery:
        """Checks the monthly limit, embeds the question and retrieves the tenant's top chunks."""
        started = time.monotonic()
        async with self._db.transaction() as session:
            used = await self._queries.count_since(
                session, tenant.id, month_start(datetime.now(UTC))
            )
        if used >= tenant.monthly_query_limit:
            raise QueryLimitError(used, tenant.monthly_query_limit)

        top_k = request.top_k or self._default_top_k
        [embedding] = await self._embeddings.embed([request.question])
        async with self._db.transaction() as session:
            sources = await self._chunks.search(session, tenant.id, embedding, top_k)
        return PreparedQuery(uuid.uuid4(), tenant.id, request.question, top_k, sources, started)

    async def stream(self, prepared: PreparedQuery) -> AsyncIterator[SseEvent]:
        """Yields `sources`, then `token`s, then `done` (or `error`), and saves the query."""
        yield {
            "event": "sources",
            "data": {
                "queryId": str(prepared.id),
                "sources": [s.to_json() for s in prepared.sources],
            },
        }

        answer: list[str] = []
        usage: LLMUsage | None = None
        status = QueryStatus.COMPLETED
        try:
            if not prepared.sources:
                # Nothing to ground an answer in: say so without spending an LLM call.
                status = QueryStatus.NO_SOURCES
                answer.append(NO_SOURCES_ANSWER)
                yield {"event": "token", "data": {"text": NO_SOURCES_ANSWER}}
            else:
                user = build_user_prompt(prepared.question, prepared.sources)
                async for item in self._llm.stream(SYSTEM_PROMPT, user):
                    if isinstance(item, LLMUsage):
                        usage = item
                    else:
                        answer.append(item)
                        yield {"event": "token", "data": {"text": item}}
                if usage and usage.stop_reason == "refusal":
                    status = QueryStatus.REFUSED
        except (asyncio.CancelledError, GeneratorExit):
            status = QueryStatus.CANCELLED  # the client disconnected mid-stream
            raise
        except Exception:
            logger.exception("Query %s failed while streaming", prepared.id)
            status = QueryStatus.FAILED
            yield {"event": "error", "data": {"code": "LLM_FAILED", "message": "Answer failed"}}
        finally:
            # Shielded so a client disconnect cannot cancel the write of the query record.
            saved = await asyncio.shield(self._save(prepared, "".join(answer), usage, status))

        yield {
            "event": "done",
            "data": {
                "queryId": str(prepared.id),
                "status": saved.status,
                "inputTokens": saved.input_tokens,
                "outputTokens": saved.output_tokens,
                "estimatedCostUsd": str(saved.estimated_cost_usd),
                "latencyMs": saved.latency_ms,
            },
        }

    async def _save(
        self, prepared: PreparedQuery, answer: str, usage: LLMUsage | None, status: QueryStatus
    ) -> Query:
        input_tokens = usage.input_tokens if usage else 0
        output_tokens = usage.output_tokens if usage else 0
        query = Query(
            id=prepared.id,
            tenant_id=prepared.tenant_id,
            question=prepared.question,
            answer=answer,
            top_k=prepared.top_k,
            source_chunk_ids=[s.id for s in prepared.sources],
            provider=self._llm.name,
            model=usage.model if usage else self._llm.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=estimate_cost(
                input_tokens, output_tokens, self._input_price, self._output_price
            ),
            latency_ms=int((time.monotonic() - prepared.started) * 1000),
            status=status,
        )
        async with self._db.transaction() as session:
            return await self._queries.add(session, query)

    async def list(self, tenant_id: UUID, page: PageParams) -> tuple[list[QueryOut], int]:
        async with self._db.transaction() as session:
            rows, total = await self._queries.list(
                session,
                Query.tenant_id == tenant_id,
                order_by=Query.created_at.desc(),
                offset=page.offset,
                limit=page.page_size,
            )
        return [QueryOut.model_validate(q) for q in rows], total

    async def get(self, tenant_id: UUID, query_id: UUID) -> QueryOut:
        async with self._db.transaction() as session:
            query = await self._queries.get_for_tenant(session, query_id, tenant_id)
        if query is None:
            raise NotFoundError("Query")
        return QueryOut.model_validate(query)
