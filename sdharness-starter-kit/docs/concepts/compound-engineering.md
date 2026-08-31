# The Compounding Cycle

> Part of **SD Harness**. Companion reads: [Mental Model](mental-model.md) · [Harness Engineering](harness-engineering.md) · [Loop Engineering](loop-engineering.md).  ·  **Level 200**

## The idea: make every run improve the next

A one-off agent run is disposable — you get code and throw away everything you learned getting it.
The **compounding cycle** is the opposite: *each unit of engineering work should make the next one
easier, faster, and more reliable* — so leverage accumulates instead of tech debt. The mechanism is a
**write-after / read-before** cycle (learnings recorded after a run are read before the next, mapping
directly onto the SD Loop plus `sdharness compound`); the principle is treating **knowledge as a
first-class artifact of the harness** — versioned, agent-readable, reused — not tribal memory in one
engineer's head.

## Three kinds of durable knowledge

SD Harness stages three seed files from `agent-context/` into every run, each read at a different
moment:

| File | What it captures | When it's read |
|------|------------------|----------------|
| `LESSONS.md` | Build-failure → fix patterns, as **Trigger / Symptom / Fix** entries | by the coding agent, before design + code |
| `QUALITY.md` | What "good" means for your team | by the coding agent (and the reviewer) |
| `STEERING_PLAYBOOK.md` | Steering tactics that worked | by the **Pilot**, during steering |

A real `LESSONS.md` entry is concrete enough to *prevent* the next occurrence — "add a test, update
a rule" as a durable artifact rather than a one-off fix (the "retrospectives-as-code" pattern):

> **Prove the wiring, not just the parts**
> **Trigger:** A multi-component design where each component has unit tests.
> **Symptom:** Every unit test passes; the system still fails because A was never wired to B.
> **Fix:** In PLAN name every cross-component seam and add an integration test; in VERIFY exercise
> every seam with cited evidence.

## The maturity ramp — what the kit ships vs. what you grow into

Compounding isn't all-or-nothing; it's a ladder. **The kit ships the first two rungs as real code**
and documents the rest as extensions (the reference implementation is the full `sdharness`). Climb
only as far as your use case needs — a fork that stops at Stage 2 is still compounding.

| Stage | What it is | In this kit? |
|-------|-----------|--------------|
| **1. Curated seed + read** | `agent-context/` staged into every run; the agent reads it before acting | ✅ **Ships** (`loop.py:stage_workspace`, turn-1 prompt) |
| **2. Agentic curation (default)** | `sdharness compound <run-dir>` — a read-only curator agent proposes a rubric-scored diff (semantic dedup · merge/refine · quality-gate · **tool/doc-first gate** · route to LESSONS/QUALITY/STEERING_PLAYBOOK · flag unverified claims); the human approves, the CLI writes. This is the default when Bedrock creds are present. | ✅ **Ships** (`harness/compound_agentic.py`) |
| **2b. Deterministic fallback** | `sdharness compound <run-dir> --deterministic` (also the automatic offline fallback) promotes a run's `progress.md ## Patterns` into `LESSONS.md` by title-dedup only — no model, credential-free. | ✅ **Ships** (`harness/compound.py`) |
| **3. Relevance-filtered injection** | Tag lessons by keyword; inject only those relevant to the method/phase within a char budget (avoids "context rot") | ⬛ Extension |
| **4. Automatic eval write-back** | An evaluator scores the run and *auto-appends* extracted lessons/quality after each run | ⬛ Extension |
| **5. Personal ↔ shared split** | Per-user writable copy seeded from the repo seed; promote personal lessons to the team via review (MR/PR) | ⬛ Extension (docs below) |
| **6. Repo-level reuse** | Sanitize a finished project into a distributable reference architecture | ⬛ Extension |

> **Why relevance-filtering (Stage 3) matters:** context is finite and recall degrades as the window
> grows ("context rot," per Anthropic/LangChain context-engineering work), so a mature harness
> surfaces *only relevant* lessons — progressive/just-in-time disclosure — rather than pasting a
> growing `LESSONS.md` into every prompt. The kit stages the whole (small) seed today; a fork adds
> tagging + a budget when the seed gets large. See [customize.md](../customize.md).

## The flywheel (and which arrows the kit automates)

```
        run a method
            │
            ▼
   capture what broke / what "good" looked like   → agent logs to progress.md ## Patterns  [automated, in-run]
            │
            ▼
   sdharness compound <run-dir>                    → promotes Patterns into LESSONS.md      [Stage 2: one command]
            │
   review the diff & commit; promote via MR        → curate into the shared seed            [manual — the curation gate]
            │
            ▼
   next run stages the seed and reads it first     → starts smarter                          [Stage 1: automated]
            │
            └────────────► (loop)
```

The `compound` + review step is deliberate, not a gap: **curation is the point.** Auto-
appending everything would drown the seed in noise; a human (or a review gate) keeps it a curated
baseline. Stage 4 automates the *extraction*, but a good setup still gates what reaches the shared seed.

**The curation hierarchy — prefer a tool/doc/skill; encode a lesson only for the residue.** Before a
fact becomes a durable lesson, ask: *can a doc, a tool the agent already has (WebFetch, boto3
introspection, a `--help`), or a skill supply it instead?* A durable-but-**documented** fact (an API
signature, a published IAM policy) doesn't belong in the seed — the agent should re-fetch it, not carry
a copy that silently drifts from the source. Only the **un-Googleable residue** — an undocumented
gotcha, a version/behavior trap you paid a failure to discover — earns a permanent lesson. The agentic
curator (default) enforces this at promotion time (its `documented-elsewhere` drop reason); it's the
same "lean direction, rich resources" discipline the intake follows, applied to knowledge.

## The team dimension: personal vs. shared (Stage 5)

The kit ships a **single repo-local seed** (`agent-context/`) that a team grows by committing
compounded lessons through **review (MR/PR)**. The advanced ramp splits it:

- **Personal (extension):** a per-user writable copy (e.g. under `~/.local/share/…`) seeded once from
  the repo seed; each run accumulates the individual's lessons privately.
- **Shared (deliberate):** promote a refined personal lesson into the checked-in seed via a merge
  request — so every teammate inherits it.

In the kit, `harness/config.py:agent_context_dir()` is the single seam a fork overrides to add the
personal layer. This mirrors how the full `sdharness` does it (per-user XDG copy + manual MR
promotion — it too leaves promotion human-gated).

## Where this sits on the maturity curve

Compounding grows *with* the tooling: **starter kit → sdharness → sdharness factory**. The kit is
the on-ramp (local seed + manual `compound`); the full `sdharness` adds relevance-filtered injection
and automatic eval write-back; the hosted **factory** adds a centralized shared knowledge base so
learnings compound across a whole team, not one repo. See the README's maturity-curve note.

## Advising a customer: standing up the compounding cycle

- [ ] **Make knowledge an artifact** — lessons/quality/steering as files in the repo, not chat history.
- [ ] **Structure lessons** (Trigger/Symptom/Fix) so they're actionable and dedup-able by title.
- [ ] **Close the loop cheaply first** — `sdharness compound` after good runs; review the diff.
- [ ] **Add relevance-filtering** (Stage 3) only when the seed grows large enough to bloat context.
- [ ] **Separate personal from shared** with a review gate before automating extraction.
- [ ] **Measure the flywheel** — does the same failure class recur run-over-run? If not, it's working.

Back to the kit: [README](../../README.md) · [How it works](../how-it-works.md) · [Customize](../customize.md).
