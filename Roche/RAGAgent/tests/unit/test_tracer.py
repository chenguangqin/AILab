import json

from roche_agent.observability import JsonTracer


def test_json_tracer_records_nested_fields(tmp_path):
    path = tmp_path / "trace.json"
    tracer = JsonTracer(path)
    with tracer.span("root", input={"query": "x"}) as root:
        with tracer.span(
            "child",
            trace_id=root["trace_id"],
            parent_span_id=root["span_id"],
        ) as child:
            child["output"] = {"ok": True}
        root["output"] = {"done": True}
    tracer.score(root["trace_id"], "success", 1.0)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert len(payload["events"]) == 4
    assert payload["scores"][0]["name"] == "success"

