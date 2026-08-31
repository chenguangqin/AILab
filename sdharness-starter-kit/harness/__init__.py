# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""SD Harness (Self-Driving Harness) — a lightweight, forkable harness.

An *outer harness* (a single steering "Pilot") drives an *inner harness* (a
coding agent — Claude Code via the Claude Agent SDK) through a gated methodology,
turn by turn, from intake to a verified result.

It ships the load-bearing ideas — config-over-code methods/strategies, a swappable
coding-agent Sandbox, deterministic artifact gates, a steering reviewer, and
kill switches — and leaves the production surface (dashboard, pipeline, conductor,
multi-agent board, telemetry) as extension points. Fork it and grow the parts you need.
"""

__version__ = "0.3.10"
