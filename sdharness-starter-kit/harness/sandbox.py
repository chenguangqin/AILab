# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""ClaudeCodeSandbox — the inner harness (the coding agent).

Wraps the Claude Agent SDK behind the `Sandbox` protocol. The outer harness only
ever sees a `TurnResult`; everything SDK-specific is contained here. To add a
different coding agent, write another file implementing the same protocol — the
loop never changes. This kit ships only Claude Code to stay lightweight.

Bedrock-only: we forward `CLAUDE_CODE_USE_BEDROCK` + AWS envs so the spawned
`claude` process authenticates through Bedrock.

The `ClaudeAgentOptions` built here:
  - system_prompt: claude_code preset + the method's system-prompt.md appended
  - setting_sources=["project","local"]  → NOT "user" (isolate from personal ~/.claude)
  - permission_mode="bypassPermissions"  → gate via can_use_tool instead of prompts
  - can_use_tool: our deterministic gate (containment + method rules)
  - strict_mcp_config=True                → reproducible; no host MCP leakage
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from .models import TurnResult


def _cost_delta(cumulative: float, prev_cumulative: float) -> tuple[float, float]:
    """Convert the SDK's session-CUMULATIVE `total_cost_usd` into this turn's spend.

    On a persistent `ClaudeSDKClient`, `ResultMessage.total_cost_usd` reports the running
    session total (it grows every query), so the per-turn cost is the delta from the prior
    turn. Summing the raw cumulative snapshots (the earlier bug) over-reports a multi-turn
    run several-fold. Returns (this_turn_cost, new_prev). Clamped at 0 defensively — a
    cumulative total should never decrease.
    """
    return max(0.0, cumulative - prev_cumulative), cumulative


def _noop_emit(event: str, **fields: object) -> None:
    """Default event sink — does nothing. The CLI passes a real emitter (a CLIRenderer
    or an NDJSON writer); a fork embedding the sandbox can ignore events entirely."""


def _format_tool_use(name: str, inp: dict, workspace: str = "") -> str:
    """One-line, human-friendly summary of a tool call (e.g. 'Read(vision.md)',
    'Bash(dnf install -y …)'). Keeps the loop output legible instead of a bare
    unlabeled tool name with an absolute path."""
    inp = inp or {}

    def _short_path(p: str) -> str:
        if workspace and p.startswith(workspace):
            p = p[len(workspace):].lstrip("/")
        return p if len(p) <= 60 else "…" + p[-57:]

    if name in ("Read", "Write", "Edit", "MultiEdit"):
        return f"{name}({_short_path(inp.get('file_path', ''))})"
    if name == "Bash":
        cmd = inp.get("command", "").replace("\n", " ")
        return f"Bash({cmd[:80]}{'…' if len(cmd) > 80 else ''})"
    if name in ("Glob", "Grep"):
        return f"{name}({inp.get('pattern', '')[:60]})"
    if name == "TodoWrite":
        return "TodoWrite(update plan)"
    args = str(inp)
    return f"{name}({args[:60]}{'…' if len(args) > 60 else ''})"


# Envs forwarded to any spawned Claude Agent SDK process (inner coding agent, Pilot,
# curator) so Bedrock auth + model selection resolve identically. This is the SINGLE
# source of truth — steering.py and compound_agentic.py import `forward_env()` rather
# than hand-typing their own subset, so the reviewer/curator can never drift from the
# proven inner-agent env (a drift that manifested as the curator's spawned CLI failing to
# authenticate to Bedrock while the inner agent worked). Includes the AWS credential vars
# so a shell that carries explicit keys (not just an instance-role/profile) still auths.
_FORWARD_ENV = (
    "CLAUDE_CODE_USE_BEDROCK",
    "AWS_PROFILE",
    "AWS_REGION",
    "AWS_DEFAULT_REGION",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "ANTHROPIC_MODEL",
    "ANTHROPIC_SMALL_FAST_MODEL",
)


def forward_env() -> dict[str, str]:
    """The env every spawned SDK process inherits (Bedrock auth + model selection).
    Shared by the inner-agent Sandbox, the Pilot (steering), and the compound curator so
    they authenticate identically — no per-caller drift."""
    return {k: os.environ[k] for k in _FORWARD_ENV if os.environ.get(k)}


def inline_schema_refs(schema: dict) -> dict:
    """Resolve `$ref`/`$defs` in a JSON Schema into a single self-contained tree — a
    best-effort COMPLEMENT to the sink-side `unwrap_structured_output` (which is the actual
    load-bearing fix; do NOT rely on this alone).

    Context (isolated via controlled live experiments on Bedrock): the `claude` CLI's
    `--json-schema` structured-output path sometimes WRAPS + JSON-stringifies the result
    (`{"findings":"{...}"}`) instead of returning the bare object. A schema with `$ref`/`$defs`
    (which Pydantic's `model_json_schema()` emits for ANY nested model, e.g. Proposal →
    ProposalItem) is ONE reproducible trigger — but NOT the only one: the full curator run wraps
    even with an inlined, ref-free schema (prompt content/size appear to matter too), and it is
    not fully deterministic. So inlining removes one known trigger and reduces reliance on the
    net, but the CLI can still wrap; `unwrap_structured_output` is what guarantees correctness.
    (Earlier "Bedrock-only vs first-party" framing was RETRACTED — never tested against the
    first-party API; all repros were on Bedrock.)

    Best-effort + non-destructive: resolves internal `#/$defs/...` (and legacy
    `#/definitions/...`) pointers, drops the now-unused `$defs`/`definitions` blocks, and
    leaves anything it can't resolve untouched. Bounded recursion guards against a
    self-referential schema; never raises."""
    import copy

    defs = {}
    for key in ("$defs", "definitions"):
        if isinstance(schema.get(key), dict):
            defs.update(schema[key])
    if not defs:
        return schema  # nothing to inline

    def _resolve(node: object, depth: int = 0) -> object:
        if depth > 12:
            return node  # self-referential schema — leave the rest for the unwrap net
        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str) and ref.startswith(("#/$defs/", "#/definitions/")):
                target = defs.get(ref.rsplit("/", 1)[-1])
                if isinstance(target, dict):
                    # Merge any sibling keys (e.g. description) over the resolved def.
                    merged = {**_resolve(target, depth + 1),
                              **{k: _resolve(v, depth + 1) for k, v in node.items() if k != "$ref"}}
                    return merged
            return {k: _resolve(v, depth + 1) for k, v in node.items()
                    if k not in ("$defs", "definitions")}
        if isinstance(node, list):
            return [_resolve(v, depth + 1) for v in node]
        return node

    resolved = _resolve(copy.deepcopy(schema))
    return resolved if isinstance(resolved, dict) else schema


def unwrap_structured_output(structured: object) -> dict | None:
    """Normalize whatever the SDK returns for `output_format` into the plain dict our
    Pydantic schemas expect — THE load-bearing fix for the structured-output wrapping quirk
    (inline_schema_refs is only a best-effort complement).

    Root cause (isolated via controlled live experiments on Bedrock): the `claude` CLI's
    `--json-schema` structured-output path sometimes WRAPS + JSON-stringifies the result under
    a synthetic single key, e.g.:

        {"findings": "{\\"items\\": [ ... ]}"}     # one key, value is a JSON *string*

    The trigger is multi-factorial and not fully deterministic (a `$ref`/`$defs` schema
    reproduces it; the full curator run wraps even with an inlined schema — prompt content/size
    also matter), so no source-side change reliably prevents it. Hence we normalize at the sink:
    a naive `structured.get("items")` / `.get("decision")` misses the wrapped form and the
    caller silently falls back (compound → empty proposal; steering → NO_GO). This peels the
    layers:
      - already the target dict → return as-is;
      - a JSON string → parse it;
      - a single-key wrapper whose value is a dict or JSON-string → unwrap recursively.
    Returns None if nothing dict-shaped can be recovered (callers then use their text
    fallback). Bounded recursion; never raises."""
    import json

    def _peel(v: object, depth: int = 0) -> dict | None:
        if depth > 4:
            return None
        if isinstance(v, dict):
            # A single-key synthetic wrapper (not our real payload) → unwrap its value.
            # Our real payloads have known top-level keys; if none are present and there's
            # exactly one key, treat it as a wrapper and descend.
            KNOWN = {"items", "decision", "direction"}
            if not (KNOWN & v.keys()) and len(v) == 1:
                return _peel(next(iter(v.values())), depth + 1)
            return v
        if isinstance(v, str):
            s = v.strip()
            if s.startswith("{"):
                try:
                    return _peel(json.loads(s), depth + 1)
                except Exception:
                    return None
        return None

    return _peel(structured)

# The SDK reads the coding-agent CLI's stdout as a stream of JSON messages behind a
# per-message byte buffer (SDK default: 1 MB). A single large tool result — e.g. the
# agent `Read`ing a screenshot it just captured (base64-inlined, ~1.33× the file), a
# big test-output dump, or a large file — can exceed 1 MB in one message; the SDK then
# raises "JSON message exceeded maximum buffer size" and the whole run dies mid-turn.
# We raise the ceiling well above any realistic single message so a long-running
# autonomous build isn't killed by one fat tool result. Override with
# HARNESS_MAX_BUFFER_SIZE (bytes) if a fork needs more (or less).
_DEFAULT_MAX_BUFFER_SIZE = 32 * 1024 * 1024  # 32 MB (SDK default is 1 MB)


def _max_buffer_size() -> int:
    raw = os.environ.get("HARNESS_MAX_BUFFER_SIZE", "").strip()
    if raw:
        try:
            return max(1, int(raw))
        except ValueError:
            pass
    return _DEFAULT_MAX_BUFFER_SIZE


class ClaudeCodeSandbox:
    """A persistent Claude Code session driven turn by turn."""

    def __init__(
        self,
        workspace: Path,
        system_prompt_append: str,
        can_use_tool: Callable | None,
        model: str | None = None,
        max_turns: int = 200,
        emit: Callable[..., None] = _noop_emit,
        skills: list[str] | None = None,
        capabilities: list[str] | None = None,
        fallback_model: str | None = None,
    ):
        self.workspace = workspace
        self.system_prompt_append = system_prompt_append
        self.can_use_tool = can_use_tool
        self.model = model or os.environ.get("ANTHROPIC_MODEL")
        self.max_turns = max_turns
        self.emit = emit
        self.skills = skills or []
        self.capabilities = capabilities or []
        # Auto-degrade to a cheaper/available model on rate limits (SDK-native). Falls back
        # to ANTHROPIC_SMALL_FAST_MODEL if the caller didn't pass one — a sensible default
        # that keeps a long autonomous run alive through a rate-limit blip. Empty = no fallback.
        self.fallback_model = fallback_model or os.environ.get("ANTHROPIC_SMALL_FAST_MODEL") or None
        self._client = None
        # ResultMessage.total_cost_usd on a PERSISTENT client is the session-cumulative
        # total (it grows every query), NOT this turn's spend — verified empirically
        # (a trivial cached follow-up query still reports a HIGHER total_cost_usd). So we
        # track the previous cumulative and report the DELTA per turn; the loop sums the
        # deltas. (The Pilot in steering.py uses a fresh one-shot query() per turn, so
        # ITS total_cost_usd is genuinely per-call — that path stays as-is.)
        self._prev_cost_usd = 0.0

    def _resolve_skills(self) -> tuple[list, list[str]]:
        """Return (plugins, skill_names) for the requested skills, skipping any
        that aren't installed — skills are best-effort, so a fork without the skill
        still runs (the agent just designs from the brief)."""
        from .config import resolve_skill_plugin

        plugins: list[dict] = []
        names: list[str] = []
        for name in self.skills:
            root = resolve_skill_plugin(name)
            if root is not None:
                plugins.append({"type": "local", "path": str(root)})
                names.append(name)
                self.emit("skill_attached", name=name, path=str(root))
            else:
                self.emit("skill_missing", name=name)
        return plugins, names

    def _resolve_capabilities(self) -> tuple[dict, list[str]]:
        """Expand the method's neutral `capabilities` keys into the Claude Sandbox's
        (mcp_servers, allowed_tools) against the curated registry. This translation
        is the coding-agent-specific step — a different Sandbox maps the same keys to
        its own tool mechanism (or ignores them), so the `Method.capabilities` schema
        stays agnostic. Unknown/unvetted keys are skipped with a warning event (never
        fatal). Empty `capabilities` → ({}, []), byte-for-byte identical to a run with
        no registry. Only registry-vetted, method-declared servers wire; combined with
        `strict_mcp_config=True` the agent can never self-wire host/user MCP config."""
        from .tools import lookup

        servers: dict = {}
        allowed: list[str] = []
        for key in self.capabilities:
            spec = lookup(key)
            if spec is None or "mcp" not in spec:
                self.emit("capability_missing", key=key)
                continue
            mcp = spec["mcp"]
            servers[mcp["server_name"]] = mcp["spec"]
            allowed.extend(spec.get("allowed_tools", []))
            self.emit("capability_attached", key=key, server=mcp["server_name"])
        return servers, allowed

    def _options(self):
        from claude_agent_sdk import ClaudeAgentOptions

        forward = forward_env()
        plugins, skill_names = self._resolve_skills()
        mcp_servers, _capability_tools = self._resolve_capabilities()  # tools surfaced via event/tests
        return ClaudeAgentOptions(
            system_prompt={
                "type": "preset",
                "preset": "claude_code",
                "append": self.system_prompt_append,
            },
            setting_sources=["project", "local"],  # not "user" — reproducible runs
            permission_mode="bypassPermissions",
            cwd=str(self.workspace),
            model=self.model or None,
            fallback_model=self.fallback_model,  # auto-degrade on rate limits (keeps long runs alive)
            can_use_tool=self.can_use_tool,
            max_turns=self.max_turns,
            # Curated, method-declared MCP servers (default {} — reproducible, no host
            # leakage). We deliberately do NOT narrow `allowed_tools` to `capability_tools`:
            # that would filter the agent down to ONLY the MCP tools and break Bash/Read/etc.
            # Under bypassPermissions the wired MCP tools are already reachable and still pass
            # through our can_use_tool gate; `capability_tools` is surfaced via the
            # `capability_attached` event for auditing (and is the allowlist an L3 broker
            # would consume). strict_mcp_config stays on so only these vetted servers wire.
            mcp_servers=mcp_servers,
            strict_mcp_config=True,
            plugins=plugins,                 # explicit skill plugins (reproducible; no "user" leak)
            skills=skill_names or None,      # enable the resolved skills by name
            hooks=self._build_hooks(),       # observe-only: surface SDK auto-compaction as an event
            env=forward,
            max_buffer_size=_max_buffer_size(),  # don't let one fat tool result (e.g. a Read image) kill the run
        )

    def _build_hooks(self):
        """The kit's one hook — PURELY OBSERVATIONAL. When the SDK is about to
        auto-compact the coding agent's context, `PreCompact` fires; we emit a
        `compaction` event so the run's own auto-compaction is visible in
        `events.jsonl` (otherwise it's below the harness's event boundary and only
        *inferable* from the ctx% drop in consecutive `context_usage` events). The
        hook returns `{}` — it never blocks, injects, or steers, so it can't affect
        the run's determinism (unlike `can_use_tool`, which gates). Best-effort: if
        this SDK build lacks `HookMatcher`/`PreCompact`, we return no hooks and the
        event simply isn't emitted — never a crash."""
        try:
            from claude_agent_sdk import HookMatcher
        except ImportError:
            return None
        return {"PreCompact": [HookMatcher(hooks=[self._on_precompact])]}

    async def _on_precompact(self, input_data: dict, tool_use_id: str | None, context) -> dict:
        """PreCompact hook callback (SDK signature). Emit a `compaction` event with the
        trigger ("auto" when the window filled, "manual" if forced) and whether custom
        compaction instructions were set. Observe-only — always returns {} (no block, no
        injection). The kit survives compaction via disk-as-memory (READ STATE re-reads
        goal.md + progress.md every turn), so this just makes it auditable."""
        self.emit(
            "compaction",
            trigger=(input_data or {}).get("trigger", ""),
            has_custom_instructions=bool((input_data or {}).get("custom_instructions")),
        )
        return {}

    async def connect(self) -> None:
        import warnings

        from claude_agent_sdk import ClaudeSDKClient

        # We deliberately use permission_mode="bypassPermissions" and gate via
        # can_use_tool; the SDK warns that the callback is shadowed. That's expected
        # for this kit's containment model — suppress the noisy stack trace.
        warnings.filterwarnings("ignore", message=".*can_use_tool will not be invoked.*")

        self._client = ClaudeSDKClient(options=self._options())
        await self._client.connect()

    async def execute(self, prompt: str) -> TurnResult:
        """Run one turn: send the prompt, drain the message stream, summarize."""
        from claude_agent_sdk import (
            AssistantMessage,
            ResultMessage,
            TextBlock,
            ThinkingBlock,
            ToolUseBlock,
        )

        assert self._client is not None, "connect() first"
        await self._client.query(prompt)

        text_parts: list[str] = []
        tool_count = 0
        workspace_writes = 0
        session_id = ""
        error = ""

        async for message in self._client.receive_messages():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, ThinkingBlock):
                        # Extended-thinking reasoning — the agent's plan before it acts.
                        # Emit separately so the renderer can dim it as a distinct panel.
                        self.emit("agent_thinking", text=block.thinking)
                    elif isinstance(block, TextBlock):
                        text_parts.append(block.text)
                        # Emit only; the renderer draws the coding-agent panel (and
                        # stops the "thinking" spinner on the first block).
                        self.emit("agent_text", text=block.text)
                    elif isinstance(block, ToolUseBlock):
                        tool_count += 1
                        if block.name in ("Write", "Edit", "MultiEdit"):
                            workspace_writes += 1
                        self.emit("tool_use", detail=_format_tool_use(
                            block.name, block.input or {}, str(self.workspace)))
            elif isinstance(message, ResultMessage):
                session_id = message.session_id or ""
                if getattr(message, "is_error", False):
                    error = message.result or "agent reported an error"
                # Context-window fill — ask the SDK, don't recompute. get_context_usage()
                # returns the same data as the CLI's /context (SDK-computed `percentage`
                # against the real per-model window), so the footer stays correct across
                # models without us tracking window sizes. Best-effort.
                await self._emit_context_usage()
                # ResultMessage ends the turn.
                self.emit("agent_turn_end", writes=workspace_writes, tool_count=tool_count)
                # total_cost_usd is the session-CUMULATIVE spend on a persistent client;
                # report this turn's DELTA so the loop's running sum is correct (summing
                # the cumulative snapshots would ~5x over-report a multi-turn run).
                cumulative = float(getattr(message, "total_cost_usd", 0.0) or 0.0)
                turn_cost, self._prev_cost_usd = _cost_delta(cumulative, self._prev_cost_usd)
                return TurnResult(
                    output=(message.result or "\n".join(text_parts)),
                    tool_count=tool_count,
                    workspace_writes=workspace_writes,
                    session_id=session_id,
                    error=error,
                    cost_usd=turn_cost,
                    metrics=dict(message.usage or {}),
                )

        # Stream ended without a ResultMessage.
        return TurnResult(
            output="\n".join(text_parts),
            tool_count=tool_count,
            workspace_writes=workspace_writes,
            session_id=session_id,
            error=error,
        )

    async def _emit_context_usage(self) -> None:
        """Emit the SDK's own context-usage percentage (the CLI `/context` value).
        Best-effort: some transports/versions don't implement it, so any failure is
        swallowed — the footer just omits the ctx% that turn."""
        try:
            usage = await self._client.get_context_usage()
        except Exception:
            return
        pct = (usage or {}).get("percentage")
        if isinstance(pct, (int, float)) and pct > 0:
            self.emit("context_usage", fill_pct=float(pct))

    async def reconnect(self) -> None:
        """Start a FRESH coding-agent session (new session_id, empty context), discarding
        the accumulated conversation. The disk docs are the handoff — the next turn's phase
        prompt already tells the agent to re-orient from `goal.md` + `loop-docs/`, exactly
        as `sdharness resume` does. Env (Bedrock/AWS) is re-forwarded because `_options()`
        re-reads it on each `connect()`. The loop calls this only at a PHASE BOUNDARY when
        `method.context_reset == "phase_boundary"` — never mid-phase (that would waste the
        prompt cache for no memory-hygiene gain)."""
        await self.disconnect()
        self._client = None
        # A fresh session restarts the SDK's cumulative `total_cost_usd` at 0, so the delta
        # baseline must reset too — otherwise the first post-reset turn's cost clamps to 0
        # (see _cost_delta) and under-reports. This is the one correctness subtlety.
        self._prev_cost_usd = 0.0
        await self.connect()

    async def disconnect(self) -> None:
        if self._client is not None:
            await self._client.disconnect()
            self._client = None
