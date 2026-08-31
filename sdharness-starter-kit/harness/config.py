# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""Load methods and strategies from JSON — with zero-code extension.

Resolution order (first hit wins) — this is the fork seam. A customer adds a
method by dropping a directory; no framework change, no reinstall:

  1. an explicit path (absolute or relative)
  2. project-local  ./harness-methods/<name>/     (or ./harness-strategies/<name>/)
  3. built-in       <kit>/methods/<name>/          (or <kit>/strategies/<name>/)
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from .models import Method, Strategy

# The kit root is the parent of this package — built-in methods/strategies live there.
_KIT_ROOT = Path(__file__).resolve().parent.parent


def _resolve(name: str, project_local: str, builtin: str) -> Path:
    p = Path(name)
    if p.is_dir():
        return p
    candidates = [
        Path.cwd() / project_local / name,
        _KIT_ROOT / builtin / name,
    ]
    for c in candidates:
        if c.is_dir():
            return c
    searched = "\n  ".join(str(c) for c in candidates)
    raise FileNotFoundError(f"Could not find '{name}'. Searched:\n  {searched}")


def load_method(name: str) -> Method:
    d = _resolve(name, "harness-methods", "methods")
    data = json.loads((d / "method.json").read_text())
    method = Method(**data)
    method.dir = d
    return method


def load_strategy(name: str) -> Strategy:
    d = _resolve(name, "harness-strategies", "strategies")
    data = json.loads((d / "strategy.json").read_text())
    strategy = Strategy(**data)
    strategy.dir = d
    return strategy


def agent_context_dir() -> Path:
    """The seed of coding-agent context (CLAUDE.md / QUALITY.md / LESSONS.md …)
    staged into each run workspace. In a fork this is the compound-engineering
    knowledge base — see docs/concepts/compound-engineering.md."""
    return _KIT_ROOT / "agent-context"


def runs_dir() -> Path:
    """Base dir for generated run workspaces — deliberately OUTSIDE the kit source tree.

    Default: a `sdharness-runs/` sibling of the kit repo (so a checkout stays clean and, in
    the workshop IDE, `workspace/sdharness-starter-kit` and `workspace/sdharness-runs` sit
    side by side rather than run artifacts piling up inside the source).

    Fully configurable via `SDHARNESS_RUNS_DIR` — a FULL path whose parent is the LOCATION
    and whose leaf is the NAME, so one setting controls both (e.g. `/data/my-runs`, or
    `~/sdharness-projects` for an upstream-style path). To change the default without an env
    var, a fork edits the one expression below (its `.parent` = location, the literal = name)."""
    env = os.environ.get("SDHARNESS_RUNS_DIR", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return _KIT_ROOT.parent / "sdharness-runs"


def read_prompt(base_dir: Path | None, filename: str | None) -> str:
    """Read a prompt file relative to a method/strategy dir; '' if absent."""
    if not base_dir or not filename:
        return ""
    p = base_dir / filename
    return p.read_text() if p.is_file() else ""


def resolve_skill_plugin(name: str) -> Path | None:
    """Find a locally-installed Claude Code skill/plugin by name, or None.

    Because the kit runs the coding agent with `setting_sources=["project","local"]`
    (no "user"), host-installed skills are NOT auto-discovered — we attach them
    explicitly and reproducibly via `plugins=[{type:local, path:...}]`. This finds
    the plugin dir that provides `skills/<name>/SKILL.md`.

    Resolution (first hit wins), all optional so a fork without the skill still runs:
      1. project-local   ./harness-skills/<name>/
      2. kit-bundled     <kit>/skills/<name>/
      3. installed plugin ~/.claude/plugins/**/<name>/**/.claude-plugin/plugin.json
    Returns the plugin ROOT dir (the one containing skills/<name>/SKILL.md), or None.
    """
    # 1 & 2: kit-controlled locations
    for base in (Path.cwd() / "harness-skills" / name, _KIT_ROOT / "skills" / name):
        if (base / "skills" / name / "SKILL.md").is_file() or (base / "SKILL.md").is_file():
            return base

    # 3: an installed Claude Code plugin (host path — portable *only* as a fallback)
    plugins_root = Path.home() / ".claude" / "plugins"
    if plugins_root.is_dir():
        for skill_md in plugins_root.glob(f"**/skills/{name}/SKILL.md"):
            # plugin root = the dir two levels up from skills/<name>/SKILL.md
            return skill_md.parent.parent.parent
    return None
