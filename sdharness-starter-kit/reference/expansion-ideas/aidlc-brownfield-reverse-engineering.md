# AI-DLC Brownfield Reverse Engineering — Playbook

> The workflow that produced the reverse-engineering docs in this directory. Companion reads:
> [Harness Engineering](../../docs/concepts/harness-engineering.md) ·
> [Mental Model](../../docs/concepts/mental-model.md).

## What this is

**AI-DLC** (AI-Driven Life Cycle, [awslabs/aidlc-workflows](https://github.com/awslabs/aidlc-workflows))
is an agent-agnostic *steering framework* — a set of rules that override the coding agent's default
behavior and drive it through three phases: **Inception → Construction → Operations**. It is one
concrete *method* you can run inside a harness (see
[Harness Engineering](../../docs/concepts/harness-engineering.md)).

Its **brownfield reverse-engineering** entry point is what generated the sibling docs here: point it
at an existing codebase and it produces a structured understanding of the system *before* any change
is planned. The run captured here used AI-DLC **v1.0.1**. You can run the same workflow on your own
harness as it grows — or on any reference implementation you want to mine — to keep an up-to-date
"what does a mature harness look like" exhibit of your own.

## When it triggers (brownfield vs. greenfield)

AI-DLC begins Inception by running **workspace detection**:

- **Existing code present → brownfield →** route to **reverse engineering**.
- **Empty workspace → greenfield →** skip RE, go straight to Requirements Analysis.

Rerun logic: if current RE artifacts already exist they are loaded and RE is skipped; they
regenerate only if stale relative to the code, or if you explicitly ask for reanalysis.

## The 13-step reverse-engineering process

From the AI-DLC v1.0.1 `inception/reverse-engineering.md` rule spec:

**Discovery (1–6):**
1. Multi-package workspace scan across all package types
2. Business-context comprehension + transaction identification
3. Infrastructure-layer detection (CDK, Terraform, CloudFormation)
4. Build-system analysis (Brazil, Maven, Gradle, npm, uv)
5. Service-architecture mapping (Lambda, containers, APIs, datastores)
6. Code-quality evaluation across languages/frameworks

**Documentation generation (7–10):**
7. Business overview + context diagrams
8. Architecture docs (system diagrams, data flows)
9. Code-structure inventory (design patterns, dependencies)
10. API documentation (REST + internal interfaces)

**Completion (11–13):**
11. Technology-stack catalog
12. Dependencies map (internal + external)
13. Code-quality assessment + technical-debt identification

## The 8 artifacts

Written to an `aidlc-docs/inception/reverse-engineering/` directory — the eight sibling files in
this folder are exactly that output:

`business-overview.md` · `architecture.md` · `code-structure.md` · `api-documentation.md` ·
`component-inventory.md` · `technology-stack.md` · `dependencies.md` · `code-quality-assessment.md`
(plus AI-DLC state/metadata in `aidlc-state.md` and `audit.md`, and a `reverse-engineering-timestamp.md`
run record — see the one in this directory for a worked freshness note).

## The mandatory approval gate

RE ends with a completion summary and a hard gate: **"Do not proceed until the user explicitly
approves."** This is the human decision point — you review the reverse-engineered understanding
before AI-DLC uses it as the foundation for Requirements Analysis and design. It's the same
harness-engineering principle the kit teaches (gated autonomy): the human stays on the *decision*,
not on every step.

## Running it yourself

The workflow is **agent-portable**: the rules are plain Markdown that override a coding agent's
default behavior, and resolve their rule-details directory per agent (`.kiro/aws-aidlc-rule-details/`
for Kiro, `.aidlc-rule-details/` for Claude Code, `.amazonq/` for Amazon Q). To run it on a codebase
you want to understand — your own harness as it grows, or another reference implementation:

1. Get the AI-DLC v1.0.1 rules ([awslabs/aidlc-workflows](https://github.com/awslabs/aidlc-workflows))
   and place them where your agent loads steering rules.
2. Point the agent at a **read-only clone** of the target and prompt: *"Using AI-DLC, reverse
   engineer the codebase in `<path>`."*
3. Let the 13 steps run, then **review at the approval gate** before using the output.

Because RE is read-only and gated, it's a low-risk, high-value first touch on an unfamiliar or
legacy codebase — and a repeatable way to keep your own "what does a mature harness look like"
exhibit current as your fork grows. The concierge skill's **Level 400 (GROW)** rung points here.
