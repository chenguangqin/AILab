from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any

from roche_agent.contracts import Citation, PipelineConfig, QueryResult, RetrievalHit
from roche_agent.observability import JsonTracer
from roche_agent.providers.base import ChatProvider, EmbeddingProvider
from roche_agent.providers.fake import HashEmbeddingProvider

from .documents import chunk_documents, load_markdown_documents
from .graph import RAGGraphState, build_rag_graph
from .index import LocalHybridIndex, QdrantHybridIndex, lexical_rerank


class RAGPipeline:
    workflow_version = "rag-langgraph-v1"

    def __init__(
        self,
        config: PipelineConfig,
        *,
        embedder: EmbeddingProvider | None = None,
        chat: ChatProvider | None = None,
        tracer: Any | None = None,
        callbacks: list[Any] | None = None,
    ):
        self.config = config
        self.embedder = embedder or HashEmbeddingProvider()
        self.chat = chat
        self.tracer = tracer or JsonTracer()
        self.callbacks = callbacks or []
        self.index: LocalHybridIndex | QdrantHybridIndex | None = None
        self.chunks = []
        self.graph = build_rag_graph(self)

    def build(self, document_dir: str | Path) -> dict[str, Any]:
        with self.tracer.span(
            "rag.index",
            input={"document_dir": str(document_dir)},
            metadata={
                "pipeline": self.config.name,
                "workflow_version": self.workflow_version,
                "index_version": self.config.index.index_version,
                "data_version": self.config.data_version,
            },
        ) as root:
            with self.tracer.span(
                "rag.index.load_documents",
                trace_id=root["trace_id"],
                parent_span_id=root["span_id"],
            ) as span:
                documents = load_markdown_documents(document_dir)
                span["output"] = {"document_count": len(documents)}
            with self.tracer.span(
                "rag.index.chunk",
                trace_id=root["trace_id"],
                parent_span_id=root["span_id"],
                metadata=self.config.index.model_dump(),
            ) as span:
                self.chunks = chunk_documents(documents, self.config.index)
                span["output"] = {
                    "chunk_count": len(self.chunks),
                    "average_chars": (
                        sum(len(chunk.text) for chunk in self.chunks) / len(self.chunks)
                        if self.chunks
                        else 0
                    ),
                }
            with self.tracer.span(
                "rag.index.embed_and_upsert",
                trace_id=root["trace_id"],
                parent_span_id=root["span_id"],
                metadata={"embedding_provider": self.config.index.embedding_provider},
            ) as span:
                if self.config.index.vector_backend == "qdrant_local":
                    self.index = QdrantHybridIndex.build(
                        self.chunks,
                        self.embedder,
                        collection_name=self.config.index.index_version.replace("-", "_"),
                    )
                else:
                    self.index = LocalHybridIndex.build(self.chunks, self.embedder)
                span["output"] = {
                    "vector_count": len(self.chunks),
                    "dimension": self.embedder.dimension,
                    "vector_backend": self.config.index.vector_backend,
                }
            manifest = {
                "trace_id": root["trace_id"],
                "pipeline": self.config.name,
                "workflow_version": self.workflow_version,
                "index_version": self.config.index.index_version,
                "data_version": self.config.data_version,
                "document_count": len(documents),
                "chunk_count": len(self.chunks),
            }
            root["output"] = manifest
            return manifest

    @staticmethod
    def classify_intent(query: str) -> str:
        if any(word in query.lower() for word in ["你好", "hello", "hi"]):
            return "chitchat"
        return "knowledge_search"

    @staticmethod
    def rewrite_query(query: str) -> str:
        expansions = {
            "冰箱": "冰箱 冷藏设备 温度",
            "岗位": "岗位 职务 任命",
            "超温": "超温 温度 超过 阈值",
        }
        rewritten = query
        for term, expansion in expansions.items():
            if term in query:
                rewritten = rewritten.replace(term, expansion)
        for month, day in re.findall(r"(\d{1,2})月(\d{1,2})日", query):
            normalized = f"2026-{int(month):02d}-{int(day):02d}"
            rewritten = f"{rewritten} {normalized}"
        return rewritten

    @staticmethod
    def _append_step(state: RAGGraphState, step: str) -> list[str]:
        return [*state.get("trajectory", []), step]

    def intent_node(self, state: RAGGraphState) -> dict[str, Any]:
        intent = (
            self.classify_intent(state["question"])
            if self.config.query.intent_routing
            else "knowledge_search"
        )
        with self.tracer.span(
            "rag.query.intent",
            trace_id=state["trace_id"],
            parent_span_id=state["parent_span_id"],
            input=state["question"],
        ) as span:
            span["output"] = intent
        return {"intent": intent, "trajectory": self._append_step(state, "intent")}

    def rewrite_node(self, state: RAGGraphState) -> dict[str, Any]:
        rewritten = (
            self.rewrite_query(state["question"])
            if self.config.query.query_rewrite
            else state["question"]
        )
        with self.tracer.span(
            "rag.query.rewrite",
            trace_id=state["trace_id"],
            parent_span_id=state["parent_span_id"],
            input=state["question"],
        ) as span:
            span["output"] = rewritten
        return {
            "rewritten_query": rewritten,
            "trajectory": self._append_step(state, "rewrite"),
        }

    def retrieve_node(self, state: RAGGraphState) -> dict[str, Any]:
        if self.index is None:
            raise RuntimeError("build the index before querying")
        candidate_k = max(
            self.config.query.retrieval_top_k,
            self.config.query.rerank_candidate_k,
        )
        with self.tracer.span(
            "rag.query.retrieve",
            trace_id=state["trace_id"],
            parent_span_id=state["parent_span_id"],
            input=state["rewritten_query"],
            metadata=self.config.query.model_dump(),
        ) as span:
            hits = self.index.search(
                state["rewritten_query"],
                top_k=candidate_k,
                alpha=self.config.query.hybrid_alpha,
                active_only=self.config.query.active_only,
            )
            span["output"] = [hit.chunk.chunk_id for hit in hits]
        return {
            "candidates": hits,
            "trajectory": self._append_step(state, "retrieve"),
        }

    def rerank_node(self, state: RAGGraphState) -> dict[str, Any]:
        with self.tracer.span(
            "rag.query.rerank",
            trace_id=state["trace_id"],
            parent_span_id=state["parent_span_id"],
            input=[hit.chunk.chunk_id for hit in state["candidates"]],
        ) as span:
            hits = lexical_rerank(state["rewritten_query"], state["candidates"])
            hits = [
                hit
                for hit in hits[: self.config.query.rerank_top_n]
                if hit.score >= self.config.query.min_relevance_score
            ]
            span["output"] = [hit.chunk.chunk_id for hit in hits]
        return {
            "selected_hits": hits,
            "trajectory": self._append_step(state, "rerank"),
        }

    @staticmethod
    def _citation(hit: RetrievalHit) -> Citation:
        metadata = hit.chunk.metadata
        evidence_id = metadata.get("evidence_id")
        if not evidence_id:
            contained = metadata.get("contained_evidence_ids", [])
            evidence_id = contained[0] if contained else hit.chunk.chunk_id
        return Citation(
            evidence_id=evidence_id,
            document_id=hit.chunk.document_id,
            page=metadata.get("page"),
            region=metadata.get("region"),
            table_cell=metadata.get("table_cell"),
        )

    def generate_node(self, state: RAGGraphState) -> dict[str, Any]:
        context_parts = []
        context_chars = 0
        selected: list[RetrievalHit] = []
        for hit in state["selected_hits"]:
            if context_chars + len(hit.chunk.text) > self.config.query.max_context_chars:
                break
            context_parts.append(f"[{hit.chunk.chunk_id}] {hit.chunk.text}")
            context_chars += len(hit.chunk.text)
            selected.append(hit)
        context = "\n\n".join(context_parts)
        with self.tracer.span(
            "rag.query.generate",
            trace_id=state["trace_id"],
            parent_span_id=state["parent_span_id"],
            input={
                "question": state["question"],
                "context_ids": [hit.chunk.chunk_id for hit in selected],
            },
        ) as span:
            if not selected:
                answer = "证据不足，无法回答。"
                abstained = True
                generation_metadata = {"mode": "abstain"}
            elif self.chat:
                prompt = (
                    "仅根据以下证据回答问题。不得补充证据外事实；证据不足时明确拒答。"
                    "直接回答用户问题，不扩展未被询问的分析；正文不超过300字。"
                    "回答后最多列出4个使用的证据ID。\n\n"
                    f"问题：{state['question']}\n\n证据：\n{context}"
                )
                response = self.chat.complete(
                    prompt,
                    metadata={
                        "trace_id": state["trace_id"],
                        "index_version": self.config.index.index_version,
                    },
                )
                answer = response.text
                abstained = "证据不足" in answer
                generation_metadata = {
                    "mode": "model",
                    "input_tokens": response.input_tokens,
                    "output_tokens": response.output_tokens,
                }
            else:
                answer = "；".join(
                    hit.chunk.text.replace("\n", " ") for hit in selected[:2]
                )
                abstained = False
                generation_metadata = {"mode": "extractive_local"}
            span["output"] = {"answer": answer, "abstained": abstained}
            span["metadata"] = generation_metadata

        retrieved_ids: list[str] = []
        for hit in state["selected_hits"]:
            evidence_ids = hit.chunk.metadata.get("contained_evidence_ids", [])
            retrieved_ids.extend(evidence_ids or [hit.chunk.chunk_id])
        return {
            "answer": answer,
            "abstained": abstained,
            "context": context,
            "input_chars": context_chars,
            "selected_hits": selected,
            "citations": [self._citation(hit) for hit in selected],
            "retrieved_ids": retrieved_ids,
            "generation_metadata": generation_metadata,
            "trajectory": self._append_step(state, "generate"),
        }

    def direct_response_node(self, state: RAGGraphState) -> dict[str, Any]:
        return {
            "rewritten_query": state["question"],
            "answer": "该请求不需要查询知识库。",
            "abstained": True,
            "citations": [],
            "retrieved_ids": [],
            "input_chars": 0,
            "trajectory": self._append_step(state, "direct_response"),
        }

    def query(self, query: str) -> QueryResult:
        start = time.perf_counter()
        with self.tracer.span(
            "rag.query",
            input={"query": query},
            metadata={
                "pipeline": self.config.name,
                "orchestrator": "langgraph",
                "workflow_version": self.workflow_version,
                "index_version": self.config.index.index_version,
                "data_version": self.config.data_version,
            },
        ) as root:
            invoke_config: dict[str, Any] = {
                "run_name": "rag-query",
                "metadata": {
                    "workflow_version": self.workflow_version,
                    "index_version": self.config.index.index_version,
                    "data_version": self.config.data_version,
                },
            }
            if self.callbacks:
                invoke_config["callbacks"] = self.callbacks
            state = self.graph.invoke(
                {
                    "question": query,
                    "trace_id": root["trace_id"],
                    "parent_span_id": root["span_id"],
                    "trajectory": [],
                },
                config=invoke_config,
            )
            root["output"] = {
                "intent": state["intent"],
                "trajectory": state["trajectory"],
                "hit_count": len(state.get("selected_hits", [])),
                "abstained": state["abstained"],
            }
            return QueryResult(
                query=query,
                rewritten_query=state.get("rewritten_query", query),
                intent=state["intent"],
                answer=state["answer"],
                citations=state.get("citations", []),
                retrieved_ids=state.get("retrieved_ids", []),
                latency_ms=(time.perf_counter() - start) * 1000,
                input_chars=state.get("input_chars", 0),
                abstained=state["abstained"],
                metadata={
                    "trace_id": root["trace_id"],
                    "workflow_version": self.workflow_version,
                    "trajectory": state["trajectory"],
                    "index_version": self.config.index.index_version,
                    "pipeline": self.config.name,
                    "generation": state.get("generation_metadata", {}),
                    "contexts": [
                        hit.chunk.text for hit in state.get("selected_hits", [])
                    ],
                },
            )
