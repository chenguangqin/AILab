#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

.venv/bin/pytest
.venv/bin/roche-lab rag evaluate \
  --config labs/E0_pipeline/config.baseline.yaml \
  --split dev
.venv/bin/roche-lab rag sweep \
  --matrix labs/E1_tuning/experiment_matrix.yaml
.venv/bin/roche-lab rules evaluate
.venv/bin/roche-lab analytics import \
  --csv data/analytics/raw/lab_operations_2026-08.csv \
  --db artifacts/lab_operations.db
.venv/bin/roche-lab analytics investigate \
  --db artifacts/lab_operations.db \
  --question "为什么早高峰前处理耗时上升？"
.venv/bin/roche-lab architecture compare
.venv/bin/roche-lab review evaluate

