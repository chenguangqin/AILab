# API Documentation

> **Note on shape:** SD Harness is a **local CLI application, not a networked service.** There is no public REST/HTTP service API. Its "interfaces" are four kinds: (1) the **CLI command surface** (the public API), (2) **internal Python protocols** (the extension contracts), (3) a **local dashboard HTTP + SSE** interface and a **WebSocket** command channel (observability/control, bound locally), and (4) **data models** exchanged across the loop. All are documented below.

## 1. CLI Command Surface (public API)

Entry point: `sdharness = sdharness.__main__:main`. Invoke `sdharness <command>`.

| Command | Purpose | Key arguments |
|---------|---------|---------------|
| `run <project_dir>` | Start or resume a single-method workflow (auto-detects). | `--method`, `--strategy`, `--yolo`, `--fresh`, `--dry-run`, `--stop-after PHASE`, `--reviewer-size`, `--max-turns`, `--max-budget`, `--sandbox`, `--scaffold`, `--iac`, `--include`, dashboard flags |
| `conduct <project_dir>` | Agentically drive across multiple methods toward a goal (the Conductor). | `--goal`, `--max-methods` (default 6), `--max-turns`, `--enabled-methods`, `--yolo`, `--dry-run`, dashboard flags |
| `pipeline <config.json>` | Run a static multi-step DAG. | `--dry-run`, dashboard flags |
| `intake [project_dir]` | AI interview → requirements/intent doc. | `--output`, `--method` |
| `scaffold [name]` | Scaffold a new project from a template. | `--template`, `--output-dir`, `--iac {CDK,Terraform}`, `--list` |
| `preflight [project_dir]` | Validate plugins, deps, sandbox, AWS access. | `--method`, `--plugin-dir`, `--sandbox`, `--json` |
| `inspect <project_dir>` | View run state. | `--checkpoints`, `--export FILE`, `--turn N`, `--json` |
| `replay <project_dir>` | Replay a completed run (terminal/browser). | dashboard flags |
| `branch <project_dir>` | Branch a worktree experiment from a checkpoint. | `--at-turn`, `--name`, `--to` |
| `graduate <run_dir>` | Export a finished run as a clean hand-off repo. | `--out` (required), `--force`, `--clean`, `--no-readme`, `--no-diagram`, `--skip-agent`, `--message`, `--author` |
| `config [show\|init]` | Show or scaffold the per-user `.env`. | `--force` |
| `pricing [show\|refresh]` | Show/refresh the Bedrock price table. | — |
| `capabilities` | Show what a method scaffolds — the skills + MCP servers + reviewer roles it pulls in (the "L2" capability join over the MCP registry). | `--method`, `--strategy`, `--json` |
| `compound <run_dir>` | Promote a finished run's `progress.md` `## Patterns` into the `LESSONS.md` seed (the compound-engineering write-back). | `--dry-run` |
| `runs` | List known runs. | `--json` |
| `status <project_dir>` | Single-shot run snapshot. | `--json` |
| `methods` / `strategies` | (hidden) List available methods/strategies. | `--json` (methods) |
| *(no args)* | Guided interactive TUI mode. | — |

**Deprecated aliases** (transformed before argparse): `checkpoints`→`inspect --checkpoints`, `summary`/`trajectory`→`inspect`, `export`→`inspect --export`, `dashboard`→`replay --dashboard`, `resume`→`run`. A bare `sdharness <dir>` auto-prepends `run`.

## 2. Internal Python Protocols (extension contracts)

Defined in `sdharness/core/protocols.py` (all `runtime_checkable`).

### `Sandbox` — coding-agent execution boundary
- **Methods**:
  - `provision(config: dict) -> None` — configure the sandbox.
  - `async connect() -> None` — establish an agent session (no-op for single-shot agents).
  - `async execute(prompt: str, **kwargs) -> TurnResult` — run one turn.
  - `async disconnect() -> None` — clean up.
  - `async reconnect(config: dict) -> None` — start a fresh session (unit boundaries).
  - `async get_context_usage() -> dict | None` — `{context_used, context_available, percent_used}` or `None`.
- **Purpose**: The only surface the outer harness uses to talk to any coding agent. Implemented by `sandboxes/claude_code.py`, `kiro_cli.py`, `gemini_cli.py`, `codex.py`.

### `Method` — development methodology
- **Methods / properties**: `name`, `phases -> list[PhaseConfig]`, `system_prompt_append(workspace)`, `initial_prompt(**kwargs)`, `is_gate(output) -> bool`, `is_complete(workspace, turn, output_length, run_metrics) -> tuple[bool, str]`, `needs_review(output, is_gate, workspace_writes) -> bool`, `gate_templates`, `evaluation_config`, `build_verification_mode`.
- **Purpose**: Declares phases, gates, and completion criteria. Implemented by `core/config_method.py:ConfigMethod` (loads `method.json`).

### `ReviewStrategy` — multi-agent review orchestration
- **Methods**: `async review(output, workspace, turn, phase, stage, is_gate, run_metrics=None, **kwargs) -> ReviewResult`, `init_reviewers(workspace, **kwargs) -> None`.
- **Purpose**: Declares who reviews and how consensus is reached. Implemented by `core/config_strategy.py:ConfigStrategy` (loads `strategy.json`).

### `EventBusProtocol` (`sdharness/events/bus.py`) — EventBridge-shaped interface
- **Methods**: `put_events(events: list[HarnessEvent]) -> None`, `subscribe(target, rule=None) -> str`, `unsubscribe(subscription_id) -> None`.
- **Purpose**: Abstract interface for the event bus (a seam for a future AWS EventBridge-backed bus). Implemented by `LocalEventBus`.

### MCP registry + capabilities resolution (`sdharness/core/mcp_registry.py`, `sdharness/scaffolding.py`)
- **`mcp_registry`** (L1): a single source of truth for MCP server specs (AWS Agent Toolkit, context7, nx-plugin, Playwright, …). Specs are defined once; strategies reference them **by name** rather than re-declaring endpoints — removing the per-strategy duplication the docs previously described.
- **`resolve_capabilities(method, strategy) -> dict`** (L2, surfaced by `sdharness capabilities`): joins a method + its strategy into the concrete set of `{skills, mcp_servers, roles}` that will be scaffolded into the coding-agent workspace — the machine-checkable answer to "what does this method actually pull in?" Also injected as a **live tools manifest** into both harness system prompts (`scaffolding.py`, `workflow_setup.py`, `core/review.py`, `reviewer.py`) so Pilot and coding agent share an accurate view of available tools.

## 3. Local Dashboard HTTP + SSE / WebSocket interfaces

### Dashboard HTTP server (`sdharness/dashboard.py`, default port `8089`, localhost)
An asyncio HTTP server (hand-rolled over `asyncio.StreamWriter`). Routes:

| Method | Path | Purpose | Response |
|--------|------|---------|----------|
| GET | `/` , `/index.html` | Dashboard SPA (`assets/dashboard.html`). | HTML |
| GET | `/events` | **SSE event stream.** Honors `Last-Event-ID` header, replaying only `seq > last_event_id`. | `text/event-stream` |
| GET | `/state` | Current run state snapshot. | JSON |
| GET | `/snapshot` | Point-in-time snapshot. | JSON |
| GET | `/files` | Workspace file tree. | JSON |
| GET | `/file?...` | A workspace file (rendered). | text |
| GET | `/file-raw...` | A workspace file (raw bytes). | bytes |
| GET | `/ws-file/...` | A workspace file by path. | text |
| POST | `/action/...` | Submit an operator action (e.g. milestone action). | JSON |

- **Request (SSE)**: `GET /events` with optional `Last-Event-ID: <seq>`.
- **Response (SSE)**: `Content-Type: text/event-stream`; each event carries the monotonic `seq` as its id and a JSON `data:` payload.

### WebSocket command channel (`sdharness/ws_server.py`)
- **Server → Client**: JSON event objects streamed from the EventBus.
- **Client → Server**: JSON command objects `{"cmd": "...", ...}`. Supported commands:
  - `{"cmd": "user_input", "value": "<text>"}` — answer a HITL prompt. Returns `{"ok": true, "cmd": "user_input"}`.
  - `{"cmd": "stop"}` — request the workflow to halt after the current turn.
  - `{"cmd": "milestone_action", "action": "<action>"}` — submit a milestone decision.
  - Unknown command → `{"ok": false, "cmd": "<cmd>", "error": "Unknown command: <cmd>"}`.

> **Security note (finding, not a defect of intended scope):** both local servers bind for a single operator and have **no authentication/authorization** layer. This is reasonable for a local single-user CLI, but any future remote exposure would require adding auth, TLS, and input validation on the control channel.

## 4. Data Models

Core exchange types (`sdharness/core/protocols.py`, `sdharness/models.py`, `sdharness/events/schema.py`, `sdharness/conductor/models.py`, `sdharness/pipeline/models.py`). All are Pydantic `BaseModel`.

### `TurnResult` (`core/protocols.py`)
- **Fields**: `output: str`, `exit_code: int = 0`, `tool_count: int = 0`, `workspace_writes: int = 0`, `session_id: str = ""`, `question: str = ""`, `metrics: dict = {}`, `checkpoint: Checkpoint | None`.
- **Purpose**: Generic result of one `Sandbox.execute()` call.

### `Checkpoint` (`core/protocols.py`)
- **Fields**: `type: str`, `question: str`, `options: list[str]`, `recommendation: str`, `context: dict`.
- **Purpose**: A pause point emitted by a sandbox at a boundary (first-class session event).

### `ReviewResult` / `ReviewDetail` (`core/protocols.py`)
- **`ReviewResult` fields**: `synthesized: str`, `gate_held: bool`, `details: list[ReviewDetail]`, `metrics: dict | None`.
- **`ReviewDetail` fields**: `role: str`, `response: str`, `decision: str`, `metrics: dict | None`.
- **Purpose**: Outcome of a review round.

### `GateDecision` / `HookAction` / `HookSpec` (`core/protocols.py`)
- **`GateDecision`**: `allow: bool`, `reason: str`, `interrupt: bool`, `updated_input: dict | None`, `system_message: str` — agent-agnostic gate result each sandbox maps to its native capability.
- **`HookAction`**: `system_message: str`, `block: bool`, `block_reason: str`.
- **`HookSpec`**: `event: str` (`pre_tool_use`/`post_tool_use`/`prompt_submit`/`pre_compact`), `matcher: str | None`, `handler: Callable | None`.

### `HarnessEvent` (`events/schema.py`)
- **Fields**: `id: str`, `source: str`, `detail_type: str` (alias `detail-type`), `detail: dict`, `time: datetime`, `resources: list[str]`, `seq: int`.
- **Validation**: EventBridge-compatible envelope; source convention `sdharness.workflow.{session_id}` / `sdharness.pipeline.{pipeline_id}.{step_id}`.
- **Relationships**: Filtered by `EventRule` (`source`/`detail_type`/`detail` prefix + equality matching).

### Conductor models (`conductor/models.py`)
- **`ConductorDecision`**: `next_method: str | None`, `done: bool`, `reason: str`, `handoff_prompt: str`, `stop_after: str | None`, `goal_md: str`, `is_progress_being_made: bool`, `is_in_loop: bool` — the structured output of the decision agent.
- **`TaskLedger`**: `goal: str`, `project_intent: str`, `plan: list[str]`, `history: list[ConductorStep]` — durable outer state.
- **`ConductorStep` / `ConductorResult`**: recorded iteration / final outcome (`stopped_reason` ∈ done / max_methods / stall / repeat_completed / repeat_failure / unresolvable_method / error).

### Pipeline models (`pipeline/models.py`)
- **`StepConfig`**: `id`, `method`, `strategy`, `sandbox`, `project_dir`, `include_paths`, `depends_on`, `params`.
- **`PipelineConfig`**: `id`, `name`, `steps`, `defaults`, `on_failure`, `output_dir`.
- **`StepResult` / `PipelineResult`**: per-step and overall execution results.

### Method / Strategy config schemas (JSON)
- **`method.json`** (validated by `ConfigMethod`): `name`, `display_name`, `description`, `default_scaffold`, `default_strategy`, `phases[]` (name/color/milestones), `phase_advancement` (artifact `complete_when` rules), `subagents{}`, `gates` (enforcement rules + templates), `checkpoints`, `completion` (terminal milestone + `terminal_requires` with `glob`/`implies`/`not`), `kill_switch`, `evaluation`, `intent_files`, `io` (consumes/produces/next). Gate predicates now include first-class **`no_unchecked`** and **`checkbox_min_checked`** leaves and **line-anchored** checkbox matching (`core/config_method.py`), so a gate proves *"every checklist item is checked"* structurally instead of relying on brittle prose `file_contains` matches (fixes #40/#41).
- **`strategy.json`** (validated by `ConfigStrategy`): `name`, `display_name`, `description`, `reviewers[]` (role/label/system_prompt_file/tools/always_review), `routing`, `execution`, `consensus` (rule), `initial_prompt`, `mcp_servers{}`.
