# Iterating on an existing project — plan, review, build

> Companion to [How it works](how-it-works.md) and [Customize](customize.md). This is the workflow
> this fork adds for **brownfield** work: improving a codebase that already exists, with a **human
> review gate between PLAN and BUILD**. It was distilled from running the kit on a real project
> (a deployed AWS SAM app) for several rounds.

## The flow

```
intake dir (vision.md, tech-env.md, samples.md …)          ← you write it
        │
        ▼
sdharness run <intake> --method loop-plan --workspace <copy>   RESEARCH → PLAN, then STOP
        │
        ▼
review loop-docs/research.md, loop-docs/architecture.md, goal.md   ← you edit / decide
        │       (answer `## Questions for reviewer`, record decisions)
        ▼
sdharness run <copy> --method loop --in-place --skip-completed-phases   BUILD → VERIFY
        │       (stops early with "awaiting human review" if the agent hands off)
        ▼
review the diff, merge the code back into the real repo, deploy yourself
```

### 1. Make a working copy — don't run on the real repo

The harness treats the workspace as its own sandbox: it runs `git init`, commits and tags every turn
(`turn/<N>`), and `resume` does `git reset --hard` + `git clean -fd`. On a real repo that means a
nested git repo (if the project is a subdirectory), untracked files at risk, and harness files
(`CLAUDE.md`, `LESSONS.md`, `QUALITY.md`, `vision.md`, `goal.md`, `loop-docs/`) mixed into the project.

```bash
# a clean copy of the committed project (no .git, no build output)
git -C <repo> archive HEAD <subdir> | tar -x -C <copy> --strip-components=1
git -C <copy> init -q
git -C <copy> config user.name  "<name>"      # REQUIRED — see "Gotchas"
git -C <copy> config user.email "<email>"
```

### 2. Write the intake

`vision.md` (what / why / success bar / non-negotiables / open questions) and `tech-env.md` (stack,
hard constraints, **what the agent must never do** — e.g. no deploys, no writes to live cloud
resources). Templates: `agent-context/templates/`. For brownfield work, state the problems you see and
your hypotheses, and let RESEARCH verify them against the code. Put anything the reviewer must decide
under *Open questions*.

### 3. `loop-plan` — RESEARCH + PLAN only

```bash
uv run sdharness run <intake> --method loop-plan --workspace <copy> --max-turns 15 --max-budget 8
```

- Surveys the existing code first and cites file paths in `research.md`.
- Writes `architecture.md` (components, wiring, integration-test list) with a
  `## Questions for reviewer` section (plain bullets — `- [ ]` would block the gate), and `goal.md`
  (milestones, all unchecked).
- A gate blocks every write outside the harness artifacts until `.harness-build-unlocked` exists —
  a file the gate itself forbids writing, so the agent can't unlock BUILD. **Caveat:** gates only
  intercept Write/Edit tool calls, not shell redirects from Bash; check `git status` after the run.
- Run events go to `<copy>/loop-plan-docs/events.jsonl`; the artifacts go to `loop-docs/` so the
  `loop` method picks them up.

### 4. Review

Edit the three artifacts directly. Record your answers (e.g. a `## Reviewer Decisions` section in
`architecture.md`, `D<n> (reviewer)` entries in `goal.md` Decisions) and tighten milestones. Useful
milestone patterns that paid off:

- **Bounded iteration:** "at most N live eval runs; prompt changes must be general rules, never
  sample-specific hints; if the bar isn't met, stop and hand off."
- **Human-owned ground truth:** "never edit the eval annotations or loosen a check to make it pass —
  record the disagreement in Open Questions and stop." (Without this, an agent under pressure will
  quietly delete a failing annotation or relax a check.)
- **Inspect the real inputs:** for model-facing code, save the exact inputs the model saw (crops,
  prompts) and require the agent to open them before diagnosing a failure.

### 5. `loop` — BUILD + VERIFY, starting where the plan left off

```bash
uv run sdharness run <copy> --method loop --in-place --skip-completed-phases --max-budget 20
```

- `--skip-completed-phases` evaluates the phase gates **before turn 1** and starts at the first phase
  whose gate is not already satisfied. Without it, every run starts at RESEARCH and turn 2 runs PLAN,
  which re-authors — and overwrites — the reviewed `architecture.md` / `goal.md`.
- The same command continues a stopped run after you add or edit milestones (the first unchecked
  milestone in `goal.md` is next).

### 6. Human handoff — the run stops instead of idling

When the agent is blocked on a human decision (e.g. an iteration budget is exhausted), it records the
blocker in `goal.md` / `progress.md` and ends its message with `HANDOFF_TO_HUMAN` **on its own last
line**; the Pilot can do the same in its direction. The loop then stops with
`reason: awaiting human review` and the turn shows a yellow `HANDOFF`. A mere mention of the word
(e.g. "if the budget runs out, hand off") does not trigger it. Before this existed, a blocked run idled
until the "no files written for 4 turns" kill switch tripped. Configure per method with
`"handoff_signal"` in `method.json` (empty string disables).

### 7. Merge back and deploy — yourself

The copy has no remote; nothing is pushed. Copy back only code and tests (not `loop-docs/`,
`loop-plan-docs/`, `goal.md`, the intake, or the seeded `CLAUDE.md` / `LESSONS.md` / `QUALITY.md`),
re-run the project's tests in the real repo, commit, deploy.

## Gotchas we hit

| Symptom | Cause | Fix |
|---|---|---|
| `git log` in the workspace shows no commits; `resume` can't find `turn/<N>` | No git identity → every checkpoint commit fails silently (`allow_fail`) | `git -C <copy> config user.name/user.email` before the first run |
| The agent can't find a sample image / CSV the intake references | Staging copies only the method's named files and top-level `*.md` from the intake dir | Put non-`.md` assets directly in the workspace (or run `--in-place`) |
| An edited intake `.md` (other than vision/tech-env/goal) isn't picked up on re-run | Extra `*.md` files are staged only if absent in the workspace | Delete or overwrite the workspace copy |
| Updated `agent-context/LESSONS.md` doesn't reach an existing workspace | Seed files are staged only if absent | Delete the workspace copy of the seed file |
| Pilot keeps saying GO but nothing happens, then the kill switch | Run blocked on a human with no way to stop | Fixed by the handoff signal (§6) |
| Tests all pass, deployed Lambda fails with `No module named …` | Tests add module dirs to `sys.path`; the runtime imports `pkg.handler` from the package root | Require a test that imports every handler the way the runtime does |
| `--max-budget` hit mid-milestone | Opus as the coding agent is ~$1–3/turn | Size the budget to the milestone count; continue with the same command |

## Reading a run afterwards

- `uv run sdharness replay <copy>/loop-docs/events.jsonl` — re-renders the console exactly (pass the
  file path; a workspace path picks the first `*-docs/events.jsonl` alphabetically).
- Tool calls are logged as summaries only; full transcripts including tool output are in
  `~/.claude/projects/<workspace-path-with-dashes>/*.jsonl`.
- `git -C <copy> log --stat` / `git show turn/<N>` — what each turn changed.
- `loop-docs/progress.md` — the agent's own per-milestone log.
