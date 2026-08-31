# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""`sdharness compound` default-flip (Part B5).

Agentic curation is now the DEFAULT: `sdharness compound <run>` attempts the curator
agent and auto-falls back to the deterministic title-dedup path offline (no SDK/creds).
`--deterministic` forces the offline path. `--agentic` is a deprecated no-op alias.

These tests pin the dispatch in `cmd_compound` without a live model: we stub
`_cmd_compound_agentic` (the agentic entry) and `compound.compound_run` (the offline
entry) and assert which one runs for each flag combination.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import harness.__main__ as m


def _args(run_dir: Path, **over) -> argparse.Namespace:
    base = {"run_dir": str(run_dir), "dry_run": True,
            "deterministic": False, "agentic": False}
    base.update(over)
    return argparse.Namespace(**base)


def _stub_paths(monkeypatch):
    """Record which path ran. Agentic returns 0 (succeeded); offline returns ([],[],[])."""
    calls: list[str] = []
    monkeypatch.setattr(m, "_cmd_compound_agentic",
                        lambda run_dir, dry_run: (calls.append("agentic"), 0)[1])
    import harness.compound as compound
    monkeypatch.setattr(compound, "compound_run",
                        lambda run_dir, dry_run: (calls.append("offline"), ([], [], []))[1])
    return calls


def test_default_runs_agentic(tmp_path, monkeypatch):
    """No flags → agentic is attempted first (the new default)."""
    calls = _stub_paths(monkeypatch)
    assert m.cmd_compound(_args(tmp_path)) == 0
    assert calls == ["agentic"]


def test_deterministic_flag_forces_offline(tmp_path, monkeypatch):
    """`--deterministic` skips the curator agent entirely."""
    calls = _stub_paths(monkeypatch)
    m.cmd_compound(_args(tmp_path, deterministic=True))
    assert calls == ["offline"]
    assert "agentic" not in calls


def test_agentic_unavailable_falls_back_to_offline(tmp_path, monkeypatch):
    """When the curator agent is unavailable (no SDK/creds → returns None), the run
    lands on the deterministic path exactly as before — the regression guard."""
    calls: list[str] = []
    monkeypatch.setattr(m, "_cmd_compound_agentic",
                        lambda run_dir, dry_run: (calls.append("agentic"), None)[1])
    import harness.compound as compound
    monkeypatch.setattr(compound, "compound_run",
                        lambda run_dir, dry_run: (calls.append("offline"), ([], [], []))[1])
    m.cmd_compound(_args(tmp_path))
    assert calls == ["agentic", "offline"]


def test_agentic_alias_is_still_accepted(tmp_path, monkeypatch):
    """The deprecated `--agentic` alias is a no-op relative to the new default: it still
    routes to the curator agent (default behavior), never crashes an existing script."""
    calls = _stub_paths(monkeypatch)
    m.cmd_compound(_args(tmp_path, agentic=True))
    assert calls == ["agentic"]
