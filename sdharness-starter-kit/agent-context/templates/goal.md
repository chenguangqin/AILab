<!--
TEMPLATE — goal.md (the executable contract the SD Loop drives in BUILD).
Usually the agent WRITES this in the PLAN phase from vision.md + architecture.md;
provide it yourself only if you want to pin the milestones. The harness considers
BUILD complete only when NO `- [ ]` remains and progress.md exists.
-->

# Goal: <one line — what this delivers>

## Goal
<one paragraph — what "done" means, as observable end-to-end behavior>

## Scope
- In: <the slices in this contract>
- Out: <deferred>

## Preconditions
<what must be true before certain milestones — e.g. a verified target before an
irreversible operation. Often "none" for a local build.>

## Milestones
<!-- Ordered checklist. Each item states its OWN validation — the command/test/
artifact that proves it done. The FIRST milestone scaffolds the project. -->
- [ ] **M1 — Scaffold** — <create the project skeleton>. Validation: <build/command exits 0>.
- [ ] **M2 — <core logic>** — <implement the engine>. Validation: <tests pass, N cases>.
- [ ] **M3 — <interface/wire-up>** — <connect the pieces>. Validation: <end-to-end call returns correct output>.
- [ ] **M4 — Tests & README** — <coverage + how-to-run>. Validation: <test suite green; a clean checkout runs it>.

## Validation
<how the overall goal is verified end-to-end — becomes the VERIFY integration tests>

## Status
Not started.

## Decisions
<choices made and why>

## Open Questions
<unresolved uncertainties / blockers>
