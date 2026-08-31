# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""Kill switches — the safety net that makes unattended autonomous runs tolerable.

Autonomy without brakes is a liability. After each turn, `check()` inspects the
run state and returns a stop-reason string (or None to continue). Thresholds come
from the method's `kill_switch` block, with sane defaults.

Signals:
  - no_files_threshold      — N turns in a row wrote nothing → likely stuck
  - state_unchanged_threshold — N turns with no phase/artifact progress
  - error_repeat_threshold  — same error N times in a row → not converging
  - max_turns / max_budget  — hard ceilings (enforced by the loop, not here)
"""

from __future__ import annotations

from .models import Method, RunState

_DEFAULTS = {
    "no_files_threshold": 4,
    "state_unchanged_threshold": 5,
    "error_repeat_threshold": 3,
}


def _cfg(method: Method, key: str) -> int:
    return int(method.kill_switch.get(key, _DEFAULTS[key]))


def update_and_check(method: Method, state: RunState, wrote_files: bool,
                     made_progress: bool, error: str) -> str | None:
    """Update counters from this turn and return a stop reason, or None.

    `made_progress` = the phase advanced OR new artifacts appeared this turn.
    """
    # no-write streak
    state.consecutive_no_write_turns = 0 if wrote_files else state.consecutive_no_write_turns + 1
    if state.consecutive_no_write_turns >= _cfg(method, "no_files_threshold"):
        return (f"No files written for {state.consecutive_no_write_turns} turns "
                "— agent appears stuck.")

    # no-progress streak
    state.consecutive_no_progress_turns = 0 if made_progress else state.consecutive_no_progress_turns + 1
    if state.consecutive_no_progress_turns >= _cfg(method, "state_unchanged_threshold"):
        return (f"No phase/artifact progress for {state.consecutive_no_progress_turns} "
                "turns — halting to avoid an idle loop.")

    # repeated-error streak
    err = (error or "").strip()
    if err and err == state.last_error:
        state.consecutive_error_repeats += 1
    else:
        state.consecutive_error_repeats = 0
    state.last_error = err
    if state.consecutive_error_repeats >= _cfg(method, "error_repeat_threshold"):
        return (f"Same error repeated {state.consecutive_error_repeats} times "
                f"— not converging: {err[:160]}")

    return None
