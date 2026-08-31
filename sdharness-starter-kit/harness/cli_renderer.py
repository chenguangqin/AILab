# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""CLIRenderer — the human-facing view of a run.

The loop/sandbox/steering never touch the console; they only `emit(event, **fields)`.
Exactly ONE subscriber is attached per run: this renderer in human mode, or an NDJSON
emitter under `--json`. That's what keeps the two channels from ever mixing (and is
why `--json` is clean).

Rendering is a dispatch table: `emit("agent_text", …)` calls `_on_agent_text`. The two
harnesses get distinct identities so you can see who's speaking:
  - ◆ Coding Agent — teal panels (the inner harness, writes code)
  - ◇ Pilot        — decision-colored panels, green GO / red NO_GO (the outer harness, reviews)

A single transient spinner (`console.status`) fills the two dead-air gaps — the coding
agent "thinking" before its first block, and the silent Pilot review — so a run never
looks hung. It's a renderer-only affordance, so it can never appear in `--json`.
"""

from __future__ import annotations

from typing import Any

from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from .console import console, fmt_duration

# Phase → rule color. Falls back to cyan for anything unlisted (custom methods).
_PHASE_STYLES = {
    "RESEARCH": "blue",
    "PLAN": "magenta",
    "BUILD": "cyan",
    "VERIFY": "yellow",
}

_AGENT_ICON = "◆"   # ◆  coding agent (inner harness)
_PILOT_ICON = "◇"   # ◇  Pilot (outer harness)

# Tool-name → color, grouped by *what the agent is doing* so a glance down the
# tool column reads as a rhythm: reads are cool blue, mutations green, shell
# commands amber. Anything unlisted falls back to the agent's teal.
_TOOL_STYLES = {
    "Read": "blue", "Glob": "blue", "Grep": "blue", "LS": "blue",       # inspect
    "Write": "green", "Edit": "green", "MultiEdit": "green",            # mutate
    "Bash": "yellow",                                                   # execute
    "TodoWrite": "magenta", "Task": "magenta",                          # orchestrate
}
_TOOL_FALLBACK = "cyan"


class CLIRenderer:
    """Renders run events to the shared (stderr) console. One instance per run."""

    def __init__(self) -> None:
        self._status = None  # single live spinner handle; only ever one at a time
        self._context_pct = 0.0  # latest context-window fill %, drawn in the turn line

    def emit(self, event: str, **fields: Any) -> None:
        getattr(self, f"_on_{event}", self._on_unknown)(fields)

    # ── spinner (transient; always stop-first so only one Live is ever active) ──
    def _spin(self, text: str, style: str = "cyan") -> None:
        # The transient "working…" line carries the speaker's identity color (teal
        # for the coding agent ◆, green for the Pilot ◇) with a matching spinner, so
        # even the dead-air gaps say *who* is busy — not a flat grey.
        self._stop()
        self._status = console.status(
            f"[{style}]{text}[/{style}]", spinner="dots", spinner_style=style)
        self._status.start()

    def _stop(self) -> None:
        if self._status is not None:
            self._status.stop()
            self._status = None

    # ── run framing ────────────────────────────────────────────────────────────
    def _on_run_config(self, f: dict) -> None:
        # A bordered kickoff banner: the SD [ HARNESS ] wordmark + the METHOD's phase
        # rail as a subtitle, then an aligned key/value table of the run.
        title = ("[bold]SD[/bold] [cyan]\\[[/cyan] [bold]HARNESS[/bold] [cyan]][/cyan]"
                 "   [grey58]· self-driving harness[/grey58]")
        # Build the rail from the METHOD's own phases (name + optional hex color) so a
        # custom method shows ITS phases — the kit is method-agnostic. Fall back to the
        # SD Loop rail for older events that predate `phases` in run_config.
        phases = f.get("phases") or []
        if phases:
            parts = []
            for p in phases:
                name = escape(str(p.get("name", "")))
                color = p.get("color") or _PHASE_STYLES.get(p.get("name", ""), "cyan")
                parts.append(f"[{color}]{name}[/{color}]")
            rail = " → ".join(parts)
        else:
            rail = "[cyan]RESEARCH[/cyan] → [magenta]PLAN[/magenta] → [blue]BUILD[/blue] → [yellow]VERIFY[/yellow]"
        t = Table.grid(padding=(0, 2))
        t.add_column(style="grey58", justify="right")
        t.add_column()
        # Show the method's friendly name (e.g. "SD Loop") alongside its slug; the
        # slug is what --method takes, the display name is what the phase rail *is*.
        method_disp = f.get("method_display") or f["method"]
        method_cell = f"[cyan]{escape(str(method_disp))}[/cyan]"
        if method_disp != f["method"]:
            method_cell += f" [grey42]([/grey42][grey58]{escape(str(f['method']))}[/grey58][grey42])[/grey42]"
        t.add_row("method", f"{method_cell}  [grey42]·[/grey42]  "
                            f"[grey58]strategy[/grey58] [cyan]{f['strategy']}[/cyan]")
        t.add_row("mode", "[yellow]autonomous[/yellow]  [grey42]·[/grey42]  "
                         f"[grey58]turn budget[/grey58] [white]{f['max_turns']}[/white]")
        # The two harnesses and their models — generator ≠ evaluator, shown with the
        # same ◆/◇ identities used throughout the run so the split is legible up front.
        if f.get("agent_model"):
            t.add_row("coding agent",
                      f"[cyan]{_AGENT_ICON}[/cyan] [white]{escape(str(f['agent_model']))}[/white] "
                      f"[grey58](inner harness · generates)[/grey58]")
        if f.get("pilot_model"):
            t.add_row("Pilot",
                      f"[green]{_PILOT_ICON}[/green] [white]{escape(str(f['pilot_model']))}[/white] "
                      f"[grey58](outer harness · reviews)[/grey58]")
        t.add_row("intent", f"[white]{escape(str(f['intent']))}[/white]")
        t.add_row("workspace", f"[grey70]{escape(str(f['workspace']))}[/grey70]")
        console.print()
        console.print(Panel(t, title=title, subtitle=rail, title_align="left",
                            subtitle_align="left", border_style="cyan", padding=(1, 2)))

    def _on_run_start(self, f: dict) -> None:
        pass  # config already drew the header

    def _on_turn_start(self, f: dict) -> None:
        style = _PHASE_STYLES.get(f["phase"], "cyan")
        console.rule(f"[bold]Turn {f['turn']} · {f['phase']}[/bold]", style=style)
        self._spin(f"{_AGENT_ICON} coding agent · thinking…")  # dead-air #1

    # ── coding agent (inner harness) ─────────────────────────────────────────────
    def _on_agent_text(self, f: dict) -> None:
        text = (f.get("text") or "").strip()
        if not text:
            return
        self._stop()
        console.print(
            Panel(escape(text), title=f"[bold cyan]{_AGENT_ICON} Coding Agent[/bold cyan]",
                  title_align="left", border_style="cyan", padding=(0, 1))
        )
        self._spin(f"{_AGENT_ICON} coding agent · working…")

    def _on_agent_thinking(self, f: dict) -> None:
        # Extended-thinking reasoning — the agent's plan before it acts. Same cyan
        # identity as the ◆ Coding Agent panels (it IS the coding agent), but dimmed
        # (non-bold title, dim border) so it reads as a quieter aside, not a peer.
        text = (f.get("text") or "").strip()
        if not text:
            return
        self._stop()
        console.print(
            Panel(escape(text),
                  title=f"[cyan]{_AGENT_ICON} Coding Agent · Reasoning[/cyan]",
                  title_align="left", border_style="dim cyan", padding=(0, 1))
        )
        self._spin(f"{_AGENT_ICON} coding agent · working…")

    def _on_context_usage(self, f: dict) -> None:
        # Stash the SDK's context-fill %; drawn in the turn-end status line so a long
        # run shows it approaching the limit. No output of its own.
        pct = f.get("fill_pct")
        if isinstance(pct, (int, float)):
            self._context_pct = float(pct)

    def _on_tool_use(self, f: dict) -> None:
        self._stop()
        # Split "Name(args…)" so the tool NAME carries its category color (read/
        # mutate/execute) and the args stay a quiet grey — the eye scans the colored
        # verb column, the paths recede. The ▸ bullet takes the tool's color too.
        detail = f["detail"]
        name, _, rest = detail.partition("(")
        style = _TOOL_STYLES.get(name, _TOOL_FALLBACK)
        if rest:
            args = escape(rest[:-1] if rest.endswith(")") else rest)
            body = f"[{style}]{escape(name)}[/{style}][grey58]([/grey58][grey70]{args}[/grey70][grey58])[/grey58]"
        else:
            body = f"[{style}]{escape(detail)}[/{style}]"
        console.print(f"    [{style}]▸[/{style}] {body}")
        self._spin(f"{_AGENT_ICON} coding agent · working…")

    def _on_agent_turn_end(self, f: dict) -> None:
        self._stop()

    def _on_skill_attached(self, f: dict) -> None:
        console.print(f"  [green]+skill[/green] [dim]{f['name']} ({f['path']})[/dim]")

    def _on_skill_missing(self, f: dict) -> None:
        console.print(f"  [yellow]skill not found, skipping:[/yellow] {f['name']}")

    # ── phase authority + Pilot (outer harness) ──────────────────────────────────
    def _on_phase_advance(self, f: dict) -> None:
        self._stop()
        console.print(f"[green]▸ phase advanced: {f['from']} → {f['to']}[/green]")

    def _on_context_reset(self, f: dict) -> None:
        # Opt-in phase-boundary reset (context_reset="phase_boundary"): the coding agent
        # got a fresh session; it re-orients from goal.md + loop-docs/. Dim — it's plumbing.
        self._stop()
        console.print(f"[grey58]↺ context reset · {f['from']} → {f['to']} (fresh session)[/grey58]")

    def _on_compaction(self, f: dict) -> None:
        # The SDK auto-compacted the coding agent's context (window filled). Observe-only —
        # the run continues; disk-as-memory keeps it coherent. Dim — it's SDK plumbing.
        self._stop()
        trigger = f.get("trigger") or "auto"
        console.print(f"[grey58]🗜  context compacted ({trigger}) — run continues[/grey58]")

    def _on_pilot_start(self, f: dict) -> None:
        self._spin(f"{_PILOT_ICON} Pilot · reviewing…", style="green")  # dead-air #2 (steer() is silent)

    def _on_pilot_review(self, f: dict) -> None:
        self._stop()
        go = f["decision"] == "GO"
        border = "green" if go else "red"
        direction = escape((f.get("direction") or "").strip() or "(no direction)")
        console.print(
            Panel(direction,
                  title=f"[bold {border}]{_PILOT_ICON} Pilot · {f['decision']}[/bold {border}]",
                  title_align="left", border_style=border, padding=(0, 1))
        )

    def _on_turn_end(self, f: dict) -> None:
        # A scannable status line: dim rule chrome, but the phase, the GO/NO_GO
        # verdict, cost, and milestone progress are colored so the eye lands on
        # the state, not the boilerplate.
        phase_style = _PHASE_STYLES.get(f["phase"], "cyan")
        go = f.get("decision") == "GO"
        verdict = f"[bold {'green' if go else 'red'}]{f.get('decision', '?')}[/]"
        total = f.get("milestones_total") or 0
        done = f.get("milestones_done", 0)
        ms = f" [grey42]·[/grey42] [white]{done}/{total}[/white] [grey58]milestones[/grey58]" if total else ""
        # Per-turn elapsed (D): pacing at a glance.
        elapsed = f.get("elapsed")
        dur = f" [grey42]·[/grey42] [grey58]{fmt_duration(elapsed)}[/grey58]" if elapsed else ""
        # Context-window fill (A): the SDK's /context %, colored by pressure —
        # quiet until half full, amber past 50%, red past 80% so a long run warns.
        ctx = ""
        if self._context_pct:
            c = "red" if self._context_pct > 80 else "yellow" if self._context_pct > 50 else "grey58"
            ctx = f" [grey42]·[/grey42] [grey58]ctx[/grey58] [{c}]{self._context_pct:.0f}%[/{c}]"
        # Turn is an OPEN ORDINAL count, not a fraction — the SD Loop finishes when its
        # terminal gate goes green, not when it "reaches" max_turns (a runaway ceiling,
        # shown once in the banner). Milestones are the real progress bar. (Upstream
        # sdharness renders turns the same way — no /max denominator anywhere.)
        console.print(
            f"[grey58]Turn[/grey58] [white]{f['turn']}[/white] "
            f"[grey42]·[/grey42] [{phase_style}]{f['phase']}[/{phase_style}] "
            f"[grey42]·[/grey42] {verdict} "
            f"[grey42]·[/grey42] [yellow]~${f.get('total_cost_usd', 0.0):.2f}[/yellow]{ms}{dur}{ctx}"
        )

    # ── terminal states ──────────────────────────────────────────────────────────
    def _on_complete(self, f: dict) -> None:
        self._stop()

    def _on_kill_switch(self, f: dict) -> None:
        self._stop()
        console.print(f"[bold red]✗ kill switch:[/bold red] {f['reason']}")

    def _on_stopped(self, f: dict) -> None:
        self._stop()
        console.print(f"[yellow]stopped: {f['reason']}[/yellow]")

    def _on_result_recap(self, f: dict) -> None:
        # A bordered result card mirroring the kickoff banner: a ✓/⚠ verdict headline
        # (border + title colored by outcome), an aligned metrics grid, milestones as
        # a done/total ratio, and the workspace called out as the "look here next"
        # pointer. Green when the run genuinely completed, amber when it stopped short.
        self._stop()
        complete = f["complete"]
        # A raised crash (loop.py's except → state.error) reads as a FAILURE, not merely
        # "incomplete": red border + ✗ headline + an error row. A clean-but-short run stays amber.
        errored = bool(f.get("error"))
        accent = "green" if complete else "red" if errored else "yellow"
        headline = ("[bold green]✓ complete[/bold green]" if complete
                    else "[bold red]✗ run failed[/bold red]" if errored
                    else "[bold yellow]⚠ incomplete[/bold yellow]")

        total = f.get("milestones_total") or 0
        done = f.get("milestones_done", 0)
        ms_done = total and done >= total
        ms_val = (f"[{'green' if ms_done else 'white'}]{done}/{total}[/] "
                  f"[grey58]milestones[/grey58]") if total else "[grey58]—[/grey58]"

        t = Table.grid(padding=(0, 2))
        t.add_column(style="grey58", justify="right")
        t.add_column()
        t.add_row("status", headline)
        t.add_row("reason", f"[grey70]{escape(str(f['reason']))}[/grey70]")
        if errored:
            t.add_row("error", f"[red]{escape(str(f['error']))}[/red]")
        t.add_row("turns", f"[white]{f['turns']}[/white]")
        t.add_row("milestones", ms_val)
        t.add_row("cost", f"[yellow]~${f['total_cost_usd']:.2f}[/yellow]")
        t.add_row("duration", f"[white]{fmt_duration(f['elapsed'])}[/white]")
        t.add_row("workspace", f"[{accent}]{escape(str(f['workspace']))}[/{accent}]")
        console.print()
        console.print(Panel(t, title="[bold]Result[/bold]", title_align="left",
                            border_style=accent, padding=(1, 2)))

    def _on_unknown(self, f: dict) -> None:
        pass  # forward-compatible: unrecognized events render nothing
