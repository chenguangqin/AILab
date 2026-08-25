from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from pydantic import BaseModel, Field

from roche_agent.retrieval import RAGPipeline

from .metrics import aggregate_results, evaluate_case


class EvalCase(BaseModel):
    case_id: str
    split: str = "dev"
    question: str
    expected_evidence_ids: list[str] = Field(default_factory=list)
    answerable: bool = True
    reference_answer: str | None = None
    tags: list[str] = Field(default_factory=list)


def load_eval_cases(path: str | Path, split: str | None = None) -> list[EvalCase]:
    cases = [
        EvalCase.model_validate_json(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return [case for case in cases if split is None or case.split == split]


class EvaluationRunner:
    def __init__(self, pipeline: RAGPipeline):
        self.pipeline = pipeline

    def run(self, cases: Iterable[EvalCase]) -> dict[str, Any]:
        rows = []
        for case in cases:
            result = self.pipeline.query(case.question)
            metrics = evaluate_case(
                result,
                expected_evidence_ids=case.expected_evidence_ids,
                answerable=case.answerable,
            )
            trace_id = str(result.metadata.get("trace_id", ""))
            for name, value in metrics.items():
                self.pipeline.tracer.score(trace_id, name, value, comment=case.case_id)
            rows.append(
                {
                    "case": case.model_dump(),
                    "result": result.model_dump(mode="json"),
                    "metrics": metrics,
                }
            )
        return {
            "pipeline": self.pipeline.config.model_dump(),
            "summary": aggregate_results(rows),
            "cases": rows,
        }

    @staticmethod
    def save(report: dict[str, Any], path: str | Path) -> None:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

