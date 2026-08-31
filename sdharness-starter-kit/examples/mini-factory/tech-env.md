# Technical Environment — Mini SD Harness Factory

## Summary
| Attribute | Value |
|---|---|
| Project type | Greenfield prototype — a small local control plane for `sdharness` |
| Language / runtime | Python 3.11+ (API + runner) · a **polished** browser UI (plain HTML/CSS/JS or a small framework — either is fine, but the craft bar applies regardless) |
| Package manager | uv (Python) · npm only if the UI needs it |
| Deploy target | **none (local only)** — runs on `localhost`, viewed in the browser |

## Frameworks & services
| Layer | Choice (directional) |
|---|---|
| API | A small Python web API (FastAPI, Starlette, or the stdlib — your call) exposing launch / list / get / stream-events |
| Run registry | Local — a JSON file or SQLite. No cloud database. |
| Runner | A subprocess that shells out to the installed **`sdharness`** CLI |
| Live events | Stream from the run's `loop-docs/events.jsonl` (tail the file) or the `sdharness run --json` stdout stream |
| UI | A **polished, responsive** browser app committed to the **"Lights-Out Factory Floor"** identity (see the craft bar in `vision.md`): `SD [ HARNESS ] FACTORY` wordmark, an **assembly line** of phase stations, an **andon stack-light** for GO/NO_GO, a live event stream that feels alive, a **floor of cells** run list, a result view. Built to `loop-docs/design.md` via the `frontend-design` skill. Not a "minimal" scaffold, and not a generic dark dashboard. |
| Design system | `loop-docs/design.md` — the structured design-token doc settled in PLAN; every view conforms to it (the cross-turn consistency anchor). For this identity it MUST define: a **palette** (near-black canvas; **sodium-amber** worklight as the one brand accent; **signal-cyan** for data; GO-green / NO_GO-red / warn-amber reserved for meaning; per-phase colors read from `run_config`); **typography** (monospace instrument voice, e.g. IBM Plex Mono, + a bolder display face for the wordmark/hero); spacing/radius/elevation; **motion** (station hand-off sweep, andon switch, live pulse, tabular-nums); and **component patterns** for the *station*, the *andon stack-light*, and the *machine cell* — plus a **blueprint-grid / machined** atmosphere. Color is only ever phase/status/brand — never decoration. |

## The `sdharness` boundary (authoritative — do NOT violate)
- **Consume `sdharness` as an installed CLI/library — never fork or re-implement it.** Launch runs with
  `sdharness run <example> --method <m> [--json] [--max-turns N]`; read the run's
  `loop-docs/events.jsonl` for the live stream. The loop, gates, methods, strategies, and the event
  schema are owned by the kit — the mini-factory only *drives* and *observes* them.
- This mirrors the real factory's defining rule (it imports sdharness as a pinned library and never
  forks it). It's the single most important constraint here.
- **The event log is the source of truth; the UI formats it.** `events.jsonl` carries cost at full
  4-decimal precision (`total_cost_usd`/`cost_usd`, e.g. `1.7556`) on purpose — don't "fix" the data.
  Format at the presentation layer: costs as 2-decimal money (`$1.76`), turns as whole integers,
  milestones as `done/total`, live numeric readouts with `tabular-nums` so they don't jitter as they
  update. Never surface a raw multi-decimal float to a user, in any view.
- **Report the kit's REAL methods — never invent a catalog.** The kit ships exactly one method,
  **`loop`** (`sdharness methods --json` returns only that). If the UI's method picker is fed from a
  `methods` command, it must reflect what the kit actually exposes. Any test double / fixture player that
  stands in for `sdharness` must mirror reality — its `methods` output returns the real method(s)
  (`loop`), NOT plausible-sounding extras like `ebc`/`frontend`. Fabricated methods are a leftover stub
  (see Prohibitions) and mislead a user into picking a method that doesn't exist.

## Prohibitions
- **No cloud / AWS of any kind** — no Lambda, DynamoDB, Fargate, S3, CloudFront, Cognito, CDK. Local only.
- **No re-implementing the harness** — do not copy or re-author the loop, gates, phase logic, or the
  event format. Drive the real `sdharness` CLI.
- No multi-user auth, no scheduler, no knowledge curator (those are the real factory's job — out of scope).
- No leftover stubs, TODOs, or lorem-ipsum in shipped code.
- **User-facing microcopy is plain, not internal jargon.** Labels, hints, and empty-states a user reads
  must make sense to someone who has never seen this run's design docs — never leak internal
  decision-language (e.g. a method-picker hint saying "no invented catalog", or a "per D6" / gate /
  artifact reference). Say the user-meaningful thing ("Fed live from the kit."), not the build rationale.
- **No fabricated data anywhere it faces the user** — including a fixture/test double's `methods`
  catalog. A stand-in for `sdharness` mirrors the real CLI's output (the kit's one method, `loop`); it
  must not invent methods, phases, or events the kit doesn't emit.
- **No private or auth-gated links in shipped UI or docs.** This app may run **offline / air-gapped** for
  a stranger who cannot reach any private, corporate, or login-walled URL (an internal git host, wiki, or
  the workspace's own git remote). Do NOT hardcode such a URL anywhere a user sees it — a nav
  "Kit"/"Source" link, a footer, the README, or a help panel. Link only to something any user can open (a
  public URL, a relative in-app route, or the local docs), or **omit the link entirely**. When in doubt,
  no outbound link — a dead link reads as broken. (Do not name specific private hosts here either; keep
  shipped docs free of environment-internal identifiers.)

## Validation commands (these prove milestones and the VERIFY seam)
Keep VERIFY **fast and cheap** — never trigger a full ~20-minute run in the tests.
- Install deps — exit 0 (e.g. `uv pip install -e .` / `uv sync`).
- Start the API locally — a `GET` health/list endpoint returns 200.
- **The end-to-end seam**, proven with a **pre-recorded `events.jsonl` fixture** (or a tiny run with a
  very low `--max-turns`) so it's fast: a scripted / Playwright check asserts
  - launching a run returns a **run id** and creates a registry entry;
  - the run's events **stream** to the client and render as turns/phases (from the fixture or tiny run);
  - on completion the **result** (status + cost + milestones) is shown and the run appears in the list.
  - **the UI renders at phone / tablet / desktop widths** (~375 / 768 / 1440px) with no broken layout,
    no horizontal scroll, and navigation that collapses on small screens — the responsive bar from
    `vision.md`, proven, not assumed.
- Prefer a small `e2e` check (Playwright, or a script hitting the API + a served page) over unit tests
  alone. A Playwright check that screenshots the three viewports doubles as the responsive-bar evidence.

## Notes for running inside a browser IDE
- A hosted IDE may serve the dev/preview server under a sub-path proxy. Keep any web-UI config
  environment-agnostic: take the base path from an env var (default `/`) rather than hardcoding a host
  path, and bind the server so a proxied host is accepted. Title-but-blank-body means the base path and
  serving path disagree.
