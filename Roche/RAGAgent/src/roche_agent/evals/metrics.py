from __future__ import annotations

import math
import statistics
from typing import Any

from roche_agent.contracts import QueryResult


def retrieval_recall(retrieved: list[str], expected: list[str]) -> float:
    if not expected:
        return 1.0
    return len(set(retrieved) & set(expected)) / len(set(expected))


def reciprocal_rank(retrieved: list[str], expected: list[str]) -> float:
    expected_set = set(expected)
    for rank, item in enumerate(retrieved, start=1):
        if item in expected_set:
            return 1.0 / rank
    return 0.0


def ndcg(retrieved: list[str], expected: list[str]) -> float:
    if not expected:
        return 1.0
    expected_set = set(expected)
    dcg = sum(
        1.0 / math.log2(rank + 1)
        for rank, item in enumerate(retrieved, start=1)
        if item in expected_set
    )
    ideal_hits = min(len(expected_set), len(retrieved))
    ideal = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    return dcg / ideal if ideal else 0.0


def evaluate_case(
    result: QueryResult,
    *,
    expected_evidence_ids: list[str],
    answerable: bool,
) -> dict[str, float]:
    cited = [citation.evidence_id for citation in result.citations]
    return {
        "evidence_recall": retrieval_recall(result.retrieved_ids, expected_evidence_ids),
        "mrr": reciprocal_rank(result.retrieved_ids, expected_evidence_ids),
        "ndcg": ndcg(result.retrieved_ids, expected_evidence_ids),
        "citation_recall": retrieval_recall(cited, expected_evidence_ids),
        "abstention_accuracy": float(result.abstained == (not answerable)),
        "latency_ms": result.latency_ms,
        "input_chars": float(result.input_chars),
    }


def aggregate_results(rows: list[dict[str, Any]]) -> dict[str, float]:
    if not rows:
        return {}
    metric_names = rows[0]["metrics"].keys()
    output: dict[str, float] = {}
    for name in metric_names:
        values = [float(row["metrics"][name]) for row in rows]
        output[f"mean_{name}"] = statistics.mean(values)
        output[f"p95_{name}"] = sorted(values)[round((len(values) - 1) * 0.95)]
    return output

