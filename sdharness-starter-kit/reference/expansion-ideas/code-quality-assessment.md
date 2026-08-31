# Code Quality Assessment

## Test Coverage

- **Overall**: **Good** (for an experimental tool). ~65 test files (~13,404 LOC) against ~28,802 LOC of package code — a ~0.47 test-to-code LOC ratio, unusually high for a project self-described as "experimental". At upstream `01a6112d` the full suite runs **1,372 passed / 19 skipped** with **pyright 0/0**.
- **Unit Tests**: Strong. Dedicated files for most modules and behaviors — `test_workflow.py`, `test_harness_run_loop.py`, `test_phase_authority.py`, `test_gates.py`, `test_reviewer.py`, `test_evaluation.py`, `test_events.py`, `test_checkpoint.py`, `test_conductor.py`, `test_pipeline.py`, `test_sandboxes.py`, `test_verification_typecheck.py`, plus per-method tests (`test_sdd_method.py`, `test_brownfield_method.py`, `test_frontend_method.py`, `test_loop_method.py`, `test_storytelling_yolo.py`, `test_mockup_yolo.py`).
- **Cross-cutting invariant tests**: Notable strength. `test_method_readiness.py` runs over **every** method + strategy (so new/edited configs are checked automatically); `test_method_config_common.py` asserts mechanical per-method facts; `test_scaffolding_completeness.py` verifies every method/strategy has the skills + MCP servers it references (now resolving through the single `core/mcp_registry.py`); `test_io_contract.py` checks method I/O contracts; `test_default_strategy.py` verifies the method→strategy pairing. Two newer invariant guards extend this: `test_module_size.py` (#116) caps god-module growth with a ratcheting allowlist, and `test_gate_boundary.py` (#117) executes the *real* generated gate hook via subprocess to prove out-of-workspace writes are blocked for both rule-bearing and rule-less methods.
- **Integration Tests**: Present at the orchestration seam (`test_harness_run_loop.py`, pipeline/conductor tests, ACP timeout tests). AWS is not required — the suite runs fully offline; some tests shell out to `git`.
- **Test layering discipline**: Documented in `docs/testing.md` and enforced culturally — "assert each fact once at the strongest layer" (cross-method invariants → readiness test; mechanical facts → config-common; core-loop → run-loop; method-specific → per-method). This is a mature testing practice.
- **Evaluation harness**: A separate `eval/` tree (golden cases, experiments, results) benchmarks the *product's outputs*, distinct from unit tests.

## Code Quality Indicators

- **Linting / Static analysis**: **Configured and enforced.** `pyright==1.1.409` (pinned) via `pyrightconfig.json`, required to be 0 errors and run locally before every push. CI proves the wheel/packaging path.
- **Type discipline**: High. Pervasive type hints, `from __future__ import annotations`, `Protocol`/`runtime_checkable` contracts, and a project rule that all data models are Pydantic `BaseModel` (no `@dataclass`).
- **Code style**: **Consistent.** Strong, explicitly documented conventions in `CLAUDE.md` (e.g. `callback_handler=None` on silent Strands agents, no `console.status()` spinners, EventBus over the old Session singleton, `review_compact` over strategy-name checks). Module docstrings are thorough and explain *why*, not just *what*.
- **Documentation**: **Good to excellent.** 54 design docs in `docs/` (30 top-level: architecture, review-system, conductor, pipelines, event-log-architecture, method-readiness, plugins, scaffolding, testing, evaluation, plus per-method docs), a mental-model doc, a changelog, and richly commented config (`sdharness.json`, `method.json`). Inline comments frequently reference issue numbers (e.g. `#15`, `#24`, `#40`, `#41`, `#42`, `#43`) tying code to their motivating bugs.
- **Separation of concerns**: Strong. Strict downward-only layering (Protocols → Sandboxes → Core → Orchestration → CLI), config-over-code composition, and agent-agnostic abstractions (`Sandbox`, `HookSpec`, `GateDecision`).

## Technical Debt

> **Upstream now tracks all of this in one place.** A consolidated register — `docs/technical-debt.md`
> (added in **!115**) — reconciles these external assessments with the architecture gap table and the
> security/harness roadmaps, giving each item a status (`mitigated` / `partially mitigated` /
> `tracked` / `open` / `deferred`), a severity, and an owning doc or issue. The statuses below mirror
> that register as of upstream `01a6112d` (2026-07-08). This is a maintained debt list, not a silent gap.

- **Very large modules** *(open — tracked #48; growth now guarded)*. Several files are large enough to be
  hard to navigate and test in isolation: `commands.py` (~3,182 LOC / 65 fns), `harness.py` (~1,910 LOC),
  `core/review.py` (~1,327 LOC), `cli_renderer.py` (~1,268 LOC), `dashboard.py` (~1,154 LOC),
  `workflow.py`, `workflow_setup.py`, `verification.py`. Extraction is underway (`turn_helpers.py`,
  `core/review.py`, `core/mcp_registry.py`, `cli_ui/`). A **ratcheting size guard shipped** in **!116**
  (`tests/test_module_size.py`): new modules are capped at ≤ 800 LOC and each grandfathered offender is
  pinned at its current size — the cap only ratchets *down* as extraction lands, so nothing grows and the
  debt burns down monotonically. The planned Phase-3 extraction (**#48**) splits `commands.py` into a
  `sdharness/cli/` package by cohesion (run / observe / orchestrate / ops) behind **re-export shims**, so
  `__main__`, the conductor, and the test suite keep their import paths — behavior-neutral, in increments.
- **Hand-rolled HTTP/SSE server** *(deferred)*. `dashboard.py` implements HTTP over raw
  `asyncio.StreamWriter` (manual header parsing, routing, response framing) rather than a maintained
  server library — more surface for edge-case bugs (partial reads, malformed requests). Justified for
  zero-dependency local-only use; replacing it is out of scope unless the auth work below makes a library
  swap cheaper.
- **No authentication on local servers** *(deferred — tracked #47)*. The SSE dashboard and control
  channel accept commands (`stop`, `user_input`, `milestone_action`) with no auth — **but the server
  binds `127.0.0.1`**, so this is a localhost-multi-user concern, not a live remote exposure. Deliberately
  deferred (workspace-security **Phase 4B**, **#47**) until multi-user/remote exposure is on the table;
  the designed fix is a per-run token on the mutating `POST /action/*` endpoints (the factory rung may
  prefer its own Cognito/IAM instead).
- **Loose top-level version pinning** → **mitigated (!116)**. Foundational deps were bare in
  `pyproject.toml` (reproducibility relied on `uv.lock` alone). **!116** added `>=` lower bounds
  (`rich`, `questionary`, `pydantic`, `websockets`, `botocore`, `prompt-toolkit`) matching `uv.lock`'s
  resolved versions, so a resolution outside the lock can't silently drift to an incompatible older
  release.
- **Fast-moving external coupling** *(prices open — tracked #46)*. Model IDs and prices are hardcoded in
  `sdharness.json`; the `as_of` stamp was **bumped to 2026-07-08 (!116)** after verifying the rates are
  current. The intended refresh seam (`sdharness pricing refresh`, AWS Price List API) currently returns
  no Claude prices and no-ops, so the table stays **hand-maintained** (#46); model IDs are a deliberate
  pinned set for reproducibility. Agent SDKs (Strands, Claude Agent SDK, ACP) still evolve quickly — the
  `>=` bounds + `uv.lock` are the seam; expect ongoing maintenance.
- **Self-declared status: experimental.** `pyproject.toml` description and the README status badge both
  say experimental; behavior and interfaces should be expected to change.
- **Gate-bypass via bash** → **partially mitigated (!117, Phase 4A)**. `docs/gate-bypass-bash-exploit.md`
  and `docs/workspace-security-roadmap.md` document that a coding agent's shell commands can sidestep
  path-based gates. **!117** shipped universal workspace-boundary enforcement: `resolves_outside_workspace()`
  in the generated bash gate hook (`core/gate_script.py`) now blocks any write resolving outside the
  workspace — absolute paths, `../` escapes, `~` expansion, and bash redirects — **for every method**
  (previously a method with no phase-ordering rules got a bare `exit 0` hook), guarded by
  `tests/test_gate_boundary.py`. Residual: complex piped/chained bash can still evade the path extractor
  (roadmap Phase 2, a post-turn diff, addresses that).
- **Acknowledged gap-analysis items.** `docs/architecture.md` itself lists "Partial/Gap/Deferred" patterns
  (e.g. no cross-run quality-trend persistence yet, error-pattern circuit breaker is a gap, TDD guard
  deferred) — an honest, maintained debt register.

## Patterns and Anti-patterns

- **Good Patterns**:
  - **Config-over-code composition** — methods/strategies as declarative JSON+Markdown; "add one = add a directory, zero Python".
  - **Protocol-based abstraction seams** — `Sandbox`, `Method`, `ReviewStrategy`, `EventBusProtocol` cleanly decouple agents, methodologies, review styles, and the bus.
  - **Deterministic-first control** — enforcement (consensus, phase advancement, kill switch) is computed deterministically; LLMs are used for judgment, not for control-flow that must be reliable.
  - **Event-sourced, resume-safe orchestration** — append-only `events.jsonl` + git checkpoints + `trajectory.jsonl`; the repository is the system of record.
  - **Anti-loop guardrails as first-class design** — method cap + stall threshold + `(method, failure-class)` repeat-failure cap in the Conductor, and a structural-done backstop, each tied to a documented failure it prevents.
  - **Automated config-drift prevention** — the readiness/completeness tests run over *all* configs, so a new method/strategy can't silently ship broken.
  - **Single-source-of-truth helpers** — `scaffolding.py` shared by CI test and preflight; `resources.py` for all resource resolution; `core/mcp_registry.py` defines each MCP spec once (L1) with strategies referencing by name, and `capabilities` resolves the L2 join.
  - **Structural gates over prose matching** — the phase-authority hardening (#40/#41) replaced brittle positive `file_contains` checks on checklist prose with line-anchored checkbox matching and first-class `no_unchecked`/`checkbox_min_checked` predicates, closing a class of gates that could either falsely pass or spin the loop.
  - **Universal deterministic workspace boundary** — the generated gate hook (`core/gate_script.py`) resolves every write target against the workspace root and blocks anything outside it (absolute / `../` / `~` / redirect), scaffolded for *all* methods and executed as the real agent hook (#117). Enforcement is a deterministic path check, not a model judgment — the same "structural over prose" discipline applied to the security boundary.
  - **Debt burned down by a ratchet, not a wishlist** — a consolidated `docs/technical-debt.md` register (#115) plus a `test_module_size.py` guard (#116) that caps each god-module at its current size and only ratchets *down*: the anti-pattern below can't grow, and every extraction MR provably shrinks it. Debt is enforced-against, not just noted.

- **Anti-patterns / risks**:
  - **God modules** — the multi-KLOC `commands.py` / `harness.py` concentrate too much responsibility (see Technical Debt). Now *bounded*: the size-guard ratchet (#116) prevents further growth while the #48 extraction proceeds.
  - **Reinvented infrastructure** — the bespoke HTTP/SSE server duplicates what a small dependency would provide more robustly (deferred; zero-dependency local-only use).
  - **Hardcoded volatile data** — model IDs/prices embedded in config with an `as_of` date stamp (refreshed to 2026-07-08 in #116); drift is inevitable while the auto-refresh seam is a no-op (#46).
  - **Broad tool consent toggling** — `_pilot_resolve_answers` temporarily sets `BYPASS_TOOL_CONSENT=true` around an editor-tool agent call; scoped and restored in a `finally`, but a pattern to watch given the documented gate-bypass concern.

## Summary

For an explicitly experimental tool, code quality is **above average**: strong typing and lint enforcement, a high and well-layered test suite with automated cross-config invariants, extensive design documentation, and disciplined architectural seams. The remaining risks are **oversized core modules**, a **hand-rolled local server without auth**, and **tight coupling to fast-moving AI SDKs and hardcoded model/pricing data** — and, notably, each is now either *fixed*, *guarded*, or *explicitly tracked* rather than latent. Since this assessment's snapshot, a technical-debt series landed (through upstream `01a6112d`): a consolidated `docs/technical-debt.md` register (!115), dependency pinning (!116), a ratcheting module-size guard (!116, so the god-modules can't grow while the #48 extraction proceeds), and a universal workspace-boundary gate hook (!117) that partially closes the gate-bypass concern. Loose pinning is now mitigated; the local-server auth (#47) and hardcoded pricing refresh (#46) are the tracked, deliberately-deferred residue. The debt is enforced-against, not just noted — the strongest signal of maturity here.
