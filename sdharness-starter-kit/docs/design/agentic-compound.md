# Design — Agentic compounding (`sdharness compound --agentic`)

**Status:** ✅ SHIPPED (v0.2.0). Built as `harness/compound_agentic.py` + `sdharness compound --agentic`;
the deterministic `compound.py` stays the default/fallback. **Owner:** kit. **Relates to:**
`harness/compound.py`, `harness/compound_agentic.py`, `docs/concepts/compound-engineering.md`, the
`compound-your-runs` workshop module.

**As built:** a read-only curator agent (one-shot `query()` + schema-enforced `output_format`, reusing
the Pilot pattern in `steering.py`) returns a `Proposal` of per-candidate verdicts
(`promote`/`merge`/`skip`/`drop`) with `target_file` routing (LESSONS/QUALITY/STEERING_PLAYBOOK),
`rationale`, and `validation` (verified/unverified/n/a). The **CLI writes** the human-approved subset —
the agent never writes files. `--dry-run` shows the proposal and stops; otherwise a y/N gate precedes any
write. Falls back to the deterministic title-dedup path if the SDK/creds are unavailable. Tests use a
mocked `Proposal` (no live Bedrock). The validation field is the safeguard against compounding a WRONG
lesson (the `allowedHosts: 'all'` bug class). Open question #5 (default-on validation vs a `--validate`
sub-flag) deferred; the field is populated by the curator but validation is best-effort, not a separate
tool pass yet.

## Why

Today `sdharness compound` is the **entry rung**: deterministic, LLM-free, offline. It extracts
`### Title` blocks from a run's `progress.md` `## Patterns` and promotes new ones into
`agent-context/LESSONS.md`, deduped by **exact title string match**, human-gated via `--dry-run`. Its own
docstring names the next rung: *"an automatic, evaluator-driven extractor is the documented extension."*

The entry rung's weakness is **curation has no baseline**. The producer signal is only "the agent chose
to log this" (no quality bar); dedup is literal-string (near-duplicates slip through); and the human's
only tool is eyeballing a raw diff with no rubric. "What should I compound?" is answered by gut feel.
That's fine for a handful of patterns; it doesn't scale, and the E2E showed the module's payoff feels
thin. **Agentic compounding replaces gut-feel with a rubric-driven, reasoned proposal the human approves.**

This is a genuine capability beyond upstream sdharness (upstream is the same LLM-free title-dedup).

## Principle (do NOT break)

- **Curation stays a human gate.** The agent *proposes* a curated diff with reasons; the human approves,
  edits, or rejects. Never auto-merges to a shared corpus. `--dry-run` still shows the full proposal.
- **The LLM-free path stays the DEFAULT.** `sdharness compound` (no flag) is unchanged: offline,
  deterministic, free, CI-safe — the teachable entry rung. `--agentic` is the opt-in *grow* rung.
- **Consume the SDK the kit already uses.** Reuse `harness/sandbox.py`'s `ClaudeSDKClient` on Bedrock
  (same auth/model env as a run) — no new dependency, no new provider.

## Interface

```
sdharness compound <run-dir> [--dry-run]              # unchanged: deterministic title-dedup
sdharness compound <run-dir> --agentic [--dry-run]    # NEW: SDK-driven curation, human-gated
```

`--agentic` implies a Bedrock call (needs creds/model env like a run). Without `--dry-run` it still
requires the human to confirm before writing (print the proposal, prompt y/N) — the gate is not optional.

## What the agent does (5 capabilities)

Given (a) the run's extracted patterns and (b) the current seed corpus (`LESSONS.md`, `QUALITY.md`,
`STEERING_PLAYBOOK.md`), a **read-only curator agent** proposes a diff. Per candidate lesson:

1. **Semantic dedup** — is this already covered by an existing entry (not just exact title)? If yes →
   propose *skip* (or *merge*, see 2), citing the existing entry.
2. **Merge / refine** — if it's a more-specific instance of an existing lesson, propose folding it in
   (rewrite the existing entry to generalize), rather than adding a near-duplicate.
3. **Quality gate** — is this a *durable, reusable truth* or a one-off? Propose *promote* vs *drop*, with
   a one-line rationale. This is the rubric the human otherwise applies by gut.
4. **Route to seed file** — classify each: build-failure→fix pattern → `LESSONS.md`; a definition of
   "good"/quality bar → `QUALITY.md`; a Pilot/steering tactic → `STEERING_PLAYBOOK.md`.
5. **Validate the claim (quick research)** — sanity-check that the lesson is actually correct before it
   becomes durable guidance (e.g. a version-specific claim, an API name, a config value). Use the agent's
   web/doc tools where available; flag *unverified* claims rather than silently promoting them. (This is
   what would have caught the `allowedHosts: 'all'` / Vite-6 bug — a "validate before durable" step.)

**The rubric (the answer to "how do humans measure what to compound"):** promote a lesson only if it is
**durable** (true beyond this run) · **reusable** (a future run will hit it) · **non-redundant**
(semantically, vs the corpus) · **validated** (claim checks out, or flagged unverified) · **correctly
routed**. The agent applies this and *shows its verdict + reason per lesson*; the human reviews the
reasoned proposal instead of raw bullets.

## Output / human gate

The agent returns a **structured proposal** (not a blind write): for each candidate —
`{title, verdict: promote|merge|skip|drop, target_file, rationale, validation: verified|unverified|n/a,
proposed_text, merge_into?}`. The CLI renders it as a reviewable diff (grouped by target file, verdicts
labeled). `--dry-run` stops there. Otherwise: human confirms → apply the approved subset. The human can
edit/reject any item; nothing writes without confirmation.

## Implementation sketch

- New `compound_run_agentic(run_dir, dry_run, corpus_paths) -> Proposal` alongside the existing pure
  `compound_run` (keep the deterministic one intact as the fallback + the default).
- Reuse `sandbox.py`'s client factory; a **read-only** tool set (read the corpus + patterns; optional
  web/doc read for validation) — the agent proposes text, the CLI writes (agent never writes files
  directly, preserving the gate).
- Force **structured output** (a JSON schema for `Proposal`) so the CLI parses, not scrapes.
- Deterministic fallback: if the SDK/creds are unavailable, fall back to the LLM-free path with a notice.

## Tests

- Pure-path tests unchanged (regression: default behavior identical).
- Agentic path unit-tested with a **mocked** client returning a canned `Proposal` (no live Bedrock in
  CI) — assert routing, dedup-skip, merge, drop, and the human-gate (nothing written on `--dry-run` /
  without confirm). One optional live smoke behind a flag, never in the required suite (mirrors the
  mini-factory-aws Tier-1/Tier-2 split).

## Workshop / teaching fit

- The `compound-your-runs` module keeps teaching the **manual** rung first (curation is a human step).
- `--agentic` becomes a **Level-400 / "grow your harness"** beat: *"now let the agent propose the
  curation — semantic dedup, merge, quality-gate, route, validate — and you approve."* It extends the
  manual rung, doesn't replace it. Bridges to the deferred hosted auto-curator (Bedrock Managed-KB +
  DynamoDB-stream) that `mini-factory-aws` names as "the hosted factory."

## Open questions

- Confirmation UX for non-`--dry-run` agentic writes (per-item y/N vs approve-all vs edit-in-`$EDITOR`).
- Whether validation (capability 5) should be default-on for `--agentic` or its own `--validate` sub-flag
  (web/doc access may be unavailable offline).
- Upstream: propose as a feature to `mindhk/sdharness` too (it lacks this), or keep kit-only as a
  differentiator.
