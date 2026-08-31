# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""The run loop — the outer harness's turn cycle.

This is the whole thing, and it is deliberately small enough to read in one sitting:

    stage workspace (intent files + agent-context)
    connect the coding-agent sandbox
    repeat until complete or a kill switch trips:
        1. build the turn prompt (phase steering + last Pilot direction)
        2. run ONE coding-agent turn (inner harness)
        3. checkpoint (git commit)
        4. advance the phase if its structural gate is satisfied  (deterministic)
        5. if complete → stop
        6. steer: the Pilot returns a typed GO/NO_GO + direction  (outer harness).
           NO_GO = feedback (direction → next prompt) + escalation (counts as
           no-progress, climbing the kill switch until the agent course-corrects).
        7. kill-switch check
    disconnect

Everything hard (which agent, what phases, how to review) lives behind the
Method / Strategy / Sandbox seams — the loop itself is agent- and method-agnostic.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from . import phase_authority
from .config import agent_context_dir, read_prompt
from .gates import build_can_use_tool
from .killswitch import update_and_check
from .models import Method, RunState, Strategy
from .sandbox import ClaudeCodeSandbox
from .steering import steer


def stage_workspace(project_dir: Path, workspace: Path, method: Method, resume: bool = False) -> None:
    """Copy intent files + the agent-context seed into a fresh run workspace.

    Layout follows the "inputs vs generated state" split (upstream sdharness #45):

      * **Authored inputs live at the workspace ROOT** — the intake the user wrote
        (`vision.md` / `tech-env.md` / any provided resources), the `goal.md`
        milestone contract, and the agent-context seed (`CLAUDE.md`, `QUALITY.md`,
        `LESSONS.md`). These are what you'd `git init` a real project around.
      * **Generated state lives under `<method>-docs/`** (e.g. `loop-docs/`) — the
        artifacts the run PRODUCES (`research.md`, `architecture.md`, `design.md`,
        `progress.md`, `integration-report.json`) plus the harness `events.jsonl`.

    So the root reads like a real project (inputs + the deliverable the agent builds),
    with all *generated* harness bookkeeping quarantined in the one dir the gates key on."""
    workspace.mkdir(parents=True, exist_ok=True)

    # Brownfield guard: if the workspace was SEEDED from a prior run (e.g. the
    # "add a chat agent on top of my site" flow copies a finished run dir in), it
    # arrives carrying that run's generated state — `<method>-docs/` (with a green
    # `integration-report.json`) and a completed `goal.md`. Left in place, THIS run's
    # phase gates + terminal predicate are satisfied by the PREVIOUS run's artifacts,
    # so the loop "completes" on turn 1 having built nothing new (a silent no-op).
    # Archive that stale generated state aside so the new intake re-plans from scratch.
    # Skipped for --in-place (workspace IS the project dir), where a re-run legitimately
    # continues in place and there's no "seeded from elsewhere" copy to quarantine.
    docs_dir = workspace / f"{method.name}-docs"
    # "Stale" = generated PLAN/BUILD/VERIFY artifacts from a prior run (a completed
    # goal.md, or research/architecture/design/progress/integration-report in the docs
    # dir). NOT the run_config line __main__ just appended to events.jsonl for THIS run —
    # events.jsonl alone must not trigger archival (else every normal run wipes its own
    # banner event and replay loses the kickoff panel).
    stale_docs = [p for p in docs_dir.glob("*")
                  if p.name != "events.jsonl"] if docs_dir.is_dir() else []
    goal = workspace / "goal.md"
    # On RESUME the prior run's `goal.md` + `<method>-docs/` are NOT stale — they are
    # exactly the state we're continuing from (the disk-doc handoff). Never archive them.
    if not resume and workspace.resolve() != project_dir.resolve() and (stale_docs or goal.exists()):
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        attic = workspace / f".superseded-{stamp}"
        attic.mkdir(parents=True, exist_ok=True)
        if goal.exists():
            shutil.move(str(goal), str(attic / goal.name))
        if stale_docs:
            # move the whole docs dir aside (preserving events.jsonl by re-teeing later),
            # but keep this run's freshly-appended events.jsonl in place.
            events = docs_dir / "events.jsonl"
            saved = events.read_bytes() if events.is_file() else None
            shutil.move(str(docs_dir), str(attic / docs_dir.name))
            docs_dir.mkdir(parents=True, exist_ok=True)
            if saved is not None:
                events.write_bytes(saved)
        # Drop the SEED's inherited git history too. A workspace cloned from a prior
        # completed run carries that run's `.git` — including its `turn/<N>` checkpoint
        # tags and a HEAD at the seed's final "complete" commit. Left in place, the fresh
        # `git init` below is a no-op re-init that PRESERVES those tags, so a later
        # `sdharness resume` can `restore_to_turn(seed's max turn)` straight onto the
        # seed's finished state (a silent no-op "completion"). Archiving goal.md/docs is
        # not enough — the git tags are the real poison. Move `.git` aside so this run
        # starts from a clean checkpoint namespace of its own.
        seed_git = workspace / ".git"
        if seed_git.is_dir():
            shutil.move(str(seed_git), str(attic / "git"))

    # Create the generated-state dir up front so events.jsonl has a home even before
    # the agent writes its first artifact. The agent produces everything else in here.
    (workspace / f"{method.name}-docs").mkdir(parents=True, exist_ok=True)

    def _stage(src: Path, dst: Path) -> None:
        # Copy src → dst, but never onto itself. Under `--in-place` the workspace IS
        # the project dir, so the intake already lives at dst — a self-copy would raise
        # shutil.SameFileError. Skip it: the file is already in place, which is exactly
        # what brownfield-in-place wants.
        if src.resolve() == dst.resolve():
            return
        shutil.copy2(src, dst)

    # Authored inputs (vision.md / tech-env.md / goal.md …) → workspace ROOT.
    for name in method.intent_files + method.context_files:
        src = project_dir / name
        if src.is_file():
            _stage(src, workspace / name)

    # Also copy any *.md the user provided that the method didn't name explicitly
    # (e.g. images.md) — supporting inputs, so they land at the root too.
    for src in project_dir.glob("*.md"):
        dst = workspace / src.name
        if not dst.exists():
            _stage(src, dst)

    # Agent-context seed → the coding agent reads these (CLAUDE.md, QUALITY.md,
    # LESSONS.md). All at the ROOT: CLAUDE.md so Claude Code auto-loads it as project
    # context, the rest alongside so they read like the project's own docs. Don't
    # clobber a brownfield project's own CLAUDE.md — only seed what isn't already there.
    ctx = agent_context_dir()
    for name in method.agent_context_files:
        src = ctx / name
        dst = workspace / name
        if src.is_file() and not dst.exists():
            _stage(src, dst)

    # Stage a .gitignore so the per-turn checkpoints (and the final run) stay lean —
    # generated dependency/build trees are large and noisy and shouldn't land in the
    # run's git history. Only written if the agent hasn't provided its own.
    gitignore = workspace / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text(
            "\n".join([
                "# Harness: keep generated dependency/build trees out of run checkpoints.",
                "node_modules/", ".venv/", "venv/", "__pycache__/", "*.pyc",
                "dist/", "build/", ".pytest_cache/", ".next/", "cdk.out/", ".DS_Store",
            ]) + "\n"
        )

    _git(workspace, "init", "-q")
    _git(workspace, "add", "-A")
    _git(workspace, "commit", "-q", "-m", "sdharness: stage workspace", allow_fail=True)


def _git(workspace: Path, *args: str, allow_fail: bool = False) -> None:
    try:
        subprocess.run(
            ["git", *args],
            cwd=workspace,
            check=not allow_fail,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        if not allow_fail:
            raise


def checkpoint(workspace: Path, turn: int, phase: str) -> None:
    """Commit the turn so the run is resumable/auditable (crash recovery).

    Also tag the commit `turn/<N>` — a stable marker `sdharness resume` resets to, so a
    run interrupted mid-way through the NEXT turn (a half-written file) rolls back to the
    last CLEAN turn boundary before continuing (mirrors upstream's checkpoint tags)."""
    _git(workspace, "add", "-A")
    _git(workspace, "commit", "-q", "-m", f"sdharness turn {turn} [{phase}]", allow_fail=True)
    _git(workspace, "tag", "-f", f"turn/{turn}", allow_fail=True)


def restore_to_turn(workspace: Path, turn: int, method_name: str = "loop") -> bool:
    """Hard-reset the workspace to the `turn/<N>` checkpoint, dropping any partial writes
    from an interrupted later turn. Returns True if the checkpoint existed and was restored.
    Best-effort: a workspace without the tag (or without git) resumes against the working
    tree as-is (still valid — the completed turns' files are already on disk).

    The event log is APPEND-ONLY and is preserved across the reset — only the deliverable
    /artifact *files* roll back to the clean turn boundary; `events.jsonl` keeps its full
    history (including the interrupted turn's partial events and the resume banner)."""
    tag = f"turn/{turn}"
    try:
        found = subprocess.run(["git", "tag", "-l", tag], cwd=workspace,
                               capture_output=True, text=True, check=False).stdout.strip()
    except (FileNotFoundError, OSError):
        return False
    if not found:
        return False
    # Preserve the append-only event log across the hard reset (the reset would otherwise
    # rewind events.jsonl to its turn-N committed state, dropping later + resume events).
    events = workspace / f"{method_name}-docs" / "events.jsonl"
    saved = events.read_bytes() if events.is_file() else None
    _git(workspace, "reset", "--hard", tag, allow_fail=True)
    _git(workspace, "clean", "-fd", "-e", f"{method_name}-docs", allow_fail=True)
    if saved is not None:
        events.parent.mkdir(parents=True, exist_ok=True)
        events.write_bytes(saved)
    return True


def _turn_prompt(method: Method, phase: str, turn: int, direction: str,
                 resume_from: int = 0) -> str:
    """Assemble the per-turn prompt: phase instruction + last Pilot direction."""
    parts: list[str] = []
    phase_instruction = method.phase_prompts.get(phase, "")
    if phase_instruction:
        parts.append(phase_instruction)
    else:
        parts.append(f"You are in the {phase} phase. Do the next unit of work for it.")
    if direction:
        parts.append(f"\n## Steering direction from the Pilot (last review)\n{direction}")
    if resume_from and turn == resume_from + 1:
        # First turn of a resumed run — this is a FRESH coding-agent session with no
        # memory of the prior turns. The on-disk artifacts are the handoff: re-orient
        # from them before doing anything, then continue where the prior run stopped.
        parts.append(
            f"\nThis run is being RESUMED at turn {turn} (a prior run reached turn {resume_from} "
            "then stopped). You are a fresh session — re-orient from the workspace on disk before "
            "acting: read `goal.md` (the contract — find the FIRST unchecked `- [ ]` milestone) and "
            "`loop-docs/progress.md` (what's been done, decisions, blockers). Then continue from that "
            "first unchecked milestone. Do NOT restart completed work or re-run finished phases."
        )
    if turn == 1:
        parts.append(
            "\nThis is turn 1. The authored inputs are at the workspace ROOT — read the intake "
            "(`vision.md` / `tech-env.md`) and the agent-context seed (`CLAUDE.md` / `QUALITY.md` / "
            "`LESSONS.md`) before you start. Write everything you PRODUCE for the harness "
            "(`research.md`, `architecture.md`, `progress.md`, `integration-report.json`, …) under "
            "`loop-docs/`, and build the deliverable itself at the workspace root."
        )
    return "\n".join(parts)


def _tee_events(inner: Callable[..., None], path: Path) -> Callable[..., None]:
    """Wrap an emit callable so every event is ALSO appended to `path` as one JSON
    line — the run's durable event record. Best-effort: a write failure never breaks
    a run (the inner emitter — renderer or NDJSON — always fires first)."""
    def emit(event: str, **fields: Any) -> None:
        inner(event, **fields)
        try:
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"event": event, **fields}, default=str) + "\n")
        except OSError:
            pass
    return emit


def _usage_summary(metrics: dict[str, Any]) -> dict[str, int]:
    """Pull the token counts out of ResultMessage.usage for the turn_end event, so a
    run's events.jsonl records where the tokens went — including cache hits. A high
    `cache_read` on later turns is the signal that prompt caching is engaging (the
    static system prompt + tools + prior context are being reused, not re-billed at
    full rate). Absent keys default to 0."""
    m = metrics or {}
    return {
        "input_tokens": int(m.get("input_tokens", 0) or 0),
        "output_tokens": int(m.get("output_tokens", 0) or 0),
        "cache_read_input_tokens": int(m.get("cache_read_input_tokens", 0) or 0),
        "cache_creation_input_tokens": int(m.get("cache_creation_input_tokens", 0) or 0),
    }


def _noop_emit(event: str, **fields: Any) -> None:
    """Default event sink — does nothing. The CLI passes a real one for `--json`
    (streams NDJSON so a coding agent driving the harness can react per turn)."""


async def run(
    project_dir: Path,
    workspace: Path,
    method: Method,
    strategy: Strategy,
    max_turns: int = 100,
    emit: Callable[..., None] = _noop_emit,
    resume_from: int = 0,
    resume_cost: float = 0.0,
    resume_phase: str = "",
    max_budget: float = 0.0,
    fallback_model: str = "",
) -> RunState:
    """Drive the method to completion (or a kill switch). Returns the final state.

    Runs are autonomous: the Pilot answers its own gates (auto-GO), no human
    prompting. Deterministic gates + containment are always enforced regardless.

    `emit(event, **fields)` is called at each loop event (run_start, phase_advance,
    turn_end, complete, kill_switch). Human mode attaches a CLIRenderer; `--json`
    attaches an emitter that streams one JSON object per line so an agent/CI driving
    the run can observe progress turn by turn.

    RESUME: `resume_from` seeds the turn counter, `resume_cost` the running total, and
    `resume_phase` the phase the prior (interrupted) run was executing in — all read back
    from its event log — so `sdharness resume` continues the same workspace instead of
    starting over. Seeding the phase (rather than defaulting to `phases[0]`) means the
    resumed run's FIRST turn reports its true phase (e.g. BUILD), not a misleading walk
    back through RESEARCH→PLAN as the gates re-advance. The gates still own advancement
    from there; a fresh coding-agent session re-orients from `goal.md` + `loop-docs/` (the
    disk-doc handoff); kill-switch counters start clean. `resume_from == 0` = fresh run.
    """
    resume = resume_from > 0
    if resume:
        # Roll the workspace back to the last CLEAN turn boundary, discarding any partial
        # files a mid-turn interrupt left behind, before continuing. The event log survives.
        restore_to_turn(workspace, resume_from, method.name)
    stage_workspace(project_dir, workspace, method, resume=resume)

    # Tee every event to <method>-docs/events.jsonl — the auditable record of the
    # run, reviewable after the fact (and committed each turn by checkpoint()). The
    # human renderer / --json emitter still fires; this just also persists. Wrapping
    # here (not in loop/sandbox) keeps the single-emit-seam clean. On resume this
    # APPENDS to the prior run's log (continuous history), which _tee_events already does.
    emit = _tee_events(emit, workspace / f"{method.name}-docs" / "events.jsonl")

    _first_phase = method.phases[0].name if method.phases else "BUILD"
    # On resume, seed the phase the prior run was executing in (from the log) so the first
    # resumed turn reports truthfully; the gates still advance it from there. Fall back to
    # the first phase if the log had no phase (or it names one this method no longer has).
    _valid_phases = {p.name for p in method.phases}
    _seed_phase = resume_phase if (resume and resume_phase in _valid_phases) else _first_phase
    state = RunState(
        workspace=workspace,
        method_name=method.name,
        strategy_name=strategy.name,
        phase=_seed_phase,
        turn=resume_from,
        total_cost_usd=resume_cost,
    )
    emit("run_start", method=method.name, strategy=strategy.name,
         phase=state.phase, max_turns=max_turns, workspace=str(workspace),
         resumed_from_turn=resume_from)

    # Resuming already at/over the turn budget: nothing to do until the ceiling is raised.
    # Stop cleanly (no sandbox connect / Bedrock spend) with an actionable reason.
    if resume_from >= max_turns:
        state.complete_reason = (f"resume: already at the turn budget ({resume_from}/{max_turns}) "
                                 "— raise --max-turns to continue")
        emit("stopped", reason=state.complete_reason)
        emit("complete", complete=False, reason=state.complete_reason, turns=state.turn,
             phase=state.phase, total_cost_usd=round(state.total_cost_usd, 4),
             milestones_done=0, milestones_total=0, error=None)
        return state

    system_prompt = read_prompt(method.dir, method.system_prompt_file)
    can_use_tool = build_can_use_tool(method, workspace)
    sandbox = ClaudeCodeSandbox(
        workspace=workspace,
        system_prompt_append=system_prompt,
        can_use_tool=can_use_tool,
        max_turns=200,
        emit=emit,  # coding-agent output flows through the same event stream
        skills=method.skills,
        capabilities=method.capabilities,  # curated MCP tools, by registry key (default none)
        fallback_model=fallback_model or None,  # auto-degrade on rate limits
    )

    direction = ""
    connected = False
    try:
        await sandbox.connect()  # inside the try: a connect crash (e.g. SDK init) must emit a terminal event too
        connected = True
        while state.turn < max_turns and not state.complete:
            state.turn += 1
            prev_phase = state.phase
            turn_started = time.monotonic()
            emit("turn_start", turn=state.turn, phase=state.phase)

            # 1–2. Run one coding-agent turn.
            prompt = _turn_prompt(method, state.phase, state.turn, direction, resume_from)
            result = await sandbox.execute(prompt)

            state.total_cost_usd += result.cost_usd

            # 3. Checkpoint.
            checkpoint(workspace, state.turn, state.phase)

            # 4. Deterministic phase advancement (harness owns this, not the agent).
            #    Compute the next phase now (the terminal check + kill-switch need it),
            #    but DON'T surface it until AFTER the Pilot reviews — the Pilot must
            #    judge the phase the work actually executed in (`prev_phase`), not the
            #    one the gate just advanced into. Otherwise a successful RESEARCH turn
            #    gets reviewed as "PLAN hasn't started" → a nonsensical NO_GO.
            next_phase = phase_authority.next_phase(method, state.phase, workspace)
            advanced = next_phase != prev_phase

            # 5. Terminal completion? (evaluated on the post-turn workspace)
            if phase_authority.is_complete(method, workspace):
                state.phase = next_phase
                state.complete = True
                state.complete_reason = "terminal completion predicate satisfied"
                done, total = phase_authority.milestones(workspace)
                emit("turn_end", turn=state.turn, phase=prev_phase, decision="GO",
                     max_turns=max_turns, elapsed=time.monotonic() - turn_started,
                     writes=result.workspace_writes, cost_usd=round(result.cost_usd, 4),
                     total_cost_usd=round(state.total_cost_usd, 4),
                     usage=_usage_summary(result.metrics),
                     milestones_done=done, milestones_total=total)
                break

            # 6. Steering review (the Pilot), against the phase the work executed in.
            #    The verdict does TWO things:
            #    (a) feedback — `direction` is injected into the NEXT turn's prompt
            #        (_turn_prompt) so the coding agent course-corrects; and
            #    (b) escalation — a NO_GO counts as "no progress" below, so a streak
            #        of un-corrected NO_GOs climbs the kill-switch counter and stops
            #        the run. A GO resets it. That's what makes NO_GO honest rather
            #        than printed-and-ignored.
            emit("pilot_start", turn=state.turn, phase=prev_phase)
            review = await steer(strategy, workspace, prev_phase, state.turn, result.output)
            direction = review.direction
            state.total_cost_usd += review.cost_usd  # the Pilot is a real, separate model call
            emit("pilot_review", turn=state.turn, decision=review.decision,
                 direction=review.direction, gate_held=review.gate_held)

            # Now surface the phase advance (after the verdict on the executed phase).
            if advanced:
                emit("phase_advance", turn=state.turn, **{"from": prev_phase, "to": next_phase})
            state.phase = next_phase

            # Per-turn progress: one structured turn_end event; the renderer draws
            # the dim human status line (cost/milestones) from it. Reported against the
            # executed phase so "Turn 1 · RESEARCH · GO" reads truthfully.
            done, total = phase_authority.milestones(workspace)
            emit("turn_end", turn=state.turn, phase=prev_phase, decision=review.decision,
                 direction=review.direction, gate_held=review.gate_held,
                 max_turns=max_turns, elapsed=time.monotonic() - turn_started,
                 writes=result.workspace_writes, cost_usd=round(result.cost_usd, 4),
                 total_cost_usd=round(state.total_cost_usd, 4),
                 usage=_usage_summary(result.metrics),
                 milestones_done=done, milestones_total=total)

            # 6b. Optional context reset at the phase boundary. When the method opts in
            #     (context_reset == "phase_boundary") and the phase actually advanced this
            #     turn, start a FRESH coding-agent session for the next phase — the disk
            #     docs (goal.md + loop-docs/) are the handoff, exactly as resume relies on.
            #     Default ("none") skips this entirely, so persistent-session runs are
            #     byte-for-byte unchanged. Emitted after turn_end so the order reads
            #     phase_advance → turn_end → context_reset → (next) turn_start.
            if advanced and method.context_reset == "phase_boundary":
                await sandbox.reconnect()
                emit("context_reset", turn=state.turn,
                     **{"from": prev_phase, "to": next_phase}, reason="phase_boundary")

            # 7. Kill-switch check. A NO_GO turn does not count as progress even if it
            #    wrote files or advanced a phase — the reviewer judged the work not
            #    acceptable, so we let the no-progress counter climb toward the cap.
            made_progress = (advanced or result.workspace_writes > 0) and review.decision == "GO"
            stop = update_and_check(
                method, state,
                wrote_files=result.workspace_writes > 0,
                made_progress=made_progress,
                error=result.error,
            )
            if stop:
                state.complete = False
                state.complete_reason = f"kill switch: {stop}"
                emit("kill_switch", turn=state.turn, reason=stop)
                break

            # 8. Budget ceiling. A hard USD cap on the whole run (agent + Pilot spend),
            #    checked after the turn's full cost is accrued — mirrors the max_turns
            #    ceiling and stays authoritative across resumes (resume_cost seeds the
            #    running total). 0 = no ceiling (default). Unlike the kill switch (a
            #    safety net for stuck runs), this is a deliberate spend limit.
            if max_budget and state.total_cost_usd >= max_budget:
                state.complete = False
                state.complete_reason = (
                    f"budget ceiling (${max_budget:.2f}) reached at "
                    f"${state.total_cost_usd:.2f} — raise --max-budget to continue"
                )
                emit("stopped", reason=state.complete_reason)
                break
        else:
            if not state.complete:
                state.complete_reason = f"reached max_turns ({max_turns})"
                emit("stopped", reason=state.complete_reason)
    except Exception as e:
        # A RAISED failure (SDK/transport/JSON-buffer overflow, a connect/execute crash) —
        # distinct from a model-*reported* error, which comes back as TurnResult(error=…) and
        # feeds the kill switch above. Without this, the exception would unwind past `finally`
        # and skip the terminal `complete` emit, so the run would die with NO terminal event in
        # events.jsonl — a consumer couldn't tell "died" from "finished". Record it on state and
        # fall through (no re-raise) to the single `complete` emit below, which now carries the
        # error. `cmd_run` then exits non-zero (return 0 if state.complete else 1). We catch
        # `Exception` (not `BaseException`), so Ctrl-C / cancellation still interrupt cleanly.
        state.complete = False
        state.error = f"{type(e).__name__}: {e}"
        state.complete_reason = f"run failed: {state.error}"
    finally:
        if connected:
            await sandbox.disconnect()  # only if connect() succeeded — else the client is half-open

    done, total = phase_authority.milestones(workspace)
    emit("complete", complete=state.complete, reason=state.complete_reason,
         turns=state.turn, phase=state.phase,
         total_cost_usd=round(state.total_cost_usd, 4),
         milestones_done=done, milestones_total=total, error=state.error)
    return state
