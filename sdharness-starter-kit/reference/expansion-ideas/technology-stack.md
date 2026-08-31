# Technology Stack

## Programming Languages

- **Python** — `>=3.11` (CI builds/tests on 3.12) — the entire orchestrator, CLI, tests, and eval harness (~149 `.py` files, ~28.8k package LOC).
- **TypeScript / TSX** — minor — small amounts in bundled plugins / UI assets (`.ts`, `.tsx`).
- **JavaScript** — minor — plugin/asset scripts.
- **HTML / CSS** — the dashboard UI (`sdharness/assets/dashboard.html`) and design-system plugin assets.
- **Markdown** — pervasive (~503 files) — system prompts, method/strategy prose, agent-context, docs, vendored skill definitions. Functionally significant: prompts and configs are *runtime inputs*, not just documentation.
- **Shell** — `scripts/setup-devdesk.sh` (bootstrap).

## Frameworks & Core Libraries

- **Strands Agents SDK** (`strands-agents >= 1.44.0`, `strands-agents-tools >= 0.8.1`) — the outer-harness (Pilot) agent framework: reviewers, facilitator, evaluator, steering, and conductor decision agents; Pipeline DAG via `GraphBuilder`/`Graph`.
- **Claude Agent SDK** (`claude-agent-sdk >= 0.2.105`) — drives Claude Code as the default inner-harness coding agent (persistent sessions, hooks, subagents).
- **Agent Communication Protocol** (`agent-client-protocol >= 0.10.1`) — drives non-Claude coding agents (Kiro CLI, Gemini CLI, Codex).
- **Model Context Protocol** (`mcp >= 1.28.0`) — attaches MCP tool servers (AWS Agent Toolkit, context7, nx-plugin-for-aws, Playwright) to reviewers and the coding agent. Specs are registered once in `core/mcp_registry.py` and referenced by strategy name.
- **Pydantic** (`pydantic`) — all data models, config schemas, and structured LLM output (project convention: no `@dataclass`).
- **Rich** (`rich`) — conversational terminal rendering (`cli_renderer.py`), tables, Live display.
- **Questionary** (`questionary`) + **prompt-toolkit** (`prompt-toolkit`) — interactive guided-mode prompts.
- **websockets** (`websockets`) — the WebSocket event/command bridge (`ws_server.py`).
- **botocore** (`botocore`) — AWS SDK core: boto session, Bedrock access, credential resolution, pricing.
- Standard library `asyncio` — the hand-rolled dashboard HTTP/SSE server and concurrency throughout.

## AI Models (via Amazon Bedrock)

Configured in `sdharness.json` (per-model pricing as of 2026-06-08, Bedrock global endpoint):
- **Coding agent (default)**: `global.anthropic.claude-opus-4-8` (overridable via `ANTHROPIC_MODEL`).
- **Reviewers / evaluator / steering / conductor**: `global.anthropic.claude-sonnet-4-6` (default review model), `max_tokens` 16384.
- **Fallback**: `claude-sonnet-4-6`. Fast/small ops: `claude-haiku-4-5`.
- **Multi-agent support**: also configures Kiro CLI (Claude Opus/Sonnet catalog, sub-catalog `default_model: claude-opus-4.7`), Gemini CLI (Gemini 3 Flash / 2.5 Pro/Flash), and Codex (GPT-5.x / gpt-oss) model catalogs.
- Coding agent routed through Bedrock via `CLAUDE_CODE_USE_BEDROCK=1`.

## Infrastructure & Cloud Services

- **Amazon Bedrock** — all model inference (region default `us-east-1`).
- **A managed agent-toolkit MCP** — reached over HTTPS, authenticated with cloud credentials (no local install).
- **A private package registry** — publish target for the built wheel (a hosted artifact repository).
- **AWS Price List API** — refreshes the Bedrock pricing table.
- **A Git host** — source hosting and CI/CD (SSH / SSO auth).
- **No self-hosted cloud infrastructure** — the tool *generates* AWS IaC (CDK/Terraform) for the projects it builds; deploy profiles (`AWS_DEPLOY_PROFILE`/`AWS_DEPLOY_REGION`) are consumed by generated projects.

## Build & Packaging Tools

- **uv** — package/dependency manager and tool installer (`uv tool install git+…`, `uv sync`, `uv build`, `uv.lock`).
- **hatchling** — wheel build backend.
- **hatch-vcs** — version derived from git tags; writes `sdharness/_version.py`; `no-local-version` scheme for package-registry compatibility.
- **hatch force-include** — bundles runtime resources into `sdharness/_bundled/`.
- **Make** — release helper targets (`Makefile`).
- **twine** + **awscli** — publish the wheel to the package registry (CI `publish` stage).

## Testing & Quality Tools

- **pytest** + **pytest-asyncio** — test suite (65 files, runs offline; some tests shell out to `git`).
- **pyright** (pinned `1.1.409`) — static type checking (`pyrightconfig.json`); must be 0 errors. Run locally pre-push.
- **CI pipeline** (a `ci` config) — wheel packaging + bundled-resource assertions + offline-install proof + package-registry publish (pyright/pytest run locally, not in CI).

## Optional / External Runtime Tooling

- **Node.js + Claude Code CLI** — the default coding agent runtime (`npm install -g @anthropic-ai/claude-code`).
- **Finch** — container build/run for build verification (falls back to local execution when absent).
- **pnpm** — nx-plugin-for-aws scaffolding + nx build/typecheck of generated full-stack projects (skipped when absent).
- **pyright / typescript-language-server** — in-agent LSP diagnostics (auto-enabled when on PATH and stack matches).
- **An SSO auth helper** — authenticates access to the Git host.
- **context7 MCP** (`npx @upstash/context7-mcp`) and **nx-plugin-for-aws MCP** (`npx @aws/nx-plugin-mcp`) — spawned via npx.
