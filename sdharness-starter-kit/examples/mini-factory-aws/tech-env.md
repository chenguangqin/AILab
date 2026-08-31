# Technical Environment — Mini SD Harness Factory on AWS (Lambda MicroVMs)

## Summary
| Attribute | Value |
|---|---|
| Project type | **Brownfield, two tiers** — evolve the local `mini-factory` control plane; swap its runner to Lambda MicroVMs (Tier 1 always-green; Tier 2 one gated live run) |
| Language / runtime | Python 3.11+ (launcher + API) · Node (the MicroVM worker) · the existing browser UI |
| Package manager | uv (Python) · npm (worker + any UI deps) |
| Deploy target | **AWS Lambda MicroVMs** (the run sandbox) — region-agnostic; the workshop runs in **us-west-2** |
| AWS access | Tier 1: none beyond local (AWS client mocked). Tier 2 (gated): the `lambda-microvms` API + Bedrock + a MicroVM **execution role** + a **build role** |
| Tier 2 gating | Runs only when the live capability is present. **The signal IS the presence of the provisioned role-ARN env vars** — `FACTORY_EXEC_ROLE_ARN` + `FACTORY_BUILD_ROLE_ARN` (+ `FACTORY_ARTIFACT_BUCKET`), which the workshop CFN exports only when it provisioned the live infra. There is **no separate on/off flag** — do NOT invent a `LIVE_MICROVM`-style env. Gate on the env-var presence for the cheap check; **let the real API call be the authority** (attempt-and-catch `AccessDenied`). Tier 1 stays green when the env vars are absent. |

## Brownfield: start from the local mini-factory
This example **builds on top of a completed local `mini-factory` run** (same pattern as
`bake-coach-agent` building on the bake site). Before running:
```bash
# 1. build the local mini-factory first (if you haven't):  sdharness run ./examples/mini-factory --method loop
#    (its workspace lands in the sibling ../sdharness-runs/mini-factory-<timestamp>/)
# 2. seed THIS run's workspace with that finished control plane:
cp -r ../sdharness-runs/mini-factory-<timestamp>/ ../sdharness-runs/mini-factory-aws-workspace/
# 3. run this example ON TOP of it:
sdharness run ./examples/mini-factory-aws --method loop --workspace ../sdharness-runs/mini-factory-aws-workspace
```
RESEARCH audits the existing launch/stream/result/registry frontend; PLAN/BUILD replace the
subprocess runner with the MicroVM launcher + image + worker, keeping the UI.

**Two tiers = one launcher, verified two ways** (not two code paths): Tier 1 verifies the launcher
cheaply on any account (mocked `lambda-microvms` client + a recorded fixture) and is always-green;
Tier 2, when the live capability is armed, fires that *same* launcher against the real service once.
They run in sequence — Tier 1 always, then Tier 2 if capable.

## Frameworks & services (directional — confirm specifics against the docs)
| Layer | Choice |
|---|---|
| Frontend + control API | **Reuse the local mini-factory's** launch form, live event stream, result view, run list — including its **"Lights-Out Factory Floor"** design system (`loop-docs/design.md`) unchanged. The **floor-of-cells** run list is where MicroVM isolation + concurrency become visible: each isolated run is a machine cell, and the floor shows many running lights-out at once. |
| Runner (the swap) | A **launcher** that drives the MicroVM lifecycle: bake an image, run one VM per run, reach its endpoint with an auth token, end the run. Use the **dedicated `lambda-microvms` boto3 client** (the MicroVM operations live only there, not on the `lambda` client). **Introspect the service model for the exact operations + request shapes** (`boto3.client("lambda-microvms").meta.service_model` — list operation names, inspect input shapes) rather than assuming them; confirm the run-lifecycle calls (run, status, auth-token, end-of-run) and the bake calls (create-image, poll-build) from the docs below. **End a run with `SuspendMicrovm`** (the pay-per-session pause), not `TerminateMicrovm` — the participant-scoped caller role deliberately grants Suspend/Resume but **not** Terminate/Delete (least-privilege; hard teardown happens on event/account reclaim), so a launcher that calls `TerminateMicrovm` will hit AccessDenied. |
| Tier-1 event source (always-green) | The factory **consumes the installed `sdharness`**: Tier-1 verification runs the **real `sdharness` CLI as a local subprocess** (tiny intake, low `--max-turns`) and streams its genuine `events.jsonl` — the kit source is available so the worker *runs* it (never forks it). Only the AWS `lambda-microvms` client is mocked. The recorded sample run (`fixtures/events.jsonl`) covers disconnect-replay + tarball-shape + CI determinism. |
| Run sandbox (Tier 2, live) | A **customer MicroVM image** baked from an **S3 zip containing a `Dockerfile` + the worker app + `requirements.txt`** — Lambda runs the Dockerfile server-side (via the **build role**), calls the worker's readiness hook, and snapshots for sub-second boot. The worker runs `sdharness run <intake> --json` in `/workspace`, streams NDJSON out, and on completion **tars `/workspace` → `workspace.tar.gz`**. Take the base-image ARN, the Dockerfile base, the worker **port + lifecycle-hook contract**, the network-connector ARNs, and the auth-token/header shape **from the docs below** — they are the source of truth, not memory. |
| Artifact store + retrieval | A **durable store** for `events.jsonl` + `workspace.tar.gz` per run — **local filesystem** is fine for single-user (S3 is the production reference); a **download route** + a **UI "download artifact"** affordance on the result view / cell. This is the core feature that makes it a factory, not a demo. |
| Registry | Local JSON/SQLite (carried from mini-factory; DynamoDB is the production reference). Per-run record: `id, status (PENDING→RUNNING→SUCCEEDED/FAILED), cost, milestones, method, artifact pointer, error, createdAt`. Terminal status/cost/error come from the kit's own terminal `complete`/`error` event — do not reinvent. |
| Live + durable events | Stream the worker's `sdharness --json` NDJSON to the browser live, AND persist it to the store as a durable `events.jsonl` so a reconnect/replay works after a disconnect (not stream-only). |
| Concurrency / fleet | One MicroVM per run, each isolated in its own workspace; the floor lists N concurrent runs. A **status reaper** flips a run to `FAILED` if its worker never reports (VM died before boot), so nothing hangs in `RUNNING`. |
| Compounding | After a run's workspace is retrieved, run the kit's own **`sdharness compound <workspace>`** to lift its `progress.md ## Patterns` into a **local** `agent-context/LESSONS.md` (human-reviewable — surface the diff / support `--dry-run`); the next run stages that `agent-context/`. Local personal KB only — NOT a vector KB / auto-curator / team corpus (deferred). |

## Read the authoritative Lambda MicroVMs docs FIRST (do this in RESEARCH)

Lambda MicroVMs is a **newly-GA** service, so **do not assume the API, the image recipe, or the IAM
from memory** — the exact operation shapes, the Dockerfile base + build hooks, the worker port/hook
contract, the network connectors, and the least-privilege IAM are defined by the official docs. In
RESEARCH, read these and pin the specifics you'll build against into `research.md` (with the doc URL
and the date you read it):

- **Getting started** (Dockerfile → S3 → create-image → run → connect walkthrough) —
  https://docs.aws.amazon.com/lambda/latest/dg/microvms-getting-started.html
- **Images** (base images, build hooks, private-ECR) —
  https://docs.aws.amazon.com/lambda/latest/dg/microvms-images.html
- **Security / IAM** (build role, execution role, trust policies, least-privilege operator policy,
  resource-ARN formats) — https://docs.aws.amazon.com/lambda/latest/dg/microvms-security.html
- **How it works** (build lifecycle + states) —
  https://docs.aws.amazon.com/lambda/latest/dg/microvms-how-it-works.html
- **Monitoring** (build + runtime logs) —
  https://docs.aws.amazon.com/lambda/latest/dg/microvms-monitoring.html

Plus **introspect the boto3 service model** for exact request/response shapes rather than guessing:
`boto3.client("lambda-microvms").meta.service_model` (operation names + input/output shapes). If the
tooling has changed since these notes, **trust the docs + the live service model over this file** — and
note the delta in `research.md`. See `LESSONS.md` for the two IAM footguns the docs do *not* surface.

## The `sdharness` boundary (authoritative — do NOT violate)
- **Consume `sdharness` as an installed CLI/library — never fork or re-implement it.** The MicroVM
  worker launches runs with `sdharness run <example> --method <m> --json` and forwards the run's
  `events.jsonl`. The loop, gates, methods, strategies, and event schema are owned by the kit — the
  factory (local or cloud) only *drives* and *observes* them. This is the single most important
  constraint, and it's identical to the local mini-factory's rule.

## Prohibitions
- **No re-implementing the harness** — drive the real `sdharness` CLI inside the VM; don't copy the
  loop/gates/event format.
- **No rewriting the frontend** — reuse the local mini-factory's UI; this is a runner swap.
- **No hardcoded region** (derive it; `AWS_REGION` is reserved — set `AWS_DEFAULT_REGION` from the
  runtime env) and **no baked secrets** (Bedrock access comes from the MicroVM's execution role, IMDS;
  set `CLAUDE_CODE_USE_BEDROCK=1`. A model API key, if ever needed, is a Secrets Manager *reference*, never a value).
- **Set the Bedrock model env explicitly in the worker.** Inside the VM there is no interactive
  shell profile (`.bashrc` is never sourced), so `sdharness` would fall back to its built-in default
  model — which may not match the models the **execution role** is scoped to invoke, and the run then
  stalls on `InvokeModel` AccessDenied. Pass the model ids through the worker env (e.g. the
  Opus/Sonnet inference-profile ids the exec role allows), don't rely on an ambient default.
- **Degrade gracefully — never fail the build for a missing capability.** If the live rung can't run,
  stop green at Tier 1.
- No leftover stubs, TODOs, or lorem-ipsum in shipped code.
- **No private or auth-gated links in shipped UI or docs.** This app may run offline / air-gapped for a
  stranger who cannot reach any private, corporate, or login-walled URL (an internal git host, wiki, or
  the workspace's own git remote). Link only to something any user can open (a public URL, a relative
  in-app route, or the local docs), or **omit the link entirely**. This is a brownfield build — if the
  inherited frontend carries such a link, **remove it** as part of the graduation.
- **No fabricated data anywhere it faces the user** — including a fixture/test double's `methods` catalog.
  A stand-in for `sdharness` mirrors the real CLI's output (the kit's one method, `loop`); it must not
  invent methods, phases, or events the kit doesn't emit.
- **User-facing microcopy is plain, not internal jargon.** Labels, hints, and empty-states must make sense
  to someone who has never seen this run's design docs — never leak internal decision-language.
- **The event log is the source of truth; the UI formats it.** Costs render as 2-decimal money (`$1.76`),
  turns as whole integers, milestones as `done/total`, live numeric readouts with `tabular-nums`. Never
  surface a raw multi-decimal float to a user, in any view.

## Validation commands (these prove milestones and the VERIFY seam)

### Tier 1 — always runs, fast + cheap, NO live MicroVM (this is the required bar)
- Install deps — exit 0 (`uv pip install -e .` / `uv sync`; `npm ci` for the worker/UI).
- Start the launcher/API locally — a `GET` health/list endpoint returns 200.
- **Launcher unit test — AWS client MOCKED:** a launch request creates a registry entry + returns a run
  id; assert the launcher calls the run operation with an image identifier, a region, and an exec-role
  ARN, requests an auth token, and ends a run with the documented end-of-run call — all against a mocked
  `lambda-microvms` client, no real API call. (Confirm the exact operation names from the service model.)
- **End-to-end happy path — a REAL local `sdharness` subprocess:** run the installed `sdharness run
  <tiny-intake> --json` (very low `--max-turns`) as the worker, and assert its **genuine** events stream
  to the client and render as turns/phases, and the result (status + cost + milestones) shows + is listed.
- **Recorded sample run (`fixtures/events.jsonl`) covers what a subprocess can't cheaply prove:**
  - **Durable events — replay after disconnect:** persist the sample events, drop the "live" connection,
    assert a reconnect/replay reproduces the full stream from the stored `events.jsonl`.
  - **Artifact retrieval — `workspace.tar.gz` round-trip:** a sample tarball is stored, the download route
    returns it, and it **unpacks to the built deliverable** (assert a known file is present).
- **Concurrency — two launches:** 2 runs → two isolated registry entries + two independent artifacts, no
  cross-run interference; a run whose worker never reports is reaped to `FAILED` (not stuck `RUNNING`).
- **Compound — a pure unit test:** run `sdharness compound --deterministic` (or `compound_run`) on a
  `progress.md` with a `## Patterns` section containing **`### Title` blocks**; assert the titled patterns
  land in `agent-context/LESSONS.md` (title-deduped) and a second run stages that seed. No LLM, no network.

### Tier 2 — the gated live run (runs ONLY when the capability is present)
Guard the entire tier behind capability detection: gate on the cheap signal (`FACTORY_EXEC_ROLE_ARN` +
`FACTORY_BUILD_ROLE_ARN` present), then **let the real API call be the authority** — attempt the bake/run
and treat an `AccessDenied` as "capability absent". When present, follow the getting-started walkthrough
(read in RESEARCH): **bake** a customer image (create-image with the build role + the S3 code-zip → poll
the build to ready), fire **one real run** with the image + execution role + the documented network
connectors + an idle/max-duration policy so a hung VM can't burn cost, **reach the worker** over its HTTPS
endpoint with the auth token, stream the run's events back, assert a green `complete`, **download the
`workspace.tar.gz`**, then end the run. One real cloud run + one retrieved artifact = Tier 2 done.
**On a `CREATE_FAILED` bake, read the build log before changing anything** (see `LESSONS.md`) — a blind
re-bake spiral is the anti-pattern.

## Notes for running inside a browser IDE
- Keep the web UI env-agnostic: base path from an env var (default `/`), bind the server to accept a
  proxied host. Title-but-blank-body means the base path and serving path disagree.
