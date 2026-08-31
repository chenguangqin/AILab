# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""`sdharness compound --agentic` — the GROW rung above the deterministic write-back.

The default `compound.py` is the entry rung: LLM-free, offline, title-dedup, human-gated.
Its weakness is that *curation has no baseline* — the only signal is "the agent chose to
log this", dedup is literal-string, and nothing checks whether a lesson is durable, correct,
or already covered. Fine for a handful of patterns; it doesn't scale, and it will happily
compound a WRONG lesson.

This module adds a **read-only curator agent** that proposes a rubric-scored diff the human
approves — semantic dedup, merge/refine, quality-gate, route-to-seed-file, and (optional)
claim validation. It reuses the same one-shot `query()` + schema-enforced `output_format`
pattern as the Pilot (`steering.py`) — no new dependency, same Bedrock auth as a run.

INVARIANTS (do NOT break):
- The agent PROPOSES; the CLI WRITES. The agent never edits files directly — that preserves
  the human gate and keeps the write path deterministic + testable.
- The deterministic path stays the DEFAULT. This runs only under `--agentic`, and falls back
  to `compound.py` if the SDK/creds are unavailable.
- Curation stays human-gated: `--dry-run` shows the proposal and stops; otherwise the CLI
  prompts before applying, and the human can approve a subset.
"""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field

from .config import agent_context_dir
from .compound import extract_patterns, _find_progress_md, _insert_entry, _is_new
from .sandbox import forward_env, inline_schema_refs, unwrap_structured_output

# The three seed files a lesson can be routed to (the compounding corpus).
_SEED_FILES = ("LESSONS.md", "QUALITY.md", "STEERING_PLAYBOOK.md")


class ProposalItem(BaseModel):
    """One curator verdict on one candidate pattern from the run."""

    title: str
    verdict: str = Field(description="promote | merge | skip | drop")
    target_file: str = Field(default="LESSONS.md", description="LESSONS.md | QUALITY.md | STEERING_PLAYBOOK.md")
    rationale: str = Field(default="", description="one line: why this verdict")
    validation: str = Field(default="n/a", description="verified | unverified | n/a")
    proposed_text: str = Field(default="", description="the body to write (promote/merge)")
    merge_into: str = Field(default="", description="for verdict=merge: the existing title to fold into")


class Proposal(BaseModel):
    """The curator agent's structured proposal for a run's patterns."""

    items: list[ProposalItem] = Field(default_factory=list)


# Inline $ref/$defs so the CLI returns the BARE structured object, not a wrapped+stringified
# one (Pydantic emits $defs for the nested ProposalItem; the CLI wraps ref-bearing schemas —
# see sandbox.inline_schema_refs). The sink-side unwrap_structured_output still nets any residue.
_PROPOSAL_OUTPUT_FORMAT = {"type": "json_schema",
                           "schema": inline_schema_refs(Proposal.model_json_schema())}

_CURATOR_CONTRACT = """
You are a knowledge CURATOR for an autonomous coding harness. You do NOT write files —
you propose a curated diff a human will approve. Given (a) the candidate lessons a run
produced and (b) the current seed corpus, judge each candidate against this rubric and
return a structured proposal.

**Promote a lesson only if it is:**
- durable (true beyond this one run), AND
- reusable (a future run will plausibly hit it), AND
- non-redundant (not already covered SEMANTICALLY by the corpus — not just by exact title), AND
- correctly routed, AND
- validated (the claim checks out) or explicitly flagged unverified, AND
- **residue** — NOT readily supplied by a doc, a tool the agent already has (WebFetch/WebSearch,
  boto3/service-model introspection, a `--help`), or a skill. A durable-but-DOCUMENTED fact — an API
  signature, a published IAM policy, a documented default — does NOT belong in the seed: the agent
  should re-fetch it from the source of truth, not carry a copy that silently drifts. Only an
  un-Googleable gotcha (an undocumented trap, a version/behavior surprise you paid a failure to find)
  earns a durable lesson. When in doubt, prefer a doc pointer over a transcribed fact.

Per candidate, set `verdict`:
- "promote": a durable, reusable, non-redundant, residue-grade truth → include `proposed_text` (may
  refine the wording; if a doc backs part of it, cite the doc and keep only the residue).
- "merge": a more-specific instance of an EXISTING corpus entry → set `merge_into` to that entry's
  title and `proposed_text` to the generalized replacement body.
- "skip": already covered semantically → cite the covering entry in `rationale`.
- "drop": one-off, not durable/reusable, or likely WRONG → say why in `rationale`. Use the reason
  "documented-elsewhere" when the ONLY problem is that a doc/tool/`--help`/introspection already
  supplies it (name the source in `rationale`) — this keeps the seed lean and the human diff shows
  exactly why a plausible-looking lesson was not promoted.

Route each promoted/merged lesson to `target_file`:
- LESSONS.md  — a build-failure→fix pattern or general engineering truth
- QUALITY.md  — a definition of "good" / a quality bar
- STEERING_PLAYBOOK.md — a Pilot/steering tactic

Set `validation`: "verified" if you're confident the claim is correct, "unverified" if it's a
version/API/config specific claim you could not confirm (flag rather than silently promote — a
confidently-stated WRONG lesson is worse than none), "n/a" for skip/drop.

Return `{"items": [ ... ]}` covering every candidate.
"""


def _seed_corpus_text(corpus_dir: Path) -> str:
    """Concatenate the current seed files so the curator can judge redundancy/routing."""
    parts: list[str] = []
    for name in _SEED_FILES:
        p = corpus_dir / name
        if p.is_file():
            parts.append(f"### === {name} ===\n{p.read_text()}")
    return "\n\n".join(parts) if parts else "(empty corpus)"


def _build_prompt(patterns: list[tuple[str, str]], corpus_text: str) -> str:
    cand = "\n\n".join(f"#### {t}\n{b}" for t, b in patterns) or "(no titled patterns)"
    return (
        f"{_CURATOR_CONTRACT}\n\n"
        f"## Current seed corpus (judge redundancy + routing against this)\n{corpus_text}\n\n"
        f"## Candidate lessons from the finished run\n{cand}\n"
    )


async def propose(run_dir: Path, corpus_dir: Path | None = None,
                  model: str | None = None) -> Proposal:
    """Run the read-only curator agent and return its structured Proposal.

    Reuses the Pilot's one-shot `query()` + `output_format` pattern (read-only tools; the
    agent proposes text, never writes). Raises if the SDK is unavailable so the caller can
    fall back to the deterministic path."""
    from claude_agent_sdk import (  # imported lazily so the deterministic path needs no SDK
        AssistantMessage,
        ClaudeAgentOptions,
        ResultMessage,
        TextBlock,
        query,
    )

    corpus_dir = corpus_dir or agent_context_dir()
    progress = _find_progress_md(run_dir)
    if progress is None:
        raise FileNotFoundError(f"No progress.md found in {run_dir} (root or *-docs/).")
    patterns = extract_patterns(progress.read_text())
    prompt = _build_prompt(patterns, _seed_corpus_text(corpus_dir))

    options = ClaudeAgentOptions(
        system_prompt={"type": "preset", "preset": "claude_code", "append": ""},
        setting_sources=["project", "local"],
        permission_mode="bypassPermissions",
        allowed_tools=["Read", "Grep", "Glob"],  # read-only — the curator proposes, never writes
        cwd=str(run_dir),
        model=model or os.environ.get("HARNESS_STEERING_MODEL") or os.environ.get("ANTHROPIC_MODEL") or None,
        max_turns=8,
        output_format=_PROPOSAL_OUTPUT_FORMAT,  # schema-enforced Proposal
        mcp_servers={},
        strict_mcp_config=True,
        env=forward_env(),  # SAME env as the inner coding agent — no auth/model drift
    )

    structured: dict | None = None
    text_parts: list[str] = []
    # Stop at ResultMessage (terminal) — do NOT iterate PAST it: the CLI process has already
    # exited, so a further `__anext__` surfaces a spurious "Claude Code returned an error
    # result" (steering.py breaks here for the same reason, and works live). The subtlety:
    # this handler runs under a one-shot `asyncio.run(propose())` (steering runs inside the
    # loop's long-lived event loop), so a bare `break` leaves the SDK generator SUSPENDED;
    # asyncio.run's shutdown_asyncgens() then calls aclose() on it CONCURRENTLY with its
    # still-alive backing task → "RuntimeError: aclose(): asynchronous generator is already
    # running" and the curator silently returns empty. Fix: after the break, explicitly
    # `await agen.aclose()` HERE (inside the live loop) so the generator finalizes
    # deterministically before teardown races it. Verified on a live workshop IDE.
    agen = query(prompt=prompt, options=options)
    try:
        async for message in agen:
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        text_parts.append(block.text)
            elif isinstance(message, ResultMessage):
                structured = getattr(message, "structured_output", None)
                if message.result:
                    text_parts.append(message.result)
                break
    finally:
        aclose = getattr(agen, "aclose", None)
        if aclose is not None:
            try:
                await aclose()  # finalize in the live loop, not during asyncio.run teardown
            except Exception:
                pass  # already finalized / nothing to close

    return _coerce_proposal(structured, "\n".join(text_parts))


def _coerce_proposal(structured: dict | None, text: str) -> Proposal:
    """Prefer the schema-enforced structured output; tolerate a JSON blob in text.
    Fail SAFE: anything unparseable yields an empty proposal (nothing gets written)."""
    # The SDK may wrap/stringify the output_format payload (see unwrap_structured_output);
    # normalize before reading it, or a correct curator verdict is silently discarded.
    normalized = unwrap_structured_output(structured)
    if isinstance(normalized, dict) and "items" in normalized:
        try:
            return Proposal(**normalized)
        except Exception:
            pass
    # Tolerant fallback: find a JSON object in the text.
    import json
    import re
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return Proposal(**json.loads(m.group(0)))
        except Exception:
            pass
    return Proposal(items=[])


def apply_proposal(proposal: Proposal, corpus_dir: Path | None = None,
                   approved_titles: set[str] | None = None) -> dict[str, list[str]]:
    """Apply the approved subset — the CLI writes, never the agent. Routes each promoted/
    merged item to its target seed file. `approved_titles=None` means apply all promote/merge
    items (the CLI passes the human-approved subset). Returns {file: [applied titles]}.

    Skip/drop verdicts are never written. A merge rewrites the `merge_into` entry in place
    (falls back to insert if the target title isn't found). Unknown target_file → LESSONS.md."""
    corpus_dir = corpus_dir or agent_context_dir()
    applied: dict[str, list[str]] = {}
    # cache file contents so multiple items to the same file accumulate
    cache: dict[str, str] = {}

    def _load(fname: str) -> str:
        if fname not in cache:
            p = corpus_dir / fname
            cache[fname] = (p.read_text() if p.is_file()
                            else f"# {fname[:-3]}\n\n## Patterns\n")
        return cache[fname]

    for item in proposal.items:
        if item.verdict not in ("promote", "merge"):
            continue
        if approved_titles is not None and item.title not in approved_titles:
            continue
        fname = item.target_file if item.target_file in _SEED_FILES else "LESSONS.md"
        content = _load(fname)
        body = item.proposed_text.strip() or "(no body)"
        if item.verdict == "merge" and item.merge_into and f"### {item.merge_into}" in content:
            content = _replace_entry(content, item.merge_into, item.title, body)
        elif _is_new(content, item.title):
            content = _insert_entry(content, item.title, body)
        else:
            content = _replace_entry(content, item.title, item.title, body)
        cache[fname] = content
        applied.setdefault(fname, []).append(item.title)

    for fname, content in cache.items():
        if fname in applied:  # only write files we changed
            (corpus_dir / fname).write_text(content)
    return applied


def _replace_entry(content: str, old_title: str, new_title: str, body: str) -> str:
    """Replace the `### old_title` block (up to the next `### ` or `## `) with a new block."""
    import re
    pat = re.compile(rf"^### {re.escape(old_title)}\s*\n.*?(?=^### |^## |\Z)", re.DOTALL | re.MULTILINE)
    entry = f"### {new_title}\n\n{body}\n\n"
    if pat.search(content):
        return pat.sub(entry, content, count=1)
    return _insert_entry(content, new_title, body)
