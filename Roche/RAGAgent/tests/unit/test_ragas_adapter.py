import pytest


@pytest.mark.ragas
def test_ragas_dataset_uses_current_single_turn_columns():
    pytest.importorskip("ragas")
    from roche_agent.evals.ragas_adapter import build_ragas_dataset

    dataset = build_ragas_dataset(
        [
            {
                "case": {
                    "question": "温度上限？",
                    "reference_answer": "5°C",
                },
                "result": {
                    "answer": "5°C",
                    "metadata": {"contexts": ["温度不得高于5°C"]},
                },
            }
        ]
    )
    assert set(dataset.column_names) == {
        "user_input",
        "response",
        "retrieved_contexts",
        "reference",
    }


def test_ragas_summary_reports_partial_metric_failures():
    pytest.importorskip("ragas")
    from roche_agent.evals.ragas_adapter import summarize_ragas_results

    summary = summarize_ragas_results(
        [
            {
                "user_input": "q1",
                "faithfulness": 1.0,
                "answer_relevancy": 0.8,
            },
            {
                "user_input": "q2",
                "faithfulness": None,
                "answer_relevancy": 0.6,
            },
        ]
    )
    assert summary["mean_faithfulness"] == 1.0
    assert summary["mean_answer_relevancy"] == pytest.approx(0.7)
    assert summary["successful_faithfulness_cases"] == 1
    assert summary["failed_metrics"] == {"faithfulness": ["q2"]}
