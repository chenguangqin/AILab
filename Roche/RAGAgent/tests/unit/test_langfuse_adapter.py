from langfuse import Langfuse

from roche_agent.evals.runner import EvalCase
from roche_agent.observability import (
    LangfuseTracer,
    create_langfuse_callback,
    sync_dataset_to_langfuse,
)


class FakeLangfuseClient:
    def __init__(self):
        self.datasets = []
        self.items = []
        self.flushed = False

    def create_dataset(self, **kwargs):
        self.datasets.append(kwargs)

    def create_dataset_item(self, **kwargs):
        self.items.append(kwargs)

    def flush(self):
        self.flushed = True


def test_langfuse_adapter_matches_local_tracer_contract():
    client = Langfuse(
        public_key="pk-test",
        secret_key="sk-test",
        base_url="http://127.0.0.1:9",
        tracing_enabled=False,
    )
    tracer = LangfuseTracer(client)
    with tracer.span("root", input={"case": "test"}) as root:
        root["output"] = {"ok": True}
    tracer.score(root["trace_id"], "success", 1.0)
    callback = create_langfuse_callback(public_key="pk-test")
    assert callback is not None


def test_langfuse_dataset_sync_preserves_expected_evidence():
    client = FakeLangfuseClient()
    case = EvalCase(
        case_id="c1",
        question="q",
        expected_evidence_ids=["e1"],
        answerable=True,
    )
    count = sync_dataset_to_langfuse("training", [case], client=client)
    assert count == 1
    assert client.items[0]["expected_output"]["expected_evidence_ids"] == ["e1"]
    assert client.flushed is True
