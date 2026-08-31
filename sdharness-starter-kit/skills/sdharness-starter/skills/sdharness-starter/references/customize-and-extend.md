# Level 300 — Customize & extend (concierge steps)

Goal: help the user make the kit their own — point the loop at a new use case, or author a new
method / strategy / skill — and verify it before they run.

## Path A — point the loop at a new use case (zero code)

Only the *intent bundle* is domain-specific; the harness, method, and skill are reusable.

```bash
cp -r examples/bake-like-a-pro examples/my-product
$EDITOR examples/my-product/vision.md      # goal, vibe, must-haves, and "done ="
# keep/adjust tech-env.md (stack + prohibitions + validation) and images.md (or delete it)
sdharness run ./examples/my-product --method loop
```

Coach the brief per `docs/concepts/loop-engineering.md` → "Setting the loop up for success":
**lean direction, rich resources.**
Say *what* and *why* + provide assets/constraints/definition-of-done; let RESEARCH and PLAN own the
*how*. A good "done =" is a command that exits 0.

**Authoring the intake well is its own skill — walk the user through it with
[`references/author-intake-docs.md`](author-intake-docs.md)**: the six-question interview, a verifiable
"Done =", non-goals, the lean-direction/rich-resources split, the fill-in templates at
`agent-context/templates/`, and the common pitfalls (prescriptive-not-directional, vague "Done",
fabricated data, internal links). This is the highest-leverage thing to get right before a run.

## Path B — author a new method (pure JSON + a prompt)

Methods resolve **project-local first**, so no reinstall:
```bash
cp -r methods/loop harness-methods/mymethod
$EDITOR harness-methods/mymethod/method.json      # phases, phase_advancement.complete_when, gates, completion
sdharness run ./examples/my-product --method mymethod
```
Rules (enforced by `tests/test_readiness.py`): the terminal phase MUST have a `complete_when`;
gates must be **structural** (`file_exists` / `file_min_lines` / `dir_has_files` / `json_field` /
`file_contains` only inside a `not`) — never a positive prose `file_contains`; `default_strategy`
must resolve. Full detail: [`docs/authoring-a-method.md`](../../../../../docs/authoring-a-method.md).

## Path C — author a new strategy (how to review)

```bash
cp -r strategies/loop-autopilot harness-strategies/mystrategy
$EDITOR harness-strategies/mystrategy/strategy.json   # reviewers + consensus rule + steering prompt
```
Rule: an `autopilot`-consensus strategy has exactly **one** reviewer. To make a reviewer's NO_GO
actually *block* a turn (not just steer), use a blocking consensus rule (`any_no_go_blocks` /
`majority`). Detail: [`docs/authoring-a-strategy.md`](../../../../../docs/authoring-a-strategy.md) and the
"Steering vs. gating" section of [`docs/customize.md`](../../../../../docs/customize.md).

## Path D — add a skill (give the coding agent a capability)

Drop a skill at `skills/<name>/skills/<name>/SKILL.md` (nested) or `skills/<name>/SKILL.md` (flat);
name it in a method's `skills: [...]`. The kit resolves it via `harness/config.py:resolve_skill_plugin`
(project-local `./harness-skills/` → kit `skills/` → host `~/.claude/plugins`). The vendored
`skills/frontend-design/` is the template. Detail: [`docs/customize.md`](../../../../../docs/customize.md).

## Path E — tune context management (long runs)

A method's **`context_reset`** field (`method.json`) controls the coding agent's context lifecycle:
`"none"` (DEFAULT) = one persistent session for the whole run (caching-optimal, right for short runs);
`"phase_boundary"` = reset to a **fresh session** at each phase advance, re-orienting from the disk docs
(`goal.md` + `loop-docs/`) — bounds context growth on long/multi-phase runs and emits a `context_reset`
event. Never clear *every* turn (kills prompt caching **and** forces the agent to re-read the workspace
each turn). Either way, the SDK's own auto-compaction (under `"none"`) is surfaced as a read-only
`compaction` event via a `PreCompact` hook (the kit's one hook — observe-only, never blocks). Detail +
the caching/quality/cost tradeoff: the "Context management" section of
[`docs/customize.md`](../../../../../docs/customize.md).

## Bigger extensions (the growth roadmap)

Swap the coding agent (new `Sandbox`), add a multi-reviewer board, add MCP tools, chain methods into
a pipeline, or promote `design.md` to a hard gate — all mapped in
[`docs/customize.md`](../../../../../docs/customize.md).

## When to graduate to Level 400 (GROW)

Level 300 is *customizing within the kit* — a new use case, method, strategy, or skill. When a team is
ready to grow the fork **toward their own production harness** — picking the *next* capability driven
by their use case + RESEARCH findings, using the bundled `reference/expansion-ideas/` RE docs as one
illustrative example — hand off to **`references/grow-with-the-reference.md`** (Level 400). And if the
kit's concepts might be stale for the team's needs, run the RESEARCH rung first
(`references/research-current-practice.md`) so growth starts from current practice.

## Always verify config changes

```bash
pytest -q                      # 13 tests incl. the readiness gate
ruff check harness tests       # style
```
`tests/test_readiness.py` is the guardrail — it fails on the gate/strategy bugs that cause runaway
loops, so a broken method/strategy can't ship.

## The two invariants to preserve in any fork

1. **Phase advancement stays deterministic** — decided by evaluating artifacts in code, never by
   asking the model.
2. **The generator and the evaluator stay separate agents** — the thing that writes is not the thing
   that judges.
