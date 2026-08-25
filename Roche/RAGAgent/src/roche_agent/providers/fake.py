from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from typing import Any

from .base import ChatResponse


class FakeChatProvider:
    """Deterministic provider for local tests and classroom failure injection."""

    def __init__(self, responses: dict[str, str] | None = None, default: str = "证据不足，需人工确认。"):
        self.responses = responses or {}
        self.default = default
        self.calls: list[str] = []

    def complete(self, prompt: str, *, metadata: dict[str, Any] | None = None) -> ChatResponse:
        self.calls.append(prompt)
        text = next((value for key, value in self.responses.items() if key in prompt), self.default)
        return ChatResponse(
            text=text,
            input_tokens=max(1, len(prompt) // 4),
            output_tokens=max(1, len(text) // 4),
            metadata=metadata or {},
        )


class HashEmbeddingProvider:
    """Small deterministic embedding model; useful for logic tests, not quality claims."""

    def __init__(self, dimension: int = 128):
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    @staticmethod
    def _tokens(text: str) -> list[str]:
        latin = re.findall(r"[a-zA-Z0-9_.-]+", text.lower())
        chinese = [char for char in text if "\u4e00" <= char <= "\u9fff"]
        bigrams = ["".join(chinese[i : i + 2]) for i in range(len(chinese) - 1)]
        return latin + chinese + bigrams

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self._dimension
        counts = Counter(self._tokens(text))
        for token, count in counts.items():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self._dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign * (1.0 + math.log(count))
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

