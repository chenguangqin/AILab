# Vision — Mini SD Harness Factory, on AWS (Lambda MicroVMs)

Take the **local mini-factory** you already built — the browser control plane that launches an
`sdharness` run, streams its events live, and shows the result — and **graduate its runner from a
local subprocess to an AWS Lambda MicroVM**. Same frontend, same launch → observe → result flow; the
run now executes in a **Firecracker-isolated, per-session cloud sandbox** instead of on your laptop.
This is the "graduate to AWS" rung the local `mini-factory` deliberately left for later — the factory
frontend proven backend-agnostic, the *runner* graduated to the cloud.

**This is a brownfield build, delivered in two tiers.** You start from a working local mini-factory
(copied into this workspace) and evolve it — RESEARCH audits what's already there, then PLAN/BUILD swap
the backend.

**The mental model in one line: ONE launcher, verified two ways.** You build a single control plane;
Tier 1 verifies it cheaply on *any* account (mocked AWS client + a recorded fixture), and Tier 2 —
when the live capability is armed — fires that *same* launcher against the real service once. The tiers
run in sequence (Tier 1 always, then Tier 2 if capable); Tier 2 is "one real call on top," never a
replacement for Tier 1 and never a separate code path. `goal.md` breaks into these two tiers:
- **Tier 1 (required, always-green): the control plane, proven against a REAL local run.** Build the
  whole factory — the launcher that runs a MicroVM per run, the durable events, the registry, artifact
  retrieval, concurrency, compounding. Prove the happy path by **running the real `sdharness` CLI locally
  as a subprocess** (a tiny intake, low `--max-turns`) and streaming its *genuine* live `events.jsonl` —
  the factory **consumes the installed kit** (it has the kit's source available to run it, never to fork
  it). Only the AWS `lambda-microvms` client is **mocked** (there's no service to call on an unentitled
  account). Keep the **recorded sample run** (`fixtures/events.jsonl`, a *recorded* real cloud run) for
  the checks a live subprocess can't cheaply cover — disconnect-replay, the exact `workspace.tar.gz`
  shape, and deterministic CI. This tier passes on ANY account, no cloud provisioning.
- **Tier 2 (gated, live): a real MicroVM run.** Bake a customer MicroVM image and fire **one real
  MicroVM run** — an actual Firecracker VM runs `sdharness` in the cloud, streams back, and hands back a
  retrievable `workspace.tar.gz`. This tier runs **only when the live-MicroVM capability is enabled**
  (the account is entitled to `lambda-microvms` and a MicroVM execution role is available); otherwise the
  build stops green at Tier 1. It is the last mile — the stub swapped for the real provision-bake-boot cycle.

## The lights-out factory floor, in the cloud
The local mini-factory already commits to a **"Lights-Out Factory Floor"** identity (control room of an
autonomous software factory — assembly-line stations, an **andon stack-light** for GO/NO_GO, a floor of
machine cells; see `mini-factory/vision.md`). **Reuse that identity verbatim** — this is a runner swap,
not a redesign. What the cloud actually *adds* is what makes the floor literal: each run now executes in
its **own isolated Lambda MicroVM — a real machine cell running unattended in the cloud**, so the floor
can show **many autonomous runs building at once**, safely and in parallel, none touching another. That's
the message the cloud makes real: **one supervisor, a fleet of self-running builds** — the human watches
outcomes (andon verdicts, stations advancing) across concurrent cells, babysitting none of them. The
fleet-leverage is the point; the lights-out floor is just how you see it. The design already earned this
metaphor; the cloud is what finally fills the floor.

## This is a lightweight, single-user mini `sdharness-factory`
The local mini-factory proved *launch → observe → result* on your laptop. This graduates it into a
**lightweight, single-user, remote-distilled `sdharness-factory`** — the production factory's core
run-lifecycle, distilled down and run **remotely in the cloud** for one operator. It adds the features
that make it a real factory rather than a demo: **remote isolated execution, a fleet of concurrent runs,
durable events, a run registry, retrievable artifacts, and a compounding knowledge loop.** It stays
**single-user** (one operator, your own runs — no multi-user auth or team fan-out; that's the hosted
factory) and it's **built by `sdharness` itself** (the harness operating one rung up, over its own cloud
runner). "The factory's core, distilled to one remote operator" is the bar.

## Problem & Users
- **Problem:** the local mini-factory runs every build as a **subprocess on one machine** — no
  isolation, no way to run many concurrently or safely, bound to whatever's installed on that laptop, and
  (the killer gap) **once a run ends you can't get the built deliverable back** — it lives and dies in the
  subprocess. A real factory needs runs that are **isolated, concurrent, durable, and retrievable** —
  each in its own clean sandbox, each producing an artifact you can collect afterward.
- **Primary user:** **you** — a single operator who wants to **launch runs from the browser into isolated
  cloud sandboxes**, watch several stream at once, **download what each one built**, and have each run
  make the next one smarter. The same experience as the local factory, now cloud-isolated + fleet-scaled
  for one person.
- **Today's workaround:** the local mini-factory's subprocess runner — fine for a solo laptop demo, but
  no isolation, no concurrency, and no way to retrieve the deliverable.

## What we're building (the ONE feature)
Keep the local mini-factory's **frontend + launch → stream → result → registry** exactly as-is, and
**replace its runner**: instead of shelling out to a local `sdharness` subprocess, a **launcher**
starts a **Lambda MicroVM** per run, a worker inside the MicroVM runs the real `sdharness` CLI in
`/workspace`, and the run's `events.jsonl` **streams back over the MicroVM's HTTPS endpoint** to the
same browser UI — the same phase/turn/gate/cost/GO-NO_GO vocabulary, now from an isolated cloud sandbox.

**Critically: retrieve the artifact before the sandbox dies.** The MicroVM is ephemeral and terminated
after the run — so on completion the worker must **capture the run's `/workspace`** (the built
deliverable: the generated code, `goal.md`, `loop-docs/`) as a **`workspace.tar.gz`** and hand it back
(to the control plane / durable store) so a user can **download what the run actually built** later. A
cloud factory you can't get the deliverable back from is a demo, not a factory — this is the difference
between "watch it run" and "collect the output." (This is exactly what the production factory does: it
persists `events.jsonl` + `workspace.tar.gz` to S3 per run.)

**The core factory features (single-user, all cloud-isolated).** Beyond the runner swap + artifact
retrieval, model these from the production factory — the minimum that makes it a *factory*:
- **Durable event log** — persist each run's `events.jsonl` durably, not only on the live stream, so a
  reconnect or a later replay works after a client disconnect (closing the transport caveat below).
- **Run registry** — a per-run record: id, status (`PENDING → RUNNING → SUCCEEDED / FAILED`), cost,
  milestones, method, the **artifact pointer** (where the `workspace.tar.gz` landed), error, timestamps.
- **Terminal state from the harness's own event** — the run's final status/cost/error is read from the
  kit's terminal `complete` (+`error`) event, not reinvented.
- **Concurrency / fleet** — launch **several runs at once**, each in its own isolated MicroVM cell; the
  floor shows them all; each is independently retrievable. A run whose VM dies before its worker boots
  lands `FAILED` (a status reaper), never stuck `RUNNING`.

**Compound engineering — each run makes the next smarter.** After a run's workspace is retrieved, the
factory runs the kit's own **`sdharness compound`** on it — lifting that run's `progress.md` `## Patterns`
into a **local** `agent-context/LESSONS.md` (title-deduped, human-reviewable — surface the diff, don't
auto-merge). The **next** run the factory launches stages that `agent-context/`, so it starts with what
prior runs learned. This is the read-before / write-after flywheel, single-user and local — **a personal
knowledge base, not a team-wide, auto-curated, MR-gated one** (that's the hosted factory). Curation stays
a human step on purpose.

## Expected outcomes (user action → system response)
- User submits a run in the browser → the **launcher** starts a MicroVM, returns a **run id** + a
  live view (unchanged UX from the local factory).
- User opens the run → the MicroVM's worker runs `sdharness run … --json`; its **events stream to the
  browser** as they happen (phases advancing, turns, Pilot GO/NO_GO, cost, milestones).
- Run finishes → the worker **captures `/workspace` → `workspace.tar.gz`** and hands it to the store; the
  page shows the **result** (complete/incomplete, turns, milestones, total cost) **with a "download
  artifact" action**; the MicroVM is terminated (pay-per-session).
- User launches **two runs at once** → both appear on the floor as separate isolated cells, stream
  independently, and each finishes with its own retrievable artifact — no cross-run interference.
- User returns later → the **registry** lists past runs with status, cost, result, and a download link;
  the next run launched **starts smarter** (it stages the `agent-context/LESSONS.md` compounded from
  prior runs).

## Done = (two tiers)

**Tier 1 — the control plane (REQUIRED; green on any account, no live MicroVM).** From the browser, a
user launches runs, watches them stream, **downloads what each built**, and sees each run make the next
smarter — proven by an automated check that (cheaply, see `tech-env.md`): (1) the launcher, given a
launch request, drives the MicroVM run operation and returns a run id + registry entry (**AWS client
mocked**; assert it's called with an image identifier, a region, an exec role); (2) the run's events —
**from a real local `sdharness` subprocess** (tiny intake, low `--max-turns`) — stream to the client and
render as turns/phases, and the durable `events.jsonl` replays after a disconnect (this check uses the
recorded sample run); (3) on completion the result (status + cost + milestones) is shown, the run is
listed with its **artifact pointer**, and the **`workspace.tar.gz` is retrievable** and unpacks to the
built deliverable; (4) **two runs launched together** each get their own isolated cell + artifact, and a
worker that never reports lands `FAILED` not stuck `RUNNING`; (5) **`sdharness compound`** on a retrieved
workspace lifts its `progress.md` Patterns into a local `agent-context/LESSONS.md`. **Never provisions a
live MicroVM** — fast, cheap, deterministic, runs anywhere.

**Tier 2 — one real MicroVM run (GATED; runs only when the live-MicroVM capability is enabled).** Bake a
customer MicroVM image (from the AL2023 base + the worker code artifact) and fire **one real MicroVM run**:
an actual Firecracker VM runs the real `sdharness` on a tiny intake, streams its events back over the
HTTPS endpoint to the same UI, and hands back a **retrievable `workspace.tar.gz`**; the launcher then ends
the VM. Done for Tier 2 = that one live run completes green and its artifact downloads. **This tier is
skipped (and the build stops green at Tier 1) whenever the capability is absent** — i.e. the MicroVM
role-ARN env vars aren't present (`FACTORY_EXEC_ROLE_ARN`/`FACTORY_BUILD_ROLE_ARN`) or the account isn't
entitled. **The signal is those env vars being present — there is no separate `LIVE_MICROVM` flag; don't
gate on one.** Detect the capability from the env-var presence and let the real API call confirm it;
never fail Tier 1 because Tier 2 can't run.

## Scope
- **In — Tier 1 (the distilled core, single-user, always-green):** the local factory's browser UI (launch
  form, live event stream, result view, floor/registry); a **launcher** that drives the MicroVM run
  lifecycle (run a VM, get an endpoint auth token, poll status, end the run — via the dedicated
  `lambda-microvms` client; confirm the exact operations from the service model in RESEARCH); a **worker**
  that runs the real installed `sdharness` CLI, streams its `--json` events out the endpoint, and
  **captures `/workspace` → `workspace.tar.gz`** on completion; **artifact retrieval** (a durable store —
  local FS or S3 — + a download route + a UI affordance); a **durable event log** (replayable after
  disconnect); a **run registry** with the record shape above; **concurrency** (N isolated runs on the
  floor) + a **status reaper**; and the **compound** step (`sdharness compound` → local
  `agent-context/LESSONS.md`, staged into the next run). Tier-1 event source = a **real local `sdharness`
  subprocess** (the factory consumes the installed kit); only the AWS client is mocked.
- **In — Tier 2 (gated live rung):** bake a customer **MicroVM image** (base AL2023 + a **build role** +
  the worker **code artifact in S3**), poll the build to ready, then drive **one real MicroVM run** with
  that image + the **MicroVM execution role** — a genuine Firecracker VM runs `sdharness` in the cloud.
  Capability-gated (see Done= Tier 2); skipped cleanly when unentitled. (Take the exact bake/run
  operations, image recipe, and IAM from the MicroVM docs read in RESEARCH — see `tech-env.md`.)
- **Out (deferred — the *hosted* factory):** multi-user auth / team scoping; the **team-wide, auto-curated
  shared knowledge base** (semantic injection + an auto-curator + promotion-MRs) — the mini version's
  compounding is deliberately *local + human-reviewed*; scheduling; a conductor/pipeline; a second
  interactive substrate; managed dashboards. Name these "the hosted factory," don't build them.

## Success bar & non-negotiables
- **Success looks like:** the same browser experience as the local mini-factory, but each run executes in
  an isolated cloud MicroVM, streams back, and — the factory difference — **you can download what it
  built**, run **several at once**, and each run **feeds the next** via a local compounding loop.
- **Non-negotiables (the factory core):**
  - **Artifact retrieval is not optional** — a run that finishes without a retrievable `workspace.tar.gz`
    fails the bar. "Watch it run" isn't enough; you must be able to collect the output.
  - **Durable, replayable events** — the event log survives a client disconnect (persisted, not
    stream-only).
  - **Concurrency + isolation** — 2+ runs execute as independent cells with independent artifacts.
  - **Compounding is local + human-reviewed** — `sdharness compound` into a local `agent-context/`,
    surface the diff; never an auto-promoted team KB.
- **Non-negotiables:**
  - **Consume the harness, don't re-implement it.** The MicroVM worker runs the real installed
    `sdharness` CLI (`sdharness run … --json`) and forwards its `events.jsonl`. NEVER re-author the
    loop, gates, methods, or the event schema — those live in the kit. (Same rule the local factory and
    the production factory enforce.)
  - **Reuse the local factory's frontend** — this is a runner swap, not a rewrite. The launch → stream
    → result → registry UX carries over; only the backend that executes a run changes.
  - **Region-agnostic** — never hardcode a region. Derive it (the launcher passes it; the image reads
    it from its runtime env) so the same build works in any Bedrock-Claude region (the workshop runs in
    **us-west-2**).
  - **No secrets in the image** — Bedrock access comes from the MicroVM's execution role, not baked
    keys. Preserve the harness's **event vocabulary** in the UI.

## Open questions
- Registry store: keep the local JSON/SQLite, or graduate to DynamoDB? (RESEARCH decides; either proves
  the point.)
- Event egress from the MicroVM: stream the worker's HTTP response body vs. SSE/WebSocket — and how to
  survive a client disconnect (see the transport caveat in `tech-env.md`).
- Tier-2 capability detection: how to tell if the live rung can run — **the signal is the presence of the
  provisioned role-ARN env vars (`FACTORY_EXEC_ROLE_ARN`/`FACTORY_BUILD_ROLE_ARN`), NOT a separate
  `LIVE_MICROVM` flag** (there is none — don't invent one). The detection MUST be graceful (Tier 1 stays
  green when those env vars are absent) **and must not *false-skip* a rung that would work**: gate on the
  env-var presence, then let the real bake/run call be the authority (attempt-and-catch `AccessDenied`).
  See `LESSONS.md` for the IAM footguns that make a naïve pre-check false-skip.

## Not in this bundle (a further rung)
Multi-user **hosting** — the SPA on **S3 + CloudFront** with **Cognito** auth and a multi-tenant API — is
the *next* graduation, built as a separate brownfield bundle (`mini-factory-aws-hosted`) on your own
account. It needs broad resource-creation IAM the workshop sandbox intentionally withholds, so it is NOT
part of this bundle. Keep this factory **single-user, IDE-run**; name hosting as "the hosted factory,"
don't build it here.
