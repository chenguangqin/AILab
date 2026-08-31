# Reverse Engineering Metadata

**Analysis Date**: 2026-07-06T00:00:00Z (full 8-artifact run; supersedes the 2026-07-02 initial run)
**Last Partial Refresh**: 2026-07-09 — `code-quality-assessment.md` only, reconciled against upstream's technical-debt MRs (see below)
**Analyzer**: AI-DLC (inception reverse-engineering workflow, v1.0.1 rules; driven by the session coding agent)
**Workspace**: the `harness-starter-kit` project root
**Analysis Target**: analysis-target/sdharness/ (read-only, git-ignored)
**Upstream Commit**: `01a6112d` (HEAD of `main`, 2026-07-08) for the code-quality refresh — a 9-MR delta (#110–#118) beyond the full run's `a8c623c` (2026-07-06). The other 7 artifacts remain as-of `a8c623c` (which was itself 26 commits / 12 MRs ahead of the initial `0a36767`).
**Total Files Analyzed**: ~774 files (excluding `.git` / `.venv`); ~149 Python (~28.8k pkg LOC + ~13.4k test LOC), ~503 Markdown, ~122 JSON (counts from the `a8c623c` full run)

## What changed since the 2026-07-02 run (the 12-MR delta)
- **Methods 14 → 15**: added `html-mockup` (one-liner → 4-page clickable HTML mockup, default-on Playwright render-verify #43); `mockup` renamed to `html-mockup` (#42 pinned Playwright to chromium).
- **Strategies 13 → 14**: added `html-mockup-autopilot`.
- **Plugins 23 → 38**: vendored **14 AWS core skills** from `aws/agent-toolkit-for-aws` (Apache-2.0) + standalone `ai-plc` product-discovery skill.
- **CLI 17 → 19 commands**: added `capabilities` (method → {skills, MCPs, roles} — L2 join) and `compound` (promote `progress.md` Patterns → `LESSONS.md` seed).
- **New core module**: `core/mcp_registry.py` — single MCP-spec registry (L1); strategies reference by name.
- **Tools manifest**: live tools manifest auto-injected into both harness system prompts.
- **Phase-authority hardening (#40/#41)**: line-anchored checkbox gates + first-class `no_unchecked` / `checkbox_min_checked` leaves + two runtime guards; fail-closed steering verdict + NO_GO escalation.
- **Templates 5 → 9**: added `harness-browser`, `harness-coder`, `harness-container`, `harness-mcp`.

## What changed since the 2026-07-06 run (the technical-debt MRs, `a8c623c` → `01a6112d`)

Only `code-quality-assessment.md` was refreshed to reflect these; the other 7 artifacts are unchanged
(the delta is debt burn-down and small fixes, not new architecture). Upstream consolidated its debt
into a maintained `docs/technical-debt.md` register (**!115**) and started working it down:

- **Debt series (#115–#118):**
  - **!115** — added the consolidated `docs/technical-debt.md` register (reconciles the external
    assessments with the architecture gap table + security/harness roadmaps; per-item status + owner).
  - **!116** *(quick-wins)* — pricing `as_of` bumped 2026-06-08 → **2026-07-08** (rates verified
    current; refresh command no-ops, **#46**); **pinned bare top-level deps** (`rich`/`questionary`/
    `pydantic`/`websockets`/`botocore`/`prompt-toolkit`) with `>=` bounds matching `uv.lock`; added
    **`tests/test_module_size.py`**, a ratcheting god-module-size guard (new ≤ 800 LOC; offenders
    capped at current size, cap only ratchets down).
  - **!117** *(security Phase 4A)* — **universal workspace-boundary enforcement** in the generated
    bash gate hook (`core/gate_script.py`): `resolves_outside_workspace()` blocks absolute / `../` /
    `~` / redirect writes outside `$WORKSPACE` for **every** method; guarded by `tests/test_gate_boundary.py`.
  - **!118** — synced the register with the landed fixes + tracking issues (pinning→mitigated;
    boundary→mitigated; gate-bypass→partially mitigated; local-server auth→deferred **#47**; god
    modules→tracked **#48**; pricing→open **#46**).
- **Supporting fixes (#110–#114):** quarantine `progress.md` into `<method>-docs/` (#110); don't
  hard-assume a named AWS profile — support IAM task/instance roles (#111); layout-agnostic path globs
  + up-front scaffold so guardrails reach agent-scaffolded workspaces (#112/#113); README lines-of-code
  badge (#114).
- **Full suite at `01a6112d`**: 1,372 passed / 19 skipped; pyright 0/0.

## Artifacts Generated
- [x] business-overview.md
- [x] architecture.md
- [x] code-structure.md
- [x] api-documentation.md
- [x] component-inventory.md
- [x] technology-stack.md
- [x] dependencies.md
- [x] code-quality-assessment.md
