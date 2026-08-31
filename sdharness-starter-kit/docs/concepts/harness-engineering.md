# Harness Engineering

> Part of **SD Harness**. Companion reads: [Mental Model](mental-model.md) · [Loop Engineering](loop-engineering.md) · [The Compounding Cycle](compound-engineering.md) · [How it works](../how-it-works.md).  ·  **Level 100**

## What "harness engineering" means

A coding agent (Claude Code, Kiro, Q, Cursor, Codex…) is powerful but, left unsupervised,
unreliable: it skips steps, invents architecture, and produces code that demos well and breaks in
production. **Harness engineering** is the discipline of wrapping that agent in an *outer control
loop* that supplies the structure, verification, and judgment a human reviewer would otherwise
provide — so the agent can run further, and eventually unattended.

The mental model is **two harnesses**:

- **Inner harness** — the coding agent itself, doing the writing. Configured through the agent's
  own primitives (below).
- **Outer harness** — a separate driver that *prompts, reviews, gates, and steers* the inner one.
  It decides what phase we are in, whether the last turn is acceptable, and whether we may proceed.

**SD Harness** makes this concrete: a steering **Pilot** (outer) drives a coding agent via the
Claude Agent SDK (inner), turn by turn, phase by phase, until a **method** completes. The Pilot
sends *prompts + direction*; the agent returns *output + artifacts*; the loop repeats. See
[How it works](../how-it-works.md) to trace one run through the code.

## The six control primitives

Frontier-lab practice (Anthropic's Claude Agent SDK, the `.claude/` convention) exposes six
levers. Any harness — hand-built `.claude/` files or a programmatic driver like SD Harness — is
some configuration of these:

| Primitive | What it controls | File convention | Programmatic equivalent (SD Harness) |
|-----------|------------------|-----------------|-------------------------------------|
| **Rules** | Hard constraints / conventions | `.claude/rules/*.md` (advisory globs), `CLAUDE.md` | `can_use_tool` **hard-deny** + `method.json` gate rules (`block_path` + `requires`) |
| **Hooks** | Interpose on the loop | `.claude/hooks/*.sh` | SDK `HookMatcher` callbacks (PreToolUse, PostToolUse, UserPromptSubmit, PreCompact) |
| **Skills** | On-demand capability/knowledge | `.claude/skills/**/SKILL.md` | `plugins` kwarg — a method skill + auxiliary skills |
| **Agents** | Sub-agents with scoped tools | `.claude/agents/*.md` | SDK `agents` kwarg — method-scoped subagents, capability derived from `tools` |
| **Commands** | Invocable procedures | `.claude/commands/*.md` | initial skill invocation + per-phase prompts (autonomous — nobody types a slash) |
| **Settings** | Model, permissions, MCP | `.claude/settings.json`, `.mcp.json` | SDK kwargs + `strict_mcp_config=True` (deterministic; no host-MCP leakage) |

The key lesson: **a human hand-editing `.claude/` files and a programmatic driver are doing the
same thing at different layers.** When you want reproducibility and enforcement (not advice), push
each primitive down to the code/SDK layer — a *deny with a reason* beats an *advisory glob*.

## From "advice" to "enforcement": the load-bearing ideas

What separates a real harness from a clever prompt:

1. **Deterministic gates, not vibes.** A phase advances only when its required artifacts exist —
   checked mechanically (`file_exists`, `file_min_lines`), not by asking the model "are we done?".
   SD Harness calls this **phase authority**; the harness, not the agent, owns phase state.
2. **Artifact-based proof.** Every stage emits an auditable artifact (design doc, test report,
   README). "It works" must be *shown*, and gates block out-of-order writes until the prerequisite
   artifact is present.
3. **Multi-agent adversarial review.** Instead of one human reviewer, a panel of domain-expert
   personas (Product, Tech Lead, Security, SRE, QA, SA/PA) reviews each gate with **veto authority**
   and issues GO / NO_GO. Any NO_GO blocks; the domain owner vetoes on their topic.
4. **Generator/evaluator split (the GAN pattern).** The agent that *writes* is not the agent that
   *scores*. A separate evaluator grades output across dimensions and drives a remediation loop.
5. **Kill switches.** Stall detection, repeated-error detection, turn caps, and budget caps stop a
   stuck or runaway agent — the safety net that makes unattended runs tolerable.
6. **Crash recovery.** Every turn is a git checkpoint; you can resume, branch, or replay from any
   point. State survives context compaction via a written handoff.

## How is this different from just running Claude Code / Kiro / Codex?

A fair question: modern coding agents — **Claude Code**, **Kiro**, **Codex** — already run their
own agentic loop. They plan, act, observe, and decide when they're done. So why wrap one in a
harness?

Those built-in loops are the **inner harness**: the *model* owns the control loop, and — this is
the crux — **the model also decides when the work is finished.** That's powerful, but it has one
structural weakness: *the thing doing the work is also the thing judging whether the work is done.*
There's no independent reviewer, no definition of "done" the model can't move, and nothing it can't
eventually talk itself past.

**SD Harness is an outer harness that wraps any of them.** It doesn't replace the agent's loop — it
*supervises* it, adding the independent reviewer, deterministic "done," and un-overridable enforcement
(the load-bearing ideas above) that a self-driving inner loop structurally can't give itself:

| | Agent's own loop (Claude Code / Kiro / Codex) | SD Harness (outer loop) |
|---|---|---|
| **Who owns the loop** | the model, internally | an external harness, turn by turn |
| **Who judges "done"** | the model (self-assessed) | a deterministic artifact gate |
| **Review** | none / self-review | a separate Pilot agent, every turn |
| **Phase structure** | emergent, freeform | explicit RESEARCH → PLAN → BUILD → VERIFY |
| **Verification** | "I think it works" | VERIFY must produce a green integration report |
| **Stopping** | model decides / context runs out | kill switches the model can't override |
| **Audit trail** | a transcript | a git commit per turn + on-disk artifacts |

> **Claude Code, Kiro, and Codex can build. SD Harness makes them prove they built the right thing,
> the right way — with a reviewer and a gate they don't control.**

This is also why the coding agent is a *swappable* seam: those agents are all interchangeable
**inner** harnesses (see [Customize → swap the coding agent](../customize.md)). SD Harness's value is
the layer *above* them — it isn't competing with their loops, it's steering and gating them.

## The Pilot is a swappable seam — and this kit picks the *slim* one

Just as the coding agent is swappable, so is the **Pilot** (the reviewer). It's an implementation of
the `ReviewStrategy` seam (`harness/models.py`), and there are two ways to build it:

| Pilot backend | Reviewer model | Dependencies | This kit |
|---------------|----------------|--------------|----------|
| **Claude Agent SDK `query()`** (this kit) | **Claude-only** (locked to Claude models) | one SDK — the same one the coder uses | ✅ the slim/lean design |
| **Strands Agents SDK** | **model-agnostic** (any Bedrock / other provider — configurable) | adds `strands-agents` | the portable design |

The deciding factor **isn't SDK count — it's model portability.** This kit's single-SDK Pilot is a
deliberate slim design (one dependency, easy to read end-to-end) with the trade-off that the reviewer
is Claude-only; reach for the model-agnostic Strands Pilot when that matters. Either way the verdict
*discipline* is identical (schema-typed, fail-closed GO/NO_GO with kill-switch escalation) — it lives
in the loop, not the SDK, so swapping the backend is just another `ReviewStrategy`. The Strands board
is a [fork recipe](../customize.md#recipe-a-multi-reviewer-board-on-strands), and this trade-off is
what the [maturity curve](../../README.md#the-maturity-curve) turns on.

## Why it maps cleanly onto AWS delivery

The same structure is what lets you turn an AI run into a *deliverable*: alongside the code you get
business rules, a tech-stack rationale, architecture docs, tested code, and deploy scripts — the
artifacts a customer needs to take it forward. This is also exactly what **AI-DLC** produces phase
by phase (see [How it works](../how-it-works.md)); AI-DLC is one
*method* you can run inside a harness.

## Advising a customer: a starter checklist

When helping a team stand up harness engineering, work down the primitives and the enforcement
ideas:

- [ ] **Pick the enforcement boundary.** Where can you *deny* rather than *advise*? (tool
      permissions, path gates, workspace containment).
- [ ] **Define phases + required artifacts** for the work. Each phase gate = "which file proves
      this phase is done?"
- [ ] **Separate generation from evaluation.** Even a lightweight second-pass scorer beats
      self-assessment.
- [ ] **Add a review perspective per risk area** the team actually cares about (Security first).
- [ ] **Install kill switches** (turn/budget caps, stall detection) *before* the first unattended
      run.
- [ ] **Checkpoint every turn** so failures are recoverable, not restarts.

Next: how the outer loop keeps *going* toward a goal across many turns and sessions —
[Loop Engineering](loop-engineering.md).
