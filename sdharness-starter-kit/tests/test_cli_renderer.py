# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""The CLIRenderer's two load-bearing invariants (tested without a live model):

1. Human rendering goes to **stderr only** — stdout stays empty, so
   `sdharness run … --json` (which streams NDJSON on stdout) is provably clean.
2. Coding-agent and Pilot output are **visually distinct** (◆ vs ◇, and the Pilot
   panel is decision-labeled), and the spinner start/stop lifecycle never crashes.
"""

from __future__ import annotations

import io
from contextlib import redirect_stdout

from rich.console import Console

import harness.cli_renderer as cli_renderer


def _render(events, width=100):
    """Drive events through a CLIRenderer whose console writes to a buffer; return
    (stdout_text, stderr_text)."""
    buf = io.StringIO()
    # no_color=True so assertions match plain substrings regardless of the shell's
    # color forcing (FORCE_COLOR/CLICOLOR_FORCE would otherwise splice ANSI codes
    # inside words like "SD Loop", breaking the `in` checks).
    rec = Console(file=buf, highlight=False, width=width, no_color=True)
    orig = cli_renderer.console
    cli_renderer.console = rec  # renderer reads module-level `console`
    try:
        r = cli_renderer.CLIRenderer()
        out = io.StringIO()
        with redirect_stdout(out):
            for event, fields in events:
                r.emit(event, **fields)
        return out.getvalue(), buf.getvalue()
    finally:
        cli_renderer.console = orig


def test_renderer_never_writes_to_stdout():
    stdout, stderr = _render([
        ("run_config", dict(method="loop", strategy="loop-autopilot", yolo=True,
                            max_turns=3, intent="./ex", workspace="./runs/ex")),
        ("turn_start", dict(turn=1, phase="RESEARCH")),
        ("agent_text", dict(text="Reading the intake.")),
        ("tool_use", dict(detail="Read(vision.md)")),
        ("agent_turn_end", dict(writes=0, tool_count=1)),
        ("result_recap", dict(complete=True, reason="done", turns=1, max_turns=3,
                             milestones_done=0, milestones_total=0,
                             total_cost_usd=0.4, elapsed=42.0, workspace="/x")),
    ])
    assert stdout == "", "renderer must not write to stdout (keeps --json clean)"
    assert stderr, "renderer should have produced human output on its console"


def test_run_config_phase_rail_is_method_agnostic():
    # The banner's phase rail must reflect the METHOD's own phases, not a hardcoded
    # RESEARCH→PLAN→BUILD→VERIFY — the kit is method-agnostic (custom methods define
    # their own phases). A custom method's phases appear; the SD-Loop ones don't leak in.
    _, custom = _render([
        ("run_config", dict(method="mymethod", strategy="mystrategy", max_turns=10,
                            phases=[{"name": "EXPLORE", "color": ""},
                                    {"name": "DRAFT", "color": ""},
                                    {"name": "SHIP", "color": ""}],
                            intent="./x", workspace="./y")),
    ])
    assert "EXPLORE" in custom and "DRAFT" in custom and "SHIP" in custom
    assert "RESEARCH" not in custom and "VERIFY" not in custom  # no hardcoded SD-Loop leak

    # Fallback: an older event without `phases` still shows the SD-Loop rail (no crash).
    _, legacy = _render([
        ("run_config", dict(method="loop", strategy="loop-autopilot", max_turns=16,
                            intent="./x", workspace="./y")),
    ])
    assert "RESEARCH" in legacy and "VERIFY" in legacy


def test_run_config_shows_method_display_name():
    # The banner shows the method's friendly name (SD Loop) + its slug (loop);
    # older events without method_display fall back to the slug alone.
    _, with_disp = _render([
        ("run_config", dict(method="loop", method_display="SD Loop",
                            strategy="loop-autopilot", max_turns=3,
                            intent="./ex", workspace="./runs/ex")),
    ])
    assert "SD Loop" in with_disp and "(loop)" in with_disp

    _, no_disp = _render([
        ("run_config", dict(method="loop", strategy="loop-autopilot", max_turns=3,
                            intent="./ex", workspace="./runs/ex")),
    ])
    assert "loop" in no_disp and "SD Loop" not in no_disp  # graceful fallback


def test_turns_render_as_open_ordinal_not_a_fraction():
    """Turns are an OPEN ordinal count, never a `Turn N/max` fraction — the loop finishes
    on its terminal gate, not by "reaching" max_turns (a runaway ceiling shown once in the
    banner). Milestones are the progress bar. Locks the reframe so the /max denominator
    can't creep back into the status line or the result card. (Matches upstream sdharness.)"""
    _, stderr = _render([
        ("run_config", dict(method="loop", strategy="loop-autopilot", max_turns=100,
                            intent="./ex", workspace="./runs/ex")),
        ("turn_end", dict(turn=3, phase="BUILD", decision="GO", max_turns=100,
                          total_cost_usd=2.28, milestones_done=1, milestones_total=13,
                          elapsed=135.0)),
        ("result_recap", dict(complete=True, reason="done", turns=18, max_turns=100,
                             milestones_done=13, milestones_total=13,
                             total_cost_usd=12.3, elapsed=2400.0, workspace="/x")),
    ])
    # The per-turn line shows the ordinal, not a fraction.
    assert "Turn 3 " in stderr and "3/100" not in stderr
    # The result card shows the turn count, not a ratio.
    assert "18/100" not in stderr
    # The banner frames the cap as a budget, not a target.
    assert "turn budget" in stderr and "max-turns" not in stderr


def test_speaker_distinction_agent_vs_pilot():
    _, stderr = _render([
        ("agent_text", dict(text="Writing the landing page.")),
        ("pilot_review", dict(turn=1, decision="GO", direction="Sound; advance.", gate_held=False)),
        ("pilot_review", dict(turn=2, decision="NO_GO", direction="Missing milestones.", gate_held=True)),
    ])
    assert "◆ Coding Agent" in stderr          # inner harness
    assert "◇ Pilot · GO" in stderr            # outer harness, GO
    assert "◇ Pilot · NO_GO" in stderr         # outer harness, NO_GO — distinct


def test_spinner_lifecycle_does_not_crash():
    # turn_start starts a spinner; agent_text/pilot_review stop it; back-to-back
    # turn_starts must not leave two Live regions active.
    stdout, _ = _render([
        ("turn_start", dict(turn=1, phase="PLAN")),
        ("pilot_start", dict(turn=1, phase="PLAN")),      # spinner swap, no output yet
        ("pilot_review", dict(turn=1, decision="GO", direction="ok", gate_held=False)),
        ("turn_start", dict(turn=2, phase="BUILD")),
        ("agent_text", dict(text="done")),
        ("complete", dict(complete=True, reason="done")),
    ])
    assert stdout == ""


def test_unknown_event_is_ignored():
    stdout, _ = _render([("some_future_event", dict(x=1))])
    assert stdout == ""


# ── events.jsonl tee (loop._tee_events) ──


def test_tee_events_writes_one_json_line_per_event(tmp_path):
    """The emit tee mirrors every event to <method>-docs/events.jsonl as one
    parseable JSON line each, while still calling the inner emitter."""
    import json

    from harness.loop import _tee_events

    seen = []
    path = tmp_path / "loop-docs" / "events.jsonl"
    path.parent.mkdir(parents=True)
    emit = _tee_events(lambda event, **f: seen.append((event, f)), path)

    emit("run_start", turn=0, workspace=str(tmp_path))
    emit("turn_start", turn=1, phase="RESEARCH")
    emit("pilot_review", turn=1, decision="GO", direction="ok")

    # inner emitter still fired
    assert [e for e, _ in seen] == ["run_start", "turn_start", "pilot_review"]
    # file has one parseable JSON object per event, in order
    lines = path.read_text().strip().splitlines()
    assert len(lines) == 3
    objs = [json.loads(line) for line in lines]
    assert [o["event"] for o in objs] == ["run_start", "turn_start", "pilot_review"]
    assert objs[2]["decision"] == "GO"


def test_tee_events_survives_unwritable_path(tmp_path):
    """A bad events path must never crash a run — the inner emitter still fires."""
    from harness.loop import _tee_events

    seen = []
    # parent dir does not exist and we don't create it → open() raises, tee swallows it
    bad = tmp_path / "nope" / "events.jsonl"
    emit = _tee_events(lambda event, **f: seen.append(event), bad)
    emit("run_start", turn=0)
    assert seen == ["run_start"]  # inner still ran despite the write failure
