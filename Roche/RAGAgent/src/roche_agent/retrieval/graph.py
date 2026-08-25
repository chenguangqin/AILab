from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from roche_agent.contracts import Citation, RetrievalHit

if TYPE_CHECKING:
    from .pipeline import RAGPipeline


class RAGGraphState(TypedDict, total=False):
    question: str
    trace_id: str
    parent_span_id: str
    intent: str
    rewritten_query: str
    candidates: list[RetrievalHit]
    selected_hits: list[RetrievalHit]
    context: str
    answer: str
    citations: list[Citation]
    retrieved_ids: list[str]
    input_chars: int
    abstained: bool
    generation_metadata: dict[str, Any]
    trajectory: list[str]


def route_after_intent(state: RAGGraphState) -> Literal["rewrite", "direct_response"]:
    return "rewrite" if state["intent"] == "knowledge_search" else "direct_response"


def build_rag_graph(pipeline: "RAGPipeline") -> Any:
    builder = StateGraph(RAGGraphState)
    builder.add_node("intent", pipeline.intent_node)
    builder.add_node("rewrite", pipeline.rewrite_node)
    builder.add_node("retrieve", pipeline.retrieve_node)
    builder.add_node("rerank", pipeline.rerank_node)
    builder.add_node("generate", pipeline.generate_node)
    builder.add_node("direct_response", pipeline.direct_response_node)

    builder.add_edge(START, "intent")
    builder.add_conditional_edges(
        "intent",
        route_after_intent,
        {
            "rewrite": "rewrite",
            "direct_response": "direct_response",
        },
    )
    builder.add_edge("rewrite", "retrieve")
    builder.add_edge("retrieve", "rerank")
    builder.add_edge("rerank", "generate")
    builder.add_edge("generate", END)
    builder.add_edge("direct_response", END)
    return builder.compile()
