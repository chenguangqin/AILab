# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""The Pilot — the outer harness's single steering reviewer.

Strategies are pluggable; this kit ships the lightest one: a single steering
reviewer with "autopilot" consensus (auto-GO, no human gate) — the `loop-autopilot`
model. Add more reviewers or a blocking consensus rule in your own strategy.

Each turn the Pilot reads the workspace artifacts (read-only tools), then returns a
typed GO / NO_GO verdict plus a short (<=~400 token) direction for the next turn. It
is a *separate* agent from the coder (the generator/evaluator split): the thing that
writes is not the thing that judges.

The verdict is **schema-enforced** via the Claude Agent SDK's `output_format`
(`{"type":"json_schema","schema": GateReview}`) — the model must return a valid
`{decision, direction}`, which arrives on `ResultMessage.structured_output`. That
removes the old free-text parse whose worst failure was a *silent default to GO*.
A text parse remains only as a fallback, and it **fails closed** (unparseable →
NO_GO), never silently GO.

Implementation note: to keep the kit to ONE SDK dependency, the Pilot runs on the
same Claude Agent SDK as the coder — a fresh read-only `query()` with Read/Grep/
Glob only, no Write/Edit/Bash. It routes through Bedrock via the same env.
"""

from __future__ import annotations

import os
from pathlib import Path

from .config import agent_context_dir, read_prompt
from .models import GateReview, ReviewResult, Strategy
from .sandbox import _max_buffer_size, forward_env, inline_schema_refs, unwrap_structured_output

# The SDK constrains the model to this schema; see GateReview in models.py. GateReview is flat
# today (scalar fields, no $ref), so inline_schema_refs is a no-op — but applying it keeps the
# bare-object guarantee if a field ever becomes a nested model (see sandbox.inline_schema_refs).
_GATE_REVIEW_OUTPUT_FORMAT = {"type": "json_schema",
                              "schema": inline_schema_refs(GateReview.model_json_schema())}

_DECISION_CONTRACT = """
You are a steering reviewer (the "Pilot") for an autonomous coding loop. You do
NOT write code — you read the workspace and steer the coding agent.

Return a JSON object with exactly two fields:
- "decision": "GO" or "NO_GO"
- "direction": one short paragraph (<=400 tokens) telling the coding agent what to
  do next. Name the concrete next artifact or milestone. If NO_GO, name the specific
  blocker to fix before advancing. Never say only "continue".
"""


def _steering_model() -> str | None:
    return os.environ.get("HARNESS_STEERING_MODEL") or os.environ.get("ANTHROPIC_MODEL")


def build_pilot_persona(strategy: Strategy) -> str:
    """Assemble the Pilot's persona: the strategy's reviewer prompt (`steering.md`)
    plus the `STEERING_PLAYBOOK.md` seed from agent-context.

    Wiring the playbook here is what makes it part of the compounding loop on the
    *Pilot* side (LESSONS.md/QUALITY.md compound on the coder side): steering tactics
    that worked accumulate in the seed and are injected into every review. Missing
    files are simply skipped (best-effort)."""
    parts: list[str] = []
    reviewer = strategy.reviewers[0] if strategy.reviewers else None
    if reviewer:
        base = read_prompt(strategy.dir, reviewer.system_prompt_file)
        if base:
            parts.append(base)
    playbook = agent_context_dir() / "STEERING_PLAYBOOK.md"
    if playbook.is_file():
        parts.append("## Steering playbook (accumulated tactics)\n\n" + playbook.read_text())
    return "\n\n".join(parts)


async def steer(
    strategy: Strategy,
    workspace: Path,
    phase: str,
    turn: int,
    agent_output: str,
) -> ReviewResult:
    """Run one steering review. Returns GO/NO_GO + direction."""
    from claude_agent_sdk import (
        AssistantMessage,
        ClaudeAgentOptions,
        ResultMessage,
        TextBlock,
        query,
    )

    persona = build_pilot_persona(strategy)

    prompt = f"""{persona}

{_DECISION_CONTRACT}

## Current state
- Phase: {phase}
- Turn: {turn}
- Workspace: {workspace}

Read the relevant artifacts in the workspace (goal.md, progress.md, loop-docs/*,
and any code) to judge whether the last turn's work is sound and what should
happen next.

## The coding agent's last output (truncated)
{agent_output[:4000]}
"""

    options = ClaudeAgentOptions(
        system_prompt={"type": "preset", "preset": "claude_code", "append": ""},
        setting_sources=["project", "local"],
        permission_mode="bypassPermissions",
        allowed_tools=["Read", "Grep", "Glob"],  # read-only: the Pilot never writes
        cwd=str(workspace),
        model=_steering_model() or None,
        max_turns=8,
        output_format=_GATE_REVIEW_OUTPUT_FORMAT,  # enforce a typed {decision, direction}
        mcp_servers={},
        strict_mcp_config=True,
        max_buffer_size=_max_buffer_size(),  # same ceiling as the coder: a UI review Reads screenshots (base64 ~1.33× file) that blow the SDK's 1 MB default
        env=forward_env(),  # same env as the inner agent — no auth/model drift
    )

    text_parts: list[str] = []
    structured: dict | None = None
    cost_usd = 0.0
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    text_parts.append(block.text)
        elif isinstance(message, ResultMessage):
            structured = getattr(message, "structured_output", None)
            # The Pilot is a separate Bedrock call — capture its cost so the run's
            # total reflects BOTH harnesses, not just the coding agent.
            cost_usd = float(getattr(message, "total_cost_usd", 0.0) or 0.0)
            if message.result:
                text_parts.append(message.result)
            break

    review = _coerce(structured, "\n".join(text_parts))
    review.cost_usd = cost_usd
    return review


def _coerce(structured: dict | None, text: str) -> ReviewResult:
    """Turn the Pilot's reply into a ReviewResult.

    Prefer the SDK's schema-enforced `structured_output`; fall back to a tolerant
    text parse only if it's absent. Either way, **fail closed**: anything we can't
    read as a clear GO becomes NO_GO — never a silent GO (the failure mode that lets
    bad work through a gate)."""
    # 1. Trust the schema-enforced structured output when present. Normalize first: the
    #    SDK may wrap/stringify the output_format payload (see unwrap_structured_output) —
    #    without this the Pilot's real GO/NO_GO is missed and it fails closed to NO_GO on
    #    EVERY turn, stalling the loop (the compound path hit the same wrap live).
    normalized = unwrap_structured_output(structured)
    if isinstance(normalized, dict) and normalized.get("decision") in ("GO", "NO_GO"):
        review = GateReview(**{"decision": normalized["decision"],
                               "direction": normalized.get("direction", "")})
        return ReviewResult(
            decision=review.decision,
            direction=review.direction or text.strip()[:1500],
            gate_held=(review.decision == "NO_GO"),
        )

    # 2. Fallback: parse text, failing CLOSED to NO_GO.
    decision = None
    direction = ""
    for line in text.splitlines():
        s = line.strip()
        up = s.upper()
        if up.startswith("DECISION:"):
            decision = "NO_GO" if ("NO_GO" in up or "NO-GO" in up) else "GO"
        elif up.startswith("DIRECTION:"):
            direction = s.split(":", 1)[1].strip()
    if decision is None:  # no clear verdict → hold the gate, don't wave it through
        decision = "NO_GO"
        if not direction:
            direction = ("Pilot verdict was unreadable — treating as NO_GO. Re-state a clear "
                         "decision and next step. " + text.strip()[:1000]).strip()
    if not direction:
        direction = text.strip()[:1500]
    return ReviewResult(
        decision=decision,
        direction=direction,
        gate_held=(decision == "NO_GO"),
    )
