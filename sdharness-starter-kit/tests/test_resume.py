# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""`sdharness resume` — continue an interrupted run from its own event log.

The kit persists no separate resume state: every event is teed to
`<method>-docs/events.jsonl`, so resume reconstructs the turn counter + accumulated
cost by reading that log back, then re-enters `run()` with `resume_from` set. Three
behaviors are load-bearing and tested here:

1. `_resume_state_from_events` recovers method/strategy/max_turns + the furthest turn
   and latest cost — from `run_config` (human mode), falling back to `run_start` (both
   modes), and from the last `turn_end` when there's no `complete` (the interrupted case).
2. `stage_workspace(resume=True)` must NOT archive the prior run's `goal.md`/`loop-docs/`
   — that's the state we're continuing from, not stale seed to quarantine.
3. `run(resume_from=N)` seeds the turn counter + cost so the loop continues at N+1 and
   the final total includes what was already spent.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import harness.loop as loop
from harness.__main__ import _resume_state_from_events
from harness.config import load_method
from harness.models import Method, ReviewResult, Strategy, TurnResult  # noqa: F401 (shared stub types)


def _write_events(workspace: Path, events: list[dict], method: str = "loop") -> Path:
    docs = workspace / f"{method}-docs"
    docs.mkdir(parents=True, exist_ok=True)
    path = docs / "events.jsonl"
    path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
    return path


# ── _resume_state_from_events ────────────────────────────────────────────────


def test_resume_state_from_last_turn_end_when_no_complete(tmp_path: Path):
    """The interrupted case: no `complete` event, so the last `turn_end` is the state
    source — recover method/strategy/max_turns + the furthest turn and latest cost."""
    path = _write_events(tmp_path, [
        {"event": "run_config", "method": "loop", "strategy": "loop-autopilot", "max_turns": 40},
        {"event": "run_start", "method": "loop", "strategy": "loop-autopilot", "max_turns": 40},
        {"event": "turn_end", "turn": 4, "phase": "BUILD", "decision": "GO", "total_cost_usd": 3.5},
        {"event": "turn_end", "turn": 5, "phase": "BUILD", "decision": "GO", "total_cost_usd": 4.2},
    ])
    st = _resume_state_from_events(path)
    assert st["method"] == "loop"
    assert st["strategy"] == "loop-autopilot"
    assert st["max_turns"] == 40
    assert st["resume_from"] == 5          # furthest turn seen
    assert st["resume_cost"] == 4.2        # latest running total
    assert st["resume_phase"] == "BUILD"   # phase of the last turn — continue there, not RESEARCH


def test_resume_state_prefers_complete_turn_count(tmp_path: Path):
    """A `complete` event carries `turns`; it counts toward the furthest-turn max."""
    path = _write_events(tmp_path, [
        {"event": "run_config", "method": "loop", "strategy": "loop-autopilot", "max_turns": 16},
        {"event": "turn_end", "turn": 6, "phase": "VERIFY", "decision": "GO", "total_cost_usd": 9.0},
        {"event": "complete", "complete": True, "turns": 6, "phase": "VERIFY", "total_cost_usd": 9.1},
    ])
    st = _resume_state_from_events(path)
    assert st["resume_from"] == 6
    assert st["resume_cost"] == 9.1


def test_resume_state_falls_back_to_run_start_for_json_runs(tmp_path: Path):
    """`--json` runs emit NO `run_config`; method/strategy/max_turns must still be
    recoverable from the always-emitted `run_start`."""
    path = _write_events(tmp_path, [
        {"event": "run_start", "method": "loop", "strategy": "loop-autopilot", "max_turns": 25},
        {"event": "turn_end", "turn": 2, "phase": "PLAN", "decision": "GO", "total_cost_usd": 1.1},
    ])
    st = _resume_state_from_events(path)
    assert st["method"] == "loop" and st["strategy"] == "loop-autopilot"
    assert st["max_turns"] == 25 and st["resume_from"] == 2


def test_resume_state_scopes_turns_to_the_current_run_segment(tmp_path: Path):
    """Brownfield regression: a workspace seeded from a PRIOR completed run leaves that
    run's `turn_end`/`complete` events in the same append-only events.jsonl. The turn scan
    must count only the CURRENT run's segment (events at/after the LAST run_config/run_start),
    so `resume_from` reflects this run's progress — not the seed's finished turn count. (Left
    unscoped, resume would compute the seed's max turn and 'continue' the seed, building
    nothing new.)"""
    path = _write_events(tmp_path, [
        # ── Seed run: a full, completed prior run (turns up to 13) ──
        {"event": "run_config", "method": "loop", "strategy": "loop-autopilot", "max_turns": 100},
        {"event": "turn_end", "turn": 12, "phase": "VERIFY", "decision": "GO", "total_cost_usd": 11.0},
        {"event": "complete", "complete": True, "turns": 13, "phase": "VERIFY", "total_cost_usd": 11.4},
        # ── THIS run: the brownfield run, interrupted at turn 1 ──
        {"event": "run_config", "method": "loop", "strategy": "loop-autopilot", "max_turns": 100},
        {"event": "turn_end", "turn": 1, "phase": "BUILD", "decision": "GO", "total_cost_usd": 0.8},
    ])
    st = _resume_state_from_events(path)
    # Resume from THIS run's turn 1 — not the seed's 13.
    assert st["resume_from"] == 1, "turn scan must ignore the seed run's turns"
    assert st["resume_cost"] == 0.8, "cost must reflect this run's segment, not the seed's"
    assert st["resume_phase"] == "BUILD"


def test_resume_state_config_only_is_a_fresh_start(tmp_path: Path):
    """A log with only run_config/run_start (no turns) → resume_from 0 (i.e. a fresh run)."""
    path = _write_events(tmp_path, [
        {"event": "run_config", "method": "loop", "strategy": "loop-autopilot", "max_turns": 40},
    ])
    st = _resume_state_from_events(path)
    assert st["resume_from"] == 0 and st["resume_cost"] == 0.0


def test_resume_state_empty_without_run_config(tmp_path: Path):
    """No run_config/run_start at all → can't reconstruct → empty (caller errors out)."""
    path = _write_events(tmp_path, [
        {"event": "turn_end", "turn": 3, "phase": "BUILD", "decision": "GO", "total_cost_usd": 2.0},
    ])
    assert _resume_state_from_events(path) == {}


# ── stage_workspace(resume=True) must NOT archive the run-in-progress state ───


def test_stage_workspace_resume_does_not_archive_prior_state(monkeypatch, tmp_path: Path):
    """On resume, the prior run's `goal.md` + `loop-docs/` are the handoff, NOT stale
    seed — `stage_workspace(resume=True)` must leave them in place (no `.superseded-*`).
    Contrast: `test_loop.py` proves the non-resume path DOES archive them."""
    project = tmp_path / "project"
    project.mkdir()
    (project / "vision.md").write_text("# Vision\nbuild a thing")
    ctx = tmp_path / "agent-context"
    ctx.mkdir()
    for name in ("CLAUDE.md", "QUALITY.md", "LESSONS.md"):
        (ctx / name).write_text(f"# {name}")
    monkeypatch.setattr(loop, "agent_context_dir", lambda: ctx)

    # A workspace mid-run: a partially-checked goal.md + a populated loop-docs/.
    workspace = tmp_path / "run"
    workspace.mkdir()
    (workspace / "goal.md").write_text("# Goal\n- [x] M1\n- [ ] M2\n")
    (workspace / "loop-docs").mkdir()
    (workspace / "loop-docs" / "research.md").write_text("# Research\ndone")

    loop.stage_workspace(project, workspace, load_method("loop"), resume=True)

    # Nothing archived; the in-progress contract + artifacts survive in place.
    assert not list(workspace.glob(".superseded-*")), "resume must not archive prior state"
    assert (workspace / "goal.md").read_text().count("- [x]") == 1
    assert (workspace / "loop-docs" / "research.md").is_file()


# ── restore_to_turn: roll back a mid-write interrupt to the clean turn boundary ──


def _git(ws: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=ws, check=True, capture_output=True, text=True)


def test_restore_to_turn_rolls_back_partial_writes_but_keeps_event_log(tmp_path: Path):
    """A turn interrupted mid-write leaves a half-file in the tree. `restore_to_turn`
    hard-resets to the last checkpoint tag (dropping the partial file) but preserves the
    append-only events.jsonl (the resume state source)."""
    ws = tmp_path / "run"
    ws.mkdir()
    _git(ws, "init", "-q")
    _git(ws, "config", "user.email", "t@e.st")
    _git(ws, "config", "user.name", "t")
    (ws / "loop-docs").mkdir()

    # Turn 3: a clean milestone file + an events log, checkpointed + tagged turn/3.
    (ws / "site.tsx").write_text("// M3 complete\n")
    (ws / "loop-docs" / "events.jsonl").write_text('{"event":"turn_end","turn":3}\n')
    loop.checkpoint(ws, 3, "BUILD")

    # Turn 4 starts, writes a PARTIAL file, then the process dies mid-write. The event log
    # also grew (an interrupted-turn line + a resume banner appended by cmd_resume).
    (ws / "half_written.tsx").write_text("// corrupt, incomplete\n")
    (ws / "loop-docs" / "events.jsonl").write_text(
        '{"event":"turn_end","turn":3}\n{"event":"run_config","resumed_from_turn":3}\n')

    restored = loop.restore_to_turn(ws, 3, "loop")

    assert restored is True
    assert not (ws / "half_written.tsx").exists(), "partial mid-write file must be dropped"
    assert (ws / "site.tsx").read_text() == "// M3 complete\n", "clean turn-3 file survives"
    # The event log is preserved in full (not rewound to its turn-3 state).
    body = (ws / "loop-docs" / "events.jsonl").read_text()
    assert "resumed_from_turn" in body, "append-only event log must survive the reset"


def test_restore_to_turn_absent_tag_is_a_noop(tmp_path: Path):
    """No checkpoint tag (or no git) → resume proceeds against the working tree as-is."""
    ws = tmp_path / "run"
    ws.mkdir()
    _git(ws, "init", "-q")
    assert loop.restore_to_turn(ws, 99, "loop") is False


# ── run(resume_from=N) seeds the turn counter + cost ─────────────────────────


def _method():
    return Method(name="loop", phases=[{"name": "RESEARCH"}, {"name": "PLAN"}, {"name": "BUILD"}])


async def test_run_resume_from_seeds_turn_and_cost(monkeypatch, tmp_path: Path):
    """`run(resume_from=3, resume_cost=5.0)` continues at turn 4 and the final total
    includes the already-spent cost — not a restart from turn 1 / $0."""
    from tests.test_loop import _install_stubs  # reuse the model-free loop harness

    review = ReviewResult(decision="GO", direction="onward", gate_held=False, cost_usd=0.25)
    calls, emit = _install_stubs(
        monkeypatch, phases=["RESEARCH", "PLAN", "BUILD"], complete_after=1, review=review)

    state = await loop.run(project_dir=tmp_path, workspace=tmp_path, method=_method(),
                           strategy=Strategy(name="loop-autopilot"), max_turns=10, emit=emit,
                           resume_from=3, resume_cost=5.0)

    # First turn of the resumed run is turn 4 (resume_from + 1), not turn 1.
    turn_starts = [f["turn"] for e, f in calls["events"] if e == "turn_start"]
    assert turn_starts and turn_starts[0] == 4
    # The accumulated total includes the $5.00 already spent before the interrupt.
    assert state.total_cost_usd > 5.0


async def test_run_resume_seeds_the_phase_from_the_log(monkeypatch, tmp_path: Path):
    """Regression for the e2e finding: seeding `resume_phase` makes the FIRST resumed turn
    report its true phase (BUILD), not a misleading walk back through RESEARCH/PLAN as the
    gates re-advance from phases[0]."""
    from tests.test_loop import _install_stubs

    review = ReviewResult(decision="GO", direction="onward", cost_usd=0.25)
    calls, emit = _install_stubs(
        monkeypatch, phases=["RESEARCH", "PLAN", "BUILD"], complete_after=1, review=review)

    await loop.run(project_dir=tmp_path, workspace=tmp_path, method=_method(),
                   strategy=Strategy(name="loop-autopilot"), max_turns=10, emit=emit,
                   resume_from=4, resume_cost=6.0, resume_phase="BUILD")

    # The first resumed turn_start reports BUILD (the seeded phase), not RESEARCH (phases[0]).
    turn_starts = [(f["turn"], f["phase"]) for e, f in calls["events"] if e == "turn_start"]
    assert turn_starts and turn_starts[0] == (5, "BUILD")


async def test_run_resume_at_budget_stops_cleanly(monkeypatch, tmp_path: Path):
    """Resuming already at/over the turn budget stops with an actionable reason and
    never connects the sandbox (no Bedrock spend)."""
    from tests.test_loop import _install_stubs

    review = ReviewResult(decision="GO", direction="onward", cost_usd=0.25)
    calls, emit = _install_stubs(
        monkeypatch, phases=["RESEARCH", "PLAN", "BUILD"], complete_after=1, review=review)

    state = await loop.run(project_dir=tmp_path, workspace=tmp_path, method=_method(),
                           strategy=Strategy(name="loop-autopilot"), max_turns=5, emit=emit,
                           resume_from=5, resume_cost=8.0)

    assert not state.complete
    assert "turn budget" in state.complete_reason
    # No turn ran — the loop never entered.
    assert not [e for e, _ in calls["events"] if e == "turn_start"]
