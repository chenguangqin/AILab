# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""Cost accounting: the coding agent runs on a PERSISTENT ClaudeSDKClient, whose
`ResultMessage.total_cost_usd` is the session-CUMULATIVE spend (it grows every turn),
NOT the per-turn cost. The sandbox must report the per-turn DELTA so the loop's running
sum equals the true final spend — summing the raw cumulative snapshots over-reports a
multi-turn run several-fold (the bug behind "a simple run cost ~$68").
"""

from __future__ import annotations

from harness.loop import _usage_summary
from harness.sandbox import _cost_delta


def test_cost_delta_turns_cumulative_into_per_turn():
    # The real cumulative snapshots from a shipped 11-turn run (loop-docs/events.jsonl).
    cumulative = [1.1503, 1.5904, 2.4849, 3.2984, 3.935, 4.7236, 6.4461, 7.6401,
                  9.6909, 10.9801, 11.7645]
    prev = 0.0
    deltas = []
    for c in cumulative:
        d, prev = _cost_delta(c, prev)
        deltas.append(d)

    # Every per-turn delta is non-negative and the running sum of deltas equals the
    # final cumulative — NOT the (much larger) sum of the cumulative snapshots.
    assert all(d >= 0 for d in deltas)
    assert round(sum(deltas), 4) == cumulative[-1]              # true coder spend ≈ $11.76
    assert round(sum(cumulative), 2) == 63.70                   # the old bug summed to ~$63.70
    assert sum(deltas) < sum(cumulative) / 4                    # ~5x over-report avoided


def test_cost_delta_clamps_non_decreasing():
    # A cumulative total should never drop; if it appears to, report 0 (not negative).
    d, prev = _cost_delta(5.0, 7.0)
    assert d == 0.0 and prev == 5.0


def test_usage_summary_extracts_cache_tokens():
    # events.jsonl records where tokens went — cache_read climbing on later turns is the
    # signal that prompt caching is engaging (static prefix reused, not re-billed).
    u = _usage_summary({
        "input_tokens": 2, "output_tokens": 8,
        "cache_read_input_tokens": 22057, "cache_creation_input_tokens": 15,
    })
    assert u == {"input_tokens": 2, "output_tokens": 8,
                 "cache_read_input_tokens": 22057, "cache_creation_input_tokens": 15}
    # Missing keys default to 0 (some transports omit usage).
    assert _usage_summary({}) == {"input_tokens": 0, "output_tokens": 0,
                                  "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}
