# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""Readiness gate — a small port of real sdharness's method-readiness audit.

Runs over EVERY built-in method + strategy so a new or edited config can't ship
broken. Fails on the bug classes that cause infinite loops or mis-steering:

  1. A structured method's terminal phase must declare a `complete_when`.
  2. Gates must use STRUCTURAL predicates — no *positive* prose-heading
     `file_contains` (a model rarely reproduces an exact heading → unsatisfiable
     gate → the loop spins). For "no unchecked items" use the `no_unchecked` leaf,
     not `not file_contains "- [ ]"` (a `file_contains` inside a `not` is still
     allowed for other needles).
  3. Every method declares a `default_strategy` that resolves to a real strategy.
  4. An autopilot-consensus strategy must have exactly ONE reviewer.
"""

from __future__ import annotations

from typing import Any

import pytest

from harness.config import _KIT_ROOT, load_method, load_strategy

METHODS = sorted(d.name for d in (_KIT_ROOT / "methods").glob("*/") if (d / "method.json").is_file())
STRATEGIES = sorted(d.name for d in (_KIT_ROOT / "strategies").glob("*/") if (d / "strategy.json").is_file())


def _positive_file_contains(pred: Any, negated: bool = False) -> bool:
    """True if a *positive* (non-negated) file_contains appears anywhere."""
    if not isinstance(pred, dict):
        return False
    found = False
    for key, val in pred.items():
        if key == "not":
            found = found or _positive_file_contains(val, negated=not negated)
        elif key in ("all", "any"):
            for sub in val:
                found = found or _positive_file_contains(sub, negated=negated)
        elif key == "file_contains":
            if not negated:
                found = True
    return found


@pytest.mark.parametrize("name", METHODS)
def test_method_terminal_has_complete_when(name: str):
    m = load_method(name)
    assert m.terminal_requires(), f"{name}: completion.terminal_requires is empty"
    terminal_phase = m.phases[-1].name
    assert m.complete_when(terminal_phase), f"{name}: terminal phase {terminal_phase} lacks complete_when"


@pytest.mark.parametrize("name", METHODS)
def test_method_gates_are_structural(name: str):
    m = load_method(name)
    for phase in m.phases:
        pred = m.complete_when(phase.name)
        assert not _positive_file_contains(pred), (
            f"{name}/{phase.name}: positive file_contains in a gate is the "
            "unsatisfiable-gate bug class — use a structural check, or wrap it in `not`."
        )
    assert not _positive_file_contains(m.terminal_requires()), (
        f"{name}: positive file_contains in terminal_requires"
    )


@pytest.mark.parametrize("name", METHODS)
def test_method_default_strategy_resolves(name: str):
    m = load_method(name)
    assert m.default_strategy, f"{name}: no default_strategy declared"
    load_strategy(m.default_strategy)  # raises if missing


@pytest.mark.parametrize("name", STRATEGIES)
def test_autopilot_strategy_has_single_reviewer(name: str):
    s = load_strategy(name)
    if s.consensus_rule == "autopilot":
        assert len(s.reviewers) == 1, (
            f"{name}: autopilot consensus must have exactly one steering reviewer, "
            f"got {len(s.reviewers)}"
        )
