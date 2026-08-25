#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON_BIN="${PYTHON_BIN:-python3.12}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python 3.12 was not found. Set PYTHON_BIN to its executable path." >&2
  exit 1
fi

"$PYTHON_BIN" - <<'PY'
import sys
if sys.version_info < (3, 12):
    raise SystemExit("Python 3.12 or newer is required")
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
