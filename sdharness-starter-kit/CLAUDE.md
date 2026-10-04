# sdharness starter kit — notes for Claude

This is a fork of the SD Harness starter kit (`README.md`). An outer loop (`harness/loop.py`) drives a
coding agent through a method's phases; methods are pure config (`methods/<name>/method.json` +
`system-prompt.md`), strategies configure the Pilot (`strategies/`).

## What this fork adds (see `docs/brownfield-iteration.md` for the full workflow)

- `methods/loop-plan/` — RESEARCH → PLAN only, stops for human review. Its artifacts land in
  `loop-docs/` so the `loop` method continues from them.
- `sdharness run … --skip-completed-phases` — start at the first phase whose gate isn't already met
  (`harness/loop.py`, opt-in; default behavior unchanged).
- Human handoff — `Method.handoff_signal` (default `HANDOFF_TO_HUMAN`); `loop.requests_handoff()`
  stops the run only when the signal is the **last non-empty line** of the agent output or the Pilot
  direction. Documented in the `loop` BUILD/VERIFY prompts and `strategies/loop-autopilot/steering.md`.

## Typical use

```bash
uv run sdharness run <intake> --method loop-plan --workspace <copy>      # plan, then human review
uv run sdharness run <copy> --method loop --in-place --skip-completed-phases   # build + verify
```

Always run on a **working copy** with a git identity configured (`git -C <copy> config user.email …`);
the harness commits every turn and `resume` hard-resets the workspace.

## Working on the kit itself

- Tests: `uv run --extra dev pytest -q`; lint: `uv run --extra dev ruff check harness tests`.
- `methods/*/method.json` and `system-prompt.md` are coupled only by convention (paths, phase names,
  completion markers) — nothing validates it; change both together.
- When editing `method.json` programmatically, keep its existing formatting (don't round-trip through
  `json.dumps`, it rewrites the whole file).
- Keep new loop behavior opt-in so existing runs are byte-for-byte unchanged, and add a test in
  `tests/test_loop.py` using the stubbed sandbox/Pilot there.
