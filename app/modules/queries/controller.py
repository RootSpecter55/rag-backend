import json
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from fastapi.responses import StreamingResponse

from app.core.auth import CurrentTenant
from app.core.pagination import PageParams, data_envelope, page_envelope
from app.modules.queries.schemas import QueryRequest
from app.modules.queries.service import QueriesService, SseEvent


async def to_sse(events: AsyncIterator[SseEvent]) -> AsyncIterator[str]:
    """Formats events as Server-Sent Events: `event: <name>` and a JSON `data:` line."""
    async for event in events:
        yield f"event: {event['event']}\ndata: {json.dumps(event['data'])}\n\n"


class QueriesController:
    def __init__(self, service: QueriesService) -> None:
        self._service = service

    async def ask(self, tenant: CurrentTenant, body: QueryRequest) -> StreamingResponse:
        # Limit check and retrieval happen before the response starts, so their errors are
        # ordinary JSON responses; only the answer itself is streamed.
        prepared = await self._service.prepare(tenant, body)
        return StreamingResponse(
            to_sse(self._service.stream(prepared)),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    async def list(self, tenant: CurrentTenant, page: PageParams) -> dict[str, Any]:
        items, total = await self._service.list(tenant.id, page)
        return page_envelope([q.to_json() for q in items], total, page)

    async def get(self, tenant: CurrentTenant, query_id: UUID) -> dict[str, Any]:
        return data_envelope((await self._service.get(tenant.id, query_id)).to_json())
