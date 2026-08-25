from __future__ import annotations

import math
import os
from typing import Any


def build_ragas_dataset(rows: list[dict[str, Any]]) -> Any:
    try:
        from datasets import Dataset
    except ImportError as exc:
        raise RuntimeError("install the ragas extra: pip install -e '.[ragas]'") from exc
    return Dataset.from_list(
        [
            {
                "user_input": row["case"]["question"],
                "response": row["result"]["answer"],
                "retrieved_contexts": row["result"].get("metadata", {}).get("contexts", []),
                "reference": row["case"].get("reference_answer") or "",
            }
            for row in rows
        ]
    )


def evaluate_with_ragas(rows: list[dict[str, Any]], **kwargs: Any) -> list[dict[str, Any]]:
    """Run optional semantic metrics without making RAGAS a core dependency.

    The adapter intentionally receives normalized rows so the classroom can swap
    RAGAS versions without coupling the retrieval pipeline to its dataset API.
    """
    try:
        from ragas import evaluate
        from ragas.metrics import answer_relevancy, faithfulness
        from ragas.run_config import RunConfig
    except ImportError as exc:
        raise RuntimeError("install the ragas extra: pip install -e '.[ragas]'") from exc

    dataset = build_ragas_dataset(rows)
    kwargs.setdefault(
        "run_config",
        RunConfig(
            timeout=int(os.getenv("RAGAS_TIMEOUT_SECONDS", "180")),
            max_retries=int(os.getenv("RAGAS_MAX_RETRIES", "3")),
            max_workers=int(os.getenv("RAGAS_MAX_WORKERS", "2")),
        ),
    )
    kwargs.setdefault("raise_exceptions", False)
    kwargs.setdefault("batch_size", 1)
    result = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy],
        **kwargs,
    )
    records = result.to_pandas().to_dict(orient="records")
    for record in records:
        for key, value in list(record.items()):
            if isinstance(value, float) and math.isnan(value):
                record[key] = None
    return records


def summarize_ragas_results(records: list[dict[str, Any]]) -> dict[str, Any]:
    metric_names = ["faithfulness", "answer_relevancy"]
    summary: dict[str, Any] = {}
    failed_metrics: dict[str, list[str]] = {}
    for metric in metric_names:
        values = [
            float(record[metric])
            for record in records
            if record.get(metric) is not None
        ]
        summary[f"mean_{metric}"] = sum(values) / len(values) if values else None
        summary[f"successful_{metric}_cases"] = len(values)
        failures = [
            str(record.get("user_input", "unknown"))
            for record in records
            if record.get(metric) is None
        ]
        if failures:
            failed_metrics[metric] = failures
    summary["total_cases"] = len(records)
    summary["failed_metrics"] = failed_metrics
    return summary


def bedrock_ragas_components() -> tuple[Any, Any]:
    try:
        from langchain_aws import BedrockEmbeddings, ChatBedrockConverse
    except ImportError as exc:
        raise RuntimeError("install the aws extra: pip install -e '.[aws]'") from exc
    chat_model = os.environ["BEDROCK_CHAT_MODEL_ID"]
    embedding_model = os.environ["BEDROCK_EMBED_MODEL_ID"]
    region = os.getenv("AWS_REGION", "us-east-1")
    return (
        ChatBedrockConverse(
            model=chat_model,
            region_name=region,
            temperature=0,
            max_tokens=int(os.getenv("RAGAS_MAX_TOKENS", "4096")),
        ),
        BedrockEmbeddings(
            model_id=embedding_model,
            region_name=region,
            normalize=True,
        ),
    )
