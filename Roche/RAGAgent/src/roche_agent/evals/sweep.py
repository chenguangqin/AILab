from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

from roche_agent.contracts import PipelineConfig
from roche_agent.observability import JsonTracer
from roche_agent.retrieval import RAGPipeline, load_pipeline_config

from .runner import EvaluationRunner, load_eval_cases


def apply_overrides(config: PipelineConfig, overrides: dict[str, Any], name: str) -> PipelineConfig:
    data = copy.deepcopy(config.model_dump())
    data["name"] = name
    for dotted_key, value in overrides.items():
        target = data
        parts = dotted_key.split(".")
        for part in parts[:-1]:
            target = target[part]
        target[parts[-1]] = value
    data["index"]["index_version"] = name
    return PipelineConfig.model_validate(data)


def run_sweep(
    matrix_path: str | Path,
    *,
    project_root: str | Path,
) -> dict[str, Any]:
    root = Path(project_root)
    matrix = yaml.safe_load(Path(matrix_path).read_text(encoding="utf-8"))
    base_path = root / matrix["base_config"]
    base = load_pipeline_config(base_path)
    cases = load_eval_cases(
        root / "evals" / "datasets" / "iso_rag_cases.jsonl",
        split=matrix.get("split", "dev"),
    )
    experiments = []
    for experiment in matrix["experiments"]:
        config = apply_overrides(
            base,
            experiment.get("overrides", {}),
            experiment["name"],
        )
        pipeline = RAGPipeline(config, tracer=JsonTracer())
        pipeline.build(root / "data" / "iso" / "documents")
        report = EvaluationRunner(pipeline).run(cases)
        experiments.append(
            {
                "name": config.name,
                "changed_variable": experiment.get("changed_variable", "baseline"),
                "overrides": experiment.get("overrides", {}),
                "summary": report["summary"],
            }
        )
    baseline = experiments[0]["summary"]
    for experiment in experiments:
        experiment["delta"] = {
            key: value - baseline.get(key, 0.0)
            for key, value in experiment["summary"].items()
            if key.startswith("mean_")
        }
    return {"matrix": str(matrix_path), "experiments": experiments}

