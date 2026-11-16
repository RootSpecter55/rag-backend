from collections.abc import AsyncIterator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.container import build_container
from app.core.config import get_settings
from app.main import create_app
from app.providers.llm.base import LLMUsage
from app.providers.llm.fake import FakeLLM
from tests.integration.conftest import ADMIN, create_tenant, parse_sse, upload

TRAVEL = """# Travel policy

Flights must be booked through the travel portal at least 14 days before departure.

Economy class is required for flights under six hours."""

EQUIPMENT = """# Equipment policy

Laptops are replaced every three years.

Lost or stolen equipment must be reported to IT within 24 hours."""


async def ask(client: AsyncClient, tenant: dict[str, Any], question: str, **extra: Any):
    response = await client.post(
        "/queries", headers=tenant["auth"], json={"question": question, **extra}
    )
    return response


class RecordingLLM(FakeLLM):
    """The fake LLM, but it remembers how often it was called and can fail or refuse."""

    def __init__(self, mode: str = "ok") -> None:
        self.calls = 0
        self.mode = mode

    async def stream(self, system: str, user: str) -> AsyncIterator[str | LLMUsage]:
        self.calls += 1
        if self.mode == "fail":
            yield "Partial "
            raise RuntimeError("provider unavailable")
        if self.mode == "refuse":
            yield LLMUsage(input_tokens=10, output_tokens=0, stop_reason="refusal", model="m")
            return
        async for item in super().stream(system, user):
            yield item


def client_with(llm: Any, **settings: Any) -> AsyncClient:
    """A client for an app with a custom LLM and/or settings (e.g. token prices)."""
    config = get_settings().model_copy(update=settings)
    app = create_app(build_container(config, llm=llm))
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_streams_sources_then_tokens_then_done(client: AsyncClient) -> None:
    tenant = await create_tenant(client)
    await upload(client, tenant, "travel.md", TRAVEL)
    await upload(client, tenant, "equipment.md", EQUIPMENT)

    response = await ask(client, tenant, "How many days before departure must flights be booked?")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    events = parse_sse(response.text)
    names = [name for name, _ in events]
    assert names[0] == "sources" and names[-1] == "done"
    assert set(names[1:-1]) == {"token"}

    sources = events[0][1]["sources"]
    assert sources[0]["filename"] == "travel.md"  # the relevant document ranks first
    answer = "".join(data["text"] for name, data in events if name == "token")
    assert "14 days" in answer and answer.startswith("According to [1]")
    assert events[-1][1]["status"] == "completed"


async def test_saves_the_query_with_tokens_and_estimated_cost(client: AsyncClient) -> None:
    async with client_with(
        FakeLLM(), llm_input_usd_per_mtok=3.0, llm_output_usd_per_mtok=15.0
    ) as priced:
        tenant = await create_tenant(priced)
        await upload(priced, tenant, "travel.md", TRAVEL)
        events = parse_sse((await ask(priced, tenant, "When must flights be booked?")).text)
        done = events[-1][1]

        saved = (await priced.get(f"/queries/{done['queryId']}", headers=tenant["auth"])).json()
        query = saved["data"]
        assert query["inputTokens"] > 0 and query["outputTokens"] > 0
        expected = (query["inputTokens"] * 3 + query["outputTokens"] * 15) / 1_000_000
        assert float(query["estimatedCostUsd"]) == pytest.approx(expected, abs=1e-6)
        assert done["estimatedCostUsd"] == query["estimatedCostUsd"]
        assert len(query["sourceChunkIds"]) >= 1


async def test_retrieval_never_crosses_tenants(client: AsyncClient) -> None:
    acme = await create_tenant(client, "Acme")
    globex = await create_tenant(client, "Globex")
    await upload(client, acme, "acme-travel.md", TRAVEL)
    globex_doc = await upload(client, globex, "globex-travel.md", TRAVEL + "\n\nGlobex note.")

    events = parse_sse((await ask(client, acme, "When must flights be booked?", topK=20)).text)
    filenames = {source["filename"] for source in events[0][1]["sources"]}
    assert filenames == {"acme-travel.md"}
    ids = {source["documentId"] for source in events[0][1]["sources"]}
    assert globex_doc["id"] not in ids


async def test_answers_without_calling_the_llm_when_there_are_no_documents() -> None:
    llm = RecordingLLM()
    async with client_with(llm) as c:
        tenant = await create_tenant(c)
        events = parse_sse((await ask(c, tenant, "Anything?")).text)
    assert llm.calls == 0
    assert events[0][1]["sources"] == []
    assert events[-1][1]["status"] == "no_sources"


async def test_reports_a_provider_failure_and_records_it() -> None:
    async with client_with(RecordingLLM(mode="fail")) as c:
        tenant = await create_tenant(c)
        await upload(c, tenant, "travel.md", TRAVEL)
        events = parse_sse((await ask(c, tenant, "When must flights be booked?")).text)
        names = [name for name, _ in events]
        assert names == ["sources", "token", "error", "done"]
        saved = await c.get(f"/queries/{events[-1][1]['queryId']}", headers=tenant["auth"])
        assert saved.json()["data"]["status"] == "failed"
        assert saved.json()["data"]["answer"] == "Partial "


async def test_records_a_refusal() -> None:
    async with client_with(RecordingLLM(mode="refuse")) as c:
        tenant = await create_tenant(c)
        await upload(c, tenant, "travel.md", TRAVEL)
        events = parse_sse((await ask(c, tenant, "When must flights be booked?")).text)
    assert events[-1][1]["status"] == "refused"


async def test_enforces_the_monthly_query_limit(client: AsyncClient) -> None:
    tenant = await create_tenant(client, monthlyQueryLimit=2)
    await upload(client, tenant, "travel.md", TRAVEL)
    for _ in range(2):
        assert (await ask(client, tenant, "Flights?")).status_code == 200

    blocked = await ask(client, tenant, "Flights?")
    assert blocked.status_code == 429
    assert blocked.json()["error"] == {
        "code": "QUERY_LIMIT_REACHED",
        "message": "Monthly query limit reached",
        "details": {"used": 2, "limit": 2},
    }


async def test_usage_totals_for_the_tenant_and_for_admins(client: AsyncClient) -> None:
    tenant = await create_tenant(client, monthlyQueryLimit=10)
    await upload(client, tenant, "travel.md", TRAVEL)
    for question in ("Flights?", "Economy class?", "Booking portal?"):
        await ask(client, tenant, question)

    mine = (await client.get("/usage", headers=tenant["auth"])).json()["data"]
    assert mine["queries"] == 3
    assert mine["queryLimit"] == 10 and mine["queriesRemaining"] == 7
    assert mine["inputTokens"] > 0

    admin = await client.get(f"/admin/tenants/{tenant['id']}/usage", headers=ADMIN)
    assert admin.json()["data"]["queries"] == 3

    other_month = await client.get("/usage?month=2001-01", headers=tenant["auth"])
    assert other_month.json()["data"]["queries"] == 0
    assert (await client.get("/usage?month=2001-13", headers=tenant["auth"])).status_code == 400


async def test_lists_past_queries_newest_first(client: AsyncClient) -> None:
    tenant = await create_tenant(client)
    await upload(client, tenant, "travel.md", TRAVEL)
    await ask(client, tenant, "first question")
    await ask(client, tenant, "second question")
    listed = (await client.get("/queries", headers=tenant["auth"])).json()
    assert [q["question"] for q in listed["data"]] == ["second question", "first question"]
