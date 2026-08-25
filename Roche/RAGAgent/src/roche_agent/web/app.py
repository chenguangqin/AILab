from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .runtime import (
    EvaluationJobManager,
    EvaluationRequest,
    IndexRebuildRequest,
    LabRuntime,
    QueryConfigRequest,
    QueryRequest,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
STATIC_ROOT = Path(__file__).resolve().parent / "static"
DEFAULT_CONFIG = "labs/E0_pipeline/config.baseline.yaml"


def create_app(
    *,
    project_root: str | Path = PROJECT_ROOT,
    config_path: str | Path = DEFAULT_CONFIG,
) -> FastAPI:
    runtime = LabRuntime(project_root, config_path)
    jobs = EvaluationJobManager(runtime)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        jobs.shutdown()

    app = FastAPI(
        title="Roche RAG Lab 0",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.runtime = runtime
    app.state.evaluation_jobs = jobs
    app.mount("/static", StaticFiles(directory=STATIC_ROOT), name="static")

    @app.get("/", include_in_schema=False)
    def home() -> FileResponse:
        return FileResponse(STATIC_ROOT / "index.html")

    @app.get("/api/status")
    def status() -> dict[str, Any]:
        return runtime.status()

    @app.post("/api/query")
    def query(request: QueryRequest) -> dict[str, Any]:
        try:
            return runtime.query(request).model_dump(mode="json")
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.put("/api/config/query")
    def update_query_config(request: QueryConfigRequest) -> dict[str, Any]:
        return runtime.update_query_config(request)

    @app.post("/api/index/rebuild")
    def rebuild_index(request: IndexRebuildRequest) -> dict[str, Any]:
        try:
            return runtime.rebuild_index(request)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/api/evaluations", status_code=202)
    def create_evaluation(request: EvaluationRequest) -> dict[str, Any]:
        return jobs.submit(request)

    @app.get("/api/evaluations/{job_id}")
    def get_evaluation(job_id: str) -> dict[str, Any]:
        job = jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="evaluation job not found")
        return job

    return app


def run_server(
    *,
    host: str = "127.0.0.1",
    port: int = 8000,
    config_path: str = DEFAULT_CONFIG,
) -> None:
    import uvicorn

    app = create_app(config_path=config_path)
    uvicorn.run(app, host=host, port=port)
