from __future__ import annotations

import hashlib
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from roche_agent.contracts import IndexConfig, PipelineConfig, QueryConfig, QueryResult
from roche_agent.evals import EvaluationRunner, load_eval_cases
from roche_agent.observability import tracer_from_env
from roche_agent.providers import create_chat_provider, create_embedding_provider
from roche_agent.retrieval import RAGPipeline, load_pipeline_config


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)


class QueryConfigRequest(BaseModel):
    query: QueryConfig


class IndexRebuildRequest(BaseModel):
    index: IndexConfig


class EvaluationRequest(BaseModel):
    split: Literal["dev", "test"] = "dev"


class LabRuntime:
    def __init__(
        self,
        project_root: str | Path,
        config_path: str | Path,
    ):
        self.project_root = Path(project_root)
        self.config_path = Path(config_path)
        if not self.config_path.is_absolute():
            self.config_path = self.project_root / self.config_path
        self.document_dir = self.project_root / "data" / "iso" / "documents"
        self.eval_path = self.project_root / "evals" / "datasets" / "iso_rag_cases.jsonl"
        self.artifact_root = self.project_root / "artifacts" / "lab0-web"
        self._lock = threading.RLock()
        self.pipeline: RAGPipeline
        self.manifest: dict[str, Any]
        self.pipeline, self.manifest = self._build_pipeline(
            load_pipeline_config(self.config_path)
        )

    def _document_digest(self) -> str:
        digest = hashlib.sha256()
        for path in sorted(self.document_dir.glob("*.md")):
            digest.update(path.name.encode("utf-8"))
            digest.update(path.read_bytes())
        return digest.hexdigest()[:12]

    def _versioned_config(self, config: PipelineConfig) -> PipelineConfig:
        index_payload = {
            "data_version": config.data_version,
            "documents": self._document_digest(),
            "index": config.index.model_dump(exclude={"index_version"}),
        }
        fingerprint = hashlib.sha256(
            json.dumps(index_payload, sort_keys=True).encode("utf-8")
        ).hexdigest()[:10]
        versioned = config.model_copy(deep=True)
        versioned.index.index_version = f"lab0-{fingerprint}"
        return versioned

    def _build_pipeline(
        self,
        config: PipelineConfig,
    ) -> tuple[RAGPipeline, dict[str, Any]]:
        config = self._versioned_config(config)
        tracer = tracer_from_env(self.artifact_root / "trace.json")
        pipeline = RAGPipeline(
            config,
            embedder=create_embedding_provider(config),
            chat=create_chat_provider(),
            tracer=tracer,
        )
        manifest = pipeline.build(self.document_dir)
        pipeline.tracer.flush()
        manifest["index_config"] = config.index.model_dump()
        manifest["built_at"] = datetime.now(timezone.utc).isoformat()
        return pipeline, manifest

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "ready": True,
                "config": self.pipeline.config.model_dump(),
                "manifest": self.manifest,
                "langfuse_enabled": self.pipeline.tracer.__class__.__name__
                == "LangfuseTracer",
                "graph": {
                    "workflow_version": self.pipeline.workflow_version,
                    "nodes": [
                        "intent",
                        "rewrite",
                        "retrieve",
                        "rerank",
                        "generate",
                    ],
                },
            }

    def query(self, request: QueryRequest) -> QueryResult:
        with self._lock:
            pipeline = self.pipeline
        result = pipeline.query(request.question)
        if hasattr(pipeline.tracer, "flush"):
            pipeline.tracer.flush()
        return result

    def update_query_config(self, request: QueryConfigRequest) -> dict[str, Any]:
        with self._lock:
            previous = self.pipeline
            config = previous.config.model_copy(deep=True)
            config.query = request.query
            pipeline = RAGPipeline(
                config,
                embedder=previous.embedder,
                chat=previous.chat,
                tracer=previous.tracer,
                callbacks=previous.callbacks,
            )
            pipeline.index = previous.index
            pipeline.chunks = previous.chunks
            self.pipeline = pipeline
            return {
                "config": config.model_dump(),
                "index_rebuilt": False,
            }

    def rebuild_index(self, request: IndexRebuildRequest) -> dict[str, Any]:
        with self._lock:
            config = self.pipeline.config.model_copy(deep=True)
        config.index = request.index
        pipeline, manifest = self._build_pipeline(config)
        with self._lock:
            self.pipeline = pipeline
            self.manifest = manifest
        if hasattr(pipeline.tracer, "flush"):
            pipeline.tracer.flush()
        return {
            "config": pipeline.config.model_dump(),
            "manifest": manifest,
            "index_rebuilt": True,
        }

    def evaluation_snapshot(self) -> RAGPipeline:
        with self._lock:
            return self.pipeline


class EvaluationJobManager:
    def __init__(self, runtime: LabRuntime):
        self.runtime = runtime
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="lab0-eval")
        self.jobs: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def submit(self, request: EvaluationRequest) -> dict[str, Any]:
        job_id = str(uuid4())
        job = {
            "job_id": job_id,
            "split": request.split,
            "status": "queued",
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            self.jobs[job_id] = job
        pipeline = self.runtime.evaluation_snapshot()
        job["pipeline"] = pipeline.config.name
        job["index_version"] = pipeline.config.index.index_version
        self.executor.submit(self._run, job_id, request.split, pipeline)
        return dict(job)

    def _run(self, job_id: str, split: str, pipeline: RAGPipeline) -> None:
        with self._lock:
            self.jobs[job_id]["status"] = "running"
            self.jobs[job_id]["started_at"] = datetime.now(timezone.utc).isoformat()
        try:
            cases = load_eval_cases(self.runtime.eval_path, split=split)
            report = EvaluationRunner(pipeline).run(cases)
            output = self.runtime.artifact_root / "evaluations" / f"{job_id}.json"
            EvaluationRunner.save(report, output)
            if hasattr(pipeline.tracer, "flush"):
                pipeline.tracer.flush()
            with self._lock:
                self.jobs[job_id].update(
                    {
                        "status": "completed",
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                        "case_count": len(cases),
                        "summary": report["summary"],
                        "artifact": str(output),
                        "pipeline": pipeline.config.name,
                        "index_version": pipeline.config.index.index_version,
                    }
                )
        except Exception as exc:
            with self._lock:
                self.jobs[job_id].update(
                    {
                        "status": "failed",
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self.jobs.get(job_id)
            return dict(job) if job else None

    def shutdown(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=True)
