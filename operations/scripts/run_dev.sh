#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$project_dir"
.venv/bin/python operations/scripts/prepare_runtime.py
exec .venv/bin/python backend/manage.py runserver --noreload "${APP_BIND:-127.0.0.1:8000}"
