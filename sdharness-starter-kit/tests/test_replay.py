# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""`sdharness replay` — re-render a finished run from its events.jsonl.

Replay is a thin reader: each recorded event is fed back through the same
CLIRenderer a live run uses, so the output is identical. These tests pin the
load-bearing behavior without a model: it finds events.jsonl under the run
workspace, renders every well-formed event, tolerates a malformed line, and
returns a clear error when there's nothing to replay.
"""

from __future__ import annotations

import json
from pathlib import Path

from harness.__main__ import cmd_replay


class _Args:
    def __init__(self, run_dir):
        self.run_dir = str(run_dir)


def _write_events(workspace: Path, events: list[dict]) -> None:
    docs = workspace / "loop-docs"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "events.jsonl").write_text(
        "\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")


def test_replay_renders_a_run_from_workspace(tmp_path: Path) -> None:
    _write_events(tmp_path, [
        {"event": "run_config", "method": "loop", "strategy": "loop-autopilot",
         "max_turns": 16, "intent": "x", "workspace": "w"},
        {"event": "turn_start", "turn": 1, "phase": "RESEARCH"},
        {"event": "tool_use", "detail": "Read(vision.md)"},
        {"event": "turn_end", "turn": 1, "phase": "RESEARCH", "decision": "GO",
         "max_turns": 16, "total_cost_usd": 1.0, "milestones_done": 0,
         "milestones_total": 7, "elapsed": 12.0},
        {"event": "result_recap", "complete": True, "reason": "done", "turns": 1,
         "max_turns": 16, "milestones_done": 7, "milestones_total": 7,
         "total_cost_usd": 1.0, "elapsed": 12.0, "workspace": "w"},
    ])
    assert cmd_replay(_Args(tmp_path)) == 0


def test_replay_accepts_events_file_directly(tmp_path: Path) -> None:
    _write_events(tmp_path, [{"event": "turn_start", "turn": 1, "phase": "BUILD"}])
    assert cmd_replay(_Args(tmp_path / "loop-docs" / "events.jsonl")) == 0


def test_replay_tolerates_a_malformed_line(tmp_path: Path) -> None:
    docs = tmp_path / "loop-docs"
    docs.mkdir()
    (docs / "events.jsonl").write_text(
        '{"event": "turn_start", "turn": 1, "phase": "BUILD"}\n'
        'not json\n'
        '{"no_event_key": true}\n'
        '{"event": "turn_end", "turn": 1, "phase": "BUILD", "decision": "GO"}\n',
        encoding="utf-8")
    # The two valid events still render; the bad lines are skipped, not fatal.
    assert cmd_replay(_Args(tmp_path)) == 0


def test_replay_missing_events_returns_error(tmp_path: Path) -> None:
    assert cmd_replay(_Args(tmp_path)) == 2  # no events.jsonl anywhere


def test_replay_empty_events_returns_one(tmp_path: Path) -> None:
    docs = tmp_path / "loop-docs"
    docs.mkdir()
    (docs / "events.jsonl").write_text("", encoding="utf-8")
    assert cmd_replay(_Args(tmp_path)) == 1


def test_append_event_creates_docs_dir(tmp_path: Path) -> None:
    """`_append_event` writes the run_config/result_recap events that make replay show
    the banner + result card. It runs for run_config BEFORE run()/stage_workspace has
    created <method>-docs/, so it must create the parent dir itself — otherwise the append
    silently fails (OSError swallowed) and replay loses the kickoff banner."""
    from harness.__main__ import _append_event

    ws = tmp_path / "run"  # loop-docs/ does NOT exist yet (as at run_config time)
    _append_event(ws, "loop", "run_config", {"method": "loop", "phases": []})
    events = ws / "loop-docs" / "events.jsonl"
    assert events.is_file(), "run_config append must create <method>-docs/ if absent"
    assert "run_config" in events.read_text()
