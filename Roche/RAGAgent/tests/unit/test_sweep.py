from roche_agent.evals import run_sweep


def test_sweep_changes_one_variable_and_reports_deltas(project_root):
    report = run_sweep(
        project_root / "labs" / "E1_tuning" / "experiment_matrix.yaml",
        project_root=project_root,
    )
    assert len(report["experiments"]) == 6
    assert report["experiments"][0]["changed_variable"] == "baseline"
    assert "mean_mrr" in report["experiments"][1]["delta"]
