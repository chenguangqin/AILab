# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""`unwrap_structured_output` — normalize the SDK's `output_format` payload.

Found via a live workshop E2E: the Claude Agent SDK's `query()` + `output_format` path
(the kit uses it for BOTH the Pilot and the compound curator) does not always hand back the
bare schema object on Bedrock. SDK 0.2.118 was observed to wrap it under a single synthetic
key AND JSON-encode it as a string — `{"findings": "{\\"items\\": [...]}"}`. A naive
`structured.get("items")` / `.get("decision")` then misses it, so the curator silently
returned an empty proposal and the Pilot would fail closed to NO_GO on every turn. The
shared helper peels those layers so every structured-output consumer reads the real object.

(Upstream sdharness uses Strands `structured_output=Model`, which returns a validated Pydantic
object — so it never sees this raw-dict wrapping. This fragility is specific to the kit's
single-SDK `query()`+`output_format` design; the helper absorbs it at the SDK boundary.)
"""

from __future__ import annotations

import json

from harness.sandbox import inline_schema_refs, unwrap_structured_output as u


def test_live_findings_wrapper_is_unwrapped():
    """The exact shape observed live: one synthetic key, value is a JSON string."""
    live = {"findings": '{"items": [{"title": "X", "verdict": "drop"}]}'}
    assert u(live) == {"items": [{"title": "X", "verdict": "drop"}]}


def test_bare_proposal_dict_passthrough():
    d = {"items": [{"title": "Y", "verdict": "promote"}]}
    assert u(d) == d


def test_bare_gatereview_dict_passthrough():
    d = {"decision": "GO", "direction": "build M2"}
    assert u(d) == d


def test_top_level_json_string_is_parsed():
    assert u('{"decision": "NO_GO", "direction": "hold"}') == {"decision": "NO_GO", "direction": "hold"}


def test_single_key_wrapper_around_a_dict():
    """A wrapper whose value is already a dict (not stringified) also unwraps."""
    assert u({"result": {"decision": "GO", "direction": "go"}}) == {"decision": "GO", "direction": "go"}


def test_nested_wrap_is_peeled_within_bounds():
    assert u({"a": '{"b": "{\\"items\\": []}"}'}) == {"items": []}


def test_junk_and_none_return_none():
    assert u(None) is None
    assert u("not json at all") is None
    assert u(123) is None


def test_known_keys_are_never_treated_as_a_wrapper():
    """A real single-field payload that happens to have one known key is NOT unwrapped."""
    # `items` is a known top-level key → returned as-is even though it's the only key.
    assert u({"items": []}) == {"items": []}
    assert u({"decision": "GO"}) == {"decision": "GO"}


# ── inline_schema_refs: the SOURCE-side fix (flatten $ref so the CLI returns bare) ──
#
# Isolated live: the CLI's --json-schema path wraps+stringifies structured_output when the
# schema has $ref/$defs (Pydantic emits them for nested models), and returns the bare object
# for a flat schema. Inlining the refs removes the trigger at the source.


def test_inline_removes_defs_and_refs_from_a_nested_pydantic_schema():
    from harness.compound_agentic import Proposal
    raw = Proposal.model_json_schema()
    assert "$defs" in raw and "$ref" in json.dumps(raw)  # precondition: Pydantic emits refs
    flat = inline_schema_refs(raw)
    assert "$defs" not in flat
    assert "$ref" not in json.dumps(flat)


def test_inline_preserves_the_nested_object_properties():
    """The resolved schema must still describe the full nested shape — inlining is
    non-destructive, it only removes the indirection."""
    from harness.compound_agentic import Proposal
    flat = inline_schema_refs(Proposal.model_json_schema())
    inner = flat["properties"]["items"]["items"]
    assert inner["type"] == "object"
    assert {"title", "verdict", "target_file", "rationale", "proposed_text"} <= set(inner["properties"])


def test_inline_is_a_noop_on_a_flat_schema():
    flat = {"type": "object", "properties": {"decision": {"type": "string"}}, "required": ["decision"]}
    assert inline_schema_refs(flat) == flat


def test_inline_survives_a_self_referential_schema():
    """A recursive $ref must not infinite-loop — bounded recursion returns *something*
    (the sink-side unwrap still covers any residual ref)."""
    recursive = {
        "type": "object",
        "$defs": {"Node": {"type": "object", "properties": {"child": {"$ref": "#/$defs/Node"}}}},
        "properties": {"root": {"$ref": "#/$defs/Node"}},
    }
    out = inline_schema_refs(recursive)  # must return, not hang
    assert isinstance(out, dict)
    assert "$defs" not in out
