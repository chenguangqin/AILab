# Level 400 — GROW toward your own production harness

Goal: help a team grow their fork **past** the teachable core toward *their own* production harness —
using the bundled `reference/expansion-ideas/` reverse-engineering docs as **one illustrative
example** of how a mature harness solved each capability. The kit is where you are; the AI Dark
Factory / increasing autonomy is the direction; the RE docs are one worked example of the road; this
skill is the guided, research-informed path. **The team chooses the destination.**

This is **directional guidance, not a build script.** Name the next decision, the trade-off, and an
example to borrow from — then let the team's coding agent do the building. Resist "do exactly this."

## The framing you must hold (say it out loud when it matters)

- **Example, not a blueprint.** The RE docs describe a *full* production harness; the kit is the
  ~2,000-LOC seed. Borrow *ideas*, adapt to the team's needs. Never "replicate upstream" or "converge
  on the goal." A fork that adds nothing from the RE docs is still a real harness.
- **Requirements drive, examples inform.** What to add comes from the team's **RESEARCH findings +
  their use case** (see `references/research-current-practice.md`). The RE docs are a *catalog of
  proven options* weighed against current practice — not the source of the requirement.
- **Autonomy is a choice, not a goal.** Grow *along* the reviewer → decision-maker → supervisor
  continuum only as far as the use case needs. The AI Dark Factory is the direction; most products
  stop well short of a fully dark loop, and that's correct.
- **The two invariants survive every step.** Deterministic phase advancement + generator/evaluator
  split (see the bottom of `docs/customize.md`). If a growth step would break either, it's the wrong
  step or the wrong shape.

## How to pick the *next* capability (the decision, not a menu)

Don't hand the team the whole roadmap. Help them pick **one** next capability by triangulating:

1. **Their use case** — what does the product actually need next? (A dark unattended factory? Better
   review? Cross-run learning? Live monitoring?)
2. **Their RESEARCH notes** — what did current practice say is worth folding in, and where on the
   autonomy continuum do they need to sit?
3. **The kit's seam** — where in the ~2,000-LOC core does that capability grow? (`docs/customize.md`
   maps every one.)
4. **The worked example** — how did a fully-grown harness solve it? (the expansion-ideas catalog — borrow the *shape*,
   not the code.)

Then build it agentically: **use the SD Loop itself** (or the team's coding agent) to implement the
step, with the readiness test as the gate. Growing the harness *with* the harness is the intended
path (and a compound-engineering flywheel).

## The capability map — kit seam ↔ worked example ↔ where to look

Each row: the growth candidate, the **kit seam** it grows from (`docs/customize.md` "growth roadmap"),
and the **worked example** (in the expansion-ideas catalog) to study for one proven approach. Pick by use case + RESEARCH, not by
working down the list.

| Candidate capability | Kit seam (grow from) | Upstream example to study (borrow the idea) |
|----------------------|----------------------|---------------------------------------------|
| **Live dashboard / replay / resume** | emit events from `loop.py` → `events.jsonl` (the biggest lever, see `docs/customize.md` "Observability") | `architecture.md` (EventBus + SSE dashboard + WebSocket) · `api-documentation.md` (dashboard HTTP+SSE routes, WS command channel) |
| **Multi-reviewer board** (Product/Tech/Security/SRE/QA) | a blocking-consensus strategy + more reviewers (`docs/customize.md` "Add a multi-reviewer board") | `business-overview.md` (Advisory Board / mob) · `component-inventory.md` (14 strategies) · `architecture.md` (review system) |
| **More methods** (SDD, WAF-hardening, mockup, brownfield…) | author a method dir (`docs/authoring-a-method.md`) | `component-inventory.md` (15 methods catalog) · `business-overview.md` (methods as products) |
| **Chain methods into a pipeline** | call `run()` repeatedly → a static DAG (`docs/customize.md` growth roadmap) | `architecture.md` (Pipeline over Strands Graph) · `api-documentation.md` (`PipelineConfig`/`StepConfig`) |
| **Agentic conductor** (agent picks next method) | wrap `run()` in a decision loop | `architecture.md` (Conductor sequence diagram) · `api-documentation.md` (`ConductorDecision`/`TaskLedger` dual-ledger) |
| **Evaluate + auto-remediate** | evaluator pass after VERIFY | `architecture.md` (7-dim scoring) · `code-quality-assessment.md` (evaluation harness) |
| **Compound learning across runs** | `sdharness compound` (agentic curator by default: semantic dedup · quality-gate · tool/doc-first gate · route · validate → human-approved diff) → `--deterministic` (offline title-dedup fallback) | `business-overview.md` (the compounding cycle, `compound` command) · `technology-stack.md` (knowledge seed) |
| **Swap / add coding agents** (Kiro, Gemini, Codex) | a new `Sandbox` impl (`docs/customize.md` "Swap or add a coding agent") | `architecture.md` (Sandbox protocol, ACP) · `api-documentation.md` (`Sandbox` protocol) |
| **MCP tools** (verified facts, browser self-correction) | add MCP to `sandbox.py` (`docs/customize.md` "Add MCP tools") | `architecture.md` (MCP registry L1 + `capabilities` L2) · `technology-stack.md` (MCP servers) |
| **Clean handoff / graduate step** | a script that strips scaffolding | `business-overview.md` (`graduate`) · `api-documentation.md` (`graduate` command) |

For the *methodology* of keeping a mature-harness exhibit current — and running the same
reverse-engineering pass on the team's own growing fork — see
[`reference/expansion-ideas/aidlc-brownfield-reverse-engineering.md`](../../../../../reference/expansion-ideas/aidlc-brownfield-reverse-engineering.md).

## The build loop for one growth step

1. **Frame the decision** with the team: capability, why now (use case + RESEARCH), the seam, the
   worked example in the expansion-ideas catalog, and *how far* on the autonomy continuum it moves them.
2. **Borrow the shape, not the code.** Read the relevant RE doc for one proven approach; adapt to the
   kit's seam and the team's needs.
3. **Build it agentically** — point the SD Loop / the coding agent at the change; keep the brief lean
   (what + why, not how).
4. **Gate it.** `pytest -q` (esp. `tests/test_readiness.py`) + `ruff check harness tests` must be
   green. If the change touches gates/strategies, readiness is the guardrail against runaway loops.
5. **Confirm the invariants held** — deterministic advancement + generator/evaluator split intact.
6. **Compound it** — capture what worked as a lesson (`agent-context/LESSONS.md`) so the next growth
   step starts ahead.

## Hand-off

- Deeper per-capability recipes: [`docs/customize.md`](../../../../../docs/customize.md).
- The concepts behind the direction: [`docs/concepts/harness-engineering.md`](../../../../../docs/concepts/harness-engineering.md)
  (reviewer → decision-maker → supervisor) and [`docs/concepts/compound-engineering.md`](../../../../../docs/concepts/compound-engineering.md).
- Current practice to weigh options against: `references/research-current-practice.md`.
