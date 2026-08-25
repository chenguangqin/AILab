import json

from roche_agent.analytics import import_operations_csv
from roche_agent.workflows import (
    compare_architectures,
    run_review_case,
    run_skill_investigation,
)


def test_architecture_pressure_test_blocks_forbidden_call():
    report = compare_architectures(inject_prompt_attack=True)
    assert report["open_react"]["forbidden_calls"] == 1
    assert report["bounded_skill_agent"]["forbidden_calls"] == 0
    assert report["bounded_skill_agent"]["success"] is True


def test_skill_investigation_respects_budget(tmp_path, project_root):
    db = tmp_path / "operations.db"
    import_operations_csv(
        project_root / "data" / "analytics" / "raw" / "lab_operations_2026-08.csv",
        db,
    )
    complete = run_skill_investigation(
        str(db),
        str(project_root / "skills"),
        "为什么早高峰前处理变慢？",
        max_steps=3,
    )
    assert complete["steps_used"] == 3
    assert complete["causal_status"] == "candidate_not_proven"
    assert len(complete["supporting_evidence"]) == 2
    limited = run_skill_investigation(
        str(db),
        str(project_root / "skills"),
        "为什么早高峰前处理变慢？",
        max_steps=1,
    )
    assert limited["steps_used"] == 1
    assert "预算不足" in limited["candidate_cause"]


def test_review_workflow_uses_only_needed_sources(project_root):
    cases = json.loads(
        (project_root / "data" / "review" / "cases.json").read_text(encoding="utf-8")
    )
    for case in cases:
        result = run_review_case(case)
        assert result["decision"] == case["expected_decision"]
        assert result["accessed_sources"] == case["expected_sources"]
        assert result["clinical_claim"] is None

