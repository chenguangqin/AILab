# Design — Pilot capability-brokering at scaffolding time ("L3")

**Status:** 🟡 DESIGNED, not shipped (near-term-buildable — Part C is its foundation). **Owner:** kit.
**Relates to:** `harness/tools.py` (the curated registry, L1), `harness/models.py:Method.capabilities`
(the declarative field, L2-lite), `harness/sandbox.py:_resolve_capabilities` + `reconnect`,
`harness/loop.py:444` (the phase-boundary reconnect seam), `docs/customize.md → Add a capability`,
`docs/design/agentic-compound.md` (the sibling propose→approve pattern this reuses).

**In one line:** today the tool set is fixed by the method's `capabilities` list at connect (static,
per-method). This design lets the **Pilot select the capability set per-mission** — from the *same*
curated registry — **once during early scaffolding (the RESEARCH→PLAN boundary)**, not mid-run. It is
upstream sdharness's explicitly-unbuilt **"L3"** (`mcp_registry.py:14-16` flags "externalized tool packs
(L3) additive-not-breaking later") layered on top of the existing **L1 registry + L2 resolver**.

## Why

The kit's lean-intake doctrine ("rich resources, lean direction") pushes the *human* out of pre-staging
the exact tools a mission needs — but today someone still has to know, up front, that a MicroVMs build
wants `aws-docs` and declare it on the method. That's the residue of manual provisioning. The mission
itself reveals what it needs **in RESEARCH** (it reads the intake and resolves the "how"); the natural
move is to let the harness *supply the capability the mission surfaces*, so the intake and the method
stay lean and you **trust the harness to provision what the mission needs**.

The generator/evaluator split the kit already rests on gives the safe shape: the **inner agent** (the
generator) surfaces a need during RESEARCH; the **Pilot** (the read-only evaluator) decides; the
**harness** wires it. The inner agent never self-wires an MCP (which under `bypassPermissions` would be
an unreviewed capability-escalation) — provisioning lives on the judging half, from a curated allowlist.

## Why *scaffolding-time*, not mid-mission (the refinement that dissolves the tensions)

An earlier framing had the inner agent request tools *whenever* it hit a wall, mid-BUILD. That fights
three kit invariants (reproducibility, the no-MCP baseline, containment) and forces a mid-run reconnect
that dumps the BUILD prompt cache. Pinning provisioning to **one moment — the RESEARCH→PLAN boundary —
resolves nearly all of it**:

- **RESEARCH is the discovery phase.** It reads the intake and resolves what the mission needs; the Pilot
  reviewing the RESEARCH turn is the information-rich, natural moment to select the capability set.
- **The reconnect seam already exists.** `loop.py:444` already does a phase-boundary `sandbox.reconnect()`
  for `context_reset == "phase_boundary"`. Provisioning rides that *same* early reconnect (before the
  cache-heavy BUILD), so there is **zero mid-run disruption** and no BUILD cache/context loss.
- **Fixed-after-scaffolding = reproducible + auditable.** One early `capability_provisioned` event in
  `events.jsonl` records the whole set; the run's tool surface is then stable for the rest of the run —
  a `resume` re-reads it, a replay shows it. This nearly eliminates the reproducibility tension.
- **The set is brokered from the CURATED registry (Part C).** The Pilot enables one of N *pre-vetted*
  entries, never an arbitrary server — so containment holds and the security surface stays small.

## Principle (do NOT break)

- **Agnostic on all three axes.** The mechanism is a generic harness loop step over data:
  - **Method-agnostic** — the *trigger* ("provision after phase N" / a declared provisioning point) is a
    field in `method.json`, read by the harness for any method. Not a hardcoded "RESEARCH→PLAN" string.
  - **Strategy-agnostic** — the Pilot's *rubric* ("given these RESEARCH findings, which registry entries
    does this mission need?") is **strategy-supplied prose** (like the steering persona already is), not
    baked into the SD Loop.
  - **Coding-agent-agnostic** — the brokered set is neutral **registry keys** (Part C); the Sandbox
    translates them to its own tool mechanism. No SDK shape crosses the harness boundary.
- **One-shot, not continuous.** Provisioning happens at the declared scaffolding boundary and then the
  tool surface is frozen. No mid-BUILD requests (that's a further, harder rung, deliberately deferred).
- **Curated registry only.** The Pilot brokers from `harness/tools.py` (Part C) — never wires an
  arbitrary server. `strict_mcp_config=True` stays.
- **Read-only evaluator selects; harness wires; agent never self-wires.** Same boundary as the run's
  gate and the agentic-compound curator.

## What gets brokered (a unified capability set)

The Pilot selects a single set spanning **all three capability types together**, because they share the
same lifecycle (fixed at connect, changed only by a reconnect) or are context-injected:

- **MCP servers** — registry keys → `mcp_servers` (via `_resolve_capabilities`, Part C).
- **Skills** — the existing `Method.skills` mechanism (`_resolve_skills`), selected the same way.
- **Doc pointers** — authoritative URLs injected into the agent's context for the rest of the run (the
  "rich resources" an intake pins today, chosen per-mission instead of hand-listed).

## Flow

```
RESEARCH turn runs → agent writes research.md (surfaces what the mission needs: "this is a MicroVMs
                     build → wants current AWS docs")
        │
Pilot reviews RESEARCH (read-only) → in addition to GO/NO_GO, returns a CAPABILITY PROPOSAL:
                     a subset of curated-registry keys + skills + doc URLs, with a one-line rationale
                     each (rubric = strategy-supplied)
        │
harness records `capability_provisioned` (the whole set + rationale) to events.jsonl
        │
phase advances RESEARCH → PLAN → harness reconnects the sandbox ONCE with the brokered set
                     (rides the existing phase-boundary reconnect; the disk docs are the handoff,
                      exactly as context_reset already works)
        │
PLAN + BUILD + VERIFY run with the frozen, provisioned tool surface
```

## Interface (sketch — not built)

- **Method (trigger, JSON):** `capability_brokering: { at: "<phase-name>", from_registry: true }` — the
  provisioning point + that it draws from the curated registry. Absent → today's static behavior.
- **Strategy (rubric, prose):** a `capability_rubric` prompt fragment the Pilot receives at the brokering
  turn: "given the RESEARCH findings, which of these registry entries / skills / docs does *this* mission
  need? Return keys + a one-line why; prefer the minimum; read-only tools only."
- **Pilot output:** extend the review at the brokering turn with an optional
  `capabilities: {mcp: [key], skills: [name], docs: [url]}` block (schema-enforced, like `GateReview`).
- **Harness:** on the brokering phase advance, merge the proposal into the sandbox's `capabilities`/
  `skills`/injected-docs, emit `capability_provisioned`, and reconnect (reuse `loop.py:444`).
- **Event:** `capability_provisioned {mcp, skills, docs, rationale, turn, phase}` — the reproducibility
  anchor; `resume`/`replay` re-read it.

## Tensions (honest, now short)

Scaffolding-time + the curated registry softens all three kit invariants that killed the mid-mission
version:

- **Reproducibility** — the set is fixed after RESEARCH and recorded in `events.jsonl`; a re-run with the
  same intake + registry version selects the same set (the RESEARCH finding is the only variable — the
  same non-determinism a run already has). Pin the registry version in the event for a hard guarantee.
- **No-MCP baseline** — default is unchanged: a method without `capability_brokering` never brokers, wires
  `{}`. This is strictly additive.
- **Containment** — brokering is from the vetted allowlist only; the inner agent still never self-wires.
- **Residual cost** — one extra reconnect after RESEARCH (a fresh session + a cache reset before BUILD).
  Acceptable because it's *before* the cache-heavy phase and the disk docs are already the handoff.

## Relationship to upstream (L1/L2/L3)

- **L1 (upstream, shipped)** — `sdharness.json → mcp.registry`, referenced by name. Kit's distilled form:
  `harness/tools.py`.
- **L2 (upstream, shipped)** — `scaffolding.py:resolve_capabilities(method, strategy)` + strategy
  `attach_to`. Static, per-method/strategy. Kit's distilled form: `Method.capabilities` + `_resolve_*`.
- **L3 (this doc — novel; upstream names it unbuilt)** — mission-driven / Pilot-brokered *dynamic*
  selection from the registry at scaffolding time. `mcp_registry.py:14-16` explicitly reserves it;
  `expansion-ideas/README.md` frames RESEARCH→provision as a growth path. **This design is that L3.** A
  fork that graduates to upstream carries the same vocabulary up.

## Status & next step

DESIGNED. Part C (the curated registry + declarative field + Sandbox resolution) is shipped and is L3's
foundation. Building L3 is ~250–400 LOC (Pilot proposal schema + rubric wiring, the method trigger, the
merge-and-reconnect step in `loop.py`, the `capability_provisioned` event + renderer, tests, a real E2E).
This idea is filed upstream as a feature request (it's genuinely novel vs. upstream L1/L2); this doc is
the request's spec.
