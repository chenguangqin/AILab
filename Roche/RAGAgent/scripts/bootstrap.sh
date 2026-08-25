#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON_BIN="${PYTHON_BIN:-python3.11}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  PYTHON_BIN=python3
fi

"$PYTHON_BIN" - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit("Python 3.11 or newer is required")
print("Python:", sys.version.split()[0])
PY

if command -v uv >/dev/null 2>&1; then
  uv sync --extra dev --extra aws --extra langfuse
  echo "Environment ready. Run: .venv/bin/pytest"
else
  "$PYTHON_BIN" -m venv .venv
  .venv/bin/pip install --upgrade pip
  .venv/bin/pip install -e '.[dev,aws,langfuse]'
  echo "Environment ready. Run: .venv/bin/pytest"
fi

if [[ "${INSTALL_RAGAS:-0}" == "1" ]]; then
  if command -v uv >/dev/null 2>&1; then
    uv sync --extra dev --extra aws --extra langfuse --extra ragas
  else
    .venv/bin/pip install -e '.[ragas]'
  fi
fi

