# Authoring a method

> **Level 300**

A **method** is *what phases to follow* — pure JSON + a system prompt, no framework
code. This is the primary fork seam: drop a directory and run it.

## Where methods resolve

`harness/config.py:load_method` searches, first hit wins:

1. an explicit path
2. `./harness-methods/<name>/`   ← **project-local; add here, no reinstall**
3. `<kit>/methods/<name>/`       ← built-in (ships with the kit)

So to add a method to a customer repo without touching the framework:
`mkdir -p harness-methods/mymethod && …` then `sdharness run <dir> --method mymethod`.

## Minimal shape

A method dir has `method.json` (required) and usually `system-prompt.md`. Copy the
built-in `methods/loop/` and edit. The load-bearing fields:

```jsonc
{
  "name": "mymethod",
  "display_name": "My Method",
  "description": "...",
  "default_strategy": "loop-autopilot",     // MUST resolve to a real strategy
  "phases": [                                // ordered
    { "name": "BUILD", "milestones": ["done"] }
  ],
  "phase_advancement": {
    "mode": "artifact",
    "phases": {
      "BUILD": { "complete_when": { "file_exists": "result.md", "file_min_lines": 5 } }
    }
  },
  "system_prompt_file": "system-prompt.md",
  "phase_prompts": { "BUILD": "You are in BUILD. Produce result.md ..." },
  "gates": { "enforcement": { "rules": [], "always_allow": ["result.md", "README.md"] } },
  "completion": { "terminal_requires": { "file_exists": "result.md", "file_min_lines": 5 } },
  "kill_switch": { "no_files_threshold": 4, "state_unchanged_threshold": 5, "error_repeat_threshold": 3 },
  "intent_files": ["vision.md"],
  "agent_context_files": ["CLAUDE.md", "QUALITY.md", "LESSONS.md"]
}
```

(Other optional fields the shipped `methods/loop/method.json` carries: `skills`, `context_reset` —
see [customize.md](customize.md).)

## The rules that keep it from spinning

These are enforced by `tests/test_readiness.py` — run it after any change:

1. **The terminal phase must declare a `complete_when`**, and `completion.terminal_requires`
   must be non-empty. Otherwise the run can never structurally complete.
2. **Gates must be structural.** Use `file_exists` / `file_min_lines` / `dir_has_files` /
   `json_field` / `no_unchecked`. **Never** a *positive*
   `file_contains` on a prose heading — the model rarely reproduces an exact string,
   so the gate never passes and the loop spins forever. (This is the single most
   common method-authoring bug; the readiness test rejects it.)
3. **For "all task-list items done", use `no_unchecked`** — not the older
   `{ "not": { "file_contains": "- [ ]" } }` idiom. A full-file substring match
   collided with prose that merely *mentioned* `- [ ]` (a doc saying "no `- [ ]`
   items remain" matched itself), silently freezing the phase. `no_unchecked` matches
   only real line-start checkboxes.
4. **`default_strategy` must resolve** to a real strategy directory.

## The predicate grammar

The full gate language (combinators + every leaf) lives in
[how-it-works.md](how-it-works.md#the-predicate-grammar-the-gate-language) — the single source of
truth; `harness/phase_authority.py:evaluate` is the implementation.

## Verify your method

```bash
sdharness methods                                   # is it listed?
uv run python -m pytest tests/test_readiness.py -q  # does it pass the gate?
sdharness run ./examples/bake-like-a-pro --method mymethod --max-turns 8
```
