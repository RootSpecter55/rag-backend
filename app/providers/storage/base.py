from typing import Protocol


class StorageProvider(Protocol):
    """Where uploaded files are kept. Implementations: local disk (default) and S3."""

    name: str

    async def put(self, key: str, data: bytes, content_type: str) -> None: ...

    async def get(self, key: str) -> bytes: ...

    async def delete(self, key: str) -> None: ...
