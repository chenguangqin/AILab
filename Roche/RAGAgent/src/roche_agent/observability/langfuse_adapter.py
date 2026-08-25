from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

from .json_tracer import JsonTracer


def langfuse_base_url() -> str | None:
    return os.getenv("LANGFUSE_BASE_URL") or os.getenv("LANGFUSE_HOST")


def langfuse_is_configured() -> bool:
    return bool(
        os.getenv("LANGFUSE_PUBLIC_KEY")
        and os.getenv("LANGFUSE_SECRET_KEY")
        and langfuse_base_url()
    )


def create_langfuse_callback(**kwargs: Any) -> Any:
    """Create the LangChain callback used by LangGraph invoke/stream config."""
    try:
        from langfuse.langchain import CallbackHandler
    except ImportError as exc:
        raise RuntimeError("install the langfuse extra: pip install -e '.[langfuse]'") from exc
    return CallbackHandler(**kwargs)


def langfuse_callbacks_from_env() -> list[Any]:
    if langfuse_is_configured():
        return [create_langfuse_callback()]
    return []


class LangfuseTracer:
    """Adapter exposing the same small tracing interface as JsonTracer."""

    def __init__(self, client: Any | None = None):
        try:
            from langfuse import Langfuse
        except ImportError as exc:
            raise RuntimeError("install the langfuse extra: pip install -e '.[langfuse]'") from exc
        self.client = client or Langfuse(
            public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
            secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
            base_url=langfuse_base_url(),
            environment=os.getenv("ROCHE_TEAM", "local"),
        )
        self.observations: dict[str, Any] = {}

    @contextmanager
    def span(
        self,
        name: str,
        *,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        input: Any = None,
        metadata: dict[str, Any] | None = None,
    ):
        parent = self.observations.get(parent_span_id or "")
        observation = (
            parent.start_observation(
                name=name,
                as_type="span",
                input=input,
                metadata=metadata,
            )
            if parent
            else self.client.start_observation(name=name, input=input, metadata=metadata)
        )
        span_id = observation.id or str(uuid4())
        actual_trace_id = observation.trace_id or trace_id or str(uuid4())
        self.observations[span_id] = observation
        context = {
            "trace_id": actual_trace_id,
            "span_id": span_id,
            "output": None,
            "metadata": {},
        }
        try:
            yield context
        except Exception as exc:
            observation.update(
                level="ERROR",
                status_message=str(exc),
                output={"type": type(exc).__name__, "message": str(exc)},
            )
            raise
        else:
            observation.update(output=context["output"], metadata=context["metadata"])
        finally:
            observation.end()
            self.observations.pop(span_id, None)

    def score(self, trace_id: str, name: str, value: float, comment: str | None = None) -> None:
        self.client.create_score(
            trace_id=trace_id,
            name=name,
            value=value,
            data_type="NUMERIC",
            comment=comment,
        )

    def flush(self) -> None:
        self.client.flush()


def tracer_from_env(json_path: str | Path | None = None) -> JsonTracer | LangfuseTracer:
    if langfuse_is_configured():
        return LangfuseTracer()
    return JsonTracer(json_path)


def sync_dataset_to_langfuse(
    dataset_name: str,
    cases: list[Any],
    *,
    client: Any | None = None,
) -> int:
    try:
        from langfuse import get_client
    except ImportError as exc:
        raise RuntimeError("install the langfuse extra: pip install -e '.[langfuse]'") from exc
    langfuse = client or get_client()
    langfuse.create_dataset(
        name=dataset_name,
        description="Roche RAG training evaluation cases",
        metadata={"data_classification": "synthetic_training"},
    )
    for case in cases:
        payload = case.model_dump() if hasattr(case, "model_dump") else dict(case)
        langfuse.create_dataset_item(
            dataset_name=dataset_name,
            id=payload["case_id"],
            input={"question": payload["question"]},
            expected_output={
                "answerable": payload["answerable"],
                "expected_evidence_ids": payload["expected_evidence_ids"],
                "reference_answer": payload.get("reference_answer"),
            },
            metadata={"split": payload.get("split"), "tags": payload.get("tags", [])},
        )
    langfuse.flush()
    return len(cases)
