# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""The curated capability registry (Part C) — the kit's vetted, named tool allowlist.

A `Method` declares neutral registry KEYS in `capabilities`; the Claude Sandbox
translates them to MCP servers at connect. These tests pin the three invariants:
  1. default (no `capabilities`) wires `mcp_servers={}` — byte-for-byte the old behavior;
  2. a declared, vetted key wires exactly that server + surfaces its tools;
  3. an unknown/unvetted key is skipped (a warning event), never fatal;
plus the agnosticism guard: `Method.capabilities` carries plain string keys, no SDK shape.
"""

from __future__ import annotations

import harness.sandbox as sandbox
import harness.tools as tools
from harness.models import Method


def _sandbox(capabilities=None) -> sandbox.ClaudeCodeSandbox:
    return sandbox.ClaudeCodeSandbox(
        workspace=sandbox.Path("."),
        system_prompt_append="",
        can_use_tool=None,
        capabilities=capabilities,
    )


# ── the registry itself ──────────────────────────────────────────────────────


def test_registry_seeds_aws_docs_read_only():
    """The registry ships the AWS Documentation MCP — vetted, read-only, credential-free."""
    spec = tools.lookup("aws-docs")
    assert spec is not None
    assert spec["mcp"]["server_name"] == "aws-docs"
    # Only read/search/recommend tools — nothing that mutates AWS.
    assert all(t.startswith("mcp__aws-docs__") for t in spec["allowed_tools"])
    assert not any(w in " ".join(spec["allowed_tools"]).lower()
                   for w in ("create", "delete", "put", "update", "write"))


def test_lookup_returns_none_for_unknown_key():
    assert tools.lookup("does-not-exist") is None


# ── resolution at the Sandbox seam ────────────────────────────────────────────


def test_default_capabilities_wire_no_mcp_servers():
    """The top safety net: a method with no capabilities wires exactly what it wires
    today — `mcp_servers={}`, byte-for-byte unchanged."""
    servers, allowed = _sandbox()._resolve_capabilities()
    assert servers == {}
    assert allowed == []


def test_declared_capability_wires_its_server_and_tools():
    events: list[tuple[str, dict]] = []
    sb = sandbox.ClaudeCodeSandbox(
        workspace=sandbox.Path("."), system_prompt_append="", can_use_tool=None,
        capabilities=["aws-docs"],
        emit=lambda event, **f: events.append((event, f)),
    )
    servers, allowed = sb._resolve_capabilities()
    assert "aws-docs" in servers
    assert servers["aws-docs"]["command"] == "uvx"
    assert "mcp__aws-docs__read_documentation" in allowed
    assert ("capability_attached", {"key": "aws-docs", "server": "aws-docs"}) in events


def test_unknown_capability_is_skipped_not_fatal():
    events: list[tuple[str, dict]] = []
    sb = sandbox.ClaudeCodeSandbox(
        workspace=sandbox.Path("."), system_prompt_append="", can_use_tool=None,
        capabilities=["aws-docs", "totally-made-up"],
        emit=lambda event, **f: events.append((event, f)),
    )
    servers, allowed = sb._resolve_capabilities()
    assert "aws-docs" in servers and "totally-made-up" not in servers
    assert ("capability_missing", {"key": "totally-made-up"}) in events


def test_options_default_wires_empty_mcp_servers(monkeypatch):
    """Regression guard at the SDK-options layer: default `_options()` still passes
    `mcp_servers={}` and keeps `strict_mcp_config=True`."""
    monkeypatch.setattr(sandbox.ClaudeCodeSandbox, "_resolve_skills", lambda self: ([], []))
    opts = _sandbox()._options()
    assert opts.mcp_servers == {}
    assert opts.strict_mcp_config is True


def test_options_wire_declared_capability_server(monkeypatch):
    monkeypatch.setattr(sandbox.ClaudeCodeSandbox, "_resolve_skills", lambda self: ([], []))
    opts = _sandbox(capabilities=["aws-docs"])._options()
    assert "aws-docs" in opts.mcp_servers
    assert opts.strict_mcp_config is True


# ── agnosticism guard ─────────────────────────────────────────────────────────


def test_method_capabilities_field_holds_plain_string_keys():
    """The neutral schema: `Method.capabilities` is a list of registry KEYS (strings),
    never an SDK-specific `mcp_servers` dict — so a non-Claude Sandbox can map or ignore
    the same keys."""
    m = Method(name="m", capabilities=["aws-docs"])
    assert m.capabilities == ["aws-docs"]
    assert all(isinstance(k, str) for k in m.capabilities)


def test_method_capabilities_default_empty():
    assert Method(name="m").capabilities == []
