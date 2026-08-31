# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""CLI entrypoint — `harness run <intent-dir> [--method loop]`.

Deliberately tiny: `run`, `methods`, and `strategies` — enough to run a method and
see what's available. Add subcommands in your fork as you need them.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from . import phase_authority
from .config import _KIT_ROOT, load_method, load_strategy, runs_dir
from .console import console
from .loop import run


def _print_catalog(title: str, noun: str, items: list, *, hint: str) -> None:
    """Render a methods/strategies list: one titled block per item (name + a
    one-line summary + display name), then a next-step hint. A per-item layout
    reads better than a wide 2-column table, which overflows and wraps awkwardly
    on a narrow terminal."""
    if not items:
        console.print(f"[yellow]No {noun}s found.[/yellow] "
                      f"Author one under [cyan]{noun}s/[/cyan] — see docs/customize.md.")
        return
    console.print(f"[bold]{title}[/bold]\n")
    for it in items:
        summary = (it.description or it.display_name or "").strip()
        console.print(f"  [bold cyan]{it.name}[/bold cyan]"
                      + (f"  [grey58]— {it.display_name}[/grey58]" if it.display_name else ""))
        if summary:
            console.print(f"    [grey70]{summary}[/grey70]")
        console.print()
    console.print(f"[grey58]{hint}[/grey58]")


def _emit_json(payload: dict) -> None:
    """Print one machine-readable JSON object to stdout — for agents/CI driving
    the CLI. Kept plain (not rich) so the output parses cleanly."""
    print(json.dumps(payload, default=str))


def _append_event(workspace: Path, method_name: str, event: str, fields: dict) -> None:
    """Append one event to the run's `<method>-docs/events.jsonl`, matching the tee
    format in loop.py. Used for the banner + recap emitted outside run(), so the
    event log is complete enough for `sdharness replay` to reproduce the run."""
    path = workspace / f"{method_name}-docs" / "events.jsonl"
    try:
        # Ensure the docs dir exists — this runs for run_config BEFORE run()/stage_workspace
        # has created it, so without mkdir the append silently failed (OSError swallowed)
        # and `sdharness replay` lost the kickoff banner.
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"event": event, **fields}, default=str) + "\n")
    except OSError:
        pass


def _load_dotenv() -> None:
    """Populate os.environ from ./.env or the kit-root .env (shell vars win)."""
    import os

    for env_path in (Path.cwd() / ".env", _KIT_ROOT / ".env"):
        if not env_path.is_file():
            continue
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key, val = key.strip(), val.strip().strip('"').strip("'")
            os.environ.setdefault(key, val)


def cmd_run(args: argparse.Namespace) -> int:
    _load_dotenv()

    project_dir = Path(args.project_dir).resolve()
    if not project_dir.is_dir():
        console.print(f"[red]No such intent directory: {project_dir}[/red]")
        return 2

    method = load_method(args.method)
    strategy = load_strategy(args.strategy or method.default_strategy)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    workspace = (
        project_dir if args.in_place
        else Path(args.workspace or (runs_dir() / f"{project_dir.name}-{stamp}")).resolve()
    )

    def _rel(p: Path) -> str:
        try:
            return "./" + str(Path(p).relative_to(Path.cwd()))
        except ValueError:
            return str(p)

    # Exactly ONE subscriber to the event stream. --json streams NDJSON on stdout so
    # an agent/CI can react turn by turn; human mode attaches a CLIRenderer (panels +
    # spinners) writing to stderr. Business logic (loop/sandbox) only emits — so the
    # two channels can never mix.
    if args.json:
        emit = lambda event, **fields: _emit_json({"event": event, **fields})  # noqa: E731
    else:
        from .cli_renderer import CLIRenderer
        emit = CLIRenderer().emit
        # Surface which model drives each harness — the generator (coding agent) and
        # the evaluator (Pilot) are deliberately separate; the banner should say so.
        # Same resolution the components use: coder ← ANTHROPIC_MODEL; Pilot ←
        # HARNESS_STEERING_MODEL, falling back to ANTHROPIC_MODEL.
        _coder_model = os.environ.get("ANTHROPIC_MODEL") or "(SDK default)"
        _pilot_model = (os.environ.get("HARNESS_STEERING_MODEL")
                        or os.environ.get("ANTHROPIC_MODEL") or "(SDK default)")
        run_config = dict(method=method.name, method_display=method.display_name,
                          strategy=strategy.name,
                          # The method's OWN phases (name + optional hex color) drive the
                          # banner's phase rail — so a custom method shows ITS phases, not a
                          # hardcoded RESEARCH→PLAN→BUILD→VERIFY. Method-agnostic by design.
                          phases=[{"name": p.name, "color": p.color} for p in method.phases],
                          max_turns=args.max_turns, intent=_rel(project_dir),
                          workspace=_rel(workspace), agent_model=_coder_model,
                          pilot_model=_pilot_model,
                          max_budget=args.max_budget or 0.0,
                          fallback_model=args.fallback_model or "")
        emit("run_config", **run_config)
        # The banner + final recap are emitted here, OUTSIDE run() (which tees only
        # the loop's own events to events.jsonl). Persist them too, so `sdharness
        # replay` re-renders an identical run — banner and result card included.
        _append_event(workspace, method.name, "run_config", run_config)

    started = time.monotonic()
    state = asyncio.run(
        run(
            project_dir=project_dir,
            workspace=workspace,
            method=method,
            strategy=strategy,
            max_turns=args.max_turns,
            emit=emit,
            max_budget=args.max_budget or 0.0,
            fallback_model=args.fallback_model or "",
        )
    )
    elapsed = time.monotonic() - started

    if args.json:
        # Machine-readable recap for an agent/CI: the outcome plus the parsed
        # integration report (the VERIFY proof) when the method produced one.
        report_path = workspace / "loop-docs" / "integration-report.json"
        report = None
        if report_path.is_file():
            try:
                report = json.loads(report_path.read_text())
            except (ValueError, OSError):
                report = None
        done, total = phase_authority.milestones(workspace)
        _emit_json({
            "event": "result",
            "complete": state.complete,
            "reason": state.complete_reason,
            "error": state.error,
            "turns": state.turn,
            "max_turns": args.max_turns,
            "phase": state.phase,
            "total_cost_usd": round(state.total_cost_usd, 4),
            "milestones_done": done,
            "milestones_total": total,
            "elapsed_seconds": round(elapsed, 1),
            "method": method.name,
            "strategy": strategy.name,
            "workspace": str(workspace),
            "integration_report": report,
        })
    else:
        done, total = phase_authority.milestones(workspace)
        recap = dict(complete=state.complete, reason=state.complete_reason,
                     error=state.error,
                     turns=state.turn, max_turns=args.max_turns,
                     milestones_done=done, milestones_total=total,
                     total_cost_usd=state.total_cost_usd, elapsed=elapsed,
                     workspace=str(workspace))
        emit("result_recap", **recap)
        _append_event(workspace, method.name, "result_recap", recap)
    return 0 if state.complete else 1


def _catalog_names(builtin_dir: str, project_local_dir: str, config_file: str) -> list[str]:
    """Names of all available methods/strategies — **project-local first**, then built-in,
    deduped. Mirrors the resolution order in `config._resolve` (project-local shadows
    built-in), so `sdharness methods` LISTS a custom `./harness-methods/<name>` the same
    way `sdharness run --method <name>` would RESOLVE it (they were out of sync — the run
    found project-local methods but the listing only showed built-ins)."""
    names: list[str] = []
    for base in (Path.cwd() / project_local_dir, _KIT_ROOT / builtin_dir):
        if not base.is_dir():
            continue
        for d in sorted(base.glob("*/")):
            if (d / config_file).is_file() and d.name not in names:
                names.append(d.name)
    return names


def cmd_methods(args: argparse.Namespace) -> int:
    items = [load_method(name) for name in _catalog_names("methods", "harness-methods", "method.json")]
    if args.json:
        _emit_json([{"name": m.name, "display_name": m.display_name,
                     "description": m.description} for m in items])
    else:
        _print_catalog("Methods", "method", items,
                       hint="Run one with:  sdharness run <intake-dir> --method <name>")
    return 0


def cmd_strategies(args: argparse.Namespace) -> int:
    items = [load_strategy(name)
             for name in _catalog_names("strategies", "harness-strategies", "strategy.json")]
    if args.json:
        _emit_json([{"name": s.name, "display_name": s.display_name,
                     "description": s.description} for s in items])
    else:
        _print_catalog("Strategies", "strategy", items,
                       hint="Use one with:  sdharness run <intake-dir> --strategy <name>")
    return 0


def cmd_compound(args: argparse.Namespace) -> int:
    """Promote a finished run's progress.md Patterns into the LESSONS.md seed."""
    from .compound import compound_run

    run_dir = Path(args.run_dir).resolve()
    if not run_dir.is_dir():
        console.print(f"[red]No such run directory: {run_dir}[/red]")
        return 2

    # Agentic curation is the DEFAULT: a read-only curator agent proposes a rubric-scored
    # diff (semantic dedup / merge / quality-gate / route / validate — and the tool/doc-first
    # gate), the human approves, the CLI writes. It auto-falls back to the deterministic
    # title-dedup path when the SDK/creds are unavailable (offline), so compound never
    # hard-fails. `--deterministic` forces that offline path explicitly. (`--agentic` is a
    # deprecated no-op alias — agentic is already the default.)
    if not getattr(args, "deterministic", False):
        rc = _cmd_compound_agentic(run_dir, dry_run=args.dry_run)
        if rc is not None:
            return rc
        console.print("[yellow]Agentic curation unavailable (no SDK/creds) — "
                      "falling back to the deterministic title-dedup path.[/yellow]")

    try:
        added, skipped, _ = compound_run(run_dir, dry_run=args.dry_run)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        return 1

    if not added and not skipped:
        console.print("[dim]No titled Patterns (### blocks under ## Patterns) — nothing to compound.[/dim]")
        return 0
    verb = "would add" if args.dry_run else "added"
    for t in added:
        console.print(f"[green]+ {verb}:[/green] {t}")
    for t in skipped:
        console.print(f"[dim]· already in LESSONS.md: {t}[/dim]")
    if args.dry_run and added:
        console.print("\n[yellow]--dry-run: nothing written.[/yellow] Re-run without --dry-run to apply.")
    elif added:
        console.print(f"\n[bold green]✓ compounded {len(added)} lesson(s)[/bold green] into agent-context/LESSONS.md — open it to review.")
    return 0


def _cmd_compound_agentic(run_dir: Path, dry_run: bool) -> int | None:
    """`--agentic` handler. Returns an exit code, or None to signal "fall back to the
    deterministic path" (SDK/creds absent). The agent PROPOSES; this function (the CLI)
    WRITES only the human-approved subset — the gate is never optional."""
    import asyncio

    try:
        from .compound_agentic import apply_proposal, propose
    except ImportError:
        return None

    console.print("[grey58]Running the curator agent (read-only) — semantic dedup, quality-gate, route, validate…[/grey58]")
    try:
        proposal = asyncio.run(propose(run_dir))
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        return 1
    except Exception as e:
        # SDK missing / not connected / no creds → let the caller fall back.
        console.print(f"[grey58]curator agent could not run: {type(e).__name__}: {str(e)[:120]}[/grey58]")
        return None

    items = proposal.items
    if not items:
        console.print("[dim]The curator proposed nothing (no titled Patterns, or all judged out).[/dim]")
        return 0

    # Render the proposal grouped by verdict — a reviewable diff, not a blind write.
    _V = {"promote": "green", "merge": "cyan", "skip": "grey58", "drop": "yellow"}
    for it in items:
        color = _V.get(it.verdict, "white")
        flag = "" if it.validation in ("verified", "n/a") else f" [yellow](⚠ {it.validation})[/yellow]"
        tgt = f" → {it.target_file}" if it.verdict in ("promote", "merge") else ""
        console.print(f"[{color}]{it.verdict.upper():7}[/{color}] {it.title}{tgt}{flag}")
        if it.rationale:
            console.print(f"          [grey58]{it.rationale}[/grey58]")

    to_apply = [it for it in items if it.verdict in ("promote", "merge")]
    if not to_apply:
        console.print("\n[dim]Nothing to promote/merge — the curator skipped or dropped every candidate.[/dim]")
        return 0

    if dry_run:
        console.print(f"\n[yellow]--dry-run: nothing written.[/yellow] {len(to_apply)} item(s) would be applied. "
                      "Re-run without --dry-run to apply the approved subset.")
        return 0

    # Human gate — never write without confirmation.
    console.print(f"\n[bold]Apply {len(to_apply)} item(s) to the seed?[/bold] [grey58](y/N)[/grey58] ", end="")
    try:
        answer = input().strip().lower()
    except EOFError:
        answer = ""
    if answer not in ("y", "yes"):
        console.print("[yellow]Aborted — nothing written.[/yellow]")
        return 0

    applied = apply_proposal(proposal)  # approved_titles=None → all promote/merge
    total = sum(len(v) for v in applied.values())
    for fname, titles in applied.items():
        for t in titles:
            console.print(f"[green]+ {fname}:[/green] {t}")
    console.print(f"\n[bold green]✓ agentically compounded {total} lesson(s)[/bold green] into agent-context/ — open LESSONS.md to review.")
    return 0


def cmd_replay(args: argparse.Namespace) -> int:
    """Re-render a finished run from its events.jsonl — identical to the live
    `sdharness run` output. The renderer is purely event-driven, so replay just
    reads each recorded event and feeds it back through the same CLIRenderer."""
    from .cli_renderer import CLIRenderer

    run_dir = Path(args.run_dir).resolve()
    # Accept either the run workspace or the events file directly; find events.jsonl
    # under any <method>-docs/ dir if given the workspace.
    if run_dir.is_file():
        events_path = run_dir
    else:
        matches = sorted(run_dir.glob("*-docs/events.jsonl"))
        events_path = matches[0] if matches else run_dir / "loop-docs" / "events.jsonl"
    if not events_path.is_file():
        console.print(f"[red]No events.jsonl found under {run_dir}[/red] "
                      "[grey58](looked for <method>-docs/events.jsonl)[/grey58]")
        return 2

    renderer = CLIRenderer()
    replayed = 0
    for line in events_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
            event = rec.pop("event")
        except (ValueError, KeyError):
            continue  # skip a malformed line rather than abort the replay
        renderer.emit(event, **rec)
        replayed += 1
    if not replayed:
        console.print(f"[yellow]events.jsonl is empty:[/yellow] {events_path}")
        return 1
    return 0


def _resume_state_from_events(events_path: Path) -> dict:
    """Reconstruct enough of a prior run from its `events.jsonl` to continue it.

    The kit already tees every event to disk, so resume needs no separate persistence:
    - `run_config` (human mode) or `run_start` (always) → method / strategy / max_turns;
    - the last `complete` or `turn_end` → the turn count + accumulated cost to resume from.
    An interrupted run usually has NO `complete` event, so the last `turn_end` is the
    authoritative fallback. Returns {} if the log has no run config to work from.
    """
    cfg: dict = {}
    resume_from = 0
    resume_cost = 0.0
    resume_phase = ""
    lines = events_path.read_text(encoding="utf-8").splitlines()
    # Segment-scope the turn scan to the CURRENT run. The event log is append-only and a
    # brownfield workspace can carry a PRIOR run's turns (a seed cloned from a finished
    # run leaves its `turn_end`/`complete` events in the same events.jsonl). Scanning the
    # whole file for the max turn would resume from the SEED's turn count, not this run's.
    # So restrict the turn/cost/phase scan to lines at/after the LAST run kickoff marker
    # (`run_config`/`run_start`) — the start of the current run's segment. Config fields
    # are still read across the whole log so an early `run_config` is never missed.
    last_start = 0
    for i, line in enumerate(lines):
        s = line.strip()
        if not s:
            continue
        try:
            ev = json.loads(s).get("event")
        except ValueError:
            continue
        if ev in ("run_config", "run_start"):
            last_start = i
    for idx, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
            event = rec.get("event")
        except ValueError:
            continue
        if event == "run_config":
            # Richest source (human-mode runs): method/strategy/max_turns + models + limits.
            cfg.update(method=rec.get("method"), strategy=rec.get("strategy"),
                       max_turns=rec.get("max_turns"),
                       max_budget=rec.get("max_budget"),
                       fallback_model=rec.get("fallback_model"))
        elif event == "run_start":
            # Always emitted (both modes) — fill any gaps run_config didn't (e.g. --json runs).
            cfg.setdefault("method", rec.get("method"))
            cfg.setdefault("strategy", rec.get("strategy"))
            if cfg.get("max_turns") is None:
                cfg["max_turns"] = rec.get("max_turns")
        elif event in ("turn_end", "complete") and idx >= last_start:
            # Track the furthest turn + latest running cost + last phase seen — but ONLY
            # within the current run's segment (idx >= last_start), so a seed run's turns
            # earlier in the append-only log can't inflate resume_from. `complete`
            # carries `turns`; `turn_end` carries `turn` (and the phase work executed in —
            # `complete` carries the advanced phase). Both carry `total_cost_usd`.
            t = rec.get("turn") if event == "turn_end" else rec.get("turns")
            if isinstance(t, int) and t >= resume_from:
                resume_from = t
                if rec.get("phase"):
                    resume_phase = rec["phase"]   # the phase to continue in, not phases[0]
            c = rec.get("total_cost_usd")
            if isinstance(c, (int, float)):
                resume_cost = max(resume_cost, float(c))
    if not cfg.get("method"):
        return {}
    cfg["resume_from"] = resume_from
    cfg["resume_cost"] = resume_cost
    cfg["resume_phase"] = resume_phase
    return cfg


def cmd_resume(args: argparse.Namespace) -> int:
    """Continue an interrupted run in place, reconstructing state from its event log.

    Reads `<workspace>/<method>-docs/events.jsonl` to recover method/strategy/turn/cost,
    then re-enters `run()` with `resume_from` set. The coding agent starts a FRESH
    session and re-orients from the on-disk artifacts (`goal.md` + `loop-docs/`) — the
    disk-doc handoff — rather than restoring a conversation. The deterministic phase
    gates carry the phase (a resumed run skips phases whose artifacts already exist)."""
    _load_dotenv()

    run_dir = Path(args.run_dir).resolve()
    if not run_dir.is_dir():
        console.print(f"[red]No such run directory: {run_dir}[/red]")
        return 2
    matches = sorted(run_dir.glob("*-docs/events.jsonl"))
    events_path = matches[0] if matches else run_dir / "loop-docs" / "events.jsonl"
    if not events_path.is_file():
        console.print(f"[red]No events.jsonl found under {run_dir}[/red] "
                      "[grey58](nothing to resume — is this a run workspace?)[/grey58]")
        return 2

    st = _resume_state_from_events(events_path)
    if not st:
        console.print(f"[red]Could not reconstruct run config from[/red] {events_path} "
                      "[grey58](no run_config/run_start event).[/grey58]")
        return 2

    method = load_method(st["method"])
    strategy = load_strategy(st.get("strategy") or method.default_strategy)
    max_turns = args.max_turns if args.max_turns is not None else (st.get("max_turns") or 100)
    resume_from = st["resume_from"]
    resume_cost = st["resume_cost"]
    resume_phase = st.get("resume_phase") or ""
    # Carry the prior run's spend limit + fallback through the resume (the budget check
    # is authoritative across resumes because resume_cost seeds the running total).
    max_budget = st.get("max_budget") or 0.0
    fallback_model = st.get("fallback_model") or ""

    from .cli_renderer import CLIRenderer
    emit = CLIRenderer().emit
    _coder_model = os.environ.get("ANTHROPIC_MODEL") or "(SDK default)"
    _pilot_model = (os.environ.get("HARNESS_STEERING_MODEL")
                    or os.environ.get("ANTHROPIC_MODEL") or "(SDK default)")

    def _rel(p: Path) -> str:
        try:
            return "./" + str(Path(p).relative_to(Path.cwd()))
        except ValueError:
            return str(p)

    # Re-draw the kickoff banner so the resumed run reads identically, with a resume note.
    run_config = dict(method=method.name, method_display=method.display_name,
                      strategy=strategy.name,
                      phases=[{"name": p.name, "color": p.color} for p in method.phases],
                      max_turns=max_turns, intent=_rel(run_dir), workspace=_rel(run_dir),
                      agent_model=_coder_model, pilot_model=_pilot_model,
                      max_budget=max_budget, fallback_model=fallback_model,
                      resumed_from_turn=resume_from)
    emit("run_config", **run_config)
    _append_event(run_dir, method.name, "run_config", run_config)
    console.print(f"[yellow]▶ Resuming[/yellow] from turn [white]{resume_from}[/white] "
                  f"[grey58](~${resume_cost:.2f} already spent · budget {max_turns})[/grey58]\n")

    # Resume in place: the workspace IS the run dir, and the intake already lives there.
    started = time.monotonic()
    state = asyncio.run(
        run(
            project_dir=run_dir,
            workspace=run_dir,
            method=method,
            strategy=strategy,
            max_turns=max_turns,
            emit=emit,
            resume_from=resume_from,
            resume_cost=resume_cost,
            resume_phase=resume_phase,
            max_budget=max_budget,
            fallback_model=fallback_model,
        )
    )
    elapsed = time.monotonic() - started
    done, total = phase_authority.milestones(run_dir)
    recap = dict(complete=state.complete, reason=state.complete_reason,
                 turns=state.turn, max_turns=max_turns,
                 milestones_done=done, milestones_total=total,
                 total_cost_usd=state.total_cost_usd, elapsed=elapsed,
                 workspace=str(run_dir))
    emit("result_recap", **recap)
    _append_event(run_dir, method.name, "result_recap", recap)
    return 0 if state.complete else 1


def build_parser() -> argparse.ArgumentParser:
    from . import __version__

    p = argparse.ArgumentParser(prog="sdharness", description="Lightweight forkable coding-agent harness.")
    # `sdharness --version` → the kit version (single source: harness/__init__.py). Lets a
    # participant/CI identify exactly which kit build they're running (the shipped zip is
    # versioned to match — see the release tag + versioned S3 key).
    p.add_argument("--version", action="version", version=f"sdharness {__version__}")
    # Not required: bare `sdharness` prints a friendly getting-started guide
    # (see main()) rather than an argparse error.
    sub = p.add_subparsers(dest="command")

    r = sub.add_parser("run", help="Run a method against an intent directory.")
    r.add_argument("project_dir", help="Directory holding intent files (vision.md, tech-env.md).")
    r.add_argument("--method", default="loop", help="Method name (default: loop).")
    r.add_argument("--strategy", default=None, help="Strategy name (default: the method's default).")
    r.add_argument("--max-turns", type=int, default=100,
                   help="Runaway safety ceiling on turns (default: 100) — a kill switch, not a "
                        "target. The run stops the moment the terminal gate is met, usually far "
                        "below this. Rarely need to set it; lower it only to bound a smoke run.")
    r.add_argument("--max-budget", type=float, default=None, metavar="USD",
                   help="Hard cost ceiling in USD (agent + Pilot spend). The run stops cleanly "
                        "when the running total reaches it. Default: no ceiling.")
    r.add_argument("--fallback-model", default=None, metavar="MODEL",
                   help="Model the coding agent degrades to on rate limits (e.g. a smaller/faster "
                        "model) so a long run survives a throttle. Default: $ANTHROPIC_SMALL_FAST_MODEL.")
    r.add_argument("--workspace", default=None,
                   help="Explicit workspace dir (default: a sibling ../sdharness-runs/<name>-<ts>; "
                        "override the base with $SDHARNESS_RUNS_DIR).")
    r.add_argument("--in-place", action="store_true", help="Use the intent dir itself as the workspace.")
    r.add_argument("--json", action="store_true", help="Emit a machine-readable JSON recap (for agents/CI); suppresses the styled output.")
    r.set_defaults(func=cmd_run)

    m = sub.add_parser("methods", help="List available methods.")
    m.add_argument("--json", action="store_true", help="Emit the method list as JSON.")
    m.set_defaults(func=cmd_methods)
    s = sub.add_parser("strategies", help="List available strategies.")
    s.add_argument("--json", action="store_true", help="Emit the strategy list as JSON.")
    s.set_defaults(func=cmd_strategies)

    c = sub.add_parser("compound", help="Promote a run's progress.md Patterns into the LESSONS.md seed (the write-back step).")
    c.add_argument("run_dir", help="Finished run workspace to compound (e.g. ./runs/<name>-<ts>).")
    c.add_argument("--dry-run", action="store_true", help="Show what would be added without writing.")
    c.add_argument("--deterministic", action="store_true",
                   help="Force the offline title-dedup path (skip the curator agent). Compound is "
                        "curated-by-default when Bedrock creds are present; use this to compound "
                        "offline or to opt out of agentic curation.")
    # Deprecated alias: agentic curation is now the DEFAULT when creds are present. Kept
    # (hidden) for one release so existing scripts/docs that pass --agentic don't break;
    # it's a no-op relative to the new default. Remove after 0.4.x.
    c.add_argument("--agentic", action="store_true", help=argparse.SUPPRESS)
    c.set_defaults(func=cmd_compound)

    rp = sub.add_parser("replay", help="Re-render a finished run from its events.jsonl (identical to the live run output).")
    rp.add_argument("run_dir", help="Finished run workspace (e.g. ./runs/<name>-<ts>) or a path to events.jsonl.")
    rp.set_defaults(func=cmd_replay)

    rs = sub.add_parser("resume", help="Continue an interrupted run in place, from its event log.")
    rs.add_argument("run_dir", help="The interrupted run workspace (e.g. ./runs/<name>-<ts>).")
    rs.add_argument("--max-turns", type=int, default=None,
                    help="Override the turn budget for the resumed run (default: the prior run's budget).")
    rs.set_defaults(func=cmd_resume)
    return p


def cmd_welcome() -> int:
    """Prescriptive getting-started guide shown when `sdharness` is run bare."""
    console.print("[bold cyan]sdharness[/bold cyan] — a self-driving harness that drives a coding "
                  "agent to a [bold]verified[/bold] result.\n")
    console.print("[bold]Start here:[/bold]")
    console.print("  [cyan]sdharness methods[/cyan]       See the available methods (start with [cyan]loop[/cyan]).")
    console.print("  [cyan]sdharness strategies[/cyan]    See the steering strategies (start with [cyan]loop-autopilot[/cyan]).")
    console.print("  [cyan]sdharness run <dir>[/cyan]     Run a method against an intake directory "
                  "(vision.md, tech-env.md).")
    console.print("  [cyan]sdharness resume <run>[/cyan]  Continue an interrupted run in place (from its event log).")
    console.print("  [cyan]sdharness compound <run>[/cyan] Promote a finished run's lessons back into the seed.\n")
    console.print("[bold]Example first run:[/bold]")
    console.print("  [dim]sdharness run examples/bake-like-a-pro[/dim]\n")
    console.print("Add [cyan]-h[/cyan] to any command for its options "
                  "(e.g. [cyan]sdharness run -h[/cyan]).")
    console.print("Check the installed kit version with [cyan]sdharness --version[/cyan].")
    return 0


def main() -> None:
    args = build_parser().parse_args()
    # Bare `sdharness` (no subcommand): show the prescriptive guide, exit 0.
    if getattr(args, "command", None) is None:
        sys.exit(cmd_welcome())
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
