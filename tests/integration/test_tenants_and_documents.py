import asyncio
import os
from pathlib import Path

from httpx import AsyncClient

from tests.integration.conftest import ADMIN, create_tenant, upload

HANDBOOK = """# Travel policy

Employees book flights through the travel portal at least 14 days ahead.

Hotel stays are reimbursed up to the city rate listed in the portal.

# Equipment

Laptops are replaced every three years. Lost equipment must be reported within 24 hours.
"""


async def test_health(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.json() == {"data": {"status": "ok"}}


async def test_admin_routes_require_the_admin_key(client: AsyncClient) -> None:
    assert (await client.get("/admin/tenants")).status_code == 401
    wrong = {"Authorization": "Bearer nope"}
    assert (await client.get("/admin/tenants", headers=wrong)).status_code == 401


async def test_tenant_key_is_shown_once_and_rotation_invalidates_it(client: AsyncClient) -> None:
    tenant = await create_tenant(client, "Acme", monthlyQueryLimit=50)
    me = await client.get("/tenant", headers=tenant["auth"])
    assert me.json()["data"]["monthlyQueryLimit"] == 50
    assert "apiKey" not in me.json()["data"]

    rotated = await client.post(f"/admin/tenants/{tenant['id']}/rotate-key", headers=ADMIN)
    new_key = rotated.json()["data"]["apiKey"]
    assert (await client.get("/tenant", headers=tenant["auth"])).status_code == 401
    assert (
        await client.get("/tenant", headers={"Authorization": f"Bearer {new_key}"})
    ).status_code == 200


async def test_list_tenants_is_paginated(client: AsyncClient) -> None:
    for name in ("A", "B", "C"):
        await create_tenant(client, name)
    response = await client.get("/admin/tenants?page=2&pageSize=2", headers=ADMIN)
    assert response.json()["meta"] == {"page": 2, "pageSize": 2, "total": 3, "totalPages": 2}


async def test_validation_errors_use_the_error_envelope(client: AsyncClient) -> None:
    response = await client.post("/admin/tenants", headers=ADMIN, json={"name": ""})
    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["details"][0]["path"] == "name"


async def test_upload_chunks_and_embeds_a_document(client: AsyncClient) -> None:
    tenant = await create_tenant(client)
    document = await upload(client, tenant, "handbook.md", HANDBOOK)
    assert document["status"] == "ready"
    assert document["chunkCount"] >= 1

    chunks = await client.get(f"/documents/{document['id']}/chunks", headers=tenant["auth"])
    texts = [c["text"] for c in chunks.json()["data"]]
    assert "14 days ahead" in " ".join(texts)
    assert chunks.json()["meta"]["total"] == document["chunkCount"]


async def test_upload_rejects_unsupported_empty_and_oversized_files(client: AsyncClient) -> None:
    tenant = await create_tenant(client)

    async def post(name: str, content: bytes) -> int:
        files = {"file": (name, content, "application/octet-stream")}
        return (await client.post("/documents", headers=tenant["auth"], files=files)).status_code

    assert await post("report.pdf", b"%PDF-1.7") == 400
    assert await post("empty.txt", b"   \n") == 400
    assert await post("binary.txt", b"\xff\xfe\x00") == 400
    assert await post("huge.txt", b"a" * 2_000_001) == 413


async def test_documents_are_private_to_their_tenant(client: AsyncClient) -> None:
    owner = await create_tenant(client, "Owner")
    other = await create_tenant(client, "Other")
    document = await upload(client, owner, "handbook.md", HANDBOOK)

    for path in (f"/documents/{document['id']}", f"/documents/{document['id']}/chunks"):
        assert (await client.get(path, headers=other["auth"])).status_code == 404
    assert (await client.get("/documents", headers=other["auth"])).json()["meta"]["total"] == 0


async def test_delete_removes_the_document_its_chunks_and_the_stored_file(
    client: AsyncClient,
) -> None:
    tenant = await create_tenant(client)
    document = await upload(client, tenant, "handbook.md", HANDBOOK)
    stored = Path(os.environ["LOCAL_STORAGE_DIR"], tenant["id"], document["id"], "handbook.md")
    assert await asyncio.to_thread(stored.exists)

    chunk_list = await client.get(f"/documents/{document['id']}/chunks", headers=tenant["auth"])
    chunk_id = chunk_list.json()["data"][0]["id"]

    response = await client.delete(f"/documents/{document['id']}", headers=tenant["auth"])
    assert response.status_code == 204
    assert not await asyncio.to_thread(stored.exists)
    assert (await client.get(f"/chunks/{chunk_id}", headers=tenant["auth"])).status_code == 404
