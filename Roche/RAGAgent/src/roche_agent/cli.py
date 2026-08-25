from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from roche_agent.analytics import import_operations_csv
from roche_agent.evals import EvaluationRunner, load_eval_cases, run_sweep
from roche_agent.observability import (
    langfuse_callbacks_from_env,
    sync_dataset_to_langfuse,
    tracer_from_env,
)
from roche_agent.providers import create_chat_provider, create_embedding_provider
from roche_agent.retrieval import RAGPipeline, load_pipeline_config
from roche_agent.rules import (
    RoleConsistencyRule,
    RuleEngine,
    TemperatureMaxRule,
    build_iso_training_facts,
)
from roche_agent.workflows import (
    compare_architectures,
    run_review_case,
    run_skill_investigation,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


def print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def rag_pipeline(config_path: str, artifact_name: str) -> RAGPipeline:
    config = load_pipeline_config(config_path)
    tracer = tracer_from_env(PROJECT_ROOT / "artifacts" / artifact_name / "trace.json")
    pipeline = RAGPipeline(
        config,
        embedder=create_embedding_provider(config),
        chat=create_chat_provider(),
        tracer=tracer,
    )
    pipeline.build(PROJECT_ROOT / "data" / "iso" / "documents")
    return pipeline


def command_rag_build(args: argparse.Namespace) -> None:
    pipeline = rag_pipeline(args.config, Path(args.config).stem)
    pipeline.tracer.flush()
    print_json(
        {
            "pipeline": pipeline.config.name,
            "index_version": pipeline.config.index.index_version,
            "chunk_count": len(pipeline.chunks),
        }
    )


def command_rag_evaluate(args: argparse.Namespace) -> None:
    pipeline = rag_pipeline(args.config, pipeline_name(args.config))
    cases = load_eval_cases(
        PROJECT_ROOT / "evals" / "datasets" / "iso_rag_cases.jsonl",
        split=args.split,
    )
    report = EvaluationRunner(pipeline).run(cases)
    if args.ragas:
        from roche_agent.evals.ragas_adapter import (
            bedrock_ragas_components,
            evaluate_with_ragas,
            summarize_ragas_results,
        )

        llm, embeddings = bedrock_ragas_components()
        ragas_records = evaluate_with_ragas(
            report["cases"],
            llm=llm,
            embeddings=embeddings,
            show_progress=False,
        )
        report["ragas"] = {
            "summary": summarize_ragas_results(ragas_records),
            "cases": ragas_records,
        }
    output = PROJECT_ROOT / "artifacts" / pipeline_name(args.config) / f"{args.split}.json"
    EvaluationRunner.save(report, output)
    pipeline.tracer.flush()
    console_output = {"output": str(output), "summary": report["summary"]}
    if args.ragas:
        console_output["ragas_summary"] = report["ragas"]["summary"]
    print_json(console_output)


def pipeline_name(config_path: str) -> str:
    return load_pipeline_config(config_path).name


def command_rag_sweep(args: argparse.Namespace) -> None:
    report = run_sweep(args.matrix, project_root=PROJECT_ROOT)
    output = PROJECT_ROOT / "artifacts" / "e1-sweep.json"
    EvaluationRunner.save(report, output)
    print_json({"output": str(output), "experiments": report["experiments"]})


def command_rules_evaluate(args: argparse.Namespace) -> None:
    facts = build_iso_training_facts(PROJECT_ROOT / "data" / "iso" / "ocr" / "temperature_log.json")
    findings = RuleEngine([TemperatureMaxRule(), RoleConsistencyRule()]).evaluate(facts)
    print_json([finding.model_dump(mode="json") for finding in findings])


def command_analytics_import(args: argparse.Namespace) -> None:
    print_json(import_operations_csv(args.csv, args.db))


def command_analytics_investigate(args: argparse.Namespace) -> None:
    result = run_skill_investigation(
        db_path=args.db,
        skill_root=str(PROJECT_ROOT / "skills"),
        question=args.question,
        max_steps=args.max_steps,
        callbacks=langfuse_callbacks_from_env(),
    )
    print_json(result)


def command_architecture_compare(args: argparse.Namespace) -> None:
    print_json(compare_architectures(inject_prompt_attack=not args.no_attack))


def command_review_evaluate(args: argparse.Namespace) -> None:
    cases = json.loads((PROJECT_ROOT / "data" / "review" / "cases.json").read_text(encoding="utf-8"))
    results = []
    for case in cases:
        result = run_review_case(case, callbacks=langfuse_callbacks_from_env())
        results.append(
            {
                "case_id": case["case_id"],
                "result": result,
                "decision_correct": result["decision"] == case["expected_decision"],
                "trajectory_correct": result["accessed_sources"] == case["expected_sources"],
            }
        )
    print_json(results)


def command_langfuse_sync_dataset(args: argparse.Namespace) -> None:
    cases = load_eval_cases(
        PROJECT_ROOT / "evals" / "datasets" / "iso_rag_cases.jsonl"
    )
    count = sync_dataset_to_langfuse(args.name, cases)
    print_json({"dataset": args.name, "items": count})


def command_web(args: argparse.Namespace) -> None:
    from roche_agent.web import run_server

    run_server(host=args.host, port=args.port, config_path=args.config)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="roche-lab")
    commands = parser.add_subparsers(dest="command", required=True)

    rag = commands.add_parser("rag")
    rag_commands = rag.add_subparsers(dest="rag_command", required=True)
    rag_build = rag_commands.add_parser("build")
    rag_build.add_argument("--config", required=True)
    rag_build.set_defaults(func=command_rag_build)
    rag_evaluate = rag_commands.add_parser("evaluate")
    rag_evaluate.add_argument("--config", required=True)
    rag_evaluate.add_argument("--split", choices=["dev", "test"], default="dev")
    rag_evaluate.add_argument(
        "--ragas",
        action="store_true",
        help="run optional Bedrock-backed semantic metrics",
    )
    rag_evaluate.set_defaults(func=command_rag_evaluate)
    rag_sweep = rag_commands.add_parser("sweep")
    rag_sweep.add_argument("--matrix", required=True)
    rag_sweep.set_defaults(func=command_rag_sweep)

    rules = commands.add_parser("rules")
    rule_commands = rules.add_subparsers(dest="rules_command", required=True)
    rule_eval = rule_commands.add_parser("evaluate")
    rule_eval.set_defaults(func=command_rules_evaluate)

    analytics = commands.add_parser("analytics")
    analytics_commands = analytics.add_subparsers(dest="analytics_command", required=True)
    analytics_import = analytics_commands.add_parser("import")
    analytics_import.add_argument("--csv", required=True)
    analytics_import.add_argument("--db", required=True)
    analytics_import.set_defaults(func=command_analytics_import)
    analytics_investigate = analytics_commands.add_parser("investigate")
    analytics_investigate.add_argument("--db", required=True)
    analytics_investigate.add_argument("--question", required=True)
    analytics_investigate.add_argument("--max-steps", type=int, default=3)
    analytics_investigate.set_defaults(func=command_analytics_investigate)

    architecture = commands.add_parser("architecture")
    architecture_commands = architecture.add_subparsers(
        dest="architecture_command", required=True
    )
    compare = architecture_commands.add_parser("compare")
    compare.add_argument("--no-attack", action="store_true")
    compare.set_defaults(func=command_architecture_compare)

    review = commands.add_parser("review")
    review_commands = review.add_subparsers(dest="review_command", required=True)
    review_eval = review_commands.add_parser("evaluate")
    review_eval.set_defaults(func=command_review_evaluate)

    langfuse = commands.add_parser("langfuse")
    langfuse_commands = langfuse.add_subparsers(
        dest="langfuse_command", required=True
    )
    sync_dataset = langfuse_commands.add_parser("sync-dataset")
    sync_dataset.add_argument("--name", default="roche-iso-rag-v1")
    sync_dataset.set_defaults(func=command_langfuse_sync_dataset)

    web = commands.add_parser("web")
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", type=int, default=8000)
    web.add_argument(
        "--config",
        default="labs/E0_pipeline/config.baseline.yaml",
    )
    web.set_defaults(func=command_web)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
