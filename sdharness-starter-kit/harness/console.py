# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""The one shared rich Console for the whole CLI.

On **stderr** deliberately: human-facing styled output (panels, spinners, the
run stream) goes here, so a machine reading `sdharness run … --json` on stdout
gets ONLY newline-delimited JSON — even if a stray print slipped through, it
lands on stderr, not the parsed channel. `highlight=False` keeps tool paths and
shell commands from being auto-recolored by rich's reprh heuristics.

A single Console instance also lets the spinner (a rich Live) coordinate with
prints on the same stream without racing.
"""

from rich.console import Console

console = Console(stderr=True, highlight=False)


def fmt_duration(seconds: float) -> str:
    """Human-friendly elapsed time: '4m 12s', '1h 03m', or '38s'."""
    s = int(round(seconds))
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m {s % 60:02d}s"
    return f"{s // 3600}h {(s % 3600) // 60:02d}m"
