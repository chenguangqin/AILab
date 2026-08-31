# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""The loop's per-turn sequencing — the two behaviors a real run got wrong:

1. The Pilot reviews the phase the work **executed in** (`prev_phase`), and the
   `phase_advance` is surfaced AFTER the verdict — so a successful RESEARCH turn
   reads `Turn 1 · RESEARCH · GO`, not `PLAN · NO_GO`. (This also fixes a kill-switch
   miscount: a phase-completing turn now gets a GO and counts as progress.)
2. The Pilot's cost is added to the run total (it's a separate model call).

Driven model-free: the sandbox, the Pilot (`steer`), and `phase_authority` are stubbed
on the `harness.loop` module, so the real loop control flow runs without Bedrock.
"""

from __future__ import annotations

from pathlib import Path

import harness.loop as loop
from harness.config import load_method
from harness.models import Method, ReviewResult, Strategy, TurnResult


def test_stage_workspace_puts_inputs_at_root_generated_in_loop_docs(monkeypatch, tmp_path: Path):
    """Inputs-at-root layout (upstream #45): the authored intake + agent-context seed
    land at the workspace ROOT; only the generated-state dir (loop-docs/) is created
    for artifacts the run produces."""
    # A project dir with the intake the user authored.
    project = tmp_path / "project"
    project.mkdir()
    (project / "vision.md").write_text("# Vision\nbuild a thing")
    (project / "tech-env.md").write_text("# Tech\nreact")
    (project / "images.md").write_text("# Images\nsome urls")  # extra *.md input

    # A fake agent-context seed so we don't depend on the kit's real files.
    ctx = tmp_path / "agent-context"
    ctx.mkdir()
    for name in ("CLAUDE.md", "QUALITY.md", "LESSONS.md"):
        (ctx / name).write_text(f"# {name}")
    monkeypatch.setattr(loop, "agent_context_dir", lambda: ctx)

    workspace = tmp_path / "run"
    loop.stage_workspace(project, workspace, load_method("loop"))

    # Authored inputs + agent-context seed at the ROOT (not nested in loop-docs/).
    for name in ("vision.md", "tech-env.md", "images.md", "CLAUDE.md", "QUALITY.md", "LESSONS.md"):
        assert (workspace / name).is_file(), f"{name} should be staged at the workspace root"
        assert not (workspace / "loop-docs" / name).exists(), f"{name} must NOT be in loop-docs/"


def test_stage_workspace_in_place_does_not_self_copy(monkeypatch, tmp_path: Path):
    """`--in-place`: workspace IS the project dir, so the intake already lives at the
    destination. stage_workspace must NOT raise shutil.SameFileError copying a file
    onto itself — it skips same-path copies and leaves the brownfield content intact.
    (Regression: the kit dropped the src!=dst guard upstream keeps in create_workspace.)"""
    project = tmp_path / "brownfield"
    project.mkdir()
    (project / "vision.md").write_text("# Vision\nadd a feature to this existing app")
    (project / "tech-env.md").write_text("# Tech\nexisting stack")
    (project / "app.py").write_text("print('existing code')")  # pre-existing brownfield code
    (project / "CLAUDE.md").write_text("# project's own CLAUDE.md")  # must not be clobbered

    ctx = tmp_path / "agent-context"
    ctx.mkdir()
    for name in ("CLAUDE.md", "QUALITY.md", "LESSONS.md"):
        (ctx / name).write_text(f"# seed {name}")
    monkeypatch.setattr(loop, "agent_context_dir", lambda: ctx)

    # workspace == project dir (the --in-place case). Must not raise.
    loop.stage_workspace(project, project, load_method("loop"))

    # Brownfield content + intake survive; the project's own CLAUDE.md is NOT overwritten.
    assert (project / "app.py").read_text() == "print('existing code')"
    assert (project / "vision.md").is_file()
    assert (project / "CLAUDE.md").read_text() == "# project's own CLAUDE.md"
    # Seed files that DON'T already exist are still staged.
    assert (project / "QUALITY.md").read_text() == "# seed QUALITY.md"
    assert (project / "loop-docs").is_dir()


def test_stage_workspace_archives_stale_generated_state_from_a_seeded_run(monkeypatch, tmp_path: Path):
    """Brownfield-on-a-prior-run (the 'add a chat agent on my site' flow): the workspace is
    SEEDED by copying a finished run dir in, so it arrives with the PRIOR run's generated
    state — a completed `goal.md` + a `loop-docs/` holding a green integration-report.json.
    stage_workspace must archive that stale state aside so THIS run's phase gates + terminal
    predicate aren't satisfied by the previous run's artifacts (which made the loop 'complete'
    on turn 1 having built nothing new). The new intake re-plans from scratch."""
    project = tmp_path / "project"
    project.mkdir()
    (project / "vision.md").write_text("# Vision\nadd a chat agent to the existing site")
    (project / "tech-env.md").write_text("# Tech\nStrands + React")

    ctx = tmp_path / "agent-context"
    ctx.mkdir()
    for name in ("CLAUDE.md", "QUALITY.md", "LESSONS.md"):
        (ctx / name).write_text(f"# {name}")
    monkeypatch.setattr(loop, "agent_context_dir", lambda: ctx)

    # A workspace SEEDED from a prior (site) run: stale goal.md (all done) + loop-docs.
    workspace = tmp_path / "run"
    workspace.mkdir()
    (workspace / "index.html").write_text("<!-- the site deliverable, keep it -->")  # brownfield code
    (workspace / "goal.md").write_text("# Goal — old site\n- [x] M1\n- [x] M2\n")
    (workspace / "loop-docs").mkdir()
    (workspace / "loop-docs" / "integration-report.json").write_text('{"status":"passed"}')

    loop.stage_workspace(project, workspace, load_method("loop"))

    # Stale generated state is archived, NOT present at the live paths the gates read.
    assert not (workspace / "goal.md").exists(), "stale goal.md must be archived so PLAN re-runs"
    assert not (workspace / "loop-docs" / "integration-report.json").exists(), \
        "stale green report must be archived so the run doesn't 'complete' on turn 1"
    # It's preserved (recoverable), not deleted.
    attic = list(workspace.glob(".superseded-*"))
    assert attic and (attic[0] / "goal.md").is_file() and (attic[0] / "loop-docs").is_dir()
    # The brownfield DELIVERABLE (the site) is untouched, and the new intake is staged.
    assert (workspace / "index.html").read_text() == "<!-- the site deliverable, keep it -->"
    assert (workspace / "vision.md").is_file()
    assert (workspace / "loop-docs").is_dir()  # fresh empty one recreated


def test_stage_workspace_quarantines_seed_git_history(monkeypatch, tmp_path: Path):
    """A brownfield workspace seeded from a prior run inherits that run's `.git` — including
    its `turn/<N>` checkpoint tags and a HEAD at the seed's 'complete' commit. If left in
    place, the fresh `git init` is a no-op re-init that PRESERVES those tags, so a later
    `sdharness resume` can `restore_to_turn(seed's max turn)` straight onto the seed's
    finished state (a silent no-op 'completion'). stage_workspace must move `.git` aside."""
    import subprocess

    project = tmp_path / "project"
    project.mkdir()
    (project / "vision.md").write_text("# Vision\nadd a chat agent")
    ctx = tmp_path / "agent-context"
    ctx.mkdir()
    for name in ("CLAUDE.md", "QUALITY.md", "LESSONS.md"):
        (ctx / name).write_text(f"# {name}")
    monkeypatch.setattr(loop, "agent_context_dir", lambda: ctx)

    # A seeded workspace WITH the prior run's git history + a turn/13 checkpoint tag.
    workspace = tmp_path / "run"
    workspace.mkdir()
    (workspace / "goal.md").write_text("# Goal — old site\n- [x] M1\n")
    (workspace / "index.html").write_text("<!-- seed deliverable -->")

    def _g(*args: str) -> None:
        subprocess.run(["git", *args], cwd=workspace, check=True, capture_output=True, text=True)
    _g("init", "-q")
    _g("config", "user.email", "t@e.st")
    _g("config", "user.name", "t")
    _g("add", "-A")
    _g("commit", "-q", "-m", "seed run turn 13")
    _g("tag", "turn/13")

    loop.stage_workspace(project, workspace, load_method("loop"))

    # The inherited git history is quarantined into the attic (tags gone from the workspace).
    attic = list(workspace.glob(".superseded-*"))
    assert attic and (attic[0] / "git").is_dir(), "seed .git must be archived aside"
    # The fresh init has NO seed tags — resume can't restore_to_turn onto the seed's state.
    tags = subprocess.run(["git", "tag", "-l"], cwd=workspace,
                          capture_output=True, text=True).stdout
    assert "turn/13" not in tags, "seed checkpoint tags must not survive into this run's git"
    # The brownfield deliverable itself is untouched.
    assert (workspace / "index.html").read_text() == "<!-- seed deliverable -->"


def test_stage_workspace_keeps_this_runs_run_config_event(monkeypatch, tmp_path: Path):
    """Regression: __main__ appends the `run_config` event to <method>-docs/events.jsonl
    BEFORE calling run()→stage_workspace. The stale-state archival must NOT treat an
    events.jsonl-only docs dir as stale — otherwise every normal run (workspace != project)
    wipes its own kickoff banner event, and `sdharness replay` loses the banner."""
    project = tmp_path / "project"
    project.mkdir()
    (project / "vision.md").write_text("# Vision\nbuild a thing")
    ctx = tmp_path / "agent-context"
    ctx.mkdir()
    for name in ("CLAUDE.md", "QUALITY.md", "LESSONS.md"):
        (ctx / name).write_text(f"# {name}")
    monkeypatch.setattr(loop, "agent_context_dir", lambda: ctx)

    # A fresh run dir with ONLY the run_config event __main__ just wrote (no stale artifacts).
    workspace = tmp_path / "run"
    (workspace / "loop-docs").mkdir(parents=True)
    (workspace / "loop-docs" / "events.jsonl").write_text('{"event": "run_config", "method": "loop"}\n')

    loop.stage_workspace(project, workspace, load_method("loop"))

    # NOT archived; the run_config line survives so replay renders the banner.
    assert not list(workspace.glob(".superseded-*")), "an events.jsonl-only dir is not stale"
    body = (workspace / "loop-docs" / "events.jsonl").read_text()
    assert "run_config" in body, "this run's run_config event must be preserved"


class _FakeSandbox:
    """Stands in for ClaudeCodeSandbox — records lifecycle calls, writes a file each turn."""

    def __init__(self, *a, **k):
        self.emit = k.get("emit")
        self.connects = 0
        self.reconnects = 0

    async def connect(self):
        self.connects += 1

    async def reconnect(self):
        self.reconnects += 1

    async def disconnect(self):
        pass

    async def execute(self, prompt: str) -> TurnResult:
        return TurnResult(output="did the work", tool_count=1, workspace_writes=1,
                          session_id="s", cost_usd=1.00)


def _install_stubs(monkeypatch, *, phases, complete_after, review):
    """Wire loop's collaborators to deterministic stubs.

    phases: list of phase names the gate walks through (one advance per turn).
    complete_after: turn number after which is_complete() returns True.
    review: the ReviewResult steer() returns each turn (records calls into `calls`).
    """
    calls = {"steer_phases": [], "events": [], "sandbox": None}

    def _make_sandbox(*a, **k):
        sb = _FakeSandbox(*a, **k)
        calls["sandbox"] = sb  # capture the instance the loop builds, so tests see reconnects
        return sb

    monkeypatch.setattr(loop, "ClaudeCodeSandbox", _make_sandbox)
    monkeypatch.setattr(loop, "stage_workspace", lambda *a, **k: None)
    monkeypatch.setattr(loop, "checkpoint", lambda *a, **k: None)
    monkeypatch.setattr(loop, "read_prompt", lambda *a, **k: "system")
    monkeypatch.setattr(loop, "build_can_use_tool", lambda *a, **k: None)
    monkeypatch.setattr(loop, "_tee_events", lambda inner, path: inner)  # no file I/O

    # phase_authority: advance one step per turn; complete after N turns.
    state = {"turn": 0}

    def _next_phase(method, current, workspace):
        idx = phases.index(current)
        return phases[idx + 1] if idx + 1 < len(phases) else current

    def _is_complete(method, workspace):
        state["turn"] += 1
        return state["turn"] > complete_after

    monkeypatch.setattr(loop.phase_authority, "next_phase", _next_phase)
    monkeypatch.setattr(loop.phase_authority, "is_complete", _is_complete)
    monkeypatch.setattr(loop.phase_authority, "milestones", lambda ws, *a, **k: (0, 4))

    async def _steer(strategy, workspace, phase, turn, output):
        calls["steer_phases"].append(phase)
        return review

    monkeypatch.setattr(loop, "steer", _steer)

    def _emit(event, **fields):
        calls["events"].append((event, fields))

    return calls, _emit


def _method(context_reset: str = "none"):
    return Method(name="loop", phases=[{"name": "RESEARCH"}, {"name": "PLAN"}, {"name": "BUILD"}],
                  context_reset=context_reset)


async def test_pilot_reviews_executed_phase_and_advance_after_verdict(monkeypatch, tmp_path: Path):
    review = ReviewResult(decision="GO", direction="onward", gate_held=False, cost_usd=0.25)
    calls, emit = _install_stubs(
        monkeypatch, phases=["RESEARCH", "PLAN", "BUILD"], complete_after=1, review=review)

    await loop.run(project_dir=tmp_path, workspace=tmp_path, method=_method(),
                   strategy=Strategy(name="loop-autopilot"), max_turns=5, emit=emit)

    # Turn 1 executed in RESEARCH — the Pilot must be asked about RESEARCH, not PLAN.
    assert calls["steer_phases"][0] == "RESEARCH"

    # Event order within turn 1: pilot_review comes BEFORE phase_advance.
    names = [e for e, _ in calls["events"]]
    assert names.index("pilot_review") < names.index("phase_advance")

    # turn_end is reported against the executed phase (RESEARCH), not the advanced one.
    turn_end = next(f for e, f in calls["events"] if e == "turn_end")
    assert turn_end["phase"] == "RESEARCH" and turn_end["decision"] == "GO"


async def test_pilot_cost_is_added_to_total(monkeypatch, tmp_path: Path):
    # Agent 1.00/turn + Pilot 0.25/turn. One reviewed turn then completion.
    review = ReviewResult(decision="GO", direction="onward", cost_usd=0.25)
    calls, emit = _install_stubs(
        monkeypatch, phases=["RESEARCH", "PLAN", "BUILD"], complete_after=1, review=review)

    state = await loop.run(project_dir=tmp_path, workspace=tmp_path, method=_method(),
                           strategy=Strategy(name="loop-autopilot"), max_turns=5, emit=emit)

    # Turn 1: agent 1.00 + pilot 0.25 reviewed. Turn 2: completion turn (agent 1.00, no steer).
    # Total must exceed agent-only (2.00) because the Pilot's 0.25 is counted.
    assert state.total_cost_usd > 2.00


# ── a raised crash emits a durable terminal `complete` event (never dies silently) ──


async def test_raised_crash_emits_terminal_complete_with_error(monkeypatch, tmp_path: Path):
    """A RAISED failure (SDK/transport/buffer overflow) must NOT unwind past the loop and die
    with no terminal event. The loop catches it, records it on state, and still emits a single
    terminal `complete` carrying complete=False + a non-empty `error` — so a consumer reading
    events.jsonl can tell "died" from "finished". run() returns (does not re-raise), so
    cmd_run's `return 0 if state.complete else 1` yields a clean non-zero exit."""
    review = ReviewResult(decision="GO", direction="onward", cost_usd=0.25)
    calls, emit = _install_stubs(
        monkeypatch, phases=["RESEARCH", "PLAN", "BUILD"], complete_after=99, review=review)

    class _CrashingSandbox(_FakeSandbox):
        async def execute(self, prompt: str) -> TurnResult:
            raise RuntimeError("JSON message exceeded maximum buffer size of 1048576 bytes")

    monkeypatch.setattr(loop, "ClaudeCodeSandbox", _CrashingSandbox)

    state = await loop.run(project_dir=tmp_path, workspace=tmp_path, method=_method(),
                           strategy=Strategy(name="loop-autopilot"), max_turns=5, emit=emit)

    # run() returned rather than propagating the exception.
    assert state.complete is False
    assert state.error and "RuntimeError" in state.error

    # Exactly one terminal `complete` event, carrying the error (not complete, not clean).
    completes = [f for e, f in calls["events"] if e == "complete"]
    assert len(completes) == 1
    assert completes[0]["complete"] is False
    assert completes[0]["error"] and "buffer size" in completes[0]["error"]

    # We reused the existing terminal `complete` — NO invented `run_error` event type
    # (kit stays a faithful subset of upstream, which signals failure via its terminal event).
    assert not any(e == "run_error" for e, _ in calls["events"])


async def test_clean_run_terminal_complete_has_no_error(monkeypatch, tmp_path: Path):
    """A normal run's terminal `complete` carries error=None — the field is additive and null
    on the happy path, so old consumers/renderers are unaffected."""
    review = ReviewResult(decision="GO", direction="onward", cost_usd=0.25)
    calls, emit = _install_stubs(
        monkeypatch, phases=["RESEARCH", "PLAN", "BUILD"], complete_after=1, review=review)

    state = await loop.run(project_dir=tmp_path, workspace=tmp_path, method=_method(),
                           strategy=Strategy(name="loop-autopilot"), max_turns=5, emit=emit)

    assert state.complete is True and state.error is None
    complete = next(f for e, f in calls["events"] if e == "complete")
    assert complete["complete"] is True
    assert complete.get("error") is None


# ── opt-in phase-boundary context reset (default "none" is byte-for-byte unchanged) ──


async def test_context_reset_none_never_reconnects_or_emits(monkeypatch, tmp_path: Path):
    """DEFAULT (context_reset="none"): the persistent-session behavior is unchanged — the
    loop connects ONCE and never reconnects, and no `context_reset` event is emitted even as
    phases advance. This is the regression guard: existing runs must not change at all."""
    review = ReviewResult(decision="GO", direction="onward", cost_usd=0.25)
    # complete_after=3 lets the gate walk RESEARCH→PLAN→BUILD (2 advances) before completing.
    calls, emit = _install_stubs(
        monkeypatch, phases=["RESEARCH", "PLAN", "BUILD"], complete_after=3, review=review)

    await loop.run(project_dir=tmp_path, workspace=tmp_path, method=_method("none"),
                   strategy=Strategy(name="loop-autopilot"), max_turns=5, emit=emit)

    # Phases DID advance (so the guard is real), but no reset happened.
    assert any(e == "phase_advance" for e, _ in calls["events"])
    assert calls["sandbox"].connects == 1, "one persistent session for the whole run"
    assert calls["sandbox"].reconnects == 0, "default must never reconnect"
    assert not any(e == "context_reset" for e, _ in calls["events"]), \
        "default emits no context_reset events"


async def test_context_reset_phase_boundary_reconnects_and_emits_per_advance(monkeypatch, tmp_path: Path):
    """OPT-IN (context_reset="phase_boundary"): the loop reconnects the coding-agent session
    once per phase advance and emits a matching `context_reset` event with the right from/to —
    and NOT on same-phase turns."""
    review = ReviewResult(decision="GO", direction="onward", cost_usd=0.25)
    calls, emit = _install_stubs(
        monkeypatch, phases=["RESEARCH", "PLAN", "BUILD"], complete_after=3, review=review)

    await loop.run(project_dir=tmp_path, workspace=tmp_path, method=_method("phase_boundary"),
                   strategy=Strategy(name="loop-autopilot"), max_turns=5, emit=emit)

    advances = [f for e, f in calls["events"] if e == "phase_advance"]
    resets = [f for e, f in calls["events"] if e == "context_reset"]
    # One reset per advance, same count, same from/to pairs, same order.
    assert len(resets) == len(advances) >= 2
    assert calls["sandbox"].reconnects == len(advances)
    assert [(r["from"], r["to"]) for r in resets] == [(a["from"], a["to"]) for a in advances]
    assert all(r["reason"] == "phase_boundary" for r in resets)
    # Ordering within a turn: phase_advance → turn_end → context_reset.
    names = [e for e, _ in calls["events"]]
    assert names.index("phase_advance") < names.index("turn_end") < names.index("context_reset")


# ── budget ceiling (--max-budget): a hard USD cap that stops the run cleanly ──


async def test_budget_ceiling_stops_the_run(monkeypatch, tmp_path: Path):
    """--max-budget caps total spend (agent + Pilot). With agent $1.00 + Pilot $0.25 = $1.25
    a turn and a $2.00 ceiling, the run must stop after the 2nd turn ($2.50 ≥ $2.00) with a
    budget-ceiling reason — not run to completion. complete_after is high so only the budget
    stops it."""
    review = ReviewResult(decision="GO", direction="onward", cost_usd=0.25)
    calls, emit = _install_stubs(
        monkeypatch, phases=["RESEARCH", "PLAN", "BUILD"], complete_after=99, review=review)

    state = await loop.run(project_dir=tmp_path, workspace=tmp_path, method=_method(),
                           strategy=Strategy(name="loop-autopilot"), max_turns=50, emit=emit,
                           max_budget=2.00)

    assert state.complete is False
    assert "budget ceiling" in state.complete_reason
    # Stopped as soon as the total crossed $2.00 — not at max_turns (50) or completion.
    assert state.turn < 50
    assert state.total_cost_usd >= 2.00
    # The terminal `complete` carries the budget reason.
    complete = next(f for e, f in calls["events"] if e == "complete")
    assert complete["complete"] is False and "budget ceiling" in complete["reason"]


async def test_no_budget_runs_to_completion(monkeypatch, tmp_path: Path):
    """Default (max_budget=0) imposes no ceiling — the run completes normally, unchanged."""
    review = ReviewResult(decision="GO", direction="onward", cost_usd=0.25)
    calls, emit = _install_stubs(
        monkeypatch, phases=["RESEARCH", "PLAN", "BUILD"], complete_after=1, review=review)

    state = await loop.run(project_dir=tmp_path, workspace=tmp_path, method=_method(),
                           strategy=Strategy(name="loop-autopilot"), max_turns=5, emit=emit)

    assert state.complete is True
    assert "budget" not in (state.complete_reason or "")


async def test_reconnect_resets_cost_baseline(monkeypatch, tmp_path: Path):
    """`reconnect()` must zero `_prev_cost_usd` — a fresh session restarts the SDK's cumulative
    total_cost_usd at 0, so without the reset the next turn's delta (see _cost_delta) would
    under-report. Unit-tested directly on the real sandbox (its client is never connected)."""
    from harness.sandbox import ClaudeCodeSandbox

    sb = ClaudeCodeSandbox(workspace=tmp_path, system_prompt_append="", can_use_tool=None)
    sb._prev_cost_usd = 7.50  # simulate a session that has spent $7.50 cumulatively

    # reconnect = disconnect + fresh connect; stub both so no real SDK client is built.
    async def _noop(self):
        self._client = None

    monkeypatch.setattr(ClaudeCodeSandbox, "disconnect", _noop)
    monkeypatch.setattr(ClaudeCodeSandbox, "connect", _noop)

    await sb.reconnect()

    assert sb._prev_cost_usd == 0.0, "the delta baseline must reset for the fresh session"
