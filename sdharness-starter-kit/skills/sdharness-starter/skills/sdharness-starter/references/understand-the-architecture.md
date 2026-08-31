# Level 200 — Understand the architecture (concierge steps)

Goal: give the user the mental model, grounded in the actual ~2,000-line core. Trace one run; name
the seams; explain why the gates are the thing that makes it trustworthy. Then hand off to the docs.

## The one-sentence model

An **outer harness (the Pilot)** steers an **inner harness (the coding agent)** through gated
phases, turn by turn — and *the harness, not the model, decides when a phase is done*.

## Trace one run through the code (open these as you explain)

`harness/__main__.py:cmd_run` → `harness/loop.py:run`, the turn cycle:
1. **Stage** the workspace — intent files + the `agent-context/` seed (`loop.py:stage_workspace`).
2. **Connect** the coding agent — build `ClaudeAgentOptions` (`sandbox.py:_options`): claude_code
   preset + method system-prompt; `setting_sources=["project","local"]` (no `"user"` → reproducible);
   `permission_mode="bypassPermissions"` + our `can_use_tool` gate. One persistent session by default;
   a method may set `context_reset: "phase_boundary"` to start a fresh session per phase (disk-doc handoff).
   A read-only `PreCompact` hook emits a `compaction` event so SDK auto-compaction is visible in `events.jsonl`.
3. **Turn:** build prompt (phase steering + last Pilot direction) → `sandbox.execute()` → `TurnResult`.
4. **Checkpoint:** `git commit` the turn (`loop.py:checkpoint`).
5. **Advance:** `phase_authority.next_phase()` — evaluate the phase's `complete_when` predicate; move
   on only if it holds. **This is deterministic; no LLM.**
6. **Complete?** `phase_authority.is_complete()` (the terminal predicate).
7. **Steer:** `steering.py:steer` — the Pilot returns GO/NO_GO + direction for the next turn.
8. **Kill-switch check:** `killswitch.py` — stop on no-writes / no-progress / repeated-error.

## The six seams (what makes it forkable)

| Seam | Where | Why it matters |
|------|-------|----------------|
| Deterministic gates | `phase_authority.py:evaluate` | phases advance on artifacts, not vibes |
| Capability-boundary enforcement | `gates.py` (`can_use_tool`) | containment + rules, even in autonomous mode |
| Generator / evaluator split | `sandbox.py` (coder) vs `steering.py` (Pilot) | the writer isn't the judge |
| Kill switches | `killswitch.py` | unattended runs stay safe |
| Config-over-code | `config.py` + `methods/` + `strategies/` | add a method/strategy with zero framework code |
| Compounding knowledge | `agent-context/` staged each run | runs get smarter over time |

## Why the gates are the point

A phase gate asks a *structural* question ("does `loop-docs/architecture.md` exist and have ≥20
lines?"), never a *prose* one. A gate that asked for an exact heading could never reliably pass and
the loop would spin — `tests/test_readiness.py` rejects that bug class. Determinism here is what
lets a human step out of the turn loop.

## Hand off to the docs (in order)

- [`docs/how-it-works.md`](../../../../../docs/how-it-works.md) — the full run trace (Level 200)
- [`docs/concepts/harness-engineering.md`](../../../../../docs/concepts/harness-engineering.md) (100) ·
  [`loop-engineering.md`](../../../../../docs/concepts/loop-engineering.md) (100) — the SD Loop is where these two meet;
  loop-engineering also covers *setting up for success* (input) and *increasing autonomy* (outcome)
- [`docs/concepts/compound-engineering.md`](../../../../../docs/concepts/compound-engineering.md) (200) — memory across runs

Next: the user gets it — offer **Level 300** (`references/customize-and-extend.md`) to build their own.
