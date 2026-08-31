# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""`sdharness compound` — the manual, LLM-free write-back that closes the loop.

This is the **Compound** step of the loop (Plan → Work → … → Compound): it promotes
what a run learned into the durable seed so the *next* run starts smarter. It lifts
each titled Pattern from a finished run's `progress.md` `## Patterns` section into the
repo's `agent-context/LESSONS.md` (title-deduped). `--dry-run` previews without writing
so a human reviews the diff before committing.

It is deliberately dependency-free and does no LLM call — the entry rung of the
knowledge write-back ladder (see docs/concepts/compound-engineering.md). An automatic,
evaluator-driven extractor is the documented *extension* above it. This mirrors the
shape shipped upstream in sdharness (`sdharness compound`, MR !98 / issue #37).
"""

from __future__ import annotations

import re
from pathlib import Path

from .config import agent_context_dir

_PATTERNS_HEADING = re.compile(r"^##\s+patterns\s*$", re.IGNORECASE)
_NEXT_SECTION = re.compile(r"^##\s+(?!#)")  # a '## ' heading that isn't '### '
_SEED_MARKER = "<!-- General truths. Check every project against these. -->"


def _find_progress_md(run_dir: Path) -> Path | None:
    """Locate a run's `progress.md` — at the workspace root or in any `*-docs/` dir.

    The SD Loop writes it at the root; a fork's method might write `<method>-docs/
    progress.md`. Prefer the root, then the most recently modified `*-docs/progress.md`.
    """
    root = run_dir / "progress.md"
    if root.is_file():
        return root
    candidates = sorted(
        run_dir.glob("*-docs/progress.md"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def extract_patterns(progress_text: str) -> list[tuple[str, str]]:
    """Extract `### Title` / body blocks from the `## Patterns` section of a
    run's progress.md. Returns [(title, body), ...] in document order.

    The `## Patterns` section accumulates reusable discoveries as `### <title>` blocks
    — the same shape `LESSONS.md` uses, so they lift directly. Stops at the next `## `
    section. A bullet-only Patterns section (no `### ` blocks) yields nothing (there's
    no titled lesson to promote).
    """
    lines = progress_text.splitlines()
    start = None
    for i, ln in enumerate(lines):
        if _PATTERNS_HEADING.match(ln.strip()):
            start = i + 1
            break
    if start is None:
        return []

    end = len(lines)
    for i in range(start, len(lines)):
        if _NEXT_SECTION.match(lines[i]):
            end = i
            break

    blocks: list[tuple[str, str]] = []
    cur_title: str | None = None
    cur_body: list[str] = []
    for ln in lines[start:end]:
        if ln.startswith("### "):
            if cur_title is not None:
                blocks.append((cur_title, "\n".join(cur_body).strip()))
            cur_title = ln[4:].strip()
            cur_body = []
        elif cur_title is not None:
            cur_body.append(ln)
    if cur_title is not None:
        blocks.append((cur_title, "\n".join(cur_body).strip()))
    return [(t, b) for t, b in blocks if t and b]


def _is_new(content: str, title: str) -> bool:
    """True if `content` has no `### <title>` entry (title-keyed dedup, like upstream)."""
    return f"### {title}" not in content


def _insert_entry(content: str, title: str, body: str) -> str:
    """Insert a `### title / body` block under `## Patterns` — after the guidance
    comment if present, else after the heading, else append to the end."""
    entry = f"### {title}\n\n{body}\n"
    if _SEED_MARKER in content:
        return content.replace(_SEED_MARKER, f"{_SEED_MARKER}\n\n{entry}", 1)
    for line in content.splitlines():
        if _PATTERNS_HEADING.match(line.strip()):
            return content.replace(line, f"{line}\n\n{entry}", 1)
    # No Patterns section — append one.
    sep = "" if content.endswith("\n") else "\n"
    return f"{content}{sep}\n## Patterns\n\n{entry}"


def compound_run(run_dir: Path, dry_run: bool = False,
                 lessons_path: Path | None = None) -> tuple[list[str], list[str], str]:
    """Promote a run's progress.md Patterns into LESSONS.md.

    Returns (added_titles, skipped_titles, new_lessons_content). Pure enough to unit-test:
    pass an explicit `lessons_path`; with `dry_run=True` nothing is written.
    """
    lessons_path = lessons_path or (agent_context_dir() / "LESSONS.md")
    progress = _find_progress_md(run_dir)
    if progress is None:
        raise FileNotFoundError(f"No progress.md found in {run_dir} (root or *-docs/).")

    patterns = extract_patterns(progress.read_text())
    original = (lessons_path.read_text() if lessons_path.is_file()
                else "# Lessons Learned\n\n## Patterns\n")
    content = original
    added: list[str] = []
    skipped: list[str] = []
    for title, body in patterns:
        if _is_new(content, title):
            content = _insert_entry(content, title, body)
            added.append(title)
        else:
            skipped.append(title)

    if added and not dry_run:
        lessons_path.write_text(content)
    return added, skipped, content
