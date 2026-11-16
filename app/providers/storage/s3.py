import asyncio
from typing import Any

import boto3


class S3Storage:
    """Stores files in one S3 bucket. boto3 is synchronous, so calls run in a worker thread.

    Not covered by the test suite: it needs an AWS account and bucket.
    """

    name = "s3"

    def __init__(self, bucket: str, region: str, client: Any = None) -> None:
        self._bucket = bucket
        self._client = client or boto3.client("s3", region_name=region)

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self._bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )

    async def get(self, key: str) -> bytes:
        response = await asyncio.to_thread(self._client.get_object, Bucket=self._bucket, Key=key)
        return await asyncio.to_thread(response["Body"].read)

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self._client.delete_object, Bucket=self._bucket, Key=key)
