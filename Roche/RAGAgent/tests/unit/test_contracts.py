import pytest
from pydantic import ValidationError

from roche_agent.contracts import IndexConfig, QueryConfig


def test_chunk_overlap_must_be_smaller_than_chunk_size():
    with pytest.raises(ValidationError):
        IndexConfig(chunk_size=100, chunk_overlap=100)


def test_rerank_candidates_must_cover_output():
    with pytest.raises(ValidationError):
        QueryConfig(rerank_candidate_k=2, rerank_top_n=3)


def test_vector_backend_is_explicit():
    assert IndexConfig(vector_backend="qdrant_local").vector_backend == "qdrant_local"
