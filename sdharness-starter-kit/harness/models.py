# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""Data models — the vocabulary the whole harness speaks.

All models are Pydantic (no dataclasses). The three seams
are the Protocols: a `Sandbox` (coding agent), a `Method` (what phases to follow),
and a `Strategy` (how to review). The harness only ever sees these plus the
plain data models below — so any piece is swappable without touching the loop.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field


# ── Coding-agent boundary ───────────────────────────────────────────────────


class TurnResult(BaseModel):
    """The result of one coding-agent turn. The harness never sees SDK types —
    the Sandbox wraps agent-specific output into this generic shape."""

    output: str = ""
    tool_count: int = 0
    workspace_writes: int = 0
    session_id: str = ""
    error: str = ""
    cost_usd: float = 0.0  # THIS turn's spend (delta of the SDK's cumulative total_cost_usd)
    metrics: dict[str, Any] = Field(default_factory=dict)  # ResultMessage.usage: input/output/cache tokens


class GateDecision(BaseModel):
    """Result of a `can_use_tool` gate check. Agent-agnostic; the Sandbox maps
    it to the SDK's PermissionResultAllow / PermissionResultDeny."""

    allow: bool = True
    reason: str = ""
    interrupt: bool = False


@runtime_checkable
class Sandbox(Protocol):
    """Execution boundary around a coding agent. Implement this to add a new
    agent (a new file in the kit); the loop is unchanged.

    Lifecycle: connect() → execute(prompt) → disconnect().
    """

    async def connect(self) -> None: ...
    async def execute(self, prompt: str) -> TurnResult: ...
    async def disconnect(self) -> None: ...


# ── Method / Strategy config (loaded from JSON) ─────────────────────────────


class Phase(BaseModel):
    """One phase of a methodology."""

    name: str
    color: str = ""
    milestones: list[str] = Field(default_factory=list)


class GateRule(BaseModel):
    """A hard gate: block writes to `block_path` until `requires` is satisfied."""

    block_path: str
    requires: dict[str, Any] = Field(default_factory=dict)
    hint: str = ""


class Method(BaseModel):
    """A methodology, loaded from `method.json`. Pure config — no subclassing.

    `phase_advancement.phases[<PHASE>].complete_when` holds a *structural*
    predicate tree (see phase_authority.evaluate). The harness advances a phase
    only when its predicate is satisfied — deterministic, LLM-free.
    """

    name: str
    display_name: str = ""
    description: str = ""
    default_strategy: str = ""
    phases: list[Phase] = Field(default_factory=list)
    # phase name -> {"complete_when": <predicate>}
    phase_advancement: dict[str, Any] = Field(default_factory=dict)
    system_prompt_file: str | None = None
    context_files: list[str] = Field(default_factory=list)
    agent_context_files: list[str] = Field(default_factory=list)
    # per-phase steering/instruction strings injected into the turn prompt
    phase_prompts: dict[str, str] = Field(default_factory=dict)
    gates: dict[str, Any] = Field(default_factory=dict)
    completion: dict[str, Any] = Field(default_factory=dict)
    kill_switch: dict[str, Any] = Field(default_factory=dict)
    intent_files: list[str] = Field(default_factory=list)
    # Claude Code skills the coding agent may use this run. Names of installed
    # skills/plugins (e.g. "frontend-design"). Empty = none attached (default,
    # fully reproducible). See docs/customize.md → "Add a skill".
    skills: list[str] = Field(default_factory=list)
    # Curated capabilities (tools) this run may use — NEUTRAL registry KEYS, not an
    # SDK-specific server dict. Each key names a vetted entry in
    # `harness/tools.py:CAPABILITY_REGISTRY` (e.g. "aws-docs"); the Sandbox translates
    # keys to its own tool mechanism (the Claude Sandbox → MCP servers), so the schema
    # stays coding-agent-agnostic. Empty = no tools wired (DEFAULT, reproducible,
    # behavior-identical to a kit with no registry). See docs/customize.md → "Add a
    # capability" and docs/design/capability-brokering.md.
    capabilities: list[str] = Field(default_factory=list)
    # Coding-agent context lifecycle across phases:
    #   "none"           — one persistent session for the whole run (DEFAULT; caching-
    #                      optimal, simple; right for short runs).
    #   "phase_boundary" — reset the session (fresh, empty context) when the loop advances
    #                      to a new phase; the disk docs (goal.md + loop-docs/) are the
    #                      handoff. Bounds context growth on long/multi-phase runs at the
    #                      cost of the cross-phase cache prefix. See docs/customize.md →
    #                      "Context management".
    context_reset: Literal["none", "phase_boundary"] = "none"

    # Set at load time so the method can resolve its own prompt files.
    dir: Path | None = None

    def complete_when(self, phase: str) -> dict[str, Any]:
        """The structural predicate that advances `phase` (empty = advance freely)."""
        return (
            self.phase_advancement.get("phases", {})
            .get(phase, {})
            .get("complete_when", {})
        )

    def terminal_requires(self) -> dict[str, Any]:
        """Structural predicate that must hold before the run may complete."""
        return self.completion.get("terminal_requires", {})

    def always_allow(self) -> list[str]:
        """Paths a gate never blocks (the method's own artifacts, README, etc.)."""
        return self.gates.get("enforcement", {}).get("always_allow", [])

    def gate_rules(self) -> list[GateRule]:
        rules = self.gates.get("enforcement", {}).get("rules", [])
        return [GateRule(**r) for r in rules]


class Reviewer(BaseModel):
    role: str
    label: str = ""
    system_prompt_file: str = ""
    always_review: bool = True


class Strategy(BaseModel):
    """A review strategy, loaded from `strategy.json`. This kit ships one:
    a single steering "Pilot" with autopilot consensus (auto-GO, no human gate)."""

    name: str
    display_name: str = ""
    description: str = ""
    reviewers: list[Reviewer] = Field(default_factory=list)
    consensus: dict[str, Any] = Field(default_factory=dict)
    steering: dict[str, Any] = Field(default_factory=dict)

    dir: Path | None = None

    @property
    def consensus_rule(self) -> str:
        return self.consensus.get("rule", "autopilot")


# ── Run-time state ──────────────────────────────────────────────────────────


class GateReview(BaseModel):
    """The Pilot's typed verdict — the schema the coding agent's steering model is
    constrained to via the Claude Agent SDK's `output_format`. Enforcing the shape
    at the SDK layer removes the brittle free-text parse whose worst failure was a
    *silent default to GO*. Binary on purpose: the loop has no distinct behavior for
    a third state, so `GO_WITH_CONDITIONS` belongs to the multi-reviewer board
    extension (see docs/customize.md), not here."""

    decision: Literal["GO", "NO_GO"]
    direction: str  # <=~400-token steer for the next turn


class ReviewResult(BaseModel):
    """The Pilot's decision for one turn (loop-facing)."""

    decision: str = "GO"  # GO | NO_GO
    direction: str = ""  # <=400-token steer for the next turn
    gate_held: bool = False
    cost_usd: float = 0.0  # the Pilot's Bedrock spend this turn (a separate model call)


class RunState(BaseModel):
    """Everything the loop needs to track across turns."""

    workspace: Path
    method_name: str
    strategy_name: str
    phase: str = ""
    turn: int = 0
    complete: bool = False
    complete_reason: str = ""
    error: str | None = None  # set ONLY on a raised crash (SDK/transport/buffer); surfaced on the terminal `complete` event so a consumer can tell "died" from "finished". Distinct from `last_error` (a kill-switch counter for model-reported errors).
    total_cost_usd: float = 0.0  # accumulated Bedrock spend across turns
    # kill-switch counters
    consecutive_no_write_turns: int = 0
    consecutive_no_progress_turns: int = 0
    last_error: str = ""
    consecutive_error_repeats: int = 0

    model_config = {"arbitrary_types_allowed": True}
