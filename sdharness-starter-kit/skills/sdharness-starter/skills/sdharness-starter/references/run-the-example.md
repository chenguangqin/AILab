# Level 100 — Run the example (concierge steps)

Goal: get the user to a **green end-to-end run** of the bake-like-a-pro example, then show them the
result. Do this before explaining internals.

## 1. Verify prerequisites (before anything else)

- **Python 3.11+** — `python3 --version`.
- **uv** (recommended) — `uv --version`; if missing, `curl -LsSf https://astral.sh/uv/install.sh | sh`.
- **Claude Code CLI** on PATH — `which claude`; if missing, `npm install -g @anthropic-ai/claude-code`.
- **Node** (the worked example builds a Vite site) — `node --version`.
- **AWS credentials with Bedrock access** — this kit is Bedrock-only. `aws sts get-caller-identity`
  should succeed for the profile you'll use.

## 2. Install + configure

```bash
uv venv && uv pip install -e ".[dev]"     # or: pip install -e ".[dev]"
cp .env.example .env
$EDITOR .env    # AWS_PROFILE, ANTHROPIC_MODEL=global.anthropic.claude-opus-4-8 (region-agnostic — uses your ambient AWS region)
```

Sanity-check the CLI resolves: `sdharness methods` and `sdharness strategies` should list `loop` and
`loop-autopilot`.

## 3. Run the worked example

```bash
sdharness run ./examples/bake-like-a-pro --method loop
```

Runs are always autonomous (the Pilot answers its own gates — no `--yolo` flag; it was removed). You
don't set a turn target: the run stops the moment the terminal gate goes green. `--max-turns` is an
optional runaway safety ceiling (default 100), not something you tune per run. Two more optional guards:
`--max-budget <USD>` (a hard cost ceiling — the run stops cleanly when agent + Pilot spend reaches it)
and `--fallback-model <model>` (auto-degrade on rate limits; defaults to `$ANTHROPIC_SMALL_FAST_MODEL`).
Both carry through `sdharness resume`.

What to expect (fully autonomous, ~tens of minutes; the Vite build + Playwright turns are slowest):
- Phases advance `RESEARCH → PLAN → BUILD → VERIFY` in `../sdharness-runs/bake-like-a-pro-<ts>/` (a sibling of the kit checkout; the banner prints the resolved path — override the base with `$SDHARNESS_RUNS_DIR`).
- The harness stages the authored inputs (`vision.md`, `tech-env.md`) at the run root and writes generated artifacts under `loop-docs/`; the generated site also lands at the run root.
- PLAN produces `loop-docs/architecture.md` + `loop-docs/design.md` + `goal.md` at the root (a milestone contract).
- BUILD checks off `goal.md` milestones one per turn, logging each to `loop-docs/progress.md`.
- VERIFY writes `loop-docs/integration-report.json`; the run completes only when it's genuinely green.
- Every event is also recorded to `loop-docs/events.jsonl` — the auditable run log.

For a deliberately fast smoke you *can* pass a low `--max-turns`, but the site example needs enough
turns to finish BUILD + VERIFY — so for a real green run, just omit it and let the default budget apply.

## 4. Interpret the result

- **Terminal recap** prints `complete: True/False`, the reason, and the turn count.
- **The integration report** (`loop-docs/integration-report.json`) is the proof: `status: "passed"`,
  `summary.all_seams_exercised: true`, every declared component exercised, every seam passed.
- **See the site:** `cd` into the run workspace and `npm run dev` (or `npm run build && npm run preview`).
- **Re-watch it:** `sdharness replay ../sdharness-runs/bake-like-a-pro-<ts>` re-renders the finished run from its
  `events.jsonl` — same banner, turns, and result card — without re-spending.

## Brownfield: add an AI chat agent on top of the bake site

A second worked example (`examples/bake-coach-agent`) is a **brownfield** run: it extends a
*completed* bake-like-a-pro site with a "Bake Coach" — a Python Strands agent on Bedrock AgentCore
plus a chat widget in the React frontend. Drive it when the user asks to "add a chat agent", "run the
bake coach", or "build on top of my bake site".

**Prerequisite: a completed bake-like-a-pro run to build on.** There is nothing to extend until that
greenfield run reached green `complete`. If they haven't run it, do the greenfield run above first.

Three deterministic steps (do NOT improvise these — copy, seed, run):

```bash
# 1. copy the intake bundle into position
cp -r examples/bake-coach-agent examples/my-bake-coach

# 2. SEED the workspace from the COMPLETED bake run (find the real dir first)
ls ../sdharness-runs/                                    # get the bake-like-a-pro-<ts> name
cp -r ../sdharness-runs/bake-like-a-pro-<ts>/ ../sdharness-runs/bake-coach-workspace/

# 3. run brownfield: point --workspace at the seeded dir
sdharness run ./examples/my-bake-coach --method loop --workspace ../sdharness-runs/bake-coach-workspace
```

Why each step matters:
- **Seeding is mandatory** — `--workspace` tells the run to build *in* the existing site. Skip the
  seed and RESEARCH has no site to audit; omit `--workspace` and it runs greenfield (builds a new site
  instead of extending the one they made). Both defeat the point of the module.
- The prior run's `loop-docs/` come along; the brownfield run archives them aside and writes fresh ones.
- This is the **longest** run (~40–70 min, full-stack + cross-language). The Pilot gates every turn.
- For a long run over a remote/detachable shell, launch it in a durable session so a dropped connection
  doesn't kill it (the mechanism is environment-specific — leave it to the host's own guidance).

**"How's my run going?"** — the run streams to a live TUI, but if it's detached or backgrounded,
report progress from its artifacts instead of re-launching: read `goal.md` (milestone `[ ]`→`[x]` ticks)
and `tail` the latest `loop-docs/progress.md` Outcome entry in the workspace dir. Never start a second
run to "check" — that clobbers the first.

Verify the result agentically when it's green: start the agent, run its smoke check, serve the site.
The **success proof** is the smoke check answering *"what is 15% of 240g?"* with **36** (proves the
agent called its recipe-scaling *tool*, not just chatted) plus a green `integration-report.json`. The
generated `README.md` records the backend dir, start command, and port — read it, don't guess (the run
picks a reliable start command and a free port, avoiding any port already in use in the environment).

## 5. Troubleshooting

- **`harness: command not found`** → the install step didn't run in this environment; re-run step 2.
- **Model/auth error** → check `.env` (`CLAUDE_CODE_USE_BEDROCK=1`, `AWS_PROFILE`, `AWS_REGION`) and
  that the profile has Bedrock access to the configured `ANTHROPIC_MODEL`.
- **Run stops on a kill switch** (no-progress / repeated-error) → that's the safety net working;
  read the last few turns in `../sdharness-runs/<…>/loop-docs/progress.md`, fix the blocker, and re-run.
- **Interrupted** (Ctrl-C, crash, transient model stall) → **`sdharness resume ../sdharness-runs/bake-like-a-pro-<ts>`**
  continues it in place: it reconstructs turn + cost from `events.jsonl`, rolls back to the last clean
  turn checkpoint, and picks up on the first unchecked `goal.md` milestone (no need to start over).

Next: the user understands *that* it works — offer **Level 200** (`references/understand-the-architecture.md`)
to explain *why*.
