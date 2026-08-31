# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""Deterministic phase advancement — the heart of "gates, not vibes".

`evaluate(predicate, workspace)` returns True/False for a structural predicate
tree. The harness — never the coding agent — decides when a phase is done by
checking whether the required artifacts exist on disk. No LLM is in this path.

Predicate grammar (the method's `complete_when`):

  Combinators:
    {"all":  [p, ...]}          all must hold
    {"any":  [p, ...]}          at least one holds
    {"not":  p}                 negation  (e.g. "no unchecked '- [ ]' remains")

  Leaves:
    {"file_exists": "path"}                         file is present
    {"file_exists": "path", "file_min_lines": N}    …and has >= N lines
    {"file": "path", "file_contains": "s"|[...]}    file contains ALL needles
    {"no_unchecked": "path"}                         file has ZERO open "- [ ]" items
    {"checkbox_min_checked": "path", "min_count": N} file has >= N "- [x]" items
    {"dir_has_files": "dir", "min_count": N}         dir has >= N (default 1) files
    {"file": "path", "json_field": "a.b", "expected_value": v}   JSON field == v

Checkbox gates: prefer the first-class `no_unchecked` leaf ("all task-list items
checked off") over the older `{"not": {"file_contains": "- [ ]"}}` idiom. The
substring form collided with prose/fenced-code that merely *mentioned* `- [ ]`,
silently freezing a phase (a doc saying "no `- [ ]` items remain" once matched
itself). `no_unchecked` — and a checkbox needle inside `file_contains` — match
ONLY a real GFM task-list item at line start, never prose.

IMPORTANT (the "unsatisfiable gate" bug class): a *positive* prose-heading
`file_contains` is forbidden by the readiness test — a model rarely reproduces an
exact heading, so the gate can never pass and the loop spins. Use structural
checks.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# A GitHub-flavored task-list item, matched ONLY at line start (optional indent,
# a bullet - * +, then "[ ]" / "[x]"). Anchored so prose that merely *mentions*
# "- [ ]" (e.g. "No open `- [ ]` items remain") is NOT a match — that false
# positive once kept a `not file_contains "- [ ]"` gate from ever passing.
# `(?im)` = case-insensitive + multiline (^ matches each line).
_UNCHECKED_RE = re.compile(r"(?im)^\s*[-*+]\s*\[ \]")
_CHECKED_RE = re.compile(r"(?im)^\s*[-*+]\s*\[[xX]\]")


def milestones(workspace: Path, doc: str = "goal.md") -> tuple[int, int]:
    """Count (checked, total) GFM task-list milestones in the run's `goal.md`.

    Used only for progress display (the status line + JSON events) — it does NOT
    drive advancement; the gates do. Looks in the workspace root and `loop-docs/`.
    Returns (0, 0) when there's no milestone doc yet.
    """
    for candidate in (workspace / doc, workspace / "loop-docs" / doc):
        if candidate.is_file():
            text = candidate.read_text()
            checked = len(_CHECKED_RE.findall(text))
            total = checked + len(_UNCHECKED_RE.findall(text))
            return checked, total
    return 0, 0


def _needle_is_checkbox(needle: str) -> str | None:
    """Classify a `file_contains` needle as a checkbox token.

    Returns "unchecked" for `- [ ]` / `-[ ]` / `* [ ]` / `+ [ ]`, "checked" for
    the `[x]` variants, or None for any other needle (plain substring). Inner
    whitespace is normalized so authors can write it either way."""
    box = needle.strip().replace(" ", "")
    if box in ("-[]", "*[]", "+[]"):
        return "unchecked"
    if box in ("-[x]", "-[X]", "*[x]", "*[X]", "+[x]", "+[X]"):
        return "checked"
    return None


def _text_contains(text: str, needle: str) -> bool:
    """`file_contains` matcher. A checkbox needle matches only a real GFM task-list
    item at line start (never prose/fenced-code that mentions the token); every
    other needle keeps plain case-insensitive substring behavior."""
    kind = _needle_is_checkbox(needle)
    if kind == "unchecked":
        return bool(_UNCHECKED_RE.search(text))
    if kind == "checked":
        return bool(_CHECKED_RE.search(text))
    return str(needle).lower() in text.lower()


def evaluate(predicate: dict[str, Any], workspace: Path) -> bool:
    """True if the structural predicate holds against `workspace`. Empty = True."""
    if not predicate:
        return True

    # ── Combinators ──
    if "all" in predicate:
        return all(evaluate(p, workspace) for p in predicate["all"])
    if "any" in predicate:
        return any(evaluate(p, workspace) for p in predicate["any"])
    if "not" in predicate:
        return not evaluate(predicate["not"], workspace)

    # ── Leaves ── (a clause may combine keys, e.g. file_exists + file_min_lines)
    ok = True

    if "file_exists" in predicate:
        if not (workspace / predicate["file_exists"]).is_file():
            ok = False

    if "file_min_lines" in predicate:
        key = predicate.get("file_exists") or predicate.get("file", "")
        path = workspace / key if key else None
        if not path or not path.is_file():
            ok = False
        elif len(path.read_text().splitlines()) < predicate["file_min_lines"]:
            ok = False

    if "file_contains" in predicate:
        key = predicate.get("file_exists") or predicate.get("file", "")
        path = workspace / key if key else None
        if not path or not path.is_file():
            ok = False
        else:
            text = path.read_text()
            needles = predicate["file_contains"]
            if isinstance(needles, str):
                needles = [needles]
            if not all(_text_contains(text, str(n)) for n in needles):
                ok = False

    # `no_unchecked` — first-class "all task-list items checked off" gate:
    # satisfied when the file exists AND has ZERO line-anchored unchecked `- [ ]`
    # items. Immune to the prose/fenced-code collision that plagued the older
    # `{"not": {"file_contains": "- [ ]"}}` idiom, and self-documenting.
    if "no_unchecked" in predicate:
        path = workspace / predicate["no_unchecked"]
        if not path.is_file() or _UNCHECKED_RE.search(path.read_text()):
            ok = False

    # `checkbox_min_checked` — satisfied when the file has >= min_count (default 1)
    # line-anchored checked `- [x]` items. For "at least N milestones done".
    if "checkbox_min_checked" in predicate:
        path = workspace / predicate["checkbox_min_checked"]
        min_count = predicate.get("min_count", 1)
        if not path.is_file() or len(_CHECKED_RE.findall(path.read_text())) < min_count:
            ok = False

    if "dir_has_files" in predicate:
        d = workspace / predicate["dir_has_files"]
        min_count = predicate.get("min_count", 1)
        if not d.is_dir():
            ok = False
        else:
            count = sum(1 for f in d.iterdir() if f.is_file() and not f.name.startswith("."))
            if count < min_count:
                ok = False

    if "json_field" in predicate:
        key = predicate.get("file_exists") or predicate.get("file", "")
        path = workspace / key if key else None
        if not path or not path.is_file():
            ok = False
        else:
            try:
                data = json.loads(path.read_text())
                val: Any = data
                for part in predicate["json_field"].split("."):
                    if isinstance(val, dict):
                        val = val.get(part)
                    elif isinstance(val, list) and part.isdigit():
                        val = val[int(part)]
                    else:
                        val = None
                        break
                expected = predicate.get("expected_value")
                if expected is not None and val != expected:
                    ok = False
                elif expected is None and val is None:
                    ok = False
            except Exception:
                ok = False

    return ok


def next_phase(method, current: str, workspace: Path) -> str:
    """Advance to the next phase iff `current`'s complete_when holds; else stay.

    Returns the (possibly unchanged) phase name.
    """
    names = [p.name for p in method.phases]
    if current not in names:
        return names[0] if names else current
    if not evaluate(method.complete_when(current), workspace):
        return current  # phase not done — hold
    idx = names.index(current)
    return names[idx + 1] if idx + 1 < len(names) else current


def is_complete(method, workspace: Path) -> bool:
    """True when the terminal completion predicate holds."""
    return evaluate(method.terminal_requires(), workspace)
