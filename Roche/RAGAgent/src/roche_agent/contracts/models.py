from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class Chunk(BaseModel):
    chunk_id: str
    document_id: str
    text: str
    chunk_type: Literal["fixed", "section", "clause", "table_row", "cell"] = "fixed"
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievalHit(BaseModel):
    chunk: Chunk
    dense_score: float = 0.0
    sparse_score: float = 0.0
    fused_score: float = 0.0
    rerank_score: float = 0.0

    @property
    def score(self) -> float:
        return self.rerank_score or self.fused_score


class Citation(BaseModel):
    evidence_id: str
    document_id: str
    page: int | None = None
    region: str | None = None
    table_cell: str | None = None


class Evidence(BaseModel):
    evidence_id: str
    source_type: str
    source_uri: str
    content: str
    document_version: str | None = None
    data_version: str | None = None
    page: int | None = None
    region: str | None = None
    table_cell: str | None = None
    retrieval_score: float | None = None
    observed_at: datetime | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class IndexConfig(BaseModel):
    chunk_strategy: Literal["fixed", "structure"] = "fixed"
    chunk_size: int = Field(default=500, ge=50, le=4000)
    chunk_overlap: int = Field(default=50, ge=0, le=1000)
    embedding_provider: Literal["hash", "bedrock"] = "hash"
    vector_backend: Literal["memory", "qdrant_local"] = "memory"
    index_version: str = "baseline-v1"

    @model_validator(mode="after")
    def validate_overlap(self) -> "IndexConfig":
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        return self


class QueryConfig(BaseModel):
    intent_routing: bool = True
    query_rewrite: bool = True
    retrieval_top_k: int = Field(default=4, ge=1, le=50)
    hybrid_alpha: float = Field(default=1.0, ge=0.0, le=1.0)
    rerank_candidate_k: int = Field(default=4, ge=1, le=100)
    rerank_top_n: int = Field(default=4, ge=1, le=50)
    min_relevance_score: float = Field(default=0.0, ge=0.0)
    max_context_chars: int = Field(default=12000, ge=500, le=100000)
    active_only: bool = False

    @model_validator(mode="after")
    def validate_candidate_sizes(self) -> "QueryConfig":
        if self.rerank_candidate_k < self.rerank_top_n:
            raise ValueError("rerank_candidate_k must be >= rerank_top_n")
        return self


class PipelineConfig(BaseModel):
    name: str = "baseline"
    data_version: str = "training-v1"
    index: IndexConfig = Field(default_factory=IndexConfig)
    query: QueryConfig = Field(default_factory=QueryConfig)


class QueryResult(BaseModel):
    query: str
    rewritten_query: str
    intent: str
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    retrieved_ids: list[str] = Field(default_factory=list)
    latency_ms: float = 0.0
    input_chars: int = 0
    abstained: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class Fact(BaseModel):
    fact_id: str
    subject: str
    attribute: str
    value: str | float | int
    unit: str | None = None
    effective_at: str | None = None
    source_evidence_id: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class RuleResult(BaseModel):
    rule_id: str
    rule_version: str
    status: Literal["passed", "failed", "unknown"]
    evidence_ids: list[str] = Field(default_factory=list)
    reason: str
    requires_human_review: bool = False


class Finding(BaseModel):
    finding: str
    rule_result: RuleResult
    uncertainty: list[str] = Field(default_factory=list)
    required_human_action: str | None = None


class Hypothesis(BaseModel):
    hypothesis_id: str
    statement: str
    status: Literal["candidate", "supported", "rejected", "unknown"] = "candidate"
    supporting_evidence: list[str] = Field(default_factory=list)
    opposing_evidence: list[str] = Field(default_factory=list)
    next_skill: str | None = None


class Budget(BaseModel):
    max_steps: int = Field(default=4, ge=1, le=20)
    max_model_calls: int = Field(default=3, ge=0, le=20)
    max_input_chars: int = Field(default=30000, ge=1000)
    steps_used: int = 0
    model_calls_used: int = 0
    input_chars_used: int = 0

    def consume_step(self) -> None:
        if self.steps_used >= self.max_steps:
            raise RuntimeError("step budget exhausted")
        self.steps_used += 1


class TraceEvent(BaseModel):
    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    name: str
    event_type: Literal["span_start", "span_end", "score", "error"]
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    input: Any | None = None
    output: Any | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
