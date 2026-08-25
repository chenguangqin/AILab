from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from roche_agent.contracts import Fact, Finding, RuleResult


class Rule(Protocol):
    rule_id: str
    version: str

    def evaluate(self, facts: list[Fact]) -> list[Finding]:
        ...


@dataclass(frozen=True)
class TemperatureMaxRule:
    maximum: float = 5.0
    rule_id: str = "TEMP_MAX_5"
    version: str = "2.0"
    min_ocr_confidence: float = 0.8

    def evaluate(self, facts: list[Fact]) -> list[Finding]:
        findings: list[Finding] = []
        temperatures = [fact for fact in facts if fact.attribute == "temperature"]
        judgements = {
            fact.subject: fact
            for fact in facts
            if fact.attribute == "manual_judgement"
        }
        for fact in temperatures:
            if fact.confidence < self.min_ocr_confidence:
                result = RuleResult(
                    rule_id=self.rule_id,
                    rule_version=self.version,
                    status="unknown",
                    evidence_ids=[fact.source_evidence_id],
                    reason="OCR confidence below the approved threshold",
                    requires_human_review=True,
                )
                findings.append(
                    Finding(
                        finding="temperature_requires_source_review",
                        rule_result=result,
                        uncertainty=["temperature value is not reliable enough for automatic judgement"],
                        required_human_action="check_original_record",
                    )
                )
                continue
            value = float(fact.value)
            judgement = judgements.get(fact.subject)
            evidence_ids = [fact.source_evidence_id]
            if judgement:
                evidence_ids.append(judgement.source_evidence_id)
            failed = value > self.maximum
            inconsistent = failed and judgement and str(judgement.value) == "合格"
            result = RuleResult(
                rule_id=self.rule_id,
                rule_version=self.version,
                status="failed" if failed else "passed",
                evidence_ids=sorted(set(evidence_ids)),
                reason=(
                    f"recorded temperature {value:g}°C exceeds {self.maximum:g}°C"
                    if failed
                    else f"recorded temperature {value:g}°C is within limit"
                ),
                requires_human_review=bool(failed),
            )
            findings.append(
                Finding(
                    finding=(
                        "temperature_out_of_range_and_marked_qualified"
                        if inconsistent
                        else "temperature_out_of_range"
                        if failed
                        else "temperature_within_range"
                    ),
                    rule_result=result,
                    required_human_action="confirm_and_create_deviation" if failed else None,
                )
            )
        return findings


@dataclass(frozen=True)
class RoleConsistencyRule:
    rule_id: str = "PERSON_ROLE_CONSISTENCY"
    version: str = "1.0"

    def evaluate(self, facts: list[Fact]) -> list[Finding]:
        by_subject: dict[str, list[Fact]] = {}
        for fact in facts:
            if fact.attribute == "role":
                by_subject.setdefault(fact.subject, []).append(fact)
        findings: list[Finding] = []
        for subject, role_facts in by_subject.items():
            values = {str(fact.value) for fact in role_facts}
            if len(values) <= 1:
                continue
            evidence_ids = [fact.source_evidence_id for fact in role_facts]
            findings.append(
                Finding(
                    finding="role_conflict",
                    rule_result=RuleResult(
                        rule_id=self.rule_id,
                        rule_version=self.version,
                        status="failed",
                        evidence_ids=evidence_ids,
                        reason=f"{subject} has conflicting active roles: {', '.join(sorted(values))}",
                        requires_human_review=True,
                    ),
                    uncertainty=["the authoritative personnel source has not been selected"],
                    required_human_action="confirm_authoritative_role",
                )
            )
        return findings


class RuleEngine:
    def __init__(self, rules: list[Rule]):
        self.rules = rules

    def evaluate(self, facts: list[Fact]) -> list[Finding]:
        findings: list[Finding] = []
        for rule in self.rules:
            findings.extend(rule.evaluate(facts))
        return findings


def build_iso_training_facts(ocr_path: str | Path) -> list[Fact]:
    """Build approved training facts.

    In production, LLM-extracted candidates would require validation before
    entering this rule path.
    """
    data = json.loads(Path(ocr_path).read_text(encoding="utf-8"))
    by_cell = {cell["cell"]: cell for cell in data["cells"]}
    return [
        Fact(
            fact_id="fact-temp-2026-08-12",
            subject="R-01@2026-08-12T09:00",
            attribute="temperature",
            value=7,
            unit="°C",
            effective_at="2026-08-12T09:00",
            source_evidence_id="temp-log-aug::table::2026-08-12",
            confidence=float(by_cell["D3"]["confidence"]),
        ),
        Fact(
            fact_id="fact-judgement-2026-08-12",
            subject="R-01@2026-08-12T09:00",
            attribute="manual_judgement",
            value="合格",
            effective_at="2026-08-12T09:00",
            source_evidence_id="temp-log-aug::table::2026-08-12",
            confidence=float(by_cell["E3"]["confidence"]),
        ),
        Fact(
            fact_id="fact-temp-2026-08-14",
            subject="R-01@2026-08-14T16:00",
            attribute="temperature",
            value=9,
            unit="°C",
            effective_at="2026-08-14T16:00",
            source_evidence_id="temp-log-low-confidence",
            confidence=float(by_cell["D9"]["confidence"]),
        ),
        Fact(
            fact_id="fact-role-appointment-li-ming",
            subject="李明",
            attribute="role",
            value="生化组组长",
            effective_at="2026-07-01",
            source_evidence_id="appointment-li-ming",
        ),
        Fact(
            fact_id="fact-role-register-li-ming",
            subject="李明",
            attribute="role",
            value="免疫组副组长",
            effective_at="2026-08-01",
            source_evidence_id="role-register-li-ming",
        ),
    ]

