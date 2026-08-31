# Customize — the fork playbook

> **Level 300**

This kit is a **baseline to grow**, not a finished product. It ships the load-bearing
core and leaves the production surface as extension points on purpose. Here's how to
grow each seam toward a higher-autonomy harness of your own.

> **Want a coding agent to walk you through this?** Install the
> [`sdharness-starter`](../skills/sdharness-starter/) concierge skill and ask Claude Code to help
> you customize the kit — it guides authoring a method, strategy, or skill against the rules below.

## Add your own method / strategy

The zero-code seam. Drop a directory:

```bash
cp -r methods/loop harness-methods/mymethod    # project-local; no reinstall
$EDITOR harness-methods/mymethod/method.json
sdharness run ./my-intent --method mymethod
```

See [authoring-a-method.md](authoring-a-method.md) / [authoring-a-strategy.md](authoring-a-strategy.md).

## Add a skill (give the coding agent a capability)

The Claude Agent SDK supports **skills** natively (`ClaudeAgentOptions.skills` / `plugins`).
Because the kit runs the agent with `setting_sources=["project","local"]` (no `"user"`, for
reproducibility), host-installed skills are **not** auto-discovered — the kit attaches them
explicitly. A method declares what it wants:

```jsonc
// methods/loop/method.json
"skills": ["frontend-design"]
```

`config.py:resolve_skill_plugin(name)` finds the skill and `sandbox.py` attaches it via
`plugins=[{type:local, path}]` + `skills=[name]`. Resolution order (first hit wins; missing →
skipped, so a fork without it still runs):

1. `./harness-skills/<name>/` — project-local
2. `<kit>/skills/<name>/` — **bundled with the kit** (the standalone, portable option)
3. `~/.claude/plugins/**/skills/<name>/SKILL.md` — a host-installed Claude Code plugin (fallback)

The kit **vendors** `frontend-design` at [`skills/frontend-design/`](../skills/frontend-design/)
(Apache-2.0) so it works standalone on any clone. To add your own, drop a skill dir in
`skills/<name>/skills/<name>/SKILL.md` and name it in a method's `skills`.

## The design-system anchor: `frontend-design` → `design.md` → BUILD

For UI builds the kit composes two things that would otherwise fight. The **`frontend-design` skill**
*generates* a bold, distinctive aesthetic (its whole job is to avoid generic "AI slop" — every run
different). A **`loop-docs/design.md`** *pins* that aesthetic so a section-by-section build stays
consistent. The pipeline: in **PLAN**, the skill settles the look and writes it as a **structured
design-token doc** (`design.md`); in **BUILD**, every milestone conforms to that file. Skill =
creativity (across runs); `design.md` = consistency (within a run) — so the last section is as
polished as the first, and the design still varies run to run.

Write `design.md` as **tokens + rationale**, not a vague paragraph: named groups (palette, typography +
type scale, spacing, radius, elevation, motion, component patterns) plus a short **Do's & Don'ts**.
See the skeleton at [`agent-context/templates/design.md`](../agent-context/templates/design.md), which
also carries an **art-direction menu** (editorial, brutalist, glassmorphism, playful, luxury…) — pick a
*direction* for the intake; the skill fills in the specific tokens. This structured shape is inspired
by the **[DESIGN.md format](https://github.com/google-labs-code/design.md)** (Apache-2.0: YAML tokens +
prose); the kit borrows the idea kit-native, without vendoring its linter.

## Promote `design.md` (or any spec) to a hard gate

The `bake-like-a-pro` brief asks the loop to produce `loop-docs/design.md` and build every
section to it — a **soft convention** that keeps a section-by-section build visually consistent.
In a frontend-only fork you can make it a **hard structural gate** so no component code is written
before the design system exists. Add to your method's PLAN `complete_when` and the `src/**` gate:

```jsonc
"phase_advancement": { "phases": { "PLAN": { "complete_when": { "all": [
  { "file_exists": "loop-docs/design.md", "file_min_lines": 15 }
]}}}},
"gates": { "enforcement": { "rules": [
  { "block_path": "src/**",
    "requires": { "file_exists": "loop-docs/design.md" },
    "hint": "Write loop-docs/design.md (design tokens) before any component code." }
]}}
```

> A design-first method makes this the norm: gate all component code on a `design-system.md`
> (or `design.md`) so the design system always exists before the UI is built.

## Swap or add a coding agent

`harness/sandbox.py` implements the `Sandbox` protocol (`connect` / `execute` /
`disconnect`) for Claude Code. To add another agent, write a new class with the
same three methods returning a `TurnResult`, and let the CLI choose it. The loop
never changes — that's the point of the protocol.

### Recipe: add Kiro (via ACP)

**Why ACP, not "a Kiro SDK":** Claude Code is embeddable as a *library* (the Claude Agent SDK gives
you an in-process client with a `can_use_tool` permission callback). **Kiro has no such SDK** — it's
a CLI. Its native programmatic surface is the **Agent Communication Protocol** (`kiro-cli acp`),
which is the only interface offering *streaming* output **and** a per-tool `request_permission`
callback (i.e. live gating). So ACP *is* the native Kiro integration, not a workaround. (Gemini and
Codex expose ACP too, so this recipe generalizes.)

What you'd build, against the same `Sandbox` seam:

1. **Shared ACP plumbing (`_acp_common.py`, ~150 LOC), write once.** Spawn the CLI as an ACP process
   (`agent-client-protocol` PyPI package), do the handshake (`initialize` → `new_session` →
   `set_session_model`), and translate streaming `session_update`s into a `TurnResult`.
2. **The Kiro sandbox (`kiro_cli.py`, ~300–400 LOC).** Implement the ACP client callbacks and the
   `connect/execute/disconnect` lifecycle; scan workspace changes into the `TurnResult`.
3. **Gate mapping — the key asymmetry.** Claude's `can_use_tool` can *allow, deny with a reason, or
   interrupt/rewrite* a call. **ACP can only allow or reject.** So the gate becomes **reject +
   prompt-injection**: on a blocked tool call, return a `DeniedOutcome`, stash the reason, and
   prepend `"[GATE] Your previous action was blocked: {reason}"` to the *next* prompt. Same
   `GateDecision` inputs (`gates.py`), different enforcement surface.
4. **Wire it up (~10 LOC):** a `create_sandbox(name)` factory branch + a `--sandbox kiro_cli` flag;
   add `agent-client-protocol` to deps; `kiro-cli` must be on PATH (`kiro-cli acp --trust-all-tools`).

**Cost:** ~450–550 LOC for the first ACP agent (the ~150-line shared layer is then reused by the
next one). A *lean* alternative — wrapping `kiro-cli chat --no-interactive --output-format json`
(~80–120 LOC, no ACP dep) — works as fire-and-read, **but loses live mid-turn gating** (gates become
post-turn checks only). Choose ACP if you want the same gate guarantees as the Claude path.

## Add a multi-reviewer board

Today the Pilot is one steering reviewer (`steering.py`). To add domain experts
(Security, SRE, QA…), run several reviewers and combine their verdicts per the
strategy's `consensus.rule` (`any_no_go_blocks`, `majority`, domain veto).

> A full advisory board runs several domain personas (Product, Tech Lead, Security,
> SRE, QA…) with veto authority — a natural next strategy to author.

### Steering vs. gating — is the Pilot load-bearing?

A subtle but important point when you configure reviewers: **steering and hard-gating are
different jobs.** The shipped `loop-autopilot` strategy steers (and escalates via the kill switch),
but does not *hard-block* a turn — that's a blocking-consensus strategy's job.

- **Gating** — *can the run advance?* In this kit that decision is **deterministic**:
  `phase_authority.py` evaluates the phase's `complete_when` artifacts, and `killswitch.py`
  stops a stuck run. Neither consults the Pilot.
- **Steering** — *what should the next turn do?* That's the Pilot: it reads the workspace
  and returns a `GO`/`NO_GO` **plus a direction** naming the next milestone and enforcing
  continuity (read `progress.md`, log an outcome, evidence before a checkbox).

With `consensus.rule: "autopilot"` (the shipped pairing), a `NO_GO` doesn't *hard-block* a turn,
but it is **not** ignored — it does two things (`loop.py`): **(1) feedback** — the Pilot's
`direction` is injected into the next turn's prompt so the coding agent course-corrects; and
**(2) escalation** — a `NO_GO` counts as *no progress*, so a streak of un-corrected `NO_GO`s climbs
the kill-switch counter and stops the run (a `GO` resets it). So the Pilot is load-bearing for
*direction, continuity, and eventual termination* — but a single `NO_GO` steers rather than halts.

**To make a reviewer's `NO_GO` actually stop a turn, change the consensus rule** to a blocking
one (`any_no_go_blocks`, `majority`, or domain veto) — i.e. move from autopilot to a board.
That is the single most important knob when you want the *review* (not just the artifacts) to
be able to hold the gate. Keep autopilot for unattended throughput; switch to blocking
consensus when a wrong decision is expensive enough that a human-like veto should stop the run.

> With a board strategy (`any_no_go_blocks` + domain veto), a Security reviewer's `NO_GO`
> genuinely blocks the turn — the review, not just the artifacts, holds the gate.

### Recipe: a multi-reviewer board on Strands

When you outgrow a single Pilot, the **Strands Agents SDK** is a natural fit for the board — it
gives you prebuilt parallel agents, per-reviewer tools/MCP, and structured output. (Strands also
keeps the reviewer **model-agnostic** — the trade-off vs. the kit's slim Claude-only Pilot is spelled
out in [Harness Engineering](concepts/harness-engineering.md#the-pilot-is-a-swappable-seam--and-this-kit-picks-the-slim-one).)
Honest sizing:

- **Minimal (~+250–350 LOC + the `strands-agents` dep):** one `BedrockModel` reviewer with a typed
  `GateReview` output. **But note:** the kit's Pilot *already* returns a typed verdict natively via
  `output_format` (see `steering.py`) — so typed verdicts are **not** a reason to adopt Strands.
- **Full board (~+1,000–1,300 LOC + `strands-agents`, `strands-agents-tools`, `mcp`):** several
  domain personas reviewed in parallel (`asyncio.gather`), content-based routing, per-reviewer MCP
  tools, and a **domain-veto / majority consensus** layer. *This* is what Strands buys you — the
  parallel board and consensus machinery — and it roughly doubles the kit.

So: reach for Strands only for a real multi-reviewer board with consensus (the production surface
the kit deliberately omits). This is also where **`GO_WITH_CONDITIONS`** earns its place — a third
verdict only means something once a consensus layer can carry conditions forward and verify them;
in the shipped single-Pilot loop it would be schema decoration with no behavior behind it, so the
kit keeps the verdict binary (`GO`/`NO_GO`).

## Add a capability (a curated MCP tool)

The kit ships **no MCP server by default** — reproducible, offline-friendly, domain-neutral. When a
run genuinely needs one, declare it from the **curated capability registry** rather than editing
`sandbox.py` by hand:

```jsonc
// method.json — a NEUTRAL registry key, not an SDK server dict
{ "name": "loop", "capabilities": ["aws-docs"] }
```

That's the whole change. `harness/tools.py:CAPABILITY_REGISTRY` maps each key → a vetted spec, and
the Sandbox (`ClaudeCodeSandbox._resolve_capabilities`) expands it into the SDK's `mcp_servers` at
connect. The key is **coding-agent-neutral** — a non-Claude Sandbox maps the same key to its own tool
mechanism, or ignores it — so `Method.capabilities` never leaks SDK shape. Default `[]` → `mcp_servers={}`,
byte-for-byte the old behavior; an unknown key is skipped with a warning, never fatal.
`strict_mcp_config=True` stays on, so only registry-vetted, method-declared servers wire — never host
or user config.

> **This is the kit's distilled form of the upstream L1 registry + L2 resolver** (`sdharness`'s
> `mcp.registry` referenced by name + `resolve_capabilities`/`attach_to`). The kit ships the *lite*
> rung — registry-by-name, wired at connect. Selecting the set *per-mission* at scaffolding time (the
> Pilot brokering from the registry after RESEARCH) is designed in
> [docs/design/capability-brokering.md](design/capability-brokering.md) — the "L3" growth rung.

**Seeded entry — `aws-docs` (AWS Documentation MCP).** Read-only, credential-free, AWS-maintained. The
right tool for a run that RESEARCHes a fast-moving AWS service (e.g. Lambda MicroVMs) — it retrieves the
*current* docs instead of the run transcribing a runbook that drifts. It's an *upgrade* to the agent's
built-in WebFetch (the doc URLs pinned in an intake already work without it), not a requirement.

> **Don't reach for the full write-capable `agent-toolkit-for-aws` in the workshop / a least-privilege
> run.** It's read-**write** across 300+ AWS services via a hosted proxy: under
> `permission_mode="bypassPermissions"` a write-capable tool has no per-call human gate (an
> unreviewed-write hazard), and the workshop's least-privilege role AccessDenies most of its surface
> anyway. Prefer the read-only `aws-docs` entry for AWS *context*; keep write-capable toolkits out of the
> default. Vet any new entry against the same bar before adding it to the registry.

### Adding a new registry entry

To vet a new capability, add it to `harness/tools.py:CAPABILITY_REGISTRY` (a neutral key → `description`
+ the Claude `mcp` realization + its `allowed_tools`), keep it read-only-by-default, and document it
here. The Playwright recipe below is a worked example of a heavier entry a frontend fork might vet.

> A clean pattern for a fork that graduates: let a **strategy** wire tools per-reviewer with an
> `attach_to: ["steering","coding_agent"]` list (upstream's L2 shape), so it declares exactly which side
> gets which tool. The lite kit keeps a single `capabilities` list on the method.

### Recipe: Playwright MCP for visual self-correction (frontend forks)

The kit ships **no** MCP server on purpose — `mcp_servers={}` keeps the baseline lean,
reproducible, and domain-neutral. But for a **frontend** fork this is the single highest-leverage
add, because it closes the gap between *"passes VERIFY"* and *"looks designed."*

Note the distinction first: the `bake-like-a-pro` run already used Playwright — as a **dev
dependency + `playwright test` script** the coding agent writes and runs via Bash (that's what
proves the enroll seam with real hydration). That needs no MCP. **Playwright *MCP*** is different:
it gives an agent **live, interactive browser tools** (`navigate`, `click`, `snapshot`,
`screenshot`, read the a11y tree) *during* a turn — so the agent can *see what it built and
self-correct the aesthetics*, not just assert facts about the DOM.

Vet it as a registry entry (a commented `playwright` stub already sits in `harness/tools.py`), then
declare `capabilities: ["playwright"]` on your frontend method — no `sandbox.py` edit:

```python
# harness/tools.py — in CAPABILITY_REGISTRY
"playwright": {
    "description": "Playwright MCP — drive a headless browser for live visual self-correction.",
    "mcp": {"server_name": "playwright",
            "spec": {"type": "stdio", "command": "npx", "args": ["-y", "@playwright/mcp@latest"]}},
    "allowed_tools": ["mcp__playwright__browser_navigate",
                      "mcp__playwright__browser_snapshot", "mcp__playwright__browser_take_screenshot"],
},
```

**The powerful move — give the *Pilot* read-only eyes.** The reviewer in `steering.py` is capped at
`["Read","Grep","Glob"]` today, so it can judge *code* but never *sees the page*. Add the
browser-inspection tools (navigate + snapshot/screenshot only — never click/type; the Pilot stays
read-only) and the Pilot can issue **aesthetic `NO_GO`s** — "the hero has no motion, the pricing
cards don't align, contrast fails on the CTA" — that a DOM assertion can't catch. That is how you
verify *delight*, not just correctness.

Pair it with an **aesthetic VERIFY seam**: have the method's VERIFY phase capture a Lighthouse a11y
score + a full-page screenshot into `loop-docs/`, and gate on the score (`json_field` on a
`lighthouse.json`) — so "it looks genuinely designed" (the brief's `Done =`) becomes machine-checked,
not asserted. See [Setting the loop up for success](concepts/loop-engineering.md#setting-the-loop-up-for-success--the-input)
for why this belongs in the method + brief, not hardcoded.

**Why this is a recipe, not a default:** it adds a running MCP server + a browser (a heavy external
dependency), and it's frontend-specific — bundling it would re-couple the kit to one domain and break
the lean/reproducible baseline. Reach for it the moment you fork for a design-heavy use case.

## Bigger extensions (the growth roadmap)

**Stay lean, or extend — your call.** The core is complete and useful as-is: a lean harness that
drives a coding agent to a verified result. Everything below is *optional capability* you can layer
on **without changing the two invariants** (deterministic gates, generator/evaluator split). Add
only what your use case needs; a fork that ships nothing from this table is still a real harness.

| You want… | The kit's seam to grow | What extending it looks like |
|-----------|------------------------|----------------------------------|
| A live browser dashboard, replay, resume | emit events from `loop.py` to an event log | an **EventBus + `events.jsonl`** → SSE dashboard (see below) |
| Chain methods (build → harden) | call `run()` repeatedly | a static pipeline DAG |
| An agent that picks the next method | wrap `run()` in a decision loop | an agentic conductor |
| Score output + auto-remediate | add an evaluator pass after VERIFY | a multi-dimension evaluator + remediation loop |
| Lessons that compound across runs | append to `agent-context/LESSONS.md` after a run | eval write-back + a personal/shared seed split |
| Bound context growth on long runs | set `context_reset: "phase_boundary"` on the method (shipped knob) | a fresh session + a disk-doc handoff (see below) |
| A clean handoff repo | a script that strips `.git`/scaffolding | a graduate/export step |

### Observability: an EventBus + `events.jsonl` (the biggest lever)

Today the kit's audit trail is deliberately minimal: **a git commit per turn** (`loop.py:checkpoint`)
plus the phase artifacts in the workspace (`loop-docs/`, `progress.md`, `integration-report.json`).
That's enough to inspect a finished run with `git log`, but it can't stream a *live* view.

To light up live monitoring, replay, and resume, introduce an **append-only event log**:

1. **Emit events.** Wherever the loop does something meaningful — turn start/end, phase advance,
   gate block, Pilot GO/NO_GO, kill-switch trip, tool use — write one JSON line to
   `<workspace>/.sdharness/events.jsonl`. A tiny `emit(event_type, **fields)` helper in `loop.py`
   is all it takes; the file is your single source of run truth.
2. **Consume it many ways** — the same log powers everything, decoupled from the loop:
   - **Dashboard:** tail `events.jsonl` and push over SSE/WebSocket to a browser view.
   - **Replay:** re-read the log after the fact to reconstruct the run turn by turn.
   - **Resume:** on restart, read the log to recover turn/cost state instead of starting over — the
     kit already ships this (`sdharness resume <run>` reconstructs state from `events.jsonl`; phase is
     re-derived from disk, and the agent re-orients from `goal.md`/`loop-docs/` in a fresh session).
   - **Telemetry / cost:** aggregate token/cost fields per turn.
3. **Keep it a bus, not a tangle.** Have producers call `emit()` and consumers subscribe to the log
   — never let the dashboard reach into loop internals. That separation (an *EventBus*) is what lets
   you add a dashboard, a cost tracker, and replay independently without touching the turn loop.

This is the cleanest place to grow the kit: `events.jsonl` is additive (the loop keeps working if
nothing consumes it), and it unlocks the dashboard/replay/resume/telemetry row above in one move.

### Context management: `context_reset` (persistent session vs. phase-boundary reset)

The coding agent's conversation context has a lifecycle knob on the method: **`context_reset`** in
`method.json` (a field on the `Method` model). It has two values:

| `context_reset` | Behavior | Use for |
|---|---|---|
| **`"none"`** (DEFAULT) | **One persistent session for the whole run** — `loop.py` calls `sandbox.connect()` once, `execute()` each turn, `disconnect()` at the end. Context accumulates across all four phases until the SDK auto-compacts. | Short runs (the kit's teaching scale): caching-optimal, simple. |
| **`"phase_boundary"`** | **Reset the session (fresh, empty context) each time the loop advances to a new phase.** The disk docs are the handoff; a `context_reset` event lands in `events.jsonl`. | Long / multi-phase runs where planning-phase chatter would bloat the construction turns. |

**Why `"none"` is the default.** Never clearing keeps prompt caching optimal (the growing prefix hits
`cache_read` @ ~0.1×), which wins at the kit's teaching scale. Clearing *every* turn is the trap — worst
caching *and* the agent re-`Read`s the workspace each turn to rebuild what it knew — so the kit gives you
no knob for it. `"phase_boundary"` is the middle path: caching stays intact *within* a phase (BUILD, the
long one, keeps its cache), and only the ~2–3 phase transitions discard the prefix, shedding stale
planning chatter entering construction. Watch the status line's **`ctx %`** drop back at each advance.

A phase-boundary reset **beats the SDK's blind auto-compaction** because it resets at a *semantic*
boundary and hands off via the disk docs — which works because the kit already externalizes state to
disk (`goal.md` + `loop-docs/` are the memory, not the conversation; it's exactly what `sdharness resume`
relies on). The only thing a reset gives up is the agent's *unwritten* reasoning, so the payoff scales
with how faithfully each turn logs to `progress.md`. Mechanically, `loop.py` calls `sandbox.reconnect()`
at the advance and emits a `context_reset` event; the next phase prompt already says "read `goal.md` /
`loop-docs/…`", so the fresh session re-orients with no special prompt.

You can *see* compaction either way: the kit's one hook (`sandbox.py:_on_precompact`, purely
observational) emits a **`compaction`** event to `events.jsonl` when the SDK auto-compacts under `"none"`;
under `"phase_boundary"` you get `context_reset` events at the advances instead.

To turn it on, set `"context_reset": "phase_boundary"` in your method's `method.json` (or a
`harness-methods/<name>/` override). No code change.

## The two invariants to preserve

However far you take a fork, keep the **two invariants** — deterministic phase advancement
(`phase_authority.py`, never asking the model "are we done?") and a **generator/evaluator split**
(`sandbox.py` vs `steering.py`, the writer is not the judge). They are what make it a harness. See
[Harness Engineering](concepts/harness-engineering.md#from-advice-to-enforcement-the-load-bearing-ideas)
for the why behind each.
