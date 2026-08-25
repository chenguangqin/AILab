from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph


class ReviewState(TypedDict, total=False):
    case: dict[str, Any]
    rule_hits: list[str]
    accessed_sources: list[str]
    evidence: list[dict[str, Any]]
    needs_more_context: bool
    requires_human_review: bool
    result: dict[str, Any]


def build_review_graph():
    def safety_rules(state: ReviewState) -> dict[str, Any]:
        case = state["case"]
        hits = []
        if case["current_result"] >= case["rules"]["review_threshold"]:
            hits.append("RESULT_REQUIRES_REVIEW")
        return {
            "rule_hits": hits,
            "accessed_sources": ["current_result", "rules"],
            "evidence": [],
            "needs_more_context": bool(hits),
            "requires_human_review": bool(hits),
        }

    def recent_history(state: ReviewState) -> dict[str, Any]:
        recent = state["case"].get("recent_history")
        evidence = [*state["evidence"]]
        if recent is not None:
            evidence.append({"source": "recent_history", "values": recent})
        return {
            "accessed_sources": [*state["accessed_sources"], "recent_history"],
            "evidence": evidence,
            "needs_more_context": recent is None or len(recent) < 2,
        }

    def operational_context(state: ReviewState) -> dict[str, Any]:
        case = state["case"]
        evidence = [
            *state["evidence"],
            {"source": "quality_control", "status": case.get("quality_control")},
            {"source": "instrument_alarm", "status": case.get("instrument_alarm")},
        ]
        conflict = (
            case.get("quality_control") != "pass"
            or case.get("instrument_alarm") not in (None, "none")
            or "quality_control" not in case
            or "instrument_alarm" not in case
        )
        return {
            "accessed_sources": [
                *state["accessed_sources"],
                "quality_control",
                "instrument_alarm",
            ],
            "evidence": evidence,
            "requires_human_review": state["requires_human_review"] or conflict,
            "needs_more_context": False,
        }

    def older_history(state: ReviewState) -> dict[str, Any]:
        older = state["case"].get("older_history")
        evidence = [*state["evidence"]]
        if older is not None:
            evidence.append({"source": "older_history", "values": older})
        return {
            "accessed_sources": [*state["accessed_sources"], "older_history"],
            "evidence": evidence,
            "needs_more_context": False,
        }

    def route_after_rules(state: ReviewState) -> str:
        return "recent" if state["needs_more_context"] else "finish"

    def route_after_recent(state: ReviewState) -> str:
        if state["needs_more_context"]:
            return "older"
        if state["requires_human_review"]:
            return "operations"
        return "finish"

    def synthesize(state: ReviewState) -> dict[str, Any]:
        missing = [
            source
            for source in ["quality_control", "instrument_alarm"]
            if source in state.get("accessed_sources", [])
            and source not in state["case"]
        ]
        requires_human = state.get("requires_human_review", False) or bool(missing)
        return {
            "result": {
                "rule_hits": state.get("rule_hits", []),
                "evidence": state.get("evidence", []),
                "accessed_sources": state.get("accessed_sources", []),
                "missing_sources": missing,
                "decision": "human_review" if requires_human else "no_additional_review",
                "requires_human_review": requires_human,
                "clinical_claim": None,
            }
        }

    graph = StateGraph(ReviewState)
    graph.add_node("safety_rules", safety_rules)
    graph.add_node("recent_history", recent_history)
    graph.add_node("older_history", older_history)
    graph.add_node("operational_context", operational_context)
    graph.add_node("synthesize", synthesize)
    graph.add_edge(START, "safety_rules")
    graph.add_conditional_edges(
        "safety_rules",
        route_after_rules,
        {"recent": "recent_history", "finish": "synthesize"},
    )
    graph.add_conditional_edges(
        "recent_history",
        route_after_recent,
        {"older": "older_history", "operations": "operational_context", "finish": "synthesize"},
    )
    graph.add_edge("older_history", "operational_context")
    graph.add_edge("operational_context", "synthesize")
    graph.add_edge("synthesize", END)
    return graph.compile()


def run_review_case(case: dict[str, Any], *, callbacks: list[Any] | None = None) -> dict[str, Any]:
    return build_review_graph().invoke(
        {"case": case},
        config={
            "callbacks": callbacks or [],
            "tags": ["E5", "review-workflow"],
            "metadata": {
                "workflow_version": "review-v1",
                "rule_version": case.get("rules", {}).get("version"),
            },
        },
    )["result"]
