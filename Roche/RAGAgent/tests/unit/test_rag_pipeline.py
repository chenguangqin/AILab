from roche_agent.evals import EvaluationRunner, load_eval_cases
from roche_agent.observability import JsonTracer
from roche_agent.retrieval import RAGPipeline, load_pipeline_config


def run_report(project_root, config_path, split):
    pipeline = RAGPipeline(
        load_pipeline_config(config_path),
        tracer=JsonTracer(),
    )
    pipeline.build(project_root / "data" / "iso" / "documents")
    cases = load_eval_cases(
        project_root / "evals" / "datasets" / "iso_rag_cases.jsonl",
        split=split,
    )
    return pipeline, EvaluationRunner(pipeline).run(cases)


def test_pipeline_records_index_version_and_returns_citations(project_root):
    pipeline, report = run_report(
        project_root,
        project_root / "labs" / "E1_tuning" / "config.optimized.yaml",
        "dev",
    )
    assert report["cases"]
    first = report["cases"][0]["result"]
    assert first["metadata"]["index_version"] == "structure-hybrid-v1"
    assert first["metadata"]["workflow_version"] == "rag-langgraph-v1"
    assert first["metadata"]["trajectory"] == [
        "intent",
        "rewrite",
        "retrieve",
        "rerank",
        "generate",
    ]
    assert first["citations"]
    event_names = {event.name for event in pipeline.tracer.events}
    assert "rag.index.chunk" in event_names
    assert "rag.query.rerank" in event_names
    assert "rag.query.generate" in event_names
    query_end = next(
        index
        for index, event in enumerate(pipeline.tracer.events)
        if event.name == "rag.query" and event.event_type == "span_end"
    )
    generation_end = next(
        index
        for index, event in enumerate(pipeline.tracer.events)
        if event.name == "rag.query.generate" and event.event_type == "span_end"
    )
    assert generation_end < query_end


def test_optimized_pipeline_improves_ranking_and_context_efficiency(project_root):
    _, baseline = run_report(
        project_root,
        project_root / "labs" / "E0_pipeline" / "config.baseline.yaml",
        "dev",
    )
    _, optimized = run_report(
        project_root,
        project_root / "labs" / "E1_tuning" / "config.optimized.yaml",
        "dev",
    )
    assert optimized["summary"]["mean_mrr"] > baseline["summary"]["mean_mrr"]
    assert optimized["summary"]["mean_citation_recall"] > baseline["summary"][
        "mean_citation_recall"
    ]
    assert optimized["summary"]["mean_input_chars"] < baseline["summary"]["mean_input_chars"]
    assert optimized["summary"]["mean_evidence_recall"] >= (
        baseline["summary"]["mean_evidence_recall"] - 0.125
    )
