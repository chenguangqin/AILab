from __future__ import annotations

import json
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from roche_agent.contracts import TraceEvent


class JsonTracer:
    """Langfuse-shaped local tracer for deterministic tests and offline labs."""

    def __init__(self, output_path: str | Path | None = None):
        self.output_path = Path(output_path) if output_path else None
        self.events: list[TraceEvent] = []
        self.scores: list[dict[str, Any]] = []

    @contextmanager
    def span(
        self,
        name: str,
        *,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        input: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> Iterator[dict[str, Any]]:
        trace_id = trace_id or str(uuid.uuid4())
        span_id = str(uuid.uuid4())
        start = time.perf_counter()
        self.events.append(
            TraceEvent(
                trace_id=trace_id,
                span_id=span_id,
                parent_span_id=parent_span_id,
                name=name,
                event_type="span_start",
                input=input,
                metadata=metadata or {},
            )
        )
        context = {"trace_id": trace_id, "span_id": span_id, "output": None, "metadata": {}}
        try:
            yield context
        except Exception as exc:
            self.events.append(
                TraceEvent(
                    trace_id=trace_id,
                    span_id=span_id,
                    parent_span_id=parent_span_id,
                    name=name,
                    event_type="error",
                    output={"type": type(exc).__name__, "message": str(exc)},
                )
            )
            self._flush()
            raise
        else:
            elapsed_ms = (time.perf_counter() - start) * 1000
            self.events.append(
                TraceEvent(
                    trace_id=trace_id,
                    span_id=span_id,
                    parent_span_id=parent_span_id,
                    name=name,
                    event_type="span_end",
                    output=context["output"],
                    metadata={**context["metadata"], "latency_ms": elapsed_ms},
                )
            )
            self._flush()

    def score(self, trace_id: str, name: str, value: float, comment: str | None = None) -> None:
        self.scores.append(
            {"trace_id": trace_id, "name": name, "value": value, "comment": comment}
        )
        self._flush()

    def _flush(self) -> None:
        if not self.output_path:
            return
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "events": [event.model_dump(mode="json") for event in self.events],
            "scores": self.scores,
        }
        self.output_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def flush(self) -> None:
        self._flush()
