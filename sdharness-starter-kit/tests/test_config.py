# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""Config loading + the structural-predicate evaluator."""

from __future__ import annotations

import json
from pathlib import Path


from harness import phase_authority as pa
from harness.config import _KIT_ROOT, load_method, load_strategy, runs_dir
from harness.gates import check


def test_loop_method_loads():
    m = load_method("loop")
    assert m.name == "loop"
    assert [p.name for p in m.phases] == ["RESEARCH", "PLAN", "BUILD", "VERIFY"]
    assert m.default_strategy == "loop-autopilot"
    assert m.system_prompt_file == "system-prompt.md"
    # every phase declares a complete_when
    for p in m.phases:
        assert m.complete_when(p.name), f"{p.name} missing complete_when"
    assert m.terminal_requires()


def test_loop_strategy_loads():
    s = load_strategy("loop-autopilot")
    assert s.name == "loop-autopilot"
    assert len(s.reviewers) == 1
    assert s.consensus_rule == "autopilot"


# ── predicate evaluator ──


def test_file_exists_and_min_lines(tmp_path: Path):
    (tmp_path / "a.md").write_text("l1\nl2\nl3\n")
    assert pa.evaluate({"file_exists": "a.md"}, tmp_path)
    assert pa.evaluate({"file_exists": "a.md", "file_min_lines": 3}, tmp_path)
    assert not pa.evaluate({"file_exists": "a.md", "file_min_lines": 4}, tmp_path)
    assert not pa.evaluate({"file_exists": "missing.md"}, tmp_path)


def test_not_and_all_combinators(tmp_path: Path):
    (tmp_path / "g.md").write_text("done\nno checkboxes here\n")
    pred = {"all": [
        {"file_exists": "g.md"},
        {"not": {"file": "g.md", "file_contains": "- [ ]"}},
    ]}
    assert pa.evaluate(pred, tmp_path)
    (tmp_path / "g.md").write_text("- [ ] still open\n")
    assert not pa.evaluate(pred, tmp_path)


def test_json_field(tmp_path: Path):
    (tmp_path / "r.json").write_text(json.dumps(
        {"status": "passed", "summary": {"all_seams_exercised": True}}
    ))
    assert pa.evaluate(
        {"file": "r.json", "json_field": "status", "expected_value": "passed"}, tmp_path)
    assert pa.evaluate(
        {"file": "r.json", "json_field": "summary.all_seams_exercised", "expected_value": True},
        tmp_path)
    assert not pa.evaluate(
        {"file": "r.json", "json_field": "status", "expected_value": "failed"}, tmp_path)


def test_next_phase_holds_until_artifact(tmp_path: Path):
    m = load_method("loop")
    # RESEARCH not done → stay
    assert pa.next_phase(m, "RESEARCH", tmp_path) == "RESEARCH"
    # write a sufficient research.md → advance
    (tmp_path / "loop-docs").mkdir()
    (tmp_path / "loop-docs" / "research.md").write_text("\n".join(f"line {i}" for i in range(15)))
    assert pa.next_phase(m, "RESEARCH", tmp_path) == "PLAN"


def test_plan_advances_on_root_goal_and_loop_docs_architecture(tmp_path: Path):
    """PLAN's gate keys on generated `loop-docs/architecture.md` + the authored
    `goal.md` contract at the workspace ROOT (inputs-at-root layout, upstream #45)."""
    m = load_method("loop")
    (tmp_path / "loop-docs").mkdir()
    (tmp_path / "loop-docs" / "architecture.md").write_text("\n".join(f"a{i}" for i in range(25)))
    # architecture present but goal.md missing at root → still PLAN
    assert pa.next_phase(m, "PLAN", tmp_path) == "PLAN"
    # goal.md at ROOT (not loop-docs/) → advance to BUILD
    (tmp_path / "goal.md").write_text("# Goal\n" + "\n".join(f"- [ ] m{i}" for i in range(12)))
    assert pa.next_phase(m, "PLAN", tmp_path) == "BUILD"


def test_build_completes_on_root_goal_all_checked(tmp_path: Path):
    """BUILD is done when the ROOT `goal.md` has no unchecked box and progress.md exists."""
    m = load_method("loop")
    (tmp_path / "loop-docs").mkdir()
    (tmp_path / "loop-docs" / "progress.md").write_text("# Progress\n" + "\n".join(f"l{i}" for i in range(6)))
    (tmp_path / "goal.md").write_text("# Goal\n" + "\n".join(f"- [x] m{i}" for i in range(12)))
    assert pa.next_phase(m, "BUILD", tmp_path) == "VERIFY"
    # an unchecked box at root holds BUILD
    (tmp_path / "goal.md").write_text("# Goal\n- [x] a\n- [ ] b\n" + "\n".join(f"x{i}" for i in range(10)))
    assert pa.next_phase(m, "BUILD", tmp_path) == "BUILD"


# ── gates ──


def test_gate_blocks_root_deliverable_before_architecture(tmp_path: Path):
    m = load_method("loop")
    # The deliverable lives at the workspace ROOT; nothing there may be written until
    # loop-docs/architecture.md exists (the PLAN gate).
    r = check(m, tmp_path, "Write", {"file_path": str(tmp_path / "package.json")})
    assert not r.allow
    r = check(m, tmp_path, "Write", {"file_path": str(tmp_path / "src" / "app.tsx")})
    assert not r.allow
    # Harness files under loop-docs/ are always allowed (that's where PLAN happens).
    r = check(m, tmp_path, "Write", {"file_path": str(tmp_path / "loop-docs" / "architecture.md")})
    assert r.allow
    # The authored inputs + the goal.md contract live at the ROOT and are always
    # allowed (they are harness inputs, not deliverable code) — even before PLAN.
    for name in ("goal.md", "vision.md", "tech-env.md", "CLAUDE.md", "QUALITY.md", "LESSONS.md"):
        r = check(m, tmp_path, "Write", {"file_path": str(tmp_path / name)})
        assert r.allow, f"{name} must be always-allowed at the root"


def test_gate_releases_root_after_architecture(tmp_path: Path):
    m = load_method("loop")
    arch = tmp_path / "loop-docs" / "architecture.md"
    arch.parent.mkdir(parents=True)
    arch.write_text("\n".join(f"line {i}" for i in range(25)))  # >= 20 lines
    # Once PLAN's architecture.md exists, root deliverable writes are allowed.
    r = check(m, tmp_path, "Write", {"file_path": str(tmp_path / "package.json")})
    assert r.allow
    r = check(m, tmp_path, "Write", {"file_path": str(tmp_path / "src" / "app.tsx")})
    assert r.allow


def test_gate_containment_blocks_escape(tmp_path: Path):
    m = load_method("loop")
    r = check(m, tmp_path, "Write", {"file_path": "/etc/evil.conf"})
    assert not r.allow and r.interrupt


def test_gates_enforced_regardless_of_autonomy(tmp_path: Path):
    """Gate enforcement is unconditional — it does NOT depend on autonomy mode.
    Autonomy is about *who answers* a gate, never a switch that disables it, so the
    same premature root write is blocked (check() takes no yolo argument by design)."""
    m = load_method("loop")
    r = check(m, tmp_path, "Write", {"file_path": str(tmp_path / "package.json")})
    assert not r.allow, "root deliverable gate must enforce regardless of autonomy mode"


# ── runs_dir(): generated workspaces live OUTSIDE the kit source tree ──────────


def test_runs_dir_defaults_to_a_sibling_of_the_kit(monkeypatch):
    """Default is `sdharness-runs/` beside the kit repo (NOT inside it), so a checkout
    stays clean and the workshop shows the two folders side by side."""
    monkeypatch.delenv("SDHARNESS_RUNS_DIR", raising=False)
    assert runs_dir() == _KIT_ROOT.parent / "sdharness-runs"
    # and it is NOT under the kit source tree
    assert _KIT_ROOT not in runs_dir().parents


def test_runs_dir_env_overrides_both_name_and_location(monkeypatch):
    """`SDHARNESS_RUNS_DIR` is a FULL path: its parent sets the LOCATION, its leaf the NAME."""
    monkeypatch.setenv("SDHARNESS_RUNS_DIR", "/data/my-runs")
    d = runs_dir()
    assert d == Path("/data/my-runs")
    assert d.parent == Path("/data")   # location
    assert d.name == "my-runs"         # name


def test_runs_dir_expands_home(monkeypatch):
    monkeypatch.setenv("SDHARNESS_RUNS_DIR", "~/sdharness-projects")
    assert runs_dir() == (Path.home() / "sdharness-projects").resolve()


def test_runs_dir_blank_env_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("SDHARNESS_RUNS_DIR", "   ")
    assert runs_dir() == _KIT_ROOT.parent / "sdharness-runs"
