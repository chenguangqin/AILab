import time

from fastapi.testclient import TestClient

from roche_agent.web import create_app


def test_lab0_web_query_configuration_and_evaluation(project_root, monkeypatch):
    for name in [
        "LANGFUSE_HOST",
        "LANGFUSE_BASE_URL",
        "LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_SECRET_KEY",
    ]:
        monkeypatch.delenv(name, raising=False)

    app = create_app(
        project_root=project_root,
        config_path="labs/E0_pipeline/config.baseline.yaml",
    )
    with TestClient(app) as client:
        home = client.get("/")
        assert home.status_code == 200
        assert "Roche RAG Lab 0" in home.text

        status = client.get("/api/status").json()
        original_index = status["config"]["index"]["index_version"]
        expected_document_count = len(
            list((project_root / "data" / "iso" / "documents").glob("*.md"))
        )
        assert status["graph"]["workflow_version"] == "rag-langgraph-v1"
        assert status["manifest"]["document_count"] == expected_document_count

        query = client.post(
            "/api/query",
            json={"question": "现行SOP规定试剂冰箱最高温度是多少？"},
        )
        assert query.status_code == 200
        assert query.json()["metadata"]["trajectory"][-1] == "generate"

        query_config = status["config"]["query"]
        query_config["query_rewrite"] = True
        updated = client.put(
            "/api/config/query",
            json={"query": query_config},
        )
        assert updated.status_code == 200
        assert updated.json()["index_rebuilt"] is False
        assert updated.json()["config"]["index"]["index_version"] == original_index

        index_config = status["config"]["index"]
        index_config["chunk_strategy"] = "structure"
        rebuilt = client.post(
            "/api/index/rebuild",
            json={"index": index_config},
        )
        assert rebuilt.status_code == 200
        assert rebuilt.json()["index_rebuilt"] is True
        assert rebuilt.json()["manifest"]["index_version"] != original_index
        assert rebuilt.json()["manifest"]["chunk_count"] > status["manifest"]["chunk_count"]

        evaluation = client.post("/api/evaluations", json={"split": "test"})
        assert evaluation.status_code == 202
        job_id = evaluation.json()["job_id"]
        for _ in range(100):
            job = client.get(f"/api/evaluations/{job_id}").json()
            if job["status"] in {"completed", "failed"}:
                break
            time.sleep(0.02)
        assert job["status"] == "completed"
        assert job["case_count"] == 4
        assert "mean_evidence_recall" in job["summary"]
