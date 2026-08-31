# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""Phase-authority predicate tests — the checkbox-gate fix distilled from
upstream sdharness MR !100 (issues #40 + #41).

The #40 bug: `file_contains "- [ ]"` matched a checkbox token as a naive full-file
substring, so a doc whose PROSE merely mentioned `- [ ]` (e.g. "No open `- [ ]`
items remain") satisfied it — freezing a `not file_contains` gate. A live
bake-like-a-pro run hit exactly this and stayed labeled RESEARCH for the whole run.

The fix: a checkbox needle matches only a real GFM task-list item at line start,
and a first-class `no_unchecked` leaf replaces the `{"not": {"file_contains":
"- [ ]"}}` idiom the shipped loop method used.
"""

from __future__ import annotations

from pathlib import Path

from harness.phase_authority import evaluate, milestones


# ── #40: file_contains checkbox needle is line-anchored ──────────────────────

def test_prose_mention_does_not_match_checkbox_needle(tmp_path: Path) -> None:
    """THE #40 REPRO. A sentence mentioning `- [ ]` must NOT satisfy file_contains,
    so the historical `not` idiom (gate: no unchecked items) still advances."""
    (tmp_path / "loop-docs").mkdir()
    (tmp_path / "loop-docs" / "research.md").write_text(
        "# Research\n" + "\n".join(f"line {i}" for i in range(14))
        + "\nNo open `- [ ]` items remain in this document.\n"
    )
    assert not evaluate(
        {"file": "loop-docs/research.md", "file_contains": "- [ ]"}, tmp_path)
    # …and therefore the negated idiom advances (the gate the live run failed on).
    assert evaluate(
        {"not": {"file": "loop-docs/research.md", "file_contains": "- [ ]"}}, tmp_path)


def test_real_unchecked_item_matches_checkbox_needle(tmp_path: Path) -> None:
    (tmp_path / "goal.md").write_text("# Goal\n- [ ] real todo\n- [x] done\n")
    assert evaluate({"file": "goal.md", "file_contains": "- [ ]"}, tmp_path)


def test_backtick_prose_mention_does_not_match(tmp_path: Path) -> None:
    (tmp_path / "doc.md").write_text("# Doc\nWrite `- [ ]` to add a task.\n")
    assert not evaluate({"file": "doc.md", "file_contains": "- [ ]"}, tmp_path)


def test_plain_substring_needle_unaffected(tmp_path: Path) -> None:
    """Non-checkbox needles keep plain case-insensitive substring behavior."""
    (tmp_path / "README.md").write_text("# P\n## Deploy\nrun it\n")
    assert evaluate({"file": "README.md", "file_contains": "## deploy"}, tmp_path)


# ── #41: no_unchecked ────────────────────────────────────────────────────────

def test_no_unchecked_true_when_all_checked(tmp_path: Path) -> None:
    (tmp_path / "goal.md").write_text("# Goal\n- [x] a\n- [x] b\nAll done.\n")
    assert evaluate({"no_unchecked": "goal.md"}, tmp_path)


def test_no_unchecked_false_with_real_item(tmp_path: Path) -> None:
    (tmp_path / "goal.md").write_text("# Goal\n- [x] a\n- [ ] b\n")
    assert not evaluate({"no_unchecked": "goal.md"}, tmp_path)


def test_no_unchecked_true_on_prose_mention(tmp_path: Path) -> None:
    (tmp_path / "goal.md").write_text("# Goal\nNo `- [ ]` items remain.\n")
    assert evaluate({"no_unchecked": "goal.md"}, tmp_path)


def test_no_unchecked_false_on_missing_file(tmp_path: Path) -> None:
    assert not evaluate({"no_unchecked": "nope.md"}, tmp_path)


# ── #41: checkbox_min_checked ────────────────────────────────────────────────

def test_checkbox_min_checked_counts_real_items(tmp_path: Path) -> None:
    (tmp_path / "goal.md").write_text("# Goal\n- [x] a\n- [x] b\n- [ ] c\n")
    assert evaluate({"checkbox_min_checked": "goal.md", "min_count": 2}, tmp_path)
    assert not evaluate({"checkbox_min_checked": "goal.md", "min_count": 3}, tmp_path)


def test_checkbox_min_checked_ignores_prose(tmp_path: Path) -> None:
    (tmp_path / "goal.md").write_text("# Goal\nWrite `- [x]` when done.\n")
    assert not evaluate({"checkbox_min_checked": "goal.md", "min_count": 1}, tmp_path)


# ── the shipped loop method's migrated gates evaluate correctly ──────────────

def test_loop_research_gate_advances_on_prose_mention(tmp_path: Path) -> None:
    """End-to-end: the loop method's RESEARCH complete_when (now using
    `no_unchecked`) is satisfied by a research.md that mentions `- [ ]` in prose
    — the exact scenario that froze the live run."""
    from harness.config import load_method

    (tmp_path / "loop-docs").mkdir()
    (tmp_path / "loop-docs" / "research.md").write_text(
        "# Research\n" + "\n".join(f"finding {i}" for i in range(14))
        + "\nNo open `- [ ]` items remain in this document.\n"
    )
    method = load_method("loop")
    assert evaluate(method.complete_when("RESEARCH"), tmp_path)


# ── milestones() — progress counting for the status line + JSON events ───────

def test_milestones_counts_checked_and_total(tmp_path: Path) -> None:
    (tmp_path / "goal.md").write_text("# Goal\n- [x] a\n- [x] b\n- [ ] c\n")
    assert milestones(tmp_path) == (2, 3)


def test_milestones_reads_loop_docs_fallback(tmp_path: Path) -> None:
    (tmp_path / "loop-docs").mkdir()
    (tmp_path / "loop-docs" / "goal.md").write_text("- [x] a\n- [ ] b\n- [ ] c\n")
    assert milestones(tmp_path) == (1, 3)


def test_milestones_zero_when_no_doc(tmp_path: Path) -> None:
    assert milestones(tmp_path) == (0, 0)
