from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .base import ChatResponse


class ReplayChatProvider:
    def __init__(self, fixture: str | Path | dict[str, Any]):
        if isinstance(fixture, (str, Path)):
            self.data = json.loads(Path(fixture).read_text(encoding="utf-8"))
        else:
            self.data = fixture

    def complete(self, prompt: str, *, metadata: dict[str, Any] | None = None) -> ChatResponse:
        key = (metadata or {}).get("replay_key")
        if not key or key not in self.data:
            raise KeyError(f"missing replay response: {key!r}")
        item = self.data[key]
        if isinstance(item, str):
            return ChatResponse(text=item)
        return ChatResponse.model_validate(item)


class ReplayEmbeddingProvider:
    def __init__(self, fixture: str | Path | dict[str, list[float]]):
        if isinstance(fixture, (str, Path)):
            self.data = json.loads(Path(fixture).read_text(encoding="utf-8"))
        else:
            self.data = fixture
        if not self.data:
            raise ValueError("embedding replay fixture is empty")
        self._dimension = len(next(iter(self.data.values())))

    @property
    def dimension(self) -> int:
        return self._dimension

    def _get(self, text: str) -> list[float]:
        if text not in self.data:
            raise KeyError(f"missing replay embedding for text: {text[:60]!r}")
        return self.data[text]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._get(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._get(text)

