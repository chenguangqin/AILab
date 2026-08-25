from __future__ import annotations

import os

from roche_agent.contracts import PipelineConfig

from .base import ChatProvider, EmbeddingProvider
from .fake import HashEmbeddingProvider


def create_embedding_provider(config: PipelineConfig) -> EmbeddingProvider:
    provider = os.getenv("EMBEDDING_PROVIDER") or config.index.embedding_provider
    if provider == "bedrock":
        from .bedrock import TitanEmbeddingProvider

        return TitanEmbeddingProvider()
    if provider == "hash":
        return HashEmbeddingProvider()
    raise ValueError(f"unsupported embedding provider: {provider}")


def create_chat_provider() -> ChatProvider | None:
    provider = os.getenv("LLM_PROVIDER", "fake")
    if provider == "bedrock":
        from .bedrock import BedrockChatProvider

        return BedrockChatProvider()
    if provider in {"fake", "none"}:
        return None
    raise ValueError(f"unsupported LLM provider: {provider}")
