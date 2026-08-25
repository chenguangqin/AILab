from roche_agent.rules import (
    RoleConsistencyRule,
    RuleEngine,
    TemperatureMaxRule,
    build_iso_training_facts,
)


def test_rules_find_temperature_role_and_low_confidence(project_root):
    facts = build_iso_training_facts(
        project_root / "data" / "iso" / "ocr" / "temperature_log.json"
    )
    findings = RuleEngine([TemperatureMaxRule(), RoleConsistencyRule()]).evaluate(facts)
    names = {finding.finding for finding in findings}
    assert "temperature_out_of_range_and_marked_qualified" in names
    assert "temperature_requires_source_review" in names
    assert "role_conflict" in names
    low_confidence = next(
        finding for finding in findings if finding.finding == "temperature_requires_source_review"
    )
    assert low_confidence.rule_result.status == "unknown"
    assert low_confidence.required_human_action == "check_original_record"

