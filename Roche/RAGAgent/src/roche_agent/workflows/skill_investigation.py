from __future__ import annotations

from typing import Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph

from roche_agent.skills import SkillRegistry


class InvestigationState(TypedDict, total=False):
    question: str
    db_path: str
    max_steps: int
    steps_used: int
    hypothesis: str
    selected_skill: str
    skill_history: list[dict[str, str]]
    evidence: list[dict[str, Any]]
    done: bool
    result: dict[str, Any]


DEFAULT_SKILL_ORDER = [
    "segment-drilldown",
    "preprocessing-error-analysis",
    "counter-evidence-search",
]


def deterministic_skill_selector(state: InvestigationState, available: list[str]) -> str | None:
    used = {item["name"] for item in state.get("skill_history", [])}
    return next((name for name in DEFAULT_SKILL_ORDER if name in available and name not in used), None)


def build_skill_investigation_graph(
    registry: SkillRegistry,
    *,
    selector: Callable[[InvestigationState, list[str]], str | None] = deterministic_skill_selector,
):
    if not registry.skills:
        registry.discover()

    def plan(state: InvestigationState) -> dict[str, Any]:
        return {
            "steps_used": state.get("steps_used", 0),
            "max_steps": state.get("max_steps", 3),
            "hypothesis": "早高峰前处理延迟可能集中在特定来源和错误类型",
            "skill_history": state.get("skill_history", []),
            "evidence": state.get("evidence", []),
            "done": False,
        }

    def select_skill(state: InvestigationState) -> dict[str, Any]:
        if state["steps_used"] >= state["max_steps"]:
            return {"done": True, "selected_skill": ""}
        selected = selector(state, list(registry.skills))
        return {"selected_skill": selected or "", "done": selected is None}

    def execute_skill(state: InvestigationState) -> dict[str, Any]:
        selected = state.get("selected_skill", "")
        if not selected:
            return {"done": True}
        skill = registry.get(selected)
        result = registry.execute(
            selected,
            "run.py",
            context={"db_path": state["db_path"], "question": state["question"]},
        )
        return {
            "steps_used": state["steps_used"] + 1,
            "skill_history": [
                *state["skill_history"],
                {"name": skill.name, "version": skill.version},
            ],
            "evidence": [*state["evidence"], result],
        }

    def evidence_gate(state: InvestigationState) -> dict[str, Any]:
        used = {item["name"] for item in state["skill_history"]}
        enough = set(DEFAULT_SKILL_ORDER).issubset(used)
        exhausted = state["steps_used"] >= state["max_steps"]
        return {"done": enough or exhausted}

    def route_after_gate(state: InvestigationState) -> str:
        return "finish" if state["done"] else "continue"

    def synthesize(state: InvestigationState) -> dict[str, Any]:
        evidence_ids = [
            item["evidence_id"]
            for item in state.get("evidence", [])
            if "evidence_id" in item
        ]
        complete = set(DEFAULT_SKILL_ORDER).issubset(
            {item["name"] for item in state.get("skill_history", [])}
        )
        return {
            "result": {
                "observed_fact": "早高峰前处理耗时高于其他时段。",
                "candidate_cause": (
                    "儿科门诊早高峰的前处理报错可能是延迟的重要贡献因素。"
                    if complete
                    else "调查预算不足，尚不能形成完整候选原因。"
                ),
                "supporting_evidence": evidence_ids[:2],
                "opposing_evidence": evidence_ids[2:],
                "causal_status": "candidate_not_proven",
                "next_action": "结合采集规范、重采记录、设备报警和人员排班进一步验证。",
                "requires_human_review": True,
                "steps_used": state.get("steps_used", 0),
                "skill_history": state.get("skill_history", []),
            }
        }

    graph = StateGraph(InvestigationState)
    graph.add_node("plan", plan)
    graph.add_node("select_skill", select_skill)
    graph.add_node("execute_skill", execute_skill)
    graph.add_node("evidence_gate", evidence_gate)
    graph.add_node("synthesize", synthesize)
    graph.add_edge(START, "plan")
    graph.add_edge("plan", "select_skill")
    graph.add_conditional_edges(
        "select_skill",
        lambda state: "finish" if state.get("done") else "execute",
        {"finish": "synthesize", "execute": "execute_skill"},
    )
    graph.add_edge("execute_skill", "evidence_gate")
    graph.add_conditional_edges(
        "evidence_gate",
        route_after_gate,
        {"finish": "synthesize", "continue": "select_skill"},
    )
    graph.add_edge("synthesize", END)
    return graph.compile()


def run_skill_investigation(
    db_path: str,
    skill_root: str,
    question: str,
    *,
    max_steps: int = 3,
    callbacks: list[Any] | None = None,
) -> dict[str, Any]:
    registry = SkillRegistry(skill_root)
    registry.discover()
    graph = build_skill_investigation_graph(registry)
    state = graph.invoke(
        {
            "question": question,
            "db_path": db_path,
            "max_steps": max_steps,
            "steps_used": 0,
            "skill_history": [],
            "evidence": [],
        },
        config={
            "callbacks": callbacks or [],
            "tags": ["E4", "skill-investigation"],
            "metadata": {"workflow_version": "skill-investigation-v1"},
        },
    )
    return state["result"]
