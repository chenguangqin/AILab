# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""The curated capability registry — the kit's vetted, named tool allowlist.

A **capability** is a coding-agent-neutral KEY (e.g. `"aws-docs"`) that a method
may declare in `method.json` (`"capabilities": ["aws-docs"]`). The harness reads
that list for ANY method; the *translation* from a neutral key to a concrete tool
lives in the coding-agent Sandbox (`ClaudeCodeSandbox._resolve_capabilities`),
so a different Sandbox can map the same key to its own tool mechanism — or ignore
it. Nothing SDK-specific leaks into the `Method` schema.

Why a registry (not a raw `mcp_servers` dict on the method):
  - **Security** — a method/fork enables one of N *pre-vetted* entries, never an
    arbitrary server. The surface collapses from "wire anything" to "name a vetted
    key." Under `permission_mode="bypassPermissions"` this matters: only read-only,
    credential-free tools belong here by default.
  - **Reproducibility** — the registry is declared, versioned, and auditable in the
    kit; a run's tool surface is a function of its method's `capabilities` list.
  - **Agnosticism** — the key is neutral. `models.Method.capabilities` is
    `list[str]`; the Claude realization (an MCP server + its tools) is confined to
    this file + the Claude Sandbox.

This is the *distilled* form of upstream sdharness's L1 registry (`mcp.registry`,
referenced by name) + L2 resolver (`resolve_capabilities` / `attach_to`). The kit
ships the lite rung — registry-by-name, wired at connect — and leaves the Pilot-
brokered *dynamic* selection (L3) as a design (see docs/design/capability-brokering.md).

To add a capability: add a vetted, read-only-by-default entry below and document it
in docs/customize.md. Keep it domain-neutral; this is an allowlist, not a grab-bag.
"""

from __future__ import annotations

from typing import Any

# key → vetted spec. `mcp` is the Claude-Sandbox realization (an MCP server the
# SDK launches over stdio); `allowed_tools` names the tools that server exposes,
# for documentation and for a future allowlist consumer (L3). A non-Claude Sandbox
# ignores `mcp` and maps the key its own way.
CAPABILITY_REGISTRY: dict[str, dict[str, Any]] = {
    "aws-docs": {
        "description": (
            "AWS Documentation MCP — search and read public AWS docs. "
            "Read-only, credential-free, AWS-maintained (stays current without a "
            "hand-kept skill). The right tool for a run that RESEARCHes a fast-moving "
            "AWS service (e.g. Lambda MicroVMs) instead of transcribing a runbook."
        ),
        "mcp": {
            "server_name": "aws-docs",
            "spec": {
                "type": "stdio",
                "command": "uvx",
                "args": ["awslabs.aws-documentation-mcp-server@latest"],
            },
        },
        "allowed_tools": [
            "mcp__aws-docs__search_documentation",
            "mcp__aws-docs__read_documentation",
            "mcp__aws-docs__recommend",
        ],
    },
    # Example of a second entry a fork might vet (NOT wired by default — a browser-
    # driving MCP is heavier and the agent already runs Playwright as a CLI via Bash):
    #   "playwright": {
    #       "description": "Playwright MCP — drive a headless browser for E2E checks.",
    #       "mcp": {"server_name": "playwright",
    #               "spec": {"type": "stdio", "command": "npx",
    #                        "args": ["-y", "@playwright/mcp@latest"]}},
    #       "allowed_tools": ["mcp__playwright__*"],
    #   },
}


def lookup(key: str) -> dict[str, Any] | None:
    """Return the vetted spec for a capability key, or None if not in the registry."""
    return CAPABILITY_REGISTRY.get(key)
