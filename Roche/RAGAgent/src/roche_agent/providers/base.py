from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field


class ChatResponse(BaseModel):
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatProvider(Protocol):
    def complete(self, prompt: str, *, metadata: dict[str, Any] | None = None) -> ChatResponse:
        ...


class EmbeddingProvider(Protocol):
    @property
    def dimension(self) -> int:
        ...

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        ...

    def embed_query(self, text: str) -> list[float]:
        ...

