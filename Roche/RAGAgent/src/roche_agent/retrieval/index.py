from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Iterable

from rank_bm25 import BM25Okapi

from roche_agent.contracts import Chunk, RetrievalHit
from roche_agent.providers.base import EmbeddingProvider


def tokenize(text: str) -> list[str]:
    latin = re.findall(r"[a-zA-Z0-9_.-]+", text.lower())
    chinese = [char for char in text if "\u4e00" <= char <= "\u9fff"]
    bigrams = ["".join(chinese[i : i + 2]) for i in range(len(chinese) - 1)]
    return latin + chinese + bigrams


def cosine_similarity(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left)) or 1.0
    right_norm = math.sqrt(sum(value * value for value in right)) or 1.0
    return numerator / (left_norm * right_norm)


@dataclass
class LocalHybridIndex:
    chunks: list[Chunk]
    vectors: list[list[float]]
    embedder: EmbeddingProvider

    def __post_init__(self) -> None:
        if len(self.chunks) != len(self.vectors):
            raise ValueError("chunks and vectors must have the same length")
        corpus = [tokenize(chunk.text) for chunk in self.chunks]
        self.bm25 = BM25Okapi(corpus)

    @classmethod
    def build(cls, chunks: list[Chunk], embedder: EmbeddingProvider) -> "LocalHybridIndex":
        vectors = embedder.embed_documents([chunk.text for chunk in chunks])
        return cls(chunks=chunks, vectors=vectors, embedder=embedder)

    @staticmethod
    def _normalize(values: Iterable[float]) -> list[float]:
        values = list(values)
        if not values:
            return []
        low, high = min(values), max(values)
        if high == low:
            return [1.0 if high > 0 else 0.0 for _ in values]
        return [(value - low) / (high - low) for value in values]

    def search(
        self,
        query: str,
        *,
        top_k: int,
        alpha: float,
        active_only: bool = False,
    ) -> list[RetrievalHit]:
        query_vector = self.embedder.embed_query(query)
        dense_raw = [
            cosine_similarity(query_vector, vector)
            for vector in self.vectors
        ]
        sparse_raw = list(self.bm25.get_scores(tokenize(query)))
        dense = self._normalize(dense_raw)
        sparse = self._normalize(sparse_raw)
        hits: list[RetrievalHit] = []
        for chunk, dense_score, sparse_score in zip(self.chunks, dense, sparse):
            if active_only and chunk.metadata.get("status") == "deprecated":
                continue
            fused = alpha * dense_score + (1.0 - alpha) * sparse_score
            hits.append(
                RetrievalHit(
                    chunk=chunk,
                    dense_score=dense_score,
                    sparse_score=sparse_score,
                    fused_score=fused,
                )
            )
        hits.sort(key=lambda item: item.fused_score, reverse=True)
        return hits[:top_k]


@dataclass
class QdrantHybridIndex:
    chunks: list[Chunk]
    embedder: EmbeddingProvider
    client: object
    collection_name: str

    def __post_init__(self) -> None:
        self.bm25 = BM25Okapi([tokenize(chunk.text) for chunk in self.chunks])

    @classmethod
    def build(
        cls,
        chunks: list[Chunk],
        embedder: EmbeddingProvider,
        *,
        collection_name: str,
    ) -> "QdrantHybridIndex":
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, PointStruct, VectorParams
        except ImportError as exc:
            raise RuntimeError("qdrant-client is required for qdrant_local") from exc
        vectors = embedder.embed_documents([chunk.text for chunk in chunks])
        if not vectors:
            raise ValueError("cannot build an empty vector index")
        client = QdrantClient(":memory:")
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=len(vectors[0]), distance=Distance.COSINE),
        )
        client.upsert(
            collection_name=collection_name,
            points=[
                PointStruct(id=index, vector=vector, payload={"chunk_index": index})
                for index, vector in enumerate(vectors)
            ],
        )
        return cls(
            chunks=chunks,
            embedder=embedder,
            client=client,
            collection_name=collection_name,
        )

    def search(
        self,
        query: str,
        *,
        top_k: int,
        alpha: float,
        active_only: bool = False,
    ) -> list[RetrievalHit]:
        query_vector = self.embedder.embed_query(query)
        response = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=len(self.chunks),
            with_payload=True,
        )
        dense_by_index = {
            int(point.payload["chunk_index"]): float(point.score)
            for point in response.points
        }
        dense_raw = [dense_by_index.get(index, 0.0) for index in range(len(self.chunks))]
        sparse_raw = list(self.bm25.get_scores(tokenize(query)))
        dense = LocalHybridIndex._normalize(dense_raw)
        sparse = LocalHybridIndex._normalize(sparse_raw)
        hits = []
        for chunk, dense_score, sparse_score in zip(self.chunks, dense, sparse):
            if active_only and chunk.metadata.get("status") == "deprecated":
                continue
            hits.append(
                RetrievalHit(
                    chunk=chunk,
                    dense_score=dense_score,
                    sparse_score=sparse_score,
                    fused_score=alpha * dense_score + (1.0 - alpha) * sparse_score,
                )
            )
        hits.sort(key=lambda item: item.fused_score, reverse=True)
        return hits[:top_k]


def lexical_rerank(query: str, hits: list[RetrievalHit]) -> list[RetrievalHit]:
    query_tokens = set(tokenize(query))
    for hit in hits:
        chunk_tokens = set(tokenize(hit.chunk.text))
        overlap = len(query_tokens & chunk_tokens) / max(1, len(query_tokens))
        version_bonus = 0.1 if hit.chunk.metadata.get("status") == "active" else 0.0
        hit.rerank_score = 0.7 * hit.fused_score + 0.3 * overlap + version_bonus
    return sorted(hits, key=lambda item: item.rerank_score, reverse=True)
