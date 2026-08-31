# How it works

> **Level 200**

The whole harness is ~2,000 lines of Python you can read in one sitting. This
traces a single run through the modules — the load-bearing seams of a self-driving
harness, kept small so you can fork it without reinventing the wheel.

![SD Harness — the two-harness loop in code. An outer harness (the Pilot: a read-only Claude Agent SDK query() that reviews at gates, returns GO/NO_GO + a direction, advances phases, and owns deterministic control with no LLM) steers an inner harness (the coding agent: a persistent Claude Code session that writes code and artifacts, one milestone per turn, contained by a can_use_tool gate behind the Sandbox seam). Below, the SD Loop method's four phases — RESEARCH → research.md, PLAN → architecture.md + goal.md, BUILD → progress.md, VERIFY → integration-report.json → verified result — each advancing only when its artifact gate passes.](assets/architecture.png)

## The two-harness model

> The *concept* (inner vs. outer harness, why the generator/evaluator split matters) lives in
> [Harness Engineering](concepts/harness-engineering.md). This section shows how it's wired in code.

```
   YOU ──intent (vision.md)──▶  OUTER HARNESS (the loop + the Pilot)
                                      │  prompt + steering direction
                                      ▼
                                INNER HARNESS (coding agent: Claude Code via SDK)
                                      │  output + file writes
                                      ▼
                                deterministic gates + phase authority
                                      │
                                      └──▶ advance phase / complete / steer again
```

- **Outer harness** — `harness/loop.py` + `harness/steering.py`. Decides what to do
  each turn, checks gates, advances phases, and steers. It never writes code.
- **Inner harness** — `harness/sandbox.py`. The coding agent that writes the code.

**Both harnesses run on the Claude Agent SDK** — the difference is role, not framework. In code that's
a lifecycle split: the inner agent is a *persistent* `ClaudeSDKClient` session with full tools
(`sandbox.py`); the Pilot is a *fresh, read-only* `query()` per turn with only `Read`/`Grep`/`Glob`
(`steering.py`).

## One run, step by step

A single BUILD turn, as the CLI renders it — the kickoff banner (method, strategy, both models,
intent, workspace), then the coding agent's tool stream and the Pilot's `GO` + one-line direction,
closing with a status line (turn · phase · GO · cost · milestones · elapsed · context %):

![A BUILD turn in the sdharness CLI — Turn 3 · BUILD: the coding agent scaffolds the project and runs npm run build; the Pilot returns GO steering to the next milestone. The status line reads Turn 3 · BUILD · GO · ~$3.05 · 1/10 milestones · ctx 7% — an open turn count, not a fraction (the turn budget is a ceiling shown once in the banner).](assets/cli-turn-build.png)

Entry: `harness/__main__.py:cmd_run` loads the method + strategy and calls
`harness/loop.py:run`.

1. **Stage the workspace** — `loop.py:stage_workspace` copies the intent files
   (`vision.md`, `tech-env.md`) and the `agent-context/` seed (`CLAUDE.md`,
   `QUALITY.md`, `LESSONS.md`) into a fresh run dir, then `git init`s it.
2. **Connect the coding agent** — `sandbox.py:ClaudeCodeSandbox.connect` builds
   `ClaudeAgentOptions` (`sandbox.py:_options`) and opens a persistent session
   (one session for the whole run by default; a method can set
   `context_reset: "phase_boundary"` to start a fresh session at each phase
   advance — see [customize.md → Context management](customize.md)).
   Key options: the `claude_code` system-prompt preset + the method's
   `system-prompt.md` appended; `setting_sources=["project","local"]` (never
   `"user"` — reproducible, no personal `~/.claude` leakage);
   `permission_mode="bypassPermissions"` paired with our `can_use_tool` gate.
3. **The turn loop** (`loop.py:run`), repeated until complete or a kill switch trips:
   1. **Build the prompt** — `loop.py:_turn_prompt`: the current phase's steering
      string (`method.phase_prompts[phase]`) + the Pilot's last direction.
   2. **Run one turn** — `sandbox.py:execute`: `client.query(prompt)`, drain the
      message stream, count tool uses + writes, return a generic `TurnResult`. The
      harness never sees an SDK type after this.
   3. **Checkpoint** — `loop.py:checkpoint`: `git commit` the turn (resume/audit).
   4. **Advance the phase** — `phase_authority.py:next_phase`: evaluate the current
      phase's `complete_when` predicate against the workspace. If satisfied, move to
      the next phase. **The harness owns this — not the agent.**
   5. **Complete?** — `phase_authority.py:is_complete`: the terminal predicate
      (`completion.terminal_requires`) — for SD Loop, a green
      `loop-docs/integration-report.json`.
   6. **Steer** — `steering.py:steer`: the Pilot (a separate, read-only agent) reads
      the artifacts and returns `GO`/`NO_GO` + a ≤400-token direction for next turn.
   7. **Kill-switch check** — `killswitch.py:update_and_check`: stop on N turns with
      no writes, no progress, or a repeated error.

## Where each idea lives

| Idea (see `docs/concepts/`) | Code |
|-----------------------------|------|
| Deterministic gates, not vibes | `phase_authority.py:evaluate` (structural predicate tree) |
| Enforcement at the capability boundary | `gates.py:check` + `build_can_use_tool` |
| Generator / evaluator split | coder in `sandbox.py`; Pilot in `steering.py` |
| Kill switches | `killswitch.py` |
| Crash recovery / checkpoints | `loop.py:checkpoint` (git per turn) |
| Config-over-code (methods/strategies) | `config.py` + `models.py` + `methods/` `strategies/` |
| Compounding knowledge | `agent-context/` staged by `loop.py:stage_workspace` |

## The predicate grammar (the gate language)

`phase_authority.py:evaluate` understands a small structural predicate tree —
combinators `all` / `any` / `not`, and leaves `file_exists`, `file_min_lines`,
`file_contains`, `no_unchecked` (zero open `- [ ]`), `checkbox_min_checked`,
`dir_has_files`, `json_field`+`expected_value`. Gates are *structural* on purpose:
a gate that asserts an exact prose heading can never be satisfied reliably (the
model won't reproduce it) and the loop spins. Checkbox predicates match only real
line-start task-list items, never prose that mentions `- [ ]` (the bug that once
froze a phase). The `tests/test_readiness.py` gate rejects that bug class.

## What's deliberately missing

To stay lightweight, this kit leaves out: a multi-agent advisory board, a browser
dashboard, a multi-method pipeline, an agentic conductor, other coding agents (via
ACP), telemetry, and clean-handoff/replay tooling. It ships a **curated capability
registry** (`harness/tools.py`) so a method can declare an MCP tool by name
(`capabilities: [...]`, default none), but mission-driven / Pilot-brokered *dynamic*
provisioning stays a design ([capability-brokering.md](design/capability-brokering.md)).
Each is a natural extension — see [customize.md](customize.md).
