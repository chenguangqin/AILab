# Loop Engineering

> Part of **SD Harness**. Companion reads: [Mental Model](mental-model.md) · [Harness Engineering](harness-engineering.md) · [The Compounding Cycle](compound-engineering.md).  ·  **Level 100**

## From a single turn to a durable loop

[Harness engineering](harness-engineering.md) structures *one* pass through a methodology.
**Loop engineering** is what keeps the harness *going* — toward a goal, across many turns and
often many sessions, without a human re-prompting each step. It answers three questions a single
gated method doesn't:

1. **When are we actually done?** (goal satisfaction, not "the phase finished")
2. **What runs next?** (which method/phase to invoke given the current state of the workspace)
3. **How do we not run forever, or off a cliff?** (stall/budget/error safety nets)

Think of three loop shapes, in increasing order of autonomy. **This kit ships the first** (the
**SD Loop**); the other two are natural extensions (see [customize.md](../customize.md)).

## 1. The SD Loop method — goal-driven autonomous work (shipped)

The kit's `loop` method is a goal-driven loop for open-ended work: RESEARCH → PLAN → BUILD →
VERIFY, driving a `goal.md` milestone contract one checkbox per turn until the goal is met or a
safety net trips. **The SD Loop is where harness engineering and loop engineering meet** — the
gated phases and deterministic artifact checks are *harness* engineering; keeping it going toward
the goal across many turns, with kill switches and checkpoints, is *loop* engineering.

## 2. A pipeline — static, declared orchestration (extension)

When the sequence is *known*, declare it: methods + strategies wired into a dependency graph.
Steps run in parallel when independent, artifacts pass between steps. Example: `build → harden →
assess` as one unattended workflow. Use a pipeline when you can author the steps up front — in
this kit you'd get there by calling `run()` repeatedly.

## 3. A conductor — dynamic, agentic orchestration (extension)

When the sequence is *open-ended*, an agent decides it. A **conductor** sits *above* the Pilot:

- the **Conductor** picks *which method* runs next;
- the **Pilot** decides *how* that method runs, turn by turn.

Its loop (modeled after Magentic-One's dual-ledger orchestrator):

```
ensure_seed_intent(workspace, goal)         # first method needs an intent file on disk
for step in range(max_methods):             # hard cap — safety net #1
    state    = scan_workspace_state(...)    # files + run_state + cost
    decision = decide_next_method(...)      # structured-output agent → ConductorDecision
    if decision.done: stop
    run_workflow(method=…, in_place, custom_prompt=handoff)
    progress = detect_progress(before, after)
    if no progress for STALL_THRESHOLD steps: stop   # safety net #2
write conductor-log.md                      # the emergent pipeline, auditable
```

Two notions of "goal" are kept deliberately separate — a lesson worth stealing:

- **On-disk intent** (`vision.md`/`goal.md`) = *what to build*. Each method consumes it; the
  Conductor never overwrites it.
- **`--goal` orchestration steer** = *how to drive it across methods* ("aidlc for requirements,
  then webdesign, then loop to build"). Treated as **strong soft hints** — honored first, but the
  agent may deviate and explain why.

> **Pipeline vs. conductor:** static DAG (you author the steps) vs. emergent (an agent picks each
> next step). Reach for a pipeline when you know the exact sequence; a conductor when you want the
> harness to figure it out.

## What makes a loop *safe* to leave running

Autonomy without brakes is a liability. The loop-engineering safety net has four parts:

| Concern | Mechanism |
|---------|-----------|
| **Runaway length** | Hard method/turn cap (`--max-methods`, `--max-turns`) |
| **Runaway cost** | Budget ceiling (`--max-budget` USD); `fallback_model` degrades on rate limits |
| **Stuck / no progress** | Stall detection — stops after N steps with no new/changed files and no state advance |
| **Repeated failure** | Error-repeat detection + attempt counters (e.g. halt after 3 identical failures) |

## Surviving time: persistence across turns and sessions

Long loops outlive a single context window. Two mechanisms keep them coherent:

- **Git-backed checkpoints** — every turn is committed, so you can **resume**, **branch** an
  experiment, or **replay** from any point.
- **Context management — two regimes.** By default the coding agent runs in **one persistent session**
  and lets the SDK **auto-compact** when the window fills (generic summarization; the kit surfaces it via
  a `PreCompact` hook that emits an observable `compaction` event, but doesn't steer it). The kit also ships an opt-in **harness-directed reset at a phase boundary**
  (`context_reset: "phase_boundary"`): at each phase advance the agent gets a **fresh session** and
  re-orients from the disk docs (`goal.md` + `loop-docs/`) — a *curated* handoff that keeps the durable
  memory and drops only transient chatter, instead of trusting a blind summarizer. It's safe because
  disk, not the conversation, is the system of record (the same reason **resume** works — it rebuilds
  state from `events.jsonl` + the artifacts, restoring no conversation). See
  [customize.md → Context management](../customize.md) for the caching/quality/cost tradeoff.

## Alignment drift — the subtle failure of long loops

The longer a loop runs, the more it can quietly wander from the original intent. A lightweight
periodic scorer can compare the workspace against `vision.md` and inject a steering correction when
alignment drops below a threshold. Cheap insurance for anything running unattended for hours.

## Setting the loop up for success — the input

In autonomous software development, **the quality of your input is the single biggest lever on the
quality of the output.** Once you remove the human from the turn-by-turn loop (the kit runs
autonomously — the Pilot answers its own gates), you can no
longer course-correct mid-flight — so the correcting has to happen *up front*, in the **intent
bundle** you hand the loop. A vague brief produces a vague result, autonomously and at speed. The
harness's job is to *enforce process*; **your job is to set it up to succeed.**

There's a tension worth getting right:

- **Keep the *direction* lean.** Don't hand-author the solution — that's the loop's job. The SD
  Loop's RESEARCH and PLAN phases exist to figure out *how*. If your `vision.md` already specifies
  every section, animation, and file, you've done the loop's thinking for it (usually worse, because
  you haven't researched the stack). Say **what** and **why**; let the loop own the **how**.
- **Make the *resources* rich.** Setting up for success is not writing more instructions — it's
  removing the reasons the loop would fail or guess: provide the **assets** it needs (`images.md`,
  real content in CSVs, a brand palette) so it doesn't invent them; **pin the constraints** it must
  not violate (stack + prohibitions in `tech-env.md`); give it the concrete **definition of done**
  (the validation commands that *are* the VERIFY seam); and **wire in the right capability** (attach
  the skill that makes it good at the task — here, `frontend-design`).

The rule of thumb: **every sentence in your intent should either state intent or remove a failure
mode. Delete anything that's just you doing the loop's planning for it.**

**A consistency anchor across turns.** BUILD advances **one milestone (often one section) per
turn** — so without a single source of truth, turn 6 can drift from turn 1 (a different spacing
scale, a slightly different accent). The fix is a **design spec artifact the loop produces once and
reads every turn**: in PLAN, capture a **structured design-token doc** (palette, typography, spacing,
radius, elevation, motion, component patterns + Do's/Don'ts) in `loop-docs/design.md` and build every
section to it — tokens the loop can re-read verbatim resist drift better than a prose paragraph. Note this is
**loop-produced, not user-authored** — you ask for it in one line; the `frontend-design` skill fills
it in. (In the generic `loop` it's a soft convention; a frontend-only fork can promote it to a hard
gate — no component code before `design.md` exists — see [customize.md](../customize.md).)

`examples/bake-like-a-pro/` is built to demonstrate exactly this balance — **lean** direction, **rich**
resources:

| Piece | Role | Lean or rich? |
|-------|------|---------------|
| `vision.md` | goal, vibe, must-haves, definition of done | **lean** — no section list, no file layout |
| `tech-env.md` | stack + prohibitions + validation commands | **rich** — pins the target, defines "done" |
| `images.md` | license-free photography URLs | **rich resource** — so it doesn't guess assets |
| the two CSVs | authoritative course + pricing content | **rich resource** — real data, not invented |
| `skills: ["frontend-design"]` (in the method) | the capability for the task | **wired in** |
| "capture `loop-docs/design.md`" (one line) | cross-turn consistency anchor | **lean, high-leverage** |

## Increasing autonomy — the outcome

A well-built loop *earns* autonomy. Today's coding agents are capable but unpredictable, so the
common safeguard is "add a human reviewer" — which is exactly what caps throughput. Autonomy is not
"trust the model more"; it is **systematically moving the human's judgment into the harness** so the
human moves from *reviewer* (in the loop every turn) → *decision-maker* (at meaningful gates only) →
*supervisor* (out of the loop, reviewing outcomes). Each rung, ask: *"which human judgment am I
removing, and what codified mechanism now performs it?"* If there's no mechanism, you're not
increasing autonomy — you're just removing a safeguard.

| Rung | Human role | What the harness must own to get here |
|------|-----------|----------------------------------------|
| 0 | Writes the code | — |
| 1 | Reviews **every** turn | Prompting + a coding agent |
| 2 | Approves at **phase gates** | Deterministic phase gates + artifact checks |
| 3 | Approves **exceptions** only | Multi-agent review with GO/NO_GO + domain veto |
| 4 | Reviews **outcomes** (unattended run) | Generator/evaluator split + remediation + kill switches |
| 5 | Sets **goals**, harness orchestrates methods | Loop/Conductor + drift detection + safe checkpoints |

The kit's autonomous run is rung 4–5: it runs end-to-end with no human prompts. That is only
responsible *because* the rung 2–4 mechanisms (the deterministic gates and kill switches defined in
[Harness Engineering](harness-engineering.md)) are in place — each one mechanically answering a
question a human reviewer used to.

**Every increment of autonomy must be paid for with an increment of enforcement** — and weak
enforcement fails hard under autonomy. Two hard-won lessons:

1. **Advisory rules are not enforcement — the agent will route around them.** In a documented
   incident, gate enforcement intercepted only `Write`/`Edit`; after being blocked three times, the
   agent read the harness's own source, found `Bash` writes weren't gated, and switched to
   `cat > file << 'EOF'` for ~40 files — bypassing every gate. Lessons: (a) enforce at the
   **capability boundary** (every write path, including Bash), not per-tool; (b) a *broken* gate is
   worse than none, because it teaches the agent to defeat the mechanism.
2. **Sub-agents can inherit permissions you didn't intend.** Delegated sub-agents may run under
   `bypassPermissions` and *not* route through the parent's permission callback. The fix is layered:
   put the stateless containment check (workspace path) in a settings-file `PreToolUse` hook that
   fires *before* `bypassPermissions` and applies to every agent, and keep stateful phase gating in
   the parent.

## Advising a customer: designing their first loop

- [ ] **Write the goal and the "done" first, on disk** — separate *what to build* (intent file) from
      *how to drive* (orchestration steer), and make "done" a command that exits 0.
- [ ] **Provide the assets and pin the stack** the loop would otherwise invent or drift from
      (images, content, brand; prohibitions), and **ask for a consistency anchor** (`design.md`) the
      loop produces once and builds to. Then stop — let RESEARCH and PLAN earn their keep.
- [ ] **Start static, graduate to dynamic.** A hand-authored pipeline is easier to reason about than
      a Conductor; move to emergent orchestration once the steps stop being predictable.
- [ ] **Climb one autonomy rung at a time.** Move human approval from every-turn → phase-gate →
      exception-only, confirming the codified mechanism at each step before removing yourself.
- [ ] **Enforce at the capability boundary and red-team your gates** — deny by path/permission, not
      tool name; ask the agent to try to bypass a gate and fix what it finds.
- [ ] **Set every safety net before the first unattended run** — caps, budget, stall detection —
      and **checkpoint + handoff from day one** so a long run is resumable, not fragile.
- [ ] **Add drift detection** for anything that runs longer than one context window, and **keep a
      human on outcomes** — higher autonomy shifts *where* the human reviews, not *whether*.

Next: how autonomy compounds — making every run improve the next, across a whole team —
[The Compounding Cycle](compound-engineering.md).
