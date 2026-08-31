# Authoring a strategy

> **Level 300**

A **strategy** is *how to review* — who steers the coding agent and how consensus
is reached. Like methods, it's pure JSON + prompt files, resolved project-local
(`./harness-strategies/<name>/`) before built-in (`<kit>/strategies/<name>/`).

This kit ships one strategy — `loop-autopilot` — because "lightweight" means one
clear example. (A multi-reviewer `advisory-board` is the natural next one to author;
its recipe is in [customize.md](customize.md), referenced again below.)

## Shape

```jsonc
{
  "name": "loop-autopilot",
  "display_name": "SD Loop Autopilot",
  "description": "...",
  "reviewers": [
    {
      "role": "steering",
      "label": "SD Loop Pilot",
      "system_prompt_file": "steering.md",   // the Pilot's persona/rubric
      "always_review": true
    }
  ],
  "consensus": { "rule": "autopilot" },       // autopilot = auto-GO, no human gate
  "steering": { "max_prompt_tokens": 400, "scope_document": "goal.md" }
}
```

The reviewer's `system_prompt_file` (e.g. `steering.md`) is the prompt the Pilot
runs with — this is where you encode *what to hold on* (missing evidence, an
unrecorded constraint) versus *what to wave through*.

## The one hard rule

`tests/test_readiness.py` enforces: **an `autopilot`-consensus strategy must have
exactly one reviewer.** Autopilot means a single steering voice auto-GOes each
turn; multiple reviewers imply a blocking consensus rule (majority / any-NO_GO),
which is a different model. Keep them distinct.

## How the Pilot runs

`harness/steering.py:steer` loads the reviewer's prompt, gives the Pilot read-only
tools (`Read`, `Grep`, `Glob` — it never writes), runs one `query()`, and parses a
`DECISION: GO|NO_GO` / `DIRECTION:` reply. (Extending this to a multi-reviewer board
is the `advisory-board` recipe in [customize.md](customize.md).)

## Verify

```bash
sdharness strategies
uv run python -m pytest tests/test_readiness.py -q
```
