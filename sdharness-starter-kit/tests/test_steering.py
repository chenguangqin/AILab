# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""The Pilot's typed verdict + the NO_GO → kill-switch escalation.

These exercise the two behaviors that make the Pilot's verdict *honest*:
1. the verdict coercion fails CLOSED (unreadable → NO_GO, never a silent GO);
2. a streak of NO_GO turns climbs the kill switch and stops the run, while a GO resets it.
Both are tested without a live model — the coercion and killswitch functions are pure.
"""

from __future__ import annotations

from harness.killswitch import update_and_check
from harness.models import Method, RunState
from harness.steering import _GATE_REVIEW_OUTPUT_FORMAT, _coerce


# ── typed verdict / fail-closed coercion ──


def test_output_format_is_json_schema():
    assert _GATE_REVIEW_OUTPUT_FORMAT["type"] == "json_schema"
    assert "schema" in _GATE_REVIEW_OUTPUT_FORMAT


def test_structured_go_and_nogo_are_honored():
    go = _coerce({"decision": "GO", "direction": "build M2"}, "")
    assert go.decision == "GO" and go.gate_held is False and go.direction == "build M2"

    nogo = _coerce({"decision": "NO_GO", "direction": "fix the failing test first"}, "")
    assert nogo.decision == "NO_GO" and nogo.gate_held is True


def test_structured_go_honored_through_sdk_wrapper():
    """Regression (live E2E): the SDK may wrap+stringify the output_format payload as
    `{"<key>": "{...}"}`. The Pilot must still read the real GO — otherwise it fails closed
    to NO_GO on EVERY turn and stalls the loop. _coerce normalizes via unwrap_structured_output."""
    wrapped = {"findings": '{"decision": "GO", "direction": "build M2"}'}
    r = _coerce(wrapped, "")
    assert r.decision == "GO" and r.gate_held is False and r.direction == "build M2"


def test_review_carries_cost_default_zero():
    # ReviewResult defaults to zero cost; steer() sets the real Pilot cost on it so
    # the loop can add it to the run total (the evaluator is a real, separate call).
    r = _coerce({"decision": "GO", "direction": "build M2"}, "")
    assert r.cost_usd == 0.0
    r.cost_usd = 0.0123
    assert r.cost_usd == 0.0123


def test_unreadable_reply_fails_closed_to_nogo():
    # No structured output and no DECISION: line → must NOT default to GO.
    r = _coerce(None, "looks good to me, keep going")
    assert r.decision == "NO_GO" and r.gate_held is True


def test_empty_reply_fails_closed():
    r = _coerce(None, "")
    assert r.decision == "NO_GO"


def test_text_fallback_go_still_works():
    r = _coerce(None, "DECISION: GO\nDIRECTION: implement M3 and run its test")
    assert r.decision == "GO" and "M3" in r.direction


def test_malformed_structured_falls_back_closed():
    # decision not in the allowed set → ignored → text fallback → fail closed
    r = _coerce({"decision": "maybe", "direction": "x"}, "no verdict line here")
    assert r.decision == "NO_GO"


# ── NO_GO escalation via the kill switch ──


def _loop_method() -> Method:
    from harness.config import load_method
    return load_method("loop")


def test_nogo_streak_trips_killswitch_and_go_resets():
    method = _loop_method()
    threshold = int(method.kill_switch.get("state_unchanged_threshold", 5))
    state = RunState(workspace=__import__("pathlib").Path("."), method_name="loop",
                     strategy_name="loop-autopilot", phase="BUILD")

    # A NO_GO turn = no progress even though files were written (mirrors loop.py).
    stop = None
    for _ in range(threshold):
        # made_progress is False on a NO_GO (the loop computes: wrote and decision=='GO')
        stop = update_and_check(method, state, wrote_files=True, made_progress=False, error="")
    assert stop is not None, "N consecutive NO_GO turns should trip the kill switch"
    assert "progress" in stop.lower()


def test_go_resets_the_no_progress_counter():
    method = _loop_method()
    threshold = int(method.kill_switch.get("state_unchanged_threshold", 5))
    state = RunState(workspace=__import__("pathlib").Path("."), method_name="loop",
                     strategy_name="loop-autopilot", phase="BUILD")

    # threshold-1 NO_GO turns, then a GO (made_progress=True) resets it.
    for _ in range(threshold - 1):
        assert update_and_check(method, state, wrote_files=True, made_progress=False, error="") is None
    assert update_and_check(method, state, wrote_files=True, made_progress=True, error="") is None
    assert state.consecutive_no_progress_turns == 0
