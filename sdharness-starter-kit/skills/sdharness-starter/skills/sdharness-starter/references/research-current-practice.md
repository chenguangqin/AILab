# RESEARCH — keep the kit current at adoption time

Goal: before a team invests in customizing or growing the kit, help them **reconcile what the kit
ships against current practice** — so their fork starts from where the field is *now*, not from the
snapshot the kit was written at. This is the same anti-staleness discipline the bundled `reference/expansion-ideas/` docs apply to a fully-grown harness, turned on the kit itself.

This is **directional**, not a checklist to execute verbatim. Point the way; let the user and their
agent do the reading and the judging.

## Why this rung exists

The kit's concepts (`docs/concepts/harness-engineering.md`, `loop-engineering.md`,
`compound-engineering.md`) were written at a point in time. Between authoring and a team's adoption,
the field moves — new agent-SDK capabilities, new evaluation patterns, new memory/knowledge designs,
new thinking on autonomy. A fork that starts from a frozen snapshot inherits that staleness. A short
research pass closes the gap before any code is written.

## How to run it (with the coding agent's web tools)

Have the agent pull **current** practice on the three axes the kit is built on, then reconcile each
finding against a specific kit seam. Prefer **primary / official sources**, cite them, and don't
over-claim — the kit's own values.

Suggested sources to sweep (not exhaustive; find what's current):
- **Harness engineering / effective agents** — Anthropic's building-effective-agents, context
  engineering, and hooks/tool-use guidance; the Claude Agent SDK docs (the kit's inner harness).
- **Loop engineering** — orchestration/eval patterns (LLM-as-judge, structured verdicts), agent
  frameworks (Strands, LangGraph), and write-ups on long-running autonomous runs (Cognition/Devin).
- **The compounding cycle** — agent memory / self-improving agents, evaluation-driven improvement,
  and knowledge-base-before-acting patterns (and the broader "compound engineering" writing this
  idea travels under).
- **AWS AI-DLC** — the AIDLC workflows the bundled RE playbook uses, for the methodology direction.

## The AI Dark Factory direction (the "why grow")

Frame the research on an **autonomy continuum**, not a feature checklist. The north star is the
**AI Dark Factory**: an autonomous software factory where deterministic, harness-owned enforcement
replaces human oversight *inside* the turn loop, so humans supervise *outcomes at gates* rather than
every step. The kit's `docs/concepts/harness-engineering.md` frames the same progression
(reviewer → decision-maker → supervisor).

Place both the current field *and* the team's own harness on that continuum. That gives GROW
(Level 400) a **direction of travel**, and lets the team choose *how far* along it their use case
actually needs to go — some products want a supervised factory; many want a strong reviewer-in-the-loop
and no more.

## Output — an advisory `research-notes.md`

Write a short, **dated** `research-notes.md` in the user's fork. Keep it advisory and human-reviewed —
**never auto-apply** findings to the harness. Suggested shape:

```markdown
# Research notes — <date>

## Deltas since the kit was written
- <finding> — source: <primary URL> — maps to kit seam: <file/concept> — worth folding in? <y/n + why>

## Autonomy read
- Where the current field sits on the reviewer→decision-maker→supervisor continuum.
- Where THIS team's use case needs to sit (and why not further).

## Candidate changes for CUSTOMIZE / GROW
- <ranked, each tied to a seam and a source>
```

Then feed the candidates into **Level 300 (CUSTOMIZE)** for in-kit changes and **Level 400 (GROW)**
for growing past the kit — where they get weighed against the expansion-ideas catalog's proven options.

## Operating rules for this rung

- **Advisory only.** Research informs decisions; the human decides. Nothing here edits the harness.
- **Cite primary sources.** Official docs over blog summaries; note dates (the field moves fast).
- **Reconcile, don't collect.** Every finding must map to a kit seam and answer "fold in? why?" — a
  pile of links isn't the deliverable.
- **Right-size autonomy.** More autonomy is a *choice tied to the use case*, not a goal in itself.
