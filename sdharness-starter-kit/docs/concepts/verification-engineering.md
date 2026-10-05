# Verification Engineering

> Part of **SD Harness**. Companion reads: [Loop Engineering](loop-engineering.md) · [Harness Engineering](harness-engineering.md) · [The Compounding Cycle](compound-engineering.md).  ·  **Level 200**

## The bottleneck moved again

AI made writing code fast, so the bottleneck moved from *writing* code to *trusting* it. A loop that
runs unattended for hours makes this sharper: every turn ends with "the box is checked because the
check passed" — so the loop is exactly as good as its checks. **Verification engineering** is the
discipline of designing those checks: what "correct" means, how it is measured, who may change the
measure, and what happens when the measure is uncertain.

[Loop engineering](loop-engineering.md) answers *when are we done?* structurally — an artifact
exists, a checklist is empty, a report says `passed`. That proves the **process** finished. It does
not prove the **result** is right. Closing that gap is domain work, and it is where most of the time
in a real brownfield run goes.

## A case study in seven failures

These all happened on one project — a photo-of-a-graded-exam → "wrong-answer notebook" recognition
pipeline built with the SD Loop over several rounds. None of them was a coding failure; every one was
a verification failure.

| What happened | What was really wrong |
|---|---|
| 230 tests green; the deployed Lambda failed on import | **Test environment ≠ runtime.** Every test put the module dir on `sys.path`; the runtime loads `pkg.handler` from the package root. |
| Under pressure to pass, the agent deleted a failing annotation and relaxed a figure check to "count only" | **The verified party could edit the verifier.** Ground truth wasn't owned by anyone. |
| The report said PASS while a recorded question had an empty stem and OCR typos | **Checks covered structure, not content.** |
| The eval passed once; the next day production missed a question the eval had caught | **One run proves nothing** for a stochastic system — and the model was sampling at temperature 1.0. |
| The agent concluded "the model can't see the strokes"; the crop had cut the mark off | **Diagnosis without looking at the actual inputs.** |
| The rule said a wrong-answer slash looks like `/` — the shape of an abbreviated tick | **The spec was wrong.** A perfect eval faithfully verifies a wrong spec. |
| Four rounds chasing 100% grading accuracy on 3 images | **The acceptance bar was wrong.** The right bar was "never wrong *silently*". |

## Six principles

### 1. Ground truth is human-owned — enforce it, don't ask for it

Annotations (`*.expected.json`), eval checks and acceptance thresholds belong to a human. A prompt
saying "don't edit the annotations" helps; a **gate** that blocks writes to them is better. When the
agent believes the ground truth is wrong, the correct move is to *record the disagreement and hand
off*, never to fix it. (In the kit: put the paths outside `always_allow` with a rule that can't be
satisfied, and use the `HANDOFF_TO_HUMAN` signal.)

### 2. Verify the way it runs

Prefer checks that exercise the real entry point: import handlers the way the runtime does, call the
real CLI, hit the real API shape, run the build the deploy uses. A unit suite that bends the
environment to make code importable can be 100% green over code that cannot start.

### 3. Measure distributions, not single runs

Anything with a model in it is a distribution. Run the eval N times; report the mean **and** per-item
consistency (which items flip between runs). Pin what can be pinned (temperature, seeds, model
version) and record what can't. An "unstable" list is often more actionable than an accuracy number.

### 4. Make failures diagnosable — keep the evidence

Save the intermediate artifacts a failure would be explained by: the exact images and prompts the
model saw, raw responses, per-stage outputs, per-run files. Require the agent to **open** them before
it names a cause. Most "model limitations" in the case study were pipeline bugs visible in the saved
inputs.

### 5. Verify the spec before verifying against it

The cheapest bug to fix is in the rule table. Before the loop builds evals, get a human to confirm
the spec on concrete examples — ideally by annotating real samples, which surfaces ambiguity
("is this stroke a slash or a tick?") that prose hides. Ambiguous spec + strict eval = confident
wrong code.

### 6. Accept imperfection, forbid silent failure

For perception, extraction and judgement tasks, 100% is the wrong bar. Better bars:

- an accuracy threshold with a **known-failures table** (every miss listed, with its evidence);
- **zero silent errors** in the dangerous direction (e.g. *no false recordings*), with uncertain cases
  routed to a human (`needsReview` + a reason);
- **stability** across runs.

Pair the bar with an **iteration budget** ("at most N eval cycles; general rules only, no
sample-specific prompt hints") so the loop can't overfit a tiny eval set or burn budget chasing noise.

## Where this lives in the harness

| Concern | Today in the kit | Natural extension |
|---|---|---|
| Process verification | Phase gates on disk artifacts (`phase_authority`), VERIFY integration report, Pilot review | — |
| Result verification | Whatever the method's prompts and the project's tests/evals do | Evals as first-class harness artifacts: dataset, runner, report schema |
| Ground-truth protection | Prompt rules | Gate rules that block writes to annotation paths |
| Stochastic systems | — | `--runs N` with consistency reports as a standard eval contract |
| Evidence | `events.jsonl`, per-turn git checkpoints | Per-stage model inputs/outputs saved and linked from reports |
| Escalation | `HANDOFF_TO_HUMAN`, kill switches | A reviewer UI over known failures and `needsReview` items |

The harness can make the loop *honest* — it cannot know what "correct" means for your domain. That
part is engineering work in its own right, and it compounds: a good eval set, a protected ground
truth and a diagnosable pipeline make every later iteration cheaper.

## Advising a customer: before the first unattended run

- [ ] **Write the acceptance bar first**, including what must never fail silently.
- [ ] **Annotate real samples with a human**; treat disagreements as spec bugs.
- [ ] **Protect the ground truth** with a gate, not only a prompt.
- [ ] **Verify through the real entry point** (runtime import, CLI, API).
- [ ] **Run evals N times**; pin temperature/model; report stability.
- [ ] **Save the evidence** each stage consumed and produced.
- [ ] **Budget the iterations** and hand off when the budget is spent.

Back to: [Loop Engineering](loop-engineering.md) · [The Compounding Cycle](compound-engineering.md).
