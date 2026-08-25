import pytest

from roche_agent.analytics import import_operations_csv
from roche_agent.skills import SkillRegistry


def test_skill_registry_progressive_disclosure_and_allowlist(tmp_path, project_root):
    db = tmp_path / "operations.db"
    import_operations_csv(
        project_root / "data" / "analytics" / "raw" / "lab_operations_2026-08.csv",
        db,
    )
    registry = SkillRegistry(project_root / "skills")
    skills = registry.discover()
    assert set(skills) == {
        "segment-drilldown",
        "preprocessing-error-analysis",
        "counter-evidence-search",
    }
    summaries = registry.summaries()
    assert all("instructions" not in summary for summary in summaries)
    reference = registry.get("segment-drilldown").read_reference("metrics.md")
    assert "前处理耗时" in reference
    result = registry.execute(
        "segment-drilldown",
        "run.py",
        context={"db_path": str(db)},
    )
    assert result["evidence_id"] == "analytics:cohort:pediatric-peak"
    with pytest.raises(PermissionError):
        registry.execute(
            "segment-drilldown",
            "not-allowed.py",
            context={"db_path": str(db)},
        )

