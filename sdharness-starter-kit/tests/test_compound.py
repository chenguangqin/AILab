# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""`sdharness compound` write-back + the STEERING_PLAYBOOK Pilot wiring.

Both are the compound-engineering seam: `compound` closes the loop (run → LESSONS
seed), and the Pilot persona now includes the accumulated steering playbook. Pure /
offline — no live model.
"""

from __future__ import annotations

from pathlib import Path

from harness.compound import compound_run, extract_patterns
from harness.config import load_strategy
from harness.steering import build_pilot_persona

_PROGRESS = """# Progress

## Patterns

### Cache node_modules across turns
**Trigger:** npm install ran every turn, wasting minutes.
**Fix:** reuse the workspace node_modules between turns.

### Prove the wiring, not just the parts
A duplicate of an existing seed lesson.

## 2026-07-03 — M1 scaffold
**Outcome:** scaffolded the app; `npm run build` exited 0.
"""

_SEED = (
    "# Lessons Learned\n\n## Patterns\n\n"
    "<!-- General truths. Check every project against these. -->\n\n"
    "### Prove the wiring, not just the parts\n\n**Fix:** existing entry.\n"
)


# ── extraction ──


def test_extract_patterns_titles_and_bodies():
    pats = extract_patterns(_PROGRESS)
    titles = [t for t, _ in pats]
    assert titles == ["Cache node_modules across turns", "Prove the wiring, not just the parts"]
    # body captured, and the trailing '## <date>' section is excluded
    assert "npm install" in pats[0][1]
    assert "Outcome" not in "\n".join(b for _, b in pats)


def test_extract_patterns_none_when_no_titled_blocks():
    assert extract_patterns("# Progress\n\n## Patterns\n\n- just a bullet, no ### block\n") == []
    assert extract_patterns("# Progress\n\nno patterns section at all\n") == []


# ── compound_run: dedup, idempotence, dry-run ──


def _run_dir(tmp_path: Path) -> Path:
    (tmp_path / "progress.md").write_text(_PROGRESS)
    return tmp_path


def test_compound_adds_new_and_dedups_existing(tmp_path: Path):
    run = _run_dir(tmp_path)
    seed = tmp_path / "LESSONS.md"
    seed.write_text(_SEED)
    added, skipped, content = compound_run(run, dry_run=False, lessons_path=seed)
    assert added == ["Cache node_modules across turns"]
    assert skipped == ["Prove the wiring, not just the parts"]
    assert "### Cache node_modules across turns" in seed.read_text()
    # the existing lesson appears exactly once (no dup inserted)
    assert content.count("### Prove the wiring, not just the parts") == 1


def test_compound_is_idempotent(tmp_path: Path):
    run = _run_dir(tmp_path)
    seed = tmp_path / "LESSONS.md"
    seed.write_text(_SEED)
    compound_run(run, dry_run=False, lessons_path=seed)
    added2, _, _ = compound_run(run, dry_run=False, lessons_path=seed)
    assert added2 == []  # second run promotes nothing new


def test_compound_dry_run_writes_nothing(tmp_path: Path):
    run = _run_dir(tmp_path)
    seed = tmp_path / "LESSONS.md"
    seed.write_text(_SEED)
    before = seed.read_text()
    added, _, _ = compound_run(run, dry_run=True, lessons_path=seed)
    assert added == ["Cache node_modules across turns"]
    assert seed.read_text() == before  # nothing written


def test_compound_finds_progress_in_docs_subdir(tmp_path: Path):
    docs = tmp_path / "loop-docs"
    docs.mkdir()
    (docs / "progress.md").write_text(_PROGRESS)
    seed = tmp_path / "LESSONS.md"
    seed.write_text(_SEED)
    added, _, _ = compound_run(tmp_path, dry_run=False, lessons_path=seed)
    assert "Cache node_modules across turns" in added


def test_compound_missing_progress_raises(tmp_path: Path):
    import pytest
    seed = tmp_path / "LESSONS.md"
    seed.write_text(_SEED)
    with pytest.raises(FileNotFoundError):
        compound_run(tmp_path, lessons_path=seed)


# ── STEERING_PLAYBOOK wired into the Pilot ──


def test_pilot_persona_includes_steering_playbook():
    persona = build_pilot_persona(load_strategy("loop-autopilot"))
    assert "Steering playbook (accumulated tactics)" in persona
    # and still includes the strategy's own steering prompt
    assert len(persona) > 500
