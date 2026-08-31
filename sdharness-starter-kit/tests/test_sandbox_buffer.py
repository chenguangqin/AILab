# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""The sandbox must raise the SDK's stdout buffer ceiling above its 1 MB default.

The Claude Agent SDK reads the coding-agent CLI's stdout as a stream of JSON messages
behind a per-message byte buffer (default 1 MB). A single large tool result — e.g. the
agent `Read`ing a screenshot it just captured (base64-inlined at ~1.33× the file size),
a big test-output dump, or a large file — can exceed 1 MB in ONE message; the SDK then
raises "JSON message exceeded maximum buffer size" and the whole autonomous run dies
mid-turn. This regression was observed on a real frontend build whose VERIFY captured
responsive screenshots and then read one back. The kit sets `max_buffer_size` on
`ClaudeAgentOptions` so a fat tool result never kills a run.
"""

from __future__ import annotations

import harness.sandbox as sandbox


def _sandbox() -> sandbox.ClaudeCodeSandbox:
    return sandbox.ClaudeCodeSandbox(
        workspace=sandbox.Path("."),
        system_prompt_append="",
        can_use_tool=None,
    )


def test_default_buffer_is_far_above_the_sdk_1mb_default():
    """The kit's default is well above the SDK's 1 MB — a base64 screenshot fits."""
    assert sandbox._max_buffer_size() > 1024 * 1024
    assert sandbox._max_buffer_size() == sandbox._DEFAULT_MAX_BUFFER_SIZE


def test_env_override_is_honored(monkeypatch):
    monkeypatch.setenv("HARNESS_MAX_BUFFER_SIZE", str(64 * 1024 * 1024))
    assert sandbox._max_buffer_size() == 64 * 1024 * 1024


def test_env_override_ignores_garbage(monkeypatch):
    """A non-integer override falls back to the default rather than crashing at startup."""
    monkeypatch.setenv("HARNESS_MAX_BUFFER_SIZE", "not-a-number")
    assert sandbox._max_buffer_size() == sandbox._DEFAULT_MAX_BUFFER_SIZE


def test_options_pass_max_buffer_size_to_the_sdk(monkeypatch):
    """`_options()` must actually set `max_buffer_size` on the SDK options object —
    the field the subprocess transport reads instead of its 1 MB default."""
    # Avoid touching the skill/plugin filesystem resolution during the unit test.
    monkeypatch.setattr(sandbox.ClaudeCodeSandbox, "_resolve_skills", lambda self: ([], []))
    opts = _sandbox()._options()
    assert opts.max_buffer_size == sandbox._max_buffer_size()
    assert opts.max_buffer_size > 1024 * 1024


# ── observe-only PreCompact hook: surface SDK auto-compaction as a `compaction` event ──


async def test_precompact_hook_emits_compaction_event_and_is_observe_only():
    """The kit's one hook is PURELY observational: `_on_precompact` emits a `compaction`
    event carrying the trigger + whether custom instructions were set, and returns `{}`
    (no block, no injection) so it can never affect the run's determinism."""
    events: list[tuple[str, dict]] = []
    sb = sandbox.ClaudeCodeSandbox(
        workspace=sandbox.Path("."), system_prompt_append="", can_use_tool=None,
        emit=lambda event, **f: events.append((event, f)),
    )

    ret = await sb._on_precompact({"trigger": "auto", "custom_instructions": None}, None, {})

    assert ret == {}, "observe-only — the hook must never block or inject"
    assert len(events) == 1 and events[0][0] == "compaction"
    assert events[0][1]["trigger"] == "auto"
    assert events[0][1]["has_custom_instructions"] is False


async def test_precompact_hook_reports_manual_trigger_and_custom_instructions():
    """The event faithfully reflects a manual, custom-instruction compaction."""
    events: list[tuple[str, dict]] = []
    sb = sandbox.ClaudeCodeSandbox(
        workspace=sandbox.Path("."), system_prompt_append="", can_use_tool=None,
        emit=lambda event, **f: events.append((event, f)),
    )

    ret = await sb._on_precompact(
        {"trigger": "manual", "custom_instructions": "keep the API contract"}, "t1", {})

    assert ret == {}
    assert events[0][1]["trigger"] == "manual"
    assert events[0][1]["has_custom_instructions"] is True


def test_options_wire_a_precompact_hook(monkeypatch):
    """`_options()` registers the PreCompact hook so SDK auto-compaction is captured."""
    monkeypatch.setattr(sandbox.ClaudeCodeSandbox, "_resolve_skills", lambda self: ([], []))
    opts = _sandbox()._options()
    assert opts.hooks and "PreCompact" in opts.hooks, "PreCompact hook must be registered"


def test_fallback_model_is_passed_to_the_sdk(monkeypatch):
    """An explicit fallback_model flows to ClaudeAgentOptions.fallback_model (SDK auto-degrade
    on rate limits)."""
    monkeypatch.setattr(sandbox.ClaudeCodeSandbox, "_resolve_skills", lambda self: ([], []))
    sb = sandbox.ClaudeCodeSandbox(
        workspace=sandbox.Path("."), system_prompt_append="", can_use_tool=None,
        fallback_model="claude-haiku-4-5")
    assert sb._options().fallback_model == "claude-haiku-4-5"


def test_fallback_model_defaults_to_small_fast_model_env(monkeypatch):
    """When no fallback is passed, it defaults to $ANTHROPIC_SMALL_FAST_MODEL (keeps a long
    run alive through a throttle without extra config)."""
    monkeypatch.setattr(sandbox.ClaudeCodeSandbox, "_resolve_skills", lambda self: ([], []))
    monkeypatch.setenv("ANTHROPIC_SMALL_FAST_MODEL", "claude-haiku-4-5")
    sb = sandbox.ClaudeCodeSandbox(
        workspace=sandbox.Path("."), system_prompt_append="", can_use_tool=None)
    assert sb.fallback_model == "claude-haiku-4-5"
