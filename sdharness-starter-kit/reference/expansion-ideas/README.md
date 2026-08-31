# Reverse-Engineering Artifacts — one mature harness, as a worked example

This directory is a **reference exhibit**: the output of an AI-DLC **inception reverse-engineering**
pass (the 13-step v1.0.1 workflow, see the co-located
[`aidlc-brownfield-reverse-engineering.md`](aidlc-brownfield-reverse-engineering.md) playbook) run
against the *full, production* harness this starter kit was distilled from. It shows what a mature
harness looks like once it has grown well past the teachable core — a catalog of proven options to
draw on as you grow your own.

> **Bridge note — this is an example, not a blueprint.** These docs describe a *full* production
> harness. What you have is the distilled ~2,000-LOC teachable subset (the seed). Treat everything
> here as an *illustrative catalog of proven options* to borrow ideas from as you grow your own
> harness — **not** a spec to replicate, and **not** a mandate to converge on the upstream tool.
> Your own requirements (and your RESEARCH into current practice — see the concierge skill's Level
> 400) decide what to add; this just shows one way each capability was solved.

> **Freshness.** Captured **2026-07-06**. The harness ecosystem moves fast, so a reverse-engineered
> snapshot drifts as the source evolves. If you have access to a harness codebase you want to mine
> this way (yours as it grows, or another reference implementation), the co-located playbook walks
> the same 13-step workflow: point it at a read-only clone, record the commit, and regenerate the 8
> artifacts below. `reverse-engineering-timestamp.md` records the run metadata + what changed since
> the prior snapshot — a template for your own freshness notes.

## The 8 artifacts

| Artifact | What it covers |
|----------|----------------|
| [`business-overview.md`](business-overview.md) | Business context, the value proposition (reviewer → decision-maker), the transactions the tool delivers, and a business dictionary. |
| [`architecture.md`](architecture.md) | System overview, the three seams (config-over-code, agent abstraction, event-driven), architecture + sequence diagrams, integration points, infrastructure. |
| [`code-structure.md`](code-structure.md) | Build system, repo layout, key classes/modules, design patterns, critical dependencies. |
| [`api-documentation.md`](api-documentation.md) | The CLI command surface (public API), internal Python protocols, the local dashboard HTTP+SSE / WebSocket interfaces, and data models. |
| [`component-inventory.md`](component-inventory.md) | Every subpackage/module group, the declarative methods/strategies/prompts/templates, bundled resources, and test packages, with counts. |
| [`technology-stack.md`](technology-stack.md) | Languages, frameworks, AI models (via Bedrock), infra/cloud services, build + test tooling. |
| [`dependencies.md`](dependencies.md) | Internal layering (downward-only) and external runtime/dev/build dependencies with licenses. |
| [`code-quality-assessment.md`](code-quality-assessment.md) | Test coverage, quality indicators, technical debt, patterns/anti-patterns. |

Plus [`reverse-engineering-timestamp.md`](reverse-engineering-timestamp.md) — run metadata + the
commit-to-commit delta.
