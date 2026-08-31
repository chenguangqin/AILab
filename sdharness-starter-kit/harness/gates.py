# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tool-use gates — enforcement at the capability boundary, not by advice.

`build_can_use_tool(method, workspace)` returns the callback the Claude
Agent SDK invokes before every tool call. Two checks, both deterministic and
**always enforced**:

  1. **Workspace containment** — deny any Write/Edit whose path escapes the
     workspace. A write outside the sandbox is a hard interrupt.
  2. **Gate rules** — for a `block_path` glob, deny the write until the rule's
     structural `requires` predicate is satisfied (e.g. "no app code before
     architecture.md exists").

Enforcement is unconditional — gates are what make the harness deterministic,
so they run on every turn. (Runs are autonomous: the Pilot answers its own gates.
Enforcement is independent of that — it's about *what* is allowed, not *who*
approves.)

NOTE (see docs/concepts/increasing-autonomy): gates that only intercept Write/Edit
can be bypassed via `Bash` redirects. This kit also checks Bash `>`/`>>`/`tee`
write targets for containment. Gate *rules* here are a teaching example; a serious
fork should also gate Bash writes against rules.
"""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path
from typing import Any, Callable

from .models import Method
from .phase_authority import evaluate

_REDIRECT_RE = re.compile(r'(?:>>?|tee\s+(?:-a\s+)?)["\']?([^\s"\'|;&]+)["\']?')


def _tool_paths(tool_name: str, tool_input: dict) -> list[str]:
    """Extract the file path(s) a tool call would write."""
    if tool_name in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        fp = tool_input.get("file_path", "")
        return [fp] if fp else []
    if tool_name == "Bash":
        return _REDIRECT_RE.findall(tool_input.get("command", "") or "")
    return []


def _escapes_workspace(path: str, workspace: Path) -> bool:
    try:
        target = Path(path)
        if not target.is_absolute():
            target = workspace / target
        return not target.resolve().is_relative_to(workspace.resolve())
    except (ValueError, OSError):
        return False


def check(
    method: Method,
    workspace: Path,
    tool_name: str,
    tool_input: dict,
) -> "GateResult":
    """Pure gate decision for one tool call — unit-testable without the SDK.

    Enforcement is UNCONDITIONAL: gates are what make the harness deterministic,
    so they apply on every run. Autonomy (the Pilot auto-answering gates) is about
    *who approves*, never *what is enforced* — the gate is the whole point."""
    paths = _tool_paths(tool_name, tool_input)
    if not paths:
        return GateResult(allow=True)

    # 1. Containment — a write outside the sandbox is a hard interrupt.
    for p in paths:
        if _escapes_workspace(p, workspace):
            return GateResult(
                allow=False,
                reason=f"Write outside workspace blocked: {p}",
                interrupt=True,
            )

    # 2. Gate rules — deny a write until its structural prerequisite exists
    #    (e.g. no app code before architecture.md). Deny is a soft redirect: the
    #    coding agent gets the hint back and course-corrects; the run continues.
    always = method.always_allow()
    for p in paths:
        rel = _relpath(p, workspace)
        if any(fnmatch.fnmatch(rel, a) or rel == a for a in always):
            continue
        for rule in method.gate_rules():
            if fnmatch.fnmatch(rel, rule.block_path):
                if not evaluate(rule.requires, workspace):
                    return GateResult(
                        allow=False,
                        reason=rule.hint or f"Gate: {rel} blocked until prerequisites exist.",
                    )
    return GateResult(allow=True)


def _relpath(path: str, workspace: Path) -> str:
    try:
        target = Path(path)
        if not target.is_absolute():
            target = workspace / target
        return str(target.resolve().relative_to(workspace.resolve()))
    except (ValueError, OSError):
        return path


class GateResult:
    """Tiny result holder (not Pydantic — it crosses into the SDK callback)."""

    __slots__ = ("allow", "reason", "interrupt")

    def __init__(self, allow: bool, reason: str = "", interrupt: bool = False):
        self.allow = allow
        self.reason = reason
        self.interrupt = interrupt


def build_can_use_tool(method: Method, workspace: Path) -> Callable:
    """Return an async `can_use_tool` callback for ClaudeAgentOptions.

    The SDK calls this before each tool use; we translate our GateResult into
    the SDK's PermissionResultAllow / PermissionResultDeny.
    """
    from claude_agent_sdk import PermissionResultAllow, PermissionResultDeny

    async def can_use_tool(tool_name: str, tool_input: dict, context: Any = None):
        result = check(method, workspace, tool_name, tool_input)
        if result.allow:
            return PermissionResultAllow()
        return PermissionResultDeny(message=result.reason, interrupt=result.interrupt)

    return can_use_tool
