#!/usr/bin/env bash
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$project_dir"
.venv/bin/python operations/scripts/prepare_runtime.py
exec .venv/bin/python backend/manage.py "$@"
