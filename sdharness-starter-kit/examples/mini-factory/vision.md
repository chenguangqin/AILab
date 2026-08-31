# Vision — Mini SD Harness Factory

Build a tiny **control plane** for the SD Harness: a browser page where you **launch an `sdharness`
run, watch its events stream live, and see the result** — without babysitting a terminal. This is a
local, single-machine *taste* of the "SD Harness Factory" (the hosted, multi-user rung at the top of
the maturity curve) — the **art of the possible**, built by the harness itself.

## Problem & Users
- **Problem:** running `sdharness` is a solo terminal affair — you kick off a run and stare at a
  scrolling log. There's no shared surface to launch a run, watch it from a browser, or glance at how
  past runs went. The lessons and results live in one person's local run workspaces and scroll away.
- **Primary user:** someone running harness builds who wants to **launch and watch from a browser** —
  start a run, walk away, check progress on a page, and see the outcome.
- **Today's workaround:** open a terminal, run `sdharness run …`, keep the tab focused, scroll back to
  find what happened.

## What we're building (the ONE feature)
A small local web app — a tiny API plus a **polished browser UI** — that **launches an `sdharness` run**,
records it in a **local run registry**, **streams that run's live events to the browser**, and shows
the **result**. The event stream is the harness's *own* `loop-docs/events.jsonl` (and `--json` stream),
surfaced in a page — the same phase/turn/gate/cost/GO-NO_GO vocabulary the CLI already emits. It runs
entirely on your machine.

## Frontend craft bar — this is a showcase, hold it to the same standard as `bake-like-a-pro`
This is the **art of the possible**: the UI a stranger sees when they meet the SD Harness for the first
time. It must look and feel like a **real, professional product** — the control room of a factory that
**builds and verifies software autonomously** — not a "minimal" dev tool or a scaffold. The bar is
**flawless, delightful, and genuinely designed**, exactly the rigor `bake-like-a-pro` sets for its
landing page.

**Why this identity — the message is autonomy, not aesthetics.** The one thing this UI must prove is that
**software gets built, gated, and verified without a human in the loop** — you set the intent and
supervise *outcomes*, not keystrokes. Everything on screen should say *"look how much happens, correctly,
without you touching it."* The "lights-out factory" is just the vehicle for that argument: a manufacturing
plant runs with the lights off precisely *because* no human is on the floor — the darkness is the
**evidence of autonomy**, not a mood. So lead with the substance — the phases advancing on their own, the
gate verdicts that let you step back, a fleet of runs finishing unattended — and let the industrial
styling carry it. If a viewer comes away impressed by "a cool dark dashboard" instead of "it did all
that by itself," the identity has failed.

**Use the `frontend-design` skill** (attached to this run) to design and build the UI.

**Keep the design consistent:** in PLAN, use the skill to settle ONE bold, cohesive aesthetic, then
capture it as a **structured `loop-docs/design.md`** — named design tokens (palette, typography + type
scale, spacing, radius, elevation, motion, component patterns) plus a short **Do's & Don'ts** — and
build **every** view to that file. It's the run's cross-turn consistency anchor: reading a written token
doc each turn keeps the last view as polished and on-brand as the first (a design system that lives only
in the agent's head drifts across turns).

**Art direction — "Lights-Out Factory Floor":** *the control room of an autonomous software factory
running in the dark. A near-black canvas lit by a **sodium-amber worklight** (the one brand accent) with
**signal-cyan** for data/telemetry; disciplined machined detailing — faint blueprint grid, hairline
edges, corner ticks — and a monospace instrument voice. Every accent carries signal; color only ever
means a phase, a status, or the brand. Restraint over decoration: the floor is dark, the data glows.*
A few motifs carry this identity — realize them however reads best:
- **The wordmark** should own the bracket treatment, `SD [ HARNESS ] FACTORY`, and feel like a plant
  that's powered on and running.
- **The four phases should feel like an assembly line** — a build visibly moving station to station, not
  four flat tabs. (Whatever the phases are: drive them from the run's own data, don't assume the four.)
- **GO / NO_GO deserves a hero, and the andon stack-light is it** — the factory-floor signal light that
  stops the line. It's the loudest thing on the screen because it's *the reason you can walk away*: an
  independent gate deciding, autonomously, whether the work is good enough to advance. Make it read
  across the room.
- **The run list is a factory floor, not a table** — each run a machine cell you can read at a glance.
  The payoff it should sell: **one supervisor, many autonomous runs** — when several run at once (the
  cloud graduation) the floor reads like a plant humming with no one on it. That fleet-leverage *is* the
  developer value.

**The live event stream is the centerpiece — make it feel alive.** This is the moment that sells the
harness: watching the line **run itself**. Phases advance with no human turn-by-turn, hand-offs feel
deliberate, the GO/NO_GO gate lands as a clear beat, and the live cost/turn/milestone readouts update
without jitter. A visitor should *feel* the factory working unattended — motion with intent, never
gratuitous.

**Show numbers the way a person reads them.** Costs read as money (`$1.76`, not a raw `1.7556` — the
`events.jsonl` keeps full precision as the source of truth; the UI is what makes it human), turns as
whole counts, milestones as done-of-total. Never render a raw multi-decimal float at a user.

**Design for adoption — responsive and easy to browse.** Visual craft alone isn't the bar; someone
should be able to launch a run and follow it from **any device** — you kick off a build at your desk and
glance at progress from your phone. Concretely:
- **Multi-device by default.** Flawless on mobile, tablet, and desktop — design mobile-first, then tune
  up. Collapse navigation on small screens (a menu, not crowded controls), keep tap targets
  finger-sized, and make the live stream + status readable one-handed on a phone. Judge it at ~375px
  (phone), ~768px (tablet), and ~1440px (desktop).
- **Scannable, not an endless log.** The **factory floor** (run list) and a single run's state must be
  graspable at a glance — clear hierarchy, each cell's andon state and current station readable at a
  glance, without reading every line. Favor compact, dense-but-legible layouts over walls of raw text.
  A **finished** run is still a first-class citizen of the floor — a completed or idle cell should read
  clearly (its outcome legible at a glance), never fade so far into the dark that the floor looks empty.
- **Easy to browse.** An obvious way to launch, an obvious current state, and a persistent quick path
  back to the run list — the route from "launch" to "watch" to "past runs" is always one glance away.

## Expected outcomes (user action → system response)
- User submits a run (an example path + method, e.g. `bake-like-a-pro` / `loop`) in the browser →
  the app launches an `sdharness` run and returns a **run id** + a live view.
- User opens the run → sees the **live event stream** render as it happens (phases advancing, turns,
  the Pilot's GO/NO_GO, cost, milestones) — the same vocabulary `sdharness` emits.
- Run finishes → the page shows the **result** (complete / incomplete, turn count, milestones, total
  cost) and a link to the run's workspace on disk.
- User returns later → a **list of past runs** (the registry) shows each run's status, cost, and result.

## Done =
From the browser, a user launches a run and watches its events stream to completion, then sees the
result — proven by an automated check that: (1) POSTing a launch starts a run and returns a run id;
(2) the run's events (from `loop-docs/events.jsonl`) stream to the browser and render as turns/phases;
(3) when the run ends, the page shows the result (status + cost + milestones) and the registry lists
it. The check must pass **fast and cheaply** — against a tiny run (very low `--max-turns`) or a
**pre-recorded `events.jsonl` fixture** — never a full ~20-minute build.

**And it must look genuinely designed** — a polished, cohesive **lights-out factory floor** conforming to
`loop-docs/design.md`: the `SD [ HARNESS ] FACTORY` wordmark, the assembly-line stations, the **andon
stack-light** as the hero GO/NO_GO signal, the run list as a floor of cells, the live stream feeling alive,
all readable at a glance — **and it must read well on mobile, tablet, and desktop** (responsive, scannable,
easy to browse — see the craft + adoption bar above). A functional-but-plain UI, or a generic dark
dashboard, does NOT meet the bar. How you get there is yours to plan.

## Scope
- **In:** a local API (launch / list / get-one / stream-events); a local run registry (a JSON file or
  SQLite); a subprocess runner that shells out to the installed `sdharness` CLI; a minimal browser UI
  (launch form, live event stream, result view, run list); streaming from the run's `events.jsonl`.
- **Out (deferred — that's the *real* factory's job):** any cloud/AWS (Lambda, DynamoDB, Fargate, S3,
  CloudFront); multi-user auth; the cross-run knowledge curator / promotion-MRs; scheduling; cost
  dashboards. Name these as "graduate to AWS," don't build them.

## Success bar & non-negotiables
- **Success looks like:** someone who's never used the `sdharness` CLI can launch a build and watch it
  run, from a browser page, on their laptop — and comes away thinking *"that's a real product."*
- **Non-negotiables:**
  - **Consume the harness, don't re-implement it.** Launch runs via the installed `sdharness` CLI
    (`sdharness run …`, `--json` for the machine stream) and read the run's `loop-docs/events.jsonl`.
    NEVER re-author the loop, gates, methods, or the event schema — those live in the kit.
  - **Local only** — no cloud account required to demonstrate it.
  - Preserve the harness's **event vocabulary** in the UI (phases, turns, GO/NO_GO, cost, milestones),
    so the page reads like the CLI you already know.
  - **Frontend craft is a non-negotiable, not a nice-to-have.** Polished, cohesive, delightful, and
    responsive (mobile/tablet/desktop), built to `loop-docs/design.md` via the `frontend-design` skill —
    same bar as `bake-like-a-pro`, and committed to the **Lights-Out Factory Floor** identity above
    (wordmark, sodium-amber worklight, assembly-line stations, andon stack-light, floor-of-cells run
    list). A plain or scaffold-grade UI — or a generic dark dashboard that ignores the identity — fails
    the run, even if the API works.

## Open questions
- Event egress mechanism for the live view: tail the run's `events.jsonl` file, or consume the
  `sdharness run --json` stdout stream? (RESEARCH decides; both are already emitted by the kit.)
- Registry store: a flat JSON file vs SQLite (either is fine for a local prototype).
