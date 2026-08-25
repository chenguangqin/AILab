from roche_agent.evals.metrics import ndcg, reciprocal_rank, retrieval_recall


def test_retrieval_metrics():
    retrieved = ["wrong", "evidence-b", "evidence-a"]
    expected = ["evidence-a", "evidence-b"]
    assert retrieval_recall(retrieved, expected) == 1.0
    assert reciprocal_rank(retrieved, expected) == 0.5
    assert 0 < ndcg(retrieved, expected) < 1


def test_empty_expected_evidence_is_not_a_retrieval_failure():
    assert retrieval_recall(["anything"], []) == 1.0
    assert ndcg(["anything"], []) == 1.0

