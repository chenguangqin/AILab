# Component Inventory

> SD Harness is a **single distributable Python package** (`sdharness`), not a multi-package monorepo. "Components" below are the package's internal subpackages/module groups plus the supporting repository directories. There are no separate infrastructure or client packages (the tool *generates* IaC for the projects it builds rather than shipping any).

## Application Package

- **`sdharness`** (the CLI orchestrator) — the entire application. Distributed as one wheel; console script `sdharness`.

### Application Component Groups (within `sdharness/`)

| Component | Path | Responsibility |
|-----------|------|----------------|
| CLI & dispatch | `__main__.py`, `commands.py` | Argument parsing, command handlers, dispatch. |
| Interactive TUI | `cli_ui/` (5 modules) | Rich guided mode: primitives, menus, confirm, scaffold, templates. |
| Workflow engine | `workflow.py`, `harness.py`, `workflow_setup.py`, `turn_helpers.py`, `post_construction.py` | Per-method turn loop, setup, completion, post-construction verify/eval. |
| Conductor | `conductor/` (`models`, `agent`, `state`, `driver`) | Agentic multi-method orchestration. |
| Pipeline | `pipeline/` (`models`, `adapter`, `orchestrator`) | Static DAG orchestration over Strands Graph. |
| Core abstractions | `core/` (16 modules) | Protocols, config loaders, review engine, phase authority, gates, agent factory, agent tools, MCP registry, knowledge, intent, drift, rubric, session store. |
| Sandboxes (agent adapters) | `sandboxes/` (`claude_code`, `kiro_cli`, `gemini_cli`, `codex`, `_acp_common`) | Coding-agent runtime adapters implementing `Sandbox`. |
| EventBus | `events/` (`schema`, `bus`) | Event-driven backbone, HITL signalling, persistence. |
| Review & agents | `reviewer.py`, `gates.py`, `agent.py` | Reviewer class/routing, stage manager/conflict resolution, Claude SDK turn exec. |
| Quality & enforcement | `verification.py`, `evaluation.py`, `scoring.py`, `preflight.py`, `scaffolding.py` | Build/lint/security, 7-dim scoring, reports, pre-run validation, completeness. |
| Observability | `dashboard.py`, `ws_server.py`, `cli_renderer.py`, `checkpoint.py`, `hooks.py`, `log.py`, `telemetry.py` | SSE dashboard, WebSocket bridge, terminal rendering, git checkpoints, SDK hooks, logging, telemetry. |
| Runtime & resources | `runtime.py`, `resources.py`, `models.py` | Config/.env/Bedrock/cost, bundled vs per-user resources, shared data models. |

## Configuration Components (declarative, bundled)

### Methods (`sdharness/methods/`) — 15
`aidlc`, `aidlc-lite`, `aidlc-v2`, `pdlc`, `frontend`, `webdesign`, `sdd`, `ebc`, `storytelling`, `brownfield`, `waf`, `loop`, `harvest-reusable-assets`, `html-mockup`, `raw`. Each is a directory of `method.json` + `system-prompt.md` (+ optional `eval_rubric.json` / state template). (`html-mockup` — a one-liner → 4-page clickable HTML mockup with a default-on post-build Playwright render-verify pass — was added in this cycle.)

### Strategies (`sdharness/strategies/`) — 14
`advisory-board`, `autopilot`, `aidlc-v2-orchestrator`, `assessment`, `ebc-autopilot`, `frontend-autopilot`, `harvest-autopilot`, `html-mockup-autopilot`, `loop-autopilot`, `sdd`, `sdd-autopilot`, `storytelling-autopilot`, `waf`, `webdesign-autopilot`. Each is a directory of `strategy.json` + reviewer/steering `.md` prompt files.

### Prompts (`sdharness/prompts/`) — 16
System prompts for the harness's own LLM roles: `conductor`, `evaluator`, `facilitator`, `pilot`, `pilot-answers`, `pilot-answers-task`, `reviewer-gate`, `reviewer-question`, `reviewer-sop`, `router`, `stage-manager`, `lesson-extractor`, `eval-lesson-extractor`, `quality-extractor`, `steering-lesson-extractor`, `steering-playbook-compactor`.

### Templates & rubrics
- `sdharness/templates/` — 9 project scaffold templates (JSON): `nx-fullstack`, `nx-website`, `nx-agent`, `frontend-minimal`, `harness-default`, `harness-browser`, `harness-coder`, `harness-container`, `harness-mcp`.
- `sdharness/eval_rubrics/base.json` — base evaluation rubric.

## Shared / Bundled Resource Components (repo root, force-included into wheel)

| Component | Path | Purpose |
|-----------|------|---------|
| Runtime config | `sdharness.json` | Models, review/eval/agent settings, pricing, dashboard port. |
| Agent-context seed | `agent-context/` | Read-only seed for CLAUDE.md, QUALITY.md, LESSONS.md, STEERING_PLAYBOOK.md, per-method rules, templates. |
| Coding-agent plugins | `plugins/` (38 dirs) | Skills/plugins staged into coding-agent workspaces per method. Includes **14 AWS core skills vendored from `aws/agent-toolkit-for-aws` (Apache-2.0)** — `aws-cdk`, `aws-cloudformation`, `aws-containers`, `aws-iam`, `aws-messaging-and-streaming`, `aws-observability`, `aws-serverless`, `aws-billing-and-cost-management`, `aws-blocks`, `aws-sdk-{js-v3,python,swift}-usage`, `amazon-bedrock`, `signing-in-to-aws` — plus the standalone `ai-plc` product-discovery skill and local method skills (aidlc, ebc, frontend, sdd, waf, html-mockup, ui-ux-pro-max, etc.). |
| Claude plugin marketplace | `.claude-plugin/marketplace.json` | Claude Code plugin marketplace manifest. |
| Env template | `.env.example` | Per-user AWS/Bedrock configuration template. |

## Test Package

- **`tests/`** — 65 test files (~13.4k LOC) + `conftest.py`. Covers methods, strategies, conductor, pipeline, gates, phase authority, reviewer, sandboxes, events, checkpoint, verification, evaluation, scaffolding completeness, I/O contract, MCP registry, capabilities resolution, and cross-method readiness invariants.
- **`eval/`** — evaluation harness (not unit tests): golden-case extraction/annotation scripts, `test-cases/`, `experiments/`, `results/`.

## Non-code / Supporting Directories

| Component | Path | Purpose |
|-----------|------|---------|
| Documentation | `docs/` (54 files, 30 top-level) | Architecture, review-system, conductor, pipelines, dashboard, evaluation, method-readiness, plugins, scaffolding, per-method docs, harness-engineering research, plus security-debt registers (`gate-bypass-bash-exploit.md`, `workspace-security-roadmap.md`). |
| Sample use cases | `sample-use-cases/` (10) | Demo intent projects (url-shortener, task-tracker, agentcore-chat, retail-storyboard, scientific-calculator-api, …). Not bundled. |
| Sample pipelines | `sample-pipelines/` (3) | `build-and-harden.json`, `fullstack-build.json`, `parallel-build.json`. Not bundled. |
| Scripts | `scripts/` | `setup-devdesk.sh`, `conduct-hasbro.py`, `spike-conductor.py`. |
| Assets | `assets/` | Architecture/title images. |

## Total Count

- **Application Packages**: 1 (`sdharness`), comprising ~12 internal component groups across 6 subpackages + ~30 top-level modules.
- **Infrastructure Packages**: 0 (IaC is generated for target projects, not shipped here).
- **Shared / Config Components**: 15 methods + 14 strategies + 16 prompts + 9 scaffold templates + bundled resources (`sdharness.json`, `agent-context/`, `plugins/` (38), `.claude-plugin/`, `.env.example`).
- **Test Packages**: 2 (`tests/` — 65 files; `eval/` harness).
- **Approximate size**: ~28,802 LOC package + ~13,404 LOC tests; ~149 Python files, ~503 Markdown files, ~122 JSON files (repo-wide, excluding `.git` / `.venv`).
