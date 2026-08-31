# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""`sdharness compound --agentic` — the curator agent's write path + gates.

The agent PROPOSES a structured `Proposal`; the CLI applies the approved subset. These
tests exercise the write/routing logic with a MOCKED proposal (no live Bedrock) and assert
the human-gate invariants: verdicts route correctly, skip/drop never write, merge rewrites
in place, and the deterministic default path is untouched.
"""

from __future__ import annotations

from pathlib import Path

from harness.compound_agentic import (
    Proposal,
    ProposalItem,
    _coerce_proposal,
    apply_proposal,
)


def _corpus(tmp_path: Path) -> Path:
    """A seed corpus dir with the three files, each with a Patterns section."""
    d = tmp_path / "agent-context"
    d.mkdir()
    (d / "LESSONS.md").write_text("# Lessons Learned\n\n## Patterns\n\n### Existing lesson\nold body\n")
    (d / "QUALITY.md").write_text("# Quality\n\n## Patterns\n")
    (d / "STEERING_PLAYBOOK.md").write_text("# Steering Playbook\n\n## Patterns\n")
    return d


def test_promote_routes_to_the_named_seed_file(tmp_path: Path):
    """A promote verdict writes its body to target_file (LESSONS / QUALITY / STEERING)."""
    d = _corpus(tmp_path)
    prop = Proposal(items=[
        ProposalItem(title="Bind allowedHosts to true", verdict="promote", target_file="LESSONS.md",
                     proposed_text="Vite 6 rejects 'all'; use the boolean true.", validation="verified"),
        ProposalItem(title="Define 'good' as green integration-report", verdict="promote",
                     target_file="QUALITY.md", proposed_text="Done = machine-checkable report passes."),
        ProposalItem(title="NO_GO names the concrete blocker", verdict="promote",
                     target_file="STEERING_PLAYBOOK.md", proposed_text="Always name the next artifact."),
    ])
    applied = apply_proposal(prop, corpus_dir=d)

    assert applied == {
        "LESSONS.md": ["Bind allowedHosts to true"],
        "QUALITY.md": ["Define 'good' as green integration-report"],
        "STEERING_PLAYBOOK.md": ["NO_GO names the concrete blocker"],
    }
    assert "Bind allowedHosts to true" in (d / "LESSONS.md").read_text()
    assert "Define 'good'" in (d / "QUALITY.md").read_text()
    assert "concrete blocker" in (d / "STEERING_PLAYBOOK.md").read_text()


def test_skip_and_drop_never_write(tmp_path: Path):
    """skip/drop verdicts must not touch any file."""
    d = _corpus(tmp_path)
    before = {f: (d / f).read_text() for f in ("LESSONS.md", "QUALITY.md", "STEERING_PLAYBOOK.md")}
    prop = Proposal(items=[
        ProposalItem(title="Already covered", verdict="skip", rationale="dup of Existing lesson"),
        ProposalItem(title="One-off noise", verdict="drop", rationale="not durable"),
    ])
    applied = apply_proposal(prop, corpus_dir=d)

    assert applied == {}, "skip/drop write nothing"
    for f, text in before.items():
        assert (d / f).read_text() == text, f"{f} must be unchanged"


def test_merge_rewrites_the_existing_entry_in_place(tmp_path: Path):
    """A merge folds into the named existing entry (generalizes it), not a duplicate append."""
    d = _corpus(tmp_path)
    prop = Proposal(items=[
        ProposalItem(title="Existing lesson (generalized)", verdict="merge", target_file="LESSONS.md",
                     merge_into="Existing lesson", proposed_text="generalized body covering both cases."),
    ])
    apply_proposal(prop, corpus_dir=d)
    text = (d / "LESSONS.md").read_text()

    assert "generalized body" in text
    assert "old body" not in text, "the merged-into entry's old body should be replaced"
    # exactly one entry heading remains (no near-duplicate)
    assert text.count("### ") == 1


def test_approved_subset_only(tmp_path: Path):
    """When the CLI passes an approved subset, only those titles are written."""
    d = _corpus(tmp_path)
    prop = Proposal(items=[
        ProposalItem(title="Keep me", verdict="promote", target_file="LESSONS.md", proposed_text="a"),
        ProposalItem(title="Reject me", verdict="promote", target_file="LESSONS.md", proposed_text="b"),
    ])
    applied = apply_proposal(prop, corpus_dir=d, approved_titles={"Keep me"})

    assert applied == {"LESSONS.md": ["Keep me"]}
    body = (d / "LESSONS.md").read_text()
    assert "Keep me" in body and "Reject me" not in body


def test_coerce_proposal_from_structured_output():
    """The schema-enforced structured_output parses into a Proposal."""
    p = _coerce_proposal({"items": [{"title": "T", "verdict": "promote", "proposed_text": "x"}]}, "")
    assert len(p.items) == 1 and p.items[0].verdict == "promote"


def test_coerce_proposal_through_sdk_wrapper():
    """Regression (live E2E): the curator's correct verdict came back wrapped+stringified as
    `{"findings": "{\\"items\\": [...]}"}`. Without normalization the coercion missed the
    top-level `items` key and silently returned an empty proposal — discarding a good verdict.
    unwrap_structured_output peels it so the proposal survives."""
    wrapped = {"findings": '{"items": [{"title": "documented API", "verdict": "drop",'
                           ' "rationale": "documented-elsewhere"}]}'}
    p = _coerce_proposal(wrapped, "")
    assert len(p.items) == 1
    assert p.items[0].verdict == "drop"
    assert "documented-elsewhere" in p.items[0].rationale


def test_coerce_proposal_fails_safe_to_empty():
    """Unparseable output yields an empty proposal — nothing will ever be written."""
    assert _coerce_proposal(None, "not json at all") == Proposal(items=[])
    assert _coerce_proposal({"wrong": "shape"}, "no json here") == Proposal(items=[])


def test_unknown_target_file_falls_back_to_lessons(tmp_path: Path):
    """A verdict with a bogus target_file routes to LESSONS.md rather than erroring."""
    d = _corpus(tmp_path)
    prop = Proposal(items=[
        ProposalItem(title="Stray", verdict="promote", target_file="NONSENSE.md", proposed_text="x"),
    ])
    applied = apply_proposal(prop, corpus_dir=d)
    assert applied == {"LESSONS.md": ["Stray"]}


# ── live-stream regression: propose() must DRAIN the SDK generator, never `break` ──
#
# The unit tests above mock the Proposal, so they never exercise `propose()`'s consumption
# of the SDK's async `query()` stream. A real E2E on the workshop IDE surfaced a crash the
# mocks hid: `propose()` ran under a one-shot `asyncio.run(...)`, `break`-ing out of the
# `async for` on ResultMessage left the SDK generator SUSPENDED; asyncio.run's
# shutdown_asyncgens() then called aclose() on it while its backing task was still alive →
# "RuntimeError: aclose(): asynchronous generator is already running" → an empty proposal.
# The fix drains the stream to completion. These tests inject a fake `claude_agent_sdk` and
# drive `propose()` through a REAL asyncio.run — the exact failing context.


class _RecordingStream:
    """A fake SDK message stream (async iterator) that records whether propose() explicitly
    closed it. The live crash ("aclose(): asynchronous generator is already running") happens
    because propose() `break`ed and left the SDK generator SUSPENDED, so asyncio.run's teardown
    closed it CONCURRENTLY with its still-alive task. The fix stops at ResultMessage (iterating
    PAST it surfaces a spurious 'error result' — so we must NOT drain) but then explicitly
    `await agen.aclose()` inside the live loop. So the invariant a regression guard asserts is:
    propose() calls aclose() exactly once, in-loop. `iterated_past_result` flags the OTHER
    failure mode (over-draining past the terminal ResultMessage)."""

    def __init__(self, messages):
        self._msgs = list(messages)
        self._i = 0
        self.aclose_calls = 0
        self.iterated_past_result = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        # If the consumer asks for a message after the terminal ResultMessage, that's the
        # over-drain failure mode — the real SDK surfaces a spurious error result here.
        seen_result = any(type(m).__name__ == "ResultMessage" for m in self._msgs[:self._i])
        if seen_result:
            self.iterated_past_result = True
            raise RuntimeError("Claude Code returned an error result: success")
        if self._i >= len(self._msgs):
            raise StopAsyncIteration
        m = self._msgs[self._i]
        self._i += 1
        return m

    async def aclose(self):
        self.aclose_calls += 1


def _install_fake_sdk(monkeypatch):
    """Register a minimal fake `claude_agent_sdk` in sys.modules so propose() imports it.
    `mod.set_stream(messages)` installs a `_RecordingStream` and returns it so a test can
    assert it was drained. """
    import sys
    import types

    class AssistantMessage:
        def __init__(self, content):
            self.content = content

    class ResultMessage:
        def __init__(self, structured_output=None, result="", is_error=False):
            self.structured_output = structured_output
            self.result = result
            self.is_error = is_error

    class TextBlock:
        def __init__(self, text):
            self.text = text

    class ThinkingBlock:  # part of the SDK surface
        def __init__(self, thinking=""):
            self.thinking = thinking

    class ToolUseBlock:
        def __init__(self, name="", input=None):
            self.name = name
            self.input = input or {}

    class ClaudeAgentOptions:
        def __init__(self, **kw):
            self.__dict__.update(kw)

    mod = types.ModuleType("claude_agent_sdk")
    mod.AssistantMessage = AssistantMessage
    mod.ResultMessage = ResultMessage
    mod.TextBlock = TextBlock
    mod.ThinkingBlock = ThinkingBlock
    mod.ToolUseBlock = ToolUseBlock
    mod.ClaudeAgentOptions = ClaudeAgentOptions

    holder = {}

    def set_stream(messages):
        holder["stream"] = _RecordingStream(messages)
        return holder["stream"]

    mod.set_stream = set_stream
    mod.query = lambda prompt=None, options=None: holder["stream"]
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", mod)
    return mod


def _run_dir_with_patterns(tmp_path: Path) -> Path:
    run = tmp_path / "run"
    (run / "loop-docs").mkdir(parents=True)
    (run / "loop-docs" / "progress.md").write_text(
        "# Progress\n\n## Patterns\n\n### A real gotcha\nsome undocumented trap and its fix\n"
    )
    return run


def test_propose_closes_stream_in_loop_and_stops_at_result(tmp_path: Path, monkeypatch):
    """propose() under asyncio.run must (1) return the curator's structured proposal,
    (2) explicitly `aclose()` the SDK stream inside the live loop (so asyncio.run teardown
    never races it → the 'already running' crash), and (3) STOP at ResultMessage — never
    iterate past it (which the SDK surfaces as a spurious 'error result: success'). A
    trailing message after ResultMessage is the over-drain tripwire."""
    import asyncio

    from harness import compound_agentic as ca

    mod = _install_fake_sdk(monkeypatch)
    stream = mod.set_stream([
        mod.AssistantMessage([mod.TextBlock("thinking out loud")]),
        mod.ResultMessage(structured_output={"items": [
            {"title": "A real gotcha", "verdict": "promote", "target_file": "LESSONS.md",
             "proposed_text": "the fix"}]}, result=""),
        mod.AssistantMessage([mod.TextBlock("trailing chatter")]),  # over-drain tripwire
    ])

    run = _run_dir_with_patterns(tmp_path)
    corpus = _corpus(tmp_path)

    # The exact failing context: a fresh one-shot event loop. Must NOT raise.
    proposal = asyncio.run(ca.propose(run, corpus_dir=corpus))

    assert len(proposal.items) == 1
    assert proposal.items[0].title == "A real gotcha"
    assert proposal.items[0].verdict == "promote"
    # Regression guards:
    assert stream.aclose_calls >= 1, "propose() must aclose() the stream inside the live loop"
    assert stream.iterated_past_result is False, "propose() must stop at ResultMessage, not over-drain"
