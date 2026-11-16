import asyncio
import json
from typing import Any

import boto3

from app.providers.embeddings.base import EMBEDDING_DIMENSION


class BedrockEmbeddings:
    """Amazon Titan Text Embeddings v2 through the Bedrock runtime (one request per text).

    Not covered by the test suite: it needs AWS credentials with Bedrock model access.
    """

    name = "bedrock"

    def __init__(self, model_id: str, region: str, client: Any = None) -> None:
        self._model_id = model_id
        self._client = client or boto3.client("bedrock-runtime", region_name=region)

    def _embed_one(self, text: str) -> list[float]:
        body = {"inputText": text, "dimensions": EMBEDDING_DIMENSION, "normalize": True}
        response = self._client.invoke_model(modelId=self._model_id, body=json.dumps(body))
        return json.loads(response["body"].read())["embedding"]

    async def embed(self, texts: list[str]) -> list[list[float]]:
        # boto3 is synchronous: run each call in a worker thread so the event loop stays free.
        return [await asyncio.to_thread(self._embed_one, text) for text in texts]
