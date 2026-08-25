from __future__ import annotations

import json
import os
from typing import Any

from .base import ChatResponse


class BedrockChatProvider:
    """Thin Bedrock Converse adapter. Model IDs are supplied by the workshop."""

    def __init__(self, model_id: str | None = None, region: str | None = None):
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError("install the aws extra: pip install -e '.[aws]'") from exc
        self.model_id = model_id or os.environ["BEDROCK_CHAT_MODEL_ID"]
        self.client = boto3.client(
            "bedrock-runtime",
            region_name=region or os.getenv("AWS_REGION", "us-east-1"),
        )

    def complete(self, prompt: str, *, metadata: dict[str, Any] | None = None) -> ChatResponse:
        response = self.client.converse(
            modelId=self.model_id,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"temperature": 0, "maxTokens": 1200},
        )
        text = "".join(part.get("text", "") for part in response["output"]["message"]["content"])
        usage = response.get("usage", {})
        return ChatResponse(
            text=text,
            input_tokens=usage.get("inputTokens", 0),
            output_tokens=usage.get("outputTokens", 0),
            metadata={"model_id": self.model_id, **(metadata or {})},
        )


class TitanEmbeddingProvider:
    def __init__(self, model_id: str | None = None, region: str | None = None):
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError("install the aws extra: pip install -e '.[aws]'") from exc
        self.model_id = model_id or os.environ["BEDROCK_EMBED_MODEL_ID"]
        self.client = boto3.client(
            "bedrock-runtime",
            region_name=region or os.getenv("AWS_REGION", "us-east-1"),
        )
        self._dimension = 0

    @property
    def dimension(self) -> int:
        return self._dimension

    def _embed(self, text: str) -> list[float]:
        response = self.client.invoke_model(
            modelId=self.model_id,
            body=json.dumps({"inputText": text}),
            accept="application/json",
            contentType="application/json",
        )
        body = json.loads(response["body"].read())
        vector = body["embedding"]
        self._dimension = len(vector)
        return vector

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

