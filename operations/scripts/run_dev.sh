#!/usr/bin/env bash
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
backend_venv="${APP_VENV_DIR:-$project_dir/.venv}"
exec "$backend_venv/bin/python" -B "$project_dir/operations/scripts/run_backend.py" dev "$@"
